"""
Task Queue Module

This module provides a task queue for executing commands in parallel.

Workflow:
1. add_task() - Called by the GUI to submit a task
2. _worker_thread() - Worker thread that processes tasks from the queue
3. _execute_task() - Executes the task and waits for it to complete
4. _update_status() - Handles the task result and updates the UI
"""

import os
import sys
import json
import time
import logging
import traceback
import subprocess
import threading
import shutil
import warnings
from datetime import datetime
from queue import Queue, Empty
from src.core.command_handler import CommandArgumentHandler

# Configure logging
# Ensure log directory exists
log_dir = os.path.join(os.getcwd(), "log")
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename=os.path.join(log_dir, 'task_queue.log'),
    filemode='a'
)
logger = logging.getLogger('TaskQueue')

class TaskQueue:
    """A task queue for executing commands in parallel"""

    def __init__(self, result_callback=None, max_workers=5, max_active_processes=10):
        """Initialize the task queue

        Args:
            result_callback (callable, optional): A callback function to call when a task is completed.
                The callback should accept the following arguments:
                - audit_id (str): The unique identifier for the audit task
                - status (str): The status of the task
                - result (str): The result message
                - full_output (str, optional): The full output of the command
                - log_file (str, optional): Path to the log file
                - err_file (str, optional): Path to the error file
            max_workers (int, optional): Maximum number of worker threads to use for parallel execution.
                This parameter is kept for backward compatibility but is no longer used.
                The number of worker threads is now equal to max_active_processes.
            max_active_processes (int, optional): Maximum number of concurrent processes to run.
                Defaults to 10.
        """
        self.task_queue = Queue()  # Thread-safe queue for tasks
        self.task_list = []  # List to keep track of all tasks (for status reporting)
        self.result_callback = result_callback
        self.running = True  # Start in running state
        self.app_dir = os.getcwd()
        self.utils_dir = os.path.join(self.app_dir, "panPHP", "utils")
        self.log_dir = os.path.join(self.app_dir, "log")
        self.output_dir = os.path.join(self.app_dir, "output")
        self.use_separate_window = False  # Always use direct subprocess execution

        # Detect operating system
        self.is_windows = sys.platform.startswith('win')

        # Ensure log and output directories exist
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

        # Add semaphore to limit concurrent processes
        self.max_active_processes = max_active_processes
        self.process_semaphore = threading.Semaphore(max_active_processes)
        logger.info(f"Initialized TaskQueue with max_active_processes={max_active_processes}")
        
        # Create worker threads
        self.workers = []
        for i in range(max_active_processes):
            thread = threading.Thread(target=self._worker_thread, daemon=True, name=f"Worker-{i+1}")
            thread.start()
            self.workers.append(thread)
            logger.debug(f"Started worker thread {i+1}/{max_active_processes}")
            
    def _worker_thread(self):
        """Worker thread function that processes tasks from the queue"""
        while self.running:
            try:
                # Get a task from the queue (blocking with timeout)
                try:
                    task = self.task_queue.get(timeout=1)
                except Empty:
                    # Queue is empty, continue waiting
                    continue
                    
                # Extract task details
                audit_id = task['audit_id']
                cmd_args = task['cmd_args']
                metadata = task['metadata']
                
                logger.debug(f"Worker thread processing task: audit_id={audit_id}")
                
                # Update task status to Queued
                self._update_status(audit_id, "Queued", "Task picked up by worker thread, waiting for semaphore...")
                
                # Try to acquire the semaphore
                logger.debug(f"Trying to acquire process semaphore for audit_id={audit_id}")
                if self.process_semaphore.acquire(blocking=True):
                    try:
                        # Update status to Running
                        self._update_status(audit_id, "Running", "Executing command...")
                        
                        # Execute the task
                        self._execute_task(audit_id, cmd_args, metadata)
                        
                        # Mark task as done in the queue
                        self.task_queue.task_done()
                    except Exception as e:
                        logger.error(f"Error executing task: {str(e)}")
                        logger.error(traceback.format_exc())
                        
                        # Update task status
                        self._update_status(
                            audit_id, 
                            "Error", 
                            f"Error executing task: {str(e)}"
                        )
                    finally:
                        # Release the semaphore
                        logger.debug(f"Releasing process semaphore for audit_id={audit_id}")
                        self.process_semaphore.release()
                else:
                    # This should not happen with blocking=True, but just in case
                    logger.warning(f"Failed to acquire semaphore for audit_id={audit_id}")
                    
                    # Put the task back in the queue
                    self.task_queue.put(task)
                    self.task_queue.task_done()
                    
                    # Sleep a bit to prevent CPU spinning
                    time.sleep(0.5)
            except Exception as e:
                logger.error(f"Error in worker thread: {str(e)}")
                logger.error(traceback.format_exc())

    def add_task(self, audit_id, cmd_args, metadata=None, paused=False):
        """Add a task to the queue for parallel execution

        Args:
            audit_id (str): The unique identifier for the audit task
            cmd_args (dict): The command arguments as a dictionary
            metadata (dict, optional): A dictionary containing metadata about the audit:
                - section_number (str, optional): The section number
                - section_name (str, optional): The section name
                - audit_number (str, optional): The audit number
                - audit_name (str, optional): The audit name
                - spg_number (str, optional): The SPG number
                - spg_name (str, optional): The SPG name
            paused (bool, optional): Whether to add the task in a paused state. Defaults to False.

        Returns:
            bool: True if the task was added successfully, False otherwise
        """
        try:
            # Create a task object
            task = {
                'audit_id': audit_id,
                'cmd_args': cmd_args,
                'metadata': metadata or {},
                'timestamp': datetime.now().isoformat(),
                'paused': paused  # Add paused state to the task
            }

            # Add the task to the list for tracking
            self.task_list.append(task)

            # Only add to the queue if not paused
            if not paused:
                # Update task status to Queued
                self._update_status(audit_id, "Queued", "Task added to queue, waiting for worker thread...")
                
                # Add the task to the queue for processing
                self.task_queue.put(task)
                logger.debug(f"Added task to queue: audit_id={audit_id}")
            else:
                # Update task status to Paused
                self._update_status(audit_id, "Paused", "Task paused by user")
                logger.debug(f"Added task in paused state: audit_id={audit_id}")

            audit_name = metadata.get('audit_name') if metadata else None
            logger.info(f"Added task: audit_id={audit_id}, audit_name={audit_name}, paused={paused}")
            return True
        except Exception as e:
            logger.error(f"Failed to add task: {str(e)}")
            logger.error(traceback.format_exc())
            return False

    def start_processing(self):
        """Start processing tasks from the queue

        DEPRECATED: This method is maintained for backward compatibility only.
        Task processing now starts automatically when tasks are added.
        """
        warnings.warn(
            "start_processing is deprecated and has no effect. "
            "Task processing now starts automatically when tasks are added.",
            DeprecationWarning, stacklevel=2
        )
        logger.info("Task processing is handled by worker threads")
        return

    def pause_task(self, audit_id):
        """Pause a task

        Args:
            audit_id (str): The unique identifier for the audit task

        Returns:
            bool: True if the task was paused successfully, False otherwise
        """
        try:
            # Find the task in the list
            for task in self.task_list:
                if task['audit_id'] == audit_id:
                    # Mark the task as paused
                    task['paused'] = True
                    
                    # Update task status
                    self._update_status(audit_id, "Paused", "Task paused by user")
                    logger.info(f"Paused task: audit_id={audit_id}")
                    return True
            
            logger.warning(f"Task not found for pausing: audit_id={audit_id}")
            return False
        except Exception as e:
            logger.error(f"Error pausing task: {str(e)}")
            logger.error(traceback.format_exc())
            return False

    def resume_task(self, audit_id):
        """Resume a paused task

        Args:
            audit_id (str): The unique identifier for the audit task

        Returns:
            bool: True if the task was resumed successfully, False otherwise
        """
        try:
            # Find the task in the list
            for task in self.task_list:
                if task['audit_id'] == audit_id and task.get('paused', False):
                    # Mark the task as not paused
                    task['paused'] = False
                    
                    # Update task status
                    self._update_status(audit_id, "Queued", "Task resumed, waiting for worker thread...")
                    
                    # Add the task to the queue for processing
                    self.task_queue.put(task)
                    
                    logger.info(f"Resumed task: audit_id={audit_id}")
                    return True
            
            logger.warning(f"Task not found for resuming: audit_id={audit_id}")
            return False
        except Exception as e:
            logger.error(f"Error resuming task: {str(e)}")
            logger.error(traceback.format_exc())
            return False

    def cancel_task(self, audit_id):
        """Cancel a task

        Args:
            audit_id (str): The unique identifier for the audit task

        Returns:
            bool: True if the task was cancelled successfully, False otherwise
        """
        try:
            # Find the task in the list
            for i, task in enumerate(self.task_list):
                if task['audit_id'] == audit_id:
                    # Remove the task from the list
                    self.task_list.pop(i)
                    
                    # Update task status
                    self._update_status(audit_id, "Cancelled", "Task cancelled by user")
                    logger.info(f"Cancelled task: audit_id={audit_id}")
                    return True
            
            logger.warning(f"Task not found for cancelling: audit_id={audit_id}")
            return False
        except Exception as e:
            logger.error(f"Error cancelling task: {str(e)}")
            logger.error(traceback.format_exc())
            return False

    def get_task_status(self, audit_id):
        """Get the status of a task

        Args:
            audit_id (str): The unique identifier for the audit task

        Returns:
            dict: The task status, or None if the task is not found
        """
        try:
            # Find the task in the list
            for task in self.task_list:
                if task['audit_id'] == audit_id:
                    return task.get('status', 'Unknown')
            
            logger.warning(f"Task not found for status check: audit_id={audit_id}")
            return None
        except Exception as e:
            logger.error(f"Error getting task status: {str(e)}")
            logger.error(traceback.format_exc())
            return None

    def get_all_tasks(self):
        """Get all tasks

        Returns:
            list: A list of all tasks
        """
        return self.task_list

    def stop_processing(self):
        """Stop processing tasks from the queue"""
        logger.info("Stopping task processing...")
        
        # Set running flag to False to stop worker threads
        self.running = False
        
        # Wait for all worker threads to finish
        for thread in self.workers:
            if thread.is_alive():
                thread.join(timeout=1.0)
                
        # Clear the queue
        while not self.task_queue.empty():
            try:
                self.task_queue.get_nowait()
                self.task_queue.task_done()
            except Empty:
                break
                
        # Clear the task list
        self.task_list.clear()
        
        logger.info("Task processing stopped")

    def _execute_task(self, audit_id, cmd_args, metadata=None):
        """Execute a task

        Args:
            audit_id (str): The unique identifier for the audit task
            cmd_args (dict): The command arguments as a dictionary
            metadata (dict, optional): A dictionary containing metadata about the audit:
                - section_number (str, optional): The section number
                - section_name (str, optional): The section name
                - audit_number (str, optional): The audit number
                - audit_name (str, optional): The audit name
                - spg_number (str, optional): The SPG number
                - spg_name (str, optional): The SPG name
        """
        metadata = metadata or {}
        audit_name = metadata.get('audit_name')
        section_number = metadata.get('section_number')

        logger.info(f"Executing task: audit_id={audit_id}, metadata={metadata}")

        try:
            # Update task status to Running (task is now being executed)
            self._update_status(audit_id, "Running", "Executing command...")

            # Extract workbookName from the command arguments
            workbookName = None
            if "actions" in cmd_args:
                workbookName = cmd_args.get("actions", "").replace("exporttoexcel:", "")
                logger.debug(f"Extracted workbookName from actions: {workbookName}")
            elif "workbookName" in cmd_args:
                workbookName = cmd_args.get("workbookName")
                logger.debug(f"Extracted workbookName from workbookName parameter: {workbookName}")
            else:
                logger.debug("No workbookName found in command arguments")

            # Create log file paths
            log_file_path = None
            err_file_path = None
            if workbookName:
                log_file_path = os.path.join(self.log_dir, workbookName.replace('.xls', '_log.log'))
                err_file_path = os.path.join(self.log_dir, workbookName.replace('.xls', '_err.log'))
                logger.debug(f"Created log file paths based on workbookName: log={log_file_path}, err={err_file_path}")
            else:
                # If no workbookName is provided, use the audit_id to create log file paths
                log_file_path = os.path.join(self.log_dir, f"{audit_id}_log.log")
                err_file_path = os.path.join(self.log_dir, f"{audit_id}_err.log")
                logger.debug(f"Created log file paths based on audit_id: log={log_file_path}, err={err_file_path}")

            # Store the log file paths in the task info
            self._update_status(
                audit_id,
                "Running",
                "Starting command execution...",
                log_file=log_file_path,
                err_file=err_file_path
            )

            # Prepare the PHP command with full path to the PHP script
            php_script_path = os.path.join(self.utils_dir, "pan-os-php.php")
            logger.debug(f"PHP script path: {php_script_path}")

            # Use CommandArgumentHandler to convert command arguments to PHP arguments
            base_php_args = CommandArgumentHandler.to_php_args(cmd_args)
            logger.debug(f"Base PHP arguments: {base_php_args}")

            # Replace the script path with the full path
            php_args = [base_php_args[0], php_script_path] + base_php_args[2:]
            logger.debug(f"Final PHP command: {' '.join(php_args)}")

            # Execute PHP directly with the arguments
            try:
                # Open log files for writing
                with open(log_file_path, 'w', encoding='utf-8') as log_file, \
                     open(err_file_path, 'w', encoding='utf-8') as err_file:

                    # Write command to log file
                    log_file.write(f"Command: {' '.join(php_args)}\n\n")
                    log_file.flush()

                    # Run the PHP command and capture output
                    self._update_status(
                        audit_id,
                        "Running",
                        "Executing command...",
                        log_file=log_file_path,
                        err_file=err_file_path
                    )

                    try:
                        # Use subprocess.Popen for execution
                        logger.debug(f"Starting subprocess for audit_id={audit_id} with working directory set to output directory: {self.output_dir}")

                        # Create the process
                        process = subprocess.Popen(
                            php_args,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                            cwd=self.output_dir,  # Set working directory to output directory
                            bufsize=1  # Line buffered
                        )
                        logger.debug(f"Subprocess started for audit_id={audit_id}, pid={process.pid}")

                        # Wait for the process to complete and capture output
                        try:
                            # Use communicate with a timeout to prevent hanging
                            stdout, stderr = process.communicate(timeout=3600)  # 1 hour timeout

                            # Get return code
                            return_code = process.returncode
                            logger.debug(f"Process completed for audit_id={audit_id}, return_code={return_code}")

                            # Write output to log files
                            stdout_length = len(stdout)
                            stderr_length = len(stderr)
                            logger.debug(f"Command output: stdout={stdout_length} chars, stderr={stderr_length} chars")

                            try:
                                # Write to log files
                                with open(log_file_path, 'a', encoding='utf-8') as log_file:
                                    log_file.write(stdout)
                                with open(err_file_path, 'a', encoding='utf-8') as err_file:
                                    err_file.write(stderr)
                            except Exception as e:
                                logger.error(f"Error writing to log files: {str(e)}")

                            # Process the results
                            if return_code == 0:
                                # Update with success message
                                self._update_status(
                                    audit_id, 
                                    "Completed", 
                                    f"Command executed successfully. Output written to {os.path.basename(log_file_path)}",
                                    full_output=stdout,
                                    log_file=log_file_path,
                                    err_file=err_file_path
                                )
                            else:
                                # Handle error
                                error_msg = f"Error executing PHP command (return code {return_code}). Check error log for details."
                                logger.error(f"Error in execute_task: {error_msg}")
                                self._update_status(
                                    audit_id, 
                                    "Failed", 
                                    error_msg,
                                    full_output=stdout,
                                    log_file=log_file_path,
                                    err_file=err_file_path
                                )
                        except subprocess.TimeoutExpired:
                            # Handle timeout
                            logger.error(f"Process timed out after 1 hour for audit_id={audit_id}")

                            # Try to terminate the process
                            try:
                                process.terminate()
                                process.wait(timeout=10)  # Wait up to 10 seconds for termination
                            except Exception as term_error:
                                logger.error(f"Error terminating process: {str(term_error)}")
                                try:
                                    # Force kill if termination fails
                                    process.kill()
                                except Exception as kill_error:
                                    logger.error(f"Error killing process: {str(kill_error)}")

                            # Update status
                            self._update_status(
                                audit_id, 
                                "Failed", 
                                "Process timed out after 1 hour",
                                log_file=log_file_path,
                                err_file=err_file_path
                            )
                    except Exception as e:
                        # Handle error starting the subprocess
                        error_msg = f"Error executing subprocess: {str(e)}"
                        logger.error(f"Exception in execute_task: {error_msg}")
                        logger.error(traceback.format_exc())

                        # Update task status
                        self._update_status(
                            audit_id, 
                            "Failed", 
                            error_msg,
                            log_file=log_file_path,
                            err_file=err_file_path
                        )
                        return
            except Exception as e:
                # Handle error opening log files
                error_msg = f"Error executing PHP command: {str(e)}"
                logger.error(f"Exception in execute_task: {error_msg}")
                logger.error(traceback.format_exc())

                # Try to write error to log files
                if log_file_path and err_file_path:
                    try:
                        with open(log_file_path, 'a', encoding='utf-8') as log_file:
                            log_file.write(f"\nError: {str(e)}\n")
                        with open(err_file_path, 'a', encoding='utf-8') as err_file:
                            err_file.write(f"Error: {str(e)}\n{traceback.format_exc()}")
                    except Exception as write_error:
                        logger.error(f"Error writing to log files: {str(write_error)}")

                # Update task status
                self._update_status(
                    audit_id, 
                    "Failed", 
                    error_msg,
                    log_file=log_file_path,
                    err_file=err_file_path
                )
                return

            # Update task status to Processing
            self._update_status(audit_id, "Processing", "Command executed, processing results...")

            # If we have a workbookName, check if the file was created
            if workbookName:
                logger.debug(f"Checking for output file with workbookName: {workbookName}")
                # Check possible locations for the file
                utils_file_path = os.path.join(self.utils_dir, workbookName)
                app_file_path = os.path.join(self.app_dir, workbookName)
                output_file_path = os.path.join(self.output_dir, workbookName)
                logger.debug(f"Possible file locations: output_dir={output_file_path}, app_dir={app_file_path}, utils_dir={utils_file_path}")

                # First check if file exists in output_dir
                if os.path.exists(output_file_path):
                    file_path = output_file_path
                    logger.info(f"Found workbook file in output directory: {file_path}")
                # Then check if file exists in app_dir
                elif os.path.exists(app_file_path):
                    file_path = app_file_path
                    logger.info(f"Found workbook file in app directory: {file_path}")
                # Then check if file exists in utils_dir
                elif os.path.exists(utils_file_path):
                    file_path = utils_file_path
                    logger.info(f"Found workbook file in utils directory: {file_path}")
                else:
                    # File not found in any location
                    logger.warning(f"Output file not found for audit_id={audit_id}, workbookName={workbookName}")
                    self._update_status(
                        audit_id, 
                        "Warning", 
                        f"File not found in expected locations. Checked: {output_file_path}, {app_file_path}, and {utils_file_path}"
                    )
                    # No file to process, so return
                    return

                # Update task status to Completed
                self._update_status(
                    audit_id, 
                    "Completed", 
                    f"Task completed successfully. Output file: {os.path.basename(file_path)}",
                    output_file=file_path
                )
            else:
                # No workbookName, so just mark as completed
                self._update_status(
                    audit_id, 
                    "Completed", 
                    "Task completed successfully."
                )
        except Exception as e:
            logger.error(f"Error executing task: {str(e)}")
            logger.error(traceback.format_exc())
            self._update_status(
                audit_id, 
                "Error", 
                f"Error executing task: {str(e)}"
            )

    def _update_status(self, audit_id, status, message, full_output=None, log_file=None, err_file=None, output_file=None):
        """Update the status of a task and call the result callback if provided

        Args:
            audit_id (str): The unique identifier for the audit task
            status (str): The status of the task
            message (str): The status message
            full_output (str, optional): The full output of the command
            log_file (str, optional): Path to the log file
            err_file (str, optional): Path to the error file
            output_file (str, optional): Path to the output file
        """
        try:
            # Find the task in the list
            task_found = False
            for task in self.task_list:
                if task['audit_id'] == audit_id:
                    # Update the task status
                    task['status'] = status
                    task['message'] = message
                    task['timestamp'] = datetime.now().isoformat()
                    
                    # Add additional info if provided
                    if full_output is not None:
                        task['full_output'] = full_output
                    if log_file is not None:
                        task['log_file'] = log_file
                    if err_file is not None:
                        task['err_file'] = err_file
                    if output_file is not None:
                        task['output_file'] = output_file
                        
                    task_found = True
                    break
                    
            if not task_found:
                # Task not found in the list, create a new one
                task = {
                    'audit_id': audit_id,
                    'status': status,
                    'message': message,
                    'timestamp': datetime.now().isoformat()
                }
                
                # Add additional info if provided
                if full_output is not None:
                    task['full_output'] = full_output
                if log_file is not None:
                    task['log_file'] = log_file
                if err_file is not None:
                    task['err_file'] = err_file
                if output_file is not None:
                    task['output_file'] = output_file
                    
                # Add the task to the list
                self.task_list.append(task)
                
            # Call the result callback if provided
            if self.result_callback:
                self.result_callback(
                    audit_id, 
                    status, 
                    message, 
                    full_output, 
                    log_file, 
                    err_file
                )
                
            logger.debug(f"Updated task status: audit_id={audit_id}, status={status}, message={message}")
        except Exception as e:
            logger.error(f"Error updating task status: {str(e)}")
            logger.error(traceback.format_exc())