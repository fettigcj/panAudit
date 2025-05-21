"""
Core Application Module

This module provides the central application logic independent of any UI.
"""

import os
import json
import logging
from datetime import datetime
from src.core.task_queue import TaskQueue
from src.core.audit_manager import AuditManager
from src.core.command_handler import AuditTask, CommandArgumentHandler

# Configure logging
logger = logging.getLogger('CoreApplication')

class PanAuditApplication:
    """Core application logic independent of UI"""

    def __init__(self, config=None):
        """
        Initialize the core application

        Args:
            config (dict, optional): Application configuration. If None, will load from default location.
        """
        # Initialize configuration
        self.app_dir = os.getcwd()
        self.utils_dir = os.path.join(self.app_dir, "panPHP", "utils")
        self.log_dir = os.path.join(self.app_dir, "log")
        self.output_dir = os.path.join(self.app_dir, "output")
        self.config_dir = os.path.join(self.app_dir, "config")

        # Ensure directories exist
        self._ensure_directories()

        # Load configuration if not provided
        self.config = config if config is not None else self._load_config()

        # Initialize task queue with result callback
        # Note: maxThreads is kept for backward compatibility but is no longer used
        # The number of worker threads is now equal to maxActiveProcesses
        max_active_processes = self.config["globalConfig"].get("maxActiveProcesses", 
                                                              self.config["globalConfig"].get("maxThreads", 5))

        self.task_queue = TaskQueue(
            result_callback=self._handle_task_result,
            max_active_processes=max_active_processes
        )
        logger.info(f"Initialized TaskQueue with max_active_processes={max_active_processes}")

        # Initialize audit manager
        self.audit_manager = AuditManager(self.config, self.task_queue)

        # Initialize current audit tasks
        self.current_audit_tasks = []

        # Set up UI callback handlers
        self.result_callback = None
        self.progress_callback = None
        self.confirm_callback = None

    def _ensure_directories(self):
        """Ensure required directories exist"""
        for directory in [self.log_dir, self.output_dir, self.config_dir]:
            if not os.path.exists(directory):
                os.makedirs(directory)

    def _load_config(self):
        """Load configuration from the default location"""
        config_file = os.path.join(self.config_dir, "panAudit.json")
        audits_file = os.path.join(self.config_dir, "audits.json")

        # Default configuration
        default_config = {
            "Panoramas": {},
            "globalConfig": {
                "currentPanorama": "",
                "maxThreads": 5,  # Kept for backward compatibility but no longer used
                "maxActiveProcesses": 5  # Controls the number of concurrent processes and worker threads
            },
            "extraArguments": {
                "shadow-ignoreInvalidAddressobjects": "enabled",
                "shadow-json": "enabled"
            }
        }

        # Try to load configuration from file
        try:
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    config = json.load(f)
                logger.info(f"Loaded configuration from {config_file}")
            else:
                config = default_config
                logger.info("Using default configuration")

            # Load audit sections from audits.json if it exists
            if os.path.exists(audits_file):
                with open(audits_file, 'r') as f:
                    audits_config = json.load(f)

                # Add audit sections to config
                if "AuditSections" in audits_config:
                    config["AuditSections"] = audits_config["AuditSections"]
                if "SPG_Audits" in audits_config:
                    config["SPG_Audits"] = audits_config["SPG_Audits"]

                logger.info(f"Loaded audit sections from {audits_file}")
        except Exception as e:
            logger.error(f"Error loading configuration: {str(e)}")
            config = default_config

        return config

    def save_config(self):
        """Save configuration to file"""
        config_file = os.path.join(self.config_dir, "panAudit.json")
        try:
            with open(config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
            logger.info(f"Configuration saved to {config_file}")
            return True
        except Exception as e:
            logger.error(f"Error saving configuration: {str(e)}")
            return False

    def _handle_task_result(self, audit_id, status, result, full_output=None, log_file=None, err_file=None):
        """
        Handle task results

        This method is called by the task queue when a task completes.
        It forwards the result to the UI callback if one is registered.

        Args:
            audit_id (str): The unique identifier for the audit task
            status (str): The status of the task (e.g., "Completed", "Failed")
            result (dict): The result of the task
            full_output (str, optional): The full output of the task
            log_file (str, optional): Path to the log file
            err_file (str, optional): Path to the error file
        """
        if self.result_callback:
            self.result_callback(audit_id, status, result, full_output, log_file, err_file)

    def set_result_callback(self, callback):
        """
        Set the callback for task results

        Args:
            callback (function): The callback function to be called when a task completes
        """
        self.result_callback = callback

    def set_progress_callback(self, callback):
        """
        Set the callback for progress updates

        Args:
            callback (function): The callback function to be called with progress updates
        """
        self.progress_callback = callback

    def set_confirm_callback(self, callback):
        """
        Set the callback for confirmation requests

        Args:
            callback (function): The callback function to be called for confirmation
        """
        self.confirm_callback = callback

    def generate_audits(self):
        """
        Generate audit tasks based on the current configuration

        Returns:
            list: A list of AuditTask objects
        """
        self.current_audit_tasks = self.audit_manager.generate_audits()
        return self.current_audit_tasks

    def execute_audits(self, audits, audit_tracker=None):
        """
        Execute one or more audit tasks.

        Args:
            audits: Either a single audit (dict of cmd_args + metadata + audit_id) or 
                   a list of AuditTask objects
            audit_tracker (object, optional): The audit tracker object to update with task status

        Returns:
            If a single audit was provided: The audit_id of the executed task (str)
            If multiple audits were provided: The number of tasks submitted (int)
        """
        # Prepare tasks (single or multiple)
        if not isinstance(audits, list):
            # Extract parameters from the single audit
            cmd_args = audits.get('cmd_args', {})
            metadata = audits.get('metadata', {})
            audit_id = audits.get('audit_id')

            # Generate a unique ID if not provided
            if audit_id is None:
                audit_id = f"audit_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

            # Create an AuditTask object
            task = AuditTask(
                audit_id=audit_id,
                cmd_args=cmd_args,
                metadata={
                    "log_dir": self.log_dir,
                    "output_dir": self.output_dir,
                    **(metadata or {})
                }
            )

            # Convert to a list with a single task
            audit_tasks = [task]
            return_single = True
        else:
            # Multiple audits case
            audit_tasks = audits
            return_single = False

        # Add tasks to the audit tracker if provided
        if audit_tracker:
            for task in audit_tasks:
                # Get the command string
                cmd_string = CommandArgumentHandler.to_command_string(task.cmd_args)

                # Extract audit name and section number from metadata
                audit_name = task.metadata.get("audit_name", "Unnamed Audit") if task.metadata else "Unnamed Audit"
                section_number = task.metadata.get("section_number", "") if task.metadata else ""

                # Add the task to the audit tracker
                audit_tracker.add_audit_task(task.audit_id, audit_name, cmd_string, section_number)

            # Show the audit tracker window
            audit_tracker.show()

        # Create a function to submit tasks in the background
        def submit_tasks_background():
            logger.info(f"Starting background thread to submit {len(audit_tasks)} tasks")

            # Define batch size for task submission
            batch_size = 2  # Smaller batch size for more frequent UI updates

            # Process tasks in batches
            for i in range(0, len(audit_tasks), batch_size):
                # Get the current batch
                batch = audit_tasks[i:i+batch_size]

                # Submit tasks in the current batch
                for task in batch:
                    self.task_queue.add_task(
                        audit_id=task.audit_id,
                        cmd_args=task.cmd_args,
                        metadata=task.metadata
                    )

                # Force UI update after each batch
                time.sleep(0.2)  # Longer delay to ensure UI responsiveness
                if audit_tracker and hasattr(audit_tracker, 'root') and audit_tracker.root:
                    try:
                        # Process all pending events
                        audit_tracker.root.update()
                        # Force garbage collection to free up resources
                        import gc
                        gc.collect()
                        logger.debug(f"Processed batch {i//batch_size + 1}/{(len(audit_tasks) + batch_size - 1)//batch_size}")
                    except Exception as e:
                        logger.warning(f"Error updating UI: {str(e)}")

            logger.info(f"Finished submitting {len(audit_tasks)} tasks in background thread")

        # Start the background thread for all tasks (single or multiple)
        import threading
        import time
        thread = threading.Thread(target=submit_tasks_background, daemon=True)
        thread.start()

        # Return appropriate value
        if return_single:
            return audit_tasks[0].audit_id
        else:
            return len(audit_tasks)

    def analyze_output(self):
        """
        Analyze output files

        Returns:
            tuple: A tuple containing (success, message, output_file) where:
                - success (bool): Whether the operation was successful
                - message (str): A message describing the result
                - output_file (str): The path to the output file
        """
        return self.audit_manager.analyze_output(
            progress_callback=self.progress_callback,
            cancel_check=None  # This could be implemented if needed
        )

    def clear_output_files(self):
        """
        Clear output files

        Returns:
            tuple: A tuple containing (success, message) where:
                - success (bool): Whether the operation was successful
                - message (str): A message describing the result
        """
        return self.audit_manager.clear_output_files(
            confirm_callback=self.confirm_callback
        )

    def copy_to_clipboard(self, cmd_args=None, all_tasks=False, clipboard_handler=None):
        """
        Copy command(s) to clipboard

        Args:
            cmd_args (dict, optional): The command arguments to copy
            all_tasks (bool, optional): Whether to copy all tasks
            clipboard_handler (function, optional): Function to handle clipboard operations

        Returns:
            bool: True if successful, False otherwise
        """
        return self.audit_manager.copy_to_clipboard(
            cmd_args=cmd_args,
            all_tasks=all_tasks,
            clipboard_handler=clipboard_handler
        )
