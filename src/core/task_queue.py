"""
Task Queue Module

This module provides a task queue for executing commands in parallel.

Workflow:
1. add_task() - Called by the GUI to submit a task
2. _execute_task() - Runs the task in a worker thread
3. _update_status() - Handles the task result and updates the UI
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
from concurrent.futures import ThreadPoolExecutor
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
                Defaults to 5.
            max_active_processes (int, optional): Maximum number of concurrent processes to run.
                Defaults to 10.
        """
        self.queue = []
        self.result_callback = result_callback
        self.running = False
        self.current_task = None
        self.app_dir = os.getcwd()
        self.utils_dir = os.path.join(self.app_dir, "panPHP", "utils")
        self.log_dir = os.path.join(self.app_dir, "log")
        self.output_dir = os.path.join(self.app_dir, "output")
        self.use_separate_window = False  # Always use direct subprocess execution

        # Initialize thread pool for parallel task execution
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.futures = {}  # Track futures by audit_id

        # Add semaphore to limit concurrent processes
        self.max_active_processes = max_active_processes
        self.active_processes = 0
        self.process_semaphore = threading.Semaphore(max_active_processes)
        logger.info(f"Initialized TaskQueue with max_workers={max_workers}, max_active_processes={max_active_processes}")

        # Detect operating system
        self.is_windows = sys.platform.startswith('win')

        # Ensure log and output directories exist
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

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

            # Add the task to the queue for tracking
            self.queue.append(task)

            # Check if we should pause this task
            should_pause = paused

            # Count active tasks (those that are not paused and not completed)
            active_tasks = 0
            for t in self.queue:
                if not t.get('paused', False) and t.get('status', '') not in ['Completed', 'Failed', 'Error']:
                    active_tasks += 1

            # If we already have max_workers active tasks, pause this one
            if active_tasks >= self.executor._max_workers:
                should_pause = True
                logger.info(f"Thread pool is full ({active_tasks}/{self.executor._max_workers}), pausing task: audit_id={audit_id}")

            # Only submit to thread pool if not paused
            if not should_pause:
                # Update task status to Queued before submitting to thread pool
                self._update_status(audit_id, "Queued", "Task added, waiting for available thread...")
                self._submit_to_thread_pool(task)
            else:
                # Mark the task as paused
                task['paused'] = True
                # Update task status to Paused
                if paused:
                    # User explicitly paused this task
                    self._update_status(audit_id, "Paused", "Task paused by user")
                else:
                    # Task paused due to thread pool being full
                    self._update_status(audit_id, "Paused", f"Waiting for available thread (max {self.executor._max_workers} threads)...")
                audit_name = metadata.get('audit_name') if metadata else None
                logger.info(f"Task added in paused state: audit_id={audit_id}, audit_name={audit_name}")

            audit_name = metadata.get('audit_name') if metadata else None
            logger.info(f"Added task to queue: audit_id={audit_id}, audit_name={audit_name}, paused={task.get('paused', False)}")
            return True
        except Exception as e:
            logger.error(f"Failed to add task to queue: {str(e)}")
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
        logger.info("Task processing is handled by the thread pool")
        return

    def _submit_to_thread_pool(self, task):
        """Submit a task to the thread pool for execution

        Args:
            task (dict): The task to submit
        """
        audit_id = task['audit_id']
        cmd_args = task['cmd_args']
        metadata = task['metadata']

        # Submit the task to the thread pool for execution, using the semaphore wrapper
        future = self.executor.submit(
            self._execute_task_with_semaphore,
            audit_id,
            cmd_args,
            metadata
        )

        # Store the future for tracking
        self.futures[audit_id] = future

        audit_name = metadata.get('audit_name') if metadata else None
        logger.info(f"Submitted task to thread pool: audit_id={audit_id}, audit_name={audit_name}")

        # Note: We don't update the status here because the task is still in "Queued" state
        # The status will be updated to "Running" when the task actually starts executing in _execute_task

    def _execute_task_with_semaphore(self, audit_id, cmd_args, metadata=None):
        """Execute a task with semaphore control to limit concurrent processes

        This method tries to acquire the semaphore before executing the task.
        If the semaphore can't be acquired immediately, the task is paused.
        The semaphore will be released by the monitoring thread when the process completes.

        Args:
            audit_id (str): The unique identifier for the audit task
            cmd_args (dict): The command arguments as a dictionary
            metadata (dict, optional): A dictionary containing metadata about the audit
        """
        # Try to acquire semaphore with a timeout to prevent indefinite blocking
        logger.debug(f"Trying to acquire process semaphore for audit_id={audit_id}")

        # First try non-blocking acquisition
        if self.process_semaphore.acquire(blocking=False):
            logger.debug(f"Acquired process semaphore immediately for audit_id={audit_id}")
            acquired = True
        else:
            # If immediate acquisition fails, update status to Paused
            logger.info(f"No semaphore immediately available, marking task as paused: audit_id={audit_id}")
            self._update_status(audit_id, "Paused", "Waiting for available process slot...")

            # Try to acquire with a timeout
            try:
                # Try to acquire with a 5-second timeout
                acquired = self.process_semaphore.acquire(blocking=True, timeout=5)
                if acquired:
                    logger.debug(f"Acquired process semaphore after waiting for audit_id={audit_id}")
                    # Update status back to Queued
                    self._update_status(audit_id, "Queued", "Process slot available, preparing to execute...")
                else:
                    logger.info(f"Semaphore acquisition timed out for audit_id={audit_id}, scheduling retry")
                    # Schedule a retry after a delay
                    self._retry_paused_task(audit_id, cmd_args, metadata)
                    return
            except Exception as e:
                logger.error(f"Error acquiring semaphore: {str(e)}")
                logger.error(traceback.format_exc())
                # Schedule a retry after a delay
                self._retry_paused_task(audit_id, cmd_args, metadata)
                return

        # If we got here, we acquired the semaphore
        if acquired:
            try:
                # Execute the task, passing the semaphore
                # The semaphore will be released by the monitoring thread when the process completes
                self._execute_task(audit_id, cmd_args, metadata, semaphore=self.process_semaphore)
            except Exception as e:
                # If an error occurs before the task is executed, release the semaphore
                logger.error(f"Error executing task with semaphore: {str(e)}")
                logger.error(traceback.format_exc())

                # Release the semaphore
                logger.debug(f"Releasing process semaphore for audit_id={audit_id} due to exception")
                self.process_semaphore.release()

                # Update task status
                self._update_status(
                    audit_id, 
                    "Error", 
                    f"Error executing task: {str(e)}"
                )
        else:
            # This should not happen, but just in case
            logger.warning(f"Failed to acquire semaphore for audit_id={audit_id} but didn't schedule retry")
            # Schedule a retry after a delay
            self._retry_paused_task(audit_id, cmd_args, metadata)

    def _retry_paused_task(self, audit_id, cmd_args, metadata=None):
        """Retry a paused task after a delay

        Args:
            audit_id (str): The unique identifier for the audit task
            cmd_args (dict): The command arguments as a dictionary
            metadata (dict, optional): A dictionary containing metadata about the audit
        """
        import threading
        import time
        import random

        # Use a single retry thread instead of creating a new one for each retry
        def retry_task():
            try:
                # Add a random component to the delay to prevent thundering herd problem
                # where all tasks try to acquire the semaphore at the same time
                jitter = random.uniform(0.5, 1.5)
                retry_delay = 2.0 * jitter

                logger.debug(f"Scheduling retry for paused task: audit_id={audit_id} after {retry_delay:.2f} seconds")
                time.sleep(retry_delay)

                logger.debug(f"Attempting to retry paused task: audit_id={audit_id}")

                # Check if the task is still in the queue
                task_exists = False
                for task in self.queue:
                    if task['audit_id'] == audit_id:
                        task_exists = True
                        break

                if not task_exists:
                    logger.debug(f"Task no longer exists in queue, cancelling retry: audit_id={audit_id}")
                    return

                # Try to acquire semaphore with a timeout
                try:
                    # Try to acquire with a short timeout
                    acquired = self.process_semaphore.acquire(blocking=True, timeout=1.0)
                    if acquired:
                        logger.debug(f"Acquired process semaphore for paused task: audit_id={audit_id}")

                        # Update task status to Running
                        self._update_status(audit_id, "Running", "Resuming execution...")

                        # Execute the task
                        self._execute_task(audit_id, cmd_args, metadata, semaphore=self.process_semaphore)
                    else:
                        # Still no semaphore available, schedule another retry with exponential backoff
                        logger.debug(f"Still no semaphore available for task: audit_id={audit_id}")

                        # Update status to ensure user knows task is still paused
                        self._update_status(audit_id, "Paused", f"Still waiting for available process slot (retry {metadata.get('retry_count', 1)})")

                        # Increment retry count in metadata
                        if metadata is None:
                            metadata = {}
                        retry_count = metadata.get('retry_count', 0) + 1
                        metadata['retry_count'] = retry_count

                        # Calculate backoff delay (capped at 30 seconds)
                        max_delay = min(30.0, 2.0 * (1.5 ** min(retry_count, 10)))
                        backoff_delay = random.uniform(2.0, max_delay)

                        logger.debug(f"Scheduling retry {retry_count} with backoff delay of {backoff_delay:.2f}s for audit_id={audit_id}")

                        # Use a timer to retry after a delay with exponential backoff
                        timer = threading.Timer(backoff_delay, lambda audit_id=audit_id, cmd_args=cmd_args, metadata=metadata: self._retry_paused_task(audit_id, cmd_args, metadata))
                        timer.daemon = True
                        timer.start()
                except Exception as e:
                    logger.error(f"Error acquiring semaphore in retry: {str(e)}")
                    logger.error(traceback.format_exc())

                    # Schedule another retry
                    timer = threading.Timer(5.0, lambda audit_id=audit_id, cmd_args=cmd_args, metadata=metadata: self._retry_paused_task(audit_id, cmd_args, metadata))
                    timer.daemon = True
                    timer.start()
            except Exception as e:
                logger.error(f"Error in retry task thread: {str(e)}")
                logger.error(traceback.format_exc())

                # Try to update status to reflect the error
                try:
                    self._update_status(
                        audit_id, 
                        "Error", 
                        f"Error retrying paused task: {str(e)}"
                    )
                except Exception as status_error:
                    logger.error(f"Error updating status: {str(status_error)}")

        # Start a thread to retry the task after a delay
        retry_thread = threading.Thread(target=retry_task)
        retry_thread.daemon = True
        retry_thread.start()

    def unpause_task(self, audit_id):
        """Unpause a specific task and submit it to the thread pool

        Args:
            audit_id (str): The unique identifier for the audit task

        Returns:
            bool: True if the task was unpaused successfully, False otherwise
        """
        for task in self.queue:
            if task['audit_id'] == audit_id and task.get('paused', False):
                task['paused'] = False
                # Update task status to Queued before submitting to thread pool
                self._update_status(audit_id, "Queued", "Task unpaused, waiting for available thread...")
                self._submit_to_thread_pool(task)
                logger.info(f"Unpaused task: audit_id={audit_id}")
                return True

        logger.warning(f"Task not found or already unpaused: audit_id={audit_id}")
        return False

    def get_paused_tasks(self):
        """Get a list of all paused tasks in the queue

        Returns:
            list: A list of paused task dictionaries
        """
        return [task for task in self.queue if task.get('paused', False)]

    def unpause_all_tasks(self):
        """Unpause all paused tasks and submit them to the thread pool

        Returns:
            int: The number of tasks that were unpaused
        """
        unpaused_count = 0
        for task in self.queue:
            if task.get('paused', False):
                task['paused'] = False
                # Update task status to Queued before submitting to thread pool
                audit_id = task['audit_id']
                self._update_status(audit_id, "Queued", "Task unpaused, waiting for available thread...")
                self._submit_to_thread_pool(task)
                unpaused_count += 1

        logger.info(f"Unpaused {unpaused_count} tasks")
        return unpaused_count

    def stop_processing(self):
        """Stop processing tasks and shut down the thread pool"""
        logger.info("Shutting down thread pool")

        # Cancel any pending futures
        for audit_id, future in self.futures.items():
            if not future.done():
                future.cancel()
                logger.info(f"Cancelled pending task: audit_id={audit_id}")

        # Shutdown the executor (but allow running tasks to complete)
        self.executor.shutdown(wait=False)

        # Clear the queue
        self.queue.clear()
        self.futures.clear()

        logger.info("Stopped task processing")

    def _execute_task(self, audit_id, cmd_args, metadata=None, semaphore=None):
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
            semaphore (threading.Semaphore, optional): The semaphore to release when the task completes
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
                        # Use subprocess.Popen for non-blocking execution
                        logger.debug(f"Starting subprocess for audit_id={audit_id} with working directory set to output directory: {self.output_dir}")

                        # Create the process with a timeout
                        try:
                            process = subprocess.Popen(
                                php_args,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True,
                                cwd=self.output_dir,  # Set working directory to output directory
                                bufsize=1  # Line buffered
                            )
                            logger.debug(f"Subprocess started for audit_id={audit_id}, pid={process.pid}")
                        except Exception as proc_error:
                            # Handle error starting the process
                            error_msg = f"Error starting subprocess: {str(proc_error)}"
                            logger.error(f"Exception starting subprocess: {error_msg}")
                            logger.error(traceback.format_exc())

                            # Update task status
                            self._update_status(
                                audit_id, 
                                "Failed", 
                                error_msg,
                                log_file=log_file_path,
                                err_file=err_file_path
                            )

                            # Release the semaphore if provided
                            if semaphore:
                                logger.debug(f"Releasing process semaphore for audit_id={audit_id} due to process start error")
                                semaphore.release()

                            return

                        # Create a monitoring function to handle process completion
                        def monitor_process():
                            try:
                                logger.debug(f"Monitoring process for audit_id={audit_id}, pid={process.pid}")

                                # Wait for process to complete and capture output with a timeout
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
                                logger.error(f"Error monitoring process: {str(e)}")
                                logger.error(traceback.format_exc())
                                self._update_status(
                                    audit_id, 
                                    "Failed", 
                                    f"Error monitoring process: {str(e)}",
                                    log_file=log_file_path,
                                    err_file=err_file_path
                                )
                            finally:
                                # Release the semaphore if provided
                                if semaphore:
                                    logger.debug(f"Releasing process semaphore for audit_id={audit_id}")
                                    semaphore.release()

                        # Start a separate thread to monitor the process
                        monitor_thread = threading.Thread(target=monitor_process, name=f"Monitor-{audit_id}")
                        monitor_thread.daemon = True
                        monitor_thread.start()
                        logger.debug(f"Started monitor thread for audit_id={audit_id}")

                        # Return immediately, allowing the worker thread to process other tasks
                        return
                    except Exception as e:
                        # Handle error starting the subprocess
                        error_msg = f"Error starting subprocess: {str(e)}"
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

                        # Release the semaphore if provided
                        if semaphore:
                            logger.debug(f"Releasing process semaphore for audit_id={audit_id} due to subprocess start exception")
                            semaphore.release()

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

                # Release the semaphore if provided
                if semaphore:
                    logger.debug(f"Releasing process semaphore for audit_id={audit_id} due to exception")
                    semaphore.release()

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

                # File exists, proceed with processing
                if os.path.exists(file_path):
                    logger.debug(f"Processing output file: {file_path}")
                    # Modify the file to replace "#br {" with "br {" between <style> and </style> tags
                    try:
                        with open(file_path, 'r', encoding='utf-8') as file:
                            content = file.read()
                        logger.debug(f"Read {len(content)} bytes from file: {file_path}")

                        # Find the style section
                        style_start = content.find("<style>")
                        style_end = content.find("</style>", style_start)
                        logger.debug(f"Style section found: start={style_start}, end={style_end}")

                        if style_start != -1 and style_end != -1:
                            # Extract the style section
                            style_section = content[style_start:style_end]
                            logger.debug(f"Extracted style section of length {len(style_section)}")

                            # Replace "#br {" with "br {" in the style section
                            modified_style = style_section.replace("#br {", "br {")
                            logger.debug("Replaced '#br {' with 'br {' in style section")

                            # Replace the original style section with the modified one
                            modified_content = content[:style_start] + modified_style + content[style_end:]
                            logger.debug(f"Created modified content of length {len(modified_content)}")

                            # Write the modified content back to the file
                            with open(file_path, 'w', encoding='utf-8') as file:
                                file.write(modified_content)
                            logger.debug(f"Wrote modified content back to file: {file_path}")

                            # Move the file to the output directory
                            destination_path = os.path.join(self.output_dir, workbookName)
                            logger.debug(f"Destination path for file: {destination_path}")

                            # Only move if source and destination are different paths
                            if file_path != destination_path:
                                try:
                                    logger.debug(f"Moving file from {file_path} to {destination_path}")
                                    # Copy the file to the destination
                                    shutil.copy2(file_path, destination_path)

                                    # Verify the copy was successful
                                    if os.path.exists(destination_path):
                                        # Delete the original file
                                        os.unlink(file_path)
                                        logger.info(f"Moved file to output directory and deleted original: {destination_path}")
                                    else:
                                        logger.error(f"Failed to copy file to output directory: {destination_path}")
                                except Exception as e:
                                    logger.error(f"Error moving file: {str(e)}")
                                    logger.error(traceback.format_exc())
                            else:
                                logger.debug(f"File already in output directory, no need to move: {file_path}")

                            # Update the task status with appropriate message
                            if file_path != destination_path:
                                self._update_status(
                                    audit_id, 
                                    "Completed", 
                                    f"File created, modified, and moved to output directory: {workbookName}"
                                )
                                logger.info(f"Task {audit_id} completed: file moved to output directory")
                            else:
                                self._update_status(
                                    audit_id, 
                                    "Completed", 
                                    f"File created and modified in place: {workbookName}"
                                )
                                logger.info(f"Task {audit_id} completed: file modified in place")
                        else:
                            # Style tags not found, update the task status
                            logger.warning(f"Style tags not found in file: {file_path}")
                            self._update_status(
                                audit_id, 
                                "Warning", 
                                f"File created but style tags not found for modification: {workbookName}"
                            )
                    except Exception as e:
                        # Update the task status if file modification fails
                        error_msg = f"File created but modification failed: {str(e)}"
                        logger.error(f"Exception in execute_task file modification: {error_msg}")
                        logger.error(traceback.format_exc())
                        logger.debug(f"Exception details for file {file_path}: {type(e).__name__}: {str(e)}")
                        self._update_status(
                            audit_id, 
                            "Warning", 
                            error_msg
                        )
                else:
                    # Update the task status if file was not created
                    logger.error(f"File exists check failed for {file_path}")
                    self._update_status(
                        audit_id, 
                        "Error", 
                        f"File was not created: {workbookName}"
                    )
            else:
                # No workbook name, just update the status
                logger.info(f"No workbook name provided for audit_id={audit_id}, marking as completed")
                self._update_status(
                    audit_id, 
                    "Completed", 
                    "Command executed successfully"
                )
                logger.debug(f"Task {audit_id} completed without workbook name")

        except Exception as e:
            # Update the task status if an error occurs
            error_msg = f"Failed to execute command: {str(e)}"
            logger.error(f"Exception in execute_task: {error_msg}")
            logger.error(traceback.format_exc())
            self._update_status(
                audit_id, 
                "Error", 
                error_msg
            )

    def _update_status(self, audit_id, status, result, full_output=None, log_file=None, err_file=None):
        """Update the status of a task and call the result callback

        Args:
            audit_id (str): The unique identifier for the audit task
            status (str): The status of the task
            result (str): The result message
            full_output (str, optional): The full output of the command
            log_file (str, optional): Path to the log file
            err_file (str, optional): Path to the error file
        """
        # Log with a more readable format
        if status in ["Completed", "Failed", "Error", "Warning", "Paused"]:
            logger.info(f"Task {audit_id} {status.lower()} with result: {result}")
        else:
            logger.info(f"Task {audit_id} status updated to {status}: {result}")

        # Update the task status in the queue
        for task in self.queue:
            if task['audit_id'] == audit_id:
                task['status'] = status
                task['result'] = result
                break

        # If a task has completed or failed, check if we can unpause a paused task
        if status in ["Completed", "Failed", "Error"]:
            # Count active tasks (those that are not paused and not completed)
            active_tasks = 0
            for task in self.queue:
                if not task.get('paused', False) and task.get('status', '') not in ['Completed', 'Failed', 'Error']:
                    active_tasks += 1

            logger.debug(f"Task {audit_id} {status.lower()}, active tasks: {active_tasks}/{self.executor._max_workers}")

            # If we have fewer active tasks than max_workers, try to unpause a task
            if active_tasks < self.executor._max_workers:
                # Find the first paused task
                for task in self.queue:
                    if task.get('paused', False):
                        paused_audit_id = task['audit_id']
                        logger.info(f"Unpausing task {paused_audit_id} as resources are now available")
                        # Unpause the task
                        task['paused'] = False
                        # Update the task status
                        self._update_status(paused_audit_id, "Queued", "Task unpaused, resources now available")
                        # Submit the task to the thread pool
                        self._submit_to_thread_pool(task)
                        break

        # Call the result callback if provided
        if self.result_callback:
            try:
                # Use a separate thread for the callback to avoid blocking
                def call_callback():
                    try:
                        # Add a small delay to allow the UI to process other events first
                        import time
                        time.sleep(0.01)

                        # Call the callback
                        self.result_callback(audit_id, status, result, full_output, log_file, err_file)
                    except Exception as e:
                        logger.error(f"Error in callback thread: {str(e)}")
                        logger.error(traceback.format_exc())

                # Start the thread with a lower priority
                callback_thread = threading.Thread(target=call_callback, daemon=True)
                callback_thread.name = f"Callback-{audit_id}-{status}"
                callback_thread.start()
            except Exception as e:
                logger.error(f"Error creating callback thread: {str(e)}")
                logger.error(traceback.format_exc())
