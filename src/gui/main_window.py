import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
import threading
import queue
import logging
import traceback
from collections import OrderedDict

from src.gui.config_window import ConfigWindow
from src.gui.tracker_window import AuditTracker
from src.gui.audit_window import AuditWindow
from src.gui.modify_audits_window import ModifyAuditsWindow
from src.core.task_queue import TaskQueue
from src.core.audit_manager import AuditManager
from src.core.command_handler import CommandArgumentHandler

# Configure logging
logger = logging.getLogger(__name__)

class PanoramaAuditGUI:
    def __init__(self, root, core_app):
        self.root = root
        self.root.title("Panorama Security Policy Auditor")
        self.root.geometry("800x600")

        # Store the core application
        self.core_app = core_app

        # Set up callbacks
        self.core_app.set_result_callback(self.handle_result_message)

        # Store paths from core app
        self.app_dir = self.core_app.app_dir
        self.utils_dir = self.core_app.utils_dir
        self.log_dir = self.core_app.log_dir
        self.output_dir = self.core_app.output_dir
        self.config_dir = self.core_app.config_dir

        # Get configuration from core app
        self.config = self.core_app.config

        # Track the current output file
        self.current_output_file = None

        # Create the audit tracker window (initially hidden)
        self.audit_tracker = AuditTracker(self.root)
        self.audit_tracker.withdraw()  # Hide the window initially

        # Create the main frame
        self.main_frame = ttk.Frame(root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Create the GUI components
        self.create_toolbar()

        # Create the audit window
        self.audit_window = AuditWindow(self.main_frame, self)

        # Initialize current_audit_tasks
        self.current_audit_tasks = []

        # Bind the window close event
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def load_config(self):
        """Load configuration from the core application"""
        return self.core_app.config

    def save_config(self):
        """Save configuration using the core application"""
        try:
            success = self.core_app.save_config()
            if not success:
                messagebox.showerror("Error", "Failed to save configuration")
            return success
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save configuration: {str(e)}")
            return False

    def create_toolbar(self):
        """Create the toolbar with buttons for configuration and audit generation"""
        toolbar_frame = ttk.Frame(self.main_frame)
        toolbar_frame.pack(fill=tk.X, pady=5)

        # Add Panorama selection dropdown
        panorama_frame = ttk.Frame(toolbar_frame)
        panorama_frame.pack(side=tk.LEFT, padx=5)

        ttk.Label(panorama_frame, text="Select Panorama:").pack(side=tk.LEFT, padx=2)
        self.toolbar_panorama_var = tk.StringVar(value=self.config.get("currentPanorama", ""))
        self.toolbar_panorama_dropdown = ttk.Combobox(panorama_frame, textvariable=self.toolbar_panorama_var, width=25)
        self.toolbar_panorama_dropdown.pack(side=tk.LEFT, padx=2)
        self.update_toolbar_panorama_dropdown()
        self.toolbar_panorama_dropdown.bind("<<ComboboxSelected>>", self.on_toolbar_panorama_selected)

        # Add Configure button
        ttk.Button(toolbar_frame, text="Configure", command=self.open_config_window).pack(side=tk.LEFT, padx=5)

        # Add Modify Audits button
        ttk.Button(toolbar_frame, text="Modify Audits", command=self.open_modify_audits_window).pack(side=tk.LEFT, padx=5)

        # Add Generate Audits button
        ttk.Button(toolbar_frame, text="Generate Audits", command=self.generateAudits).pack(side=tk.LEFT, padx=5)

        # Add Audit Tracker button
        ttk.Button(toolbar_frame, text="Audit Progress Status", command=self.show_audit_tracker).pack(side=tk.LEFT, padx=5)

    def handle_result_message(self, audit_id, status, result, full_output=None, log_file=None, err_file=None):
        """Handle a result message from the task processor

        Args:
            audit_id (str): The unique identifier for the audit task
            status (str): The status of the task
            result (str): The result message
            full_output (str, optional): The full output of the command
            log_file (str, optional): Path to the log file
            err_file (str, optional): Path to the error file
        """
        logger.info(f"Handling result message for audit_id={audit_id}, status={status}")

        # Update the audit task status in the audit tracker
        self.audit_tracker.update_audit_task(audit_id, status=status, result=result, full_output=full_output, log_file=log_file, err_file=err_file)

    def on_close(self):
        """Handle the window close event with improved error handling"""
        logger.info("Application closing...")

        try:
            # Stop the task processor via core_app
            logger.info("Stopping task processor...")
            self.core_app.task_queue.stop_processing()
            logger.info("Task processor stopped")

            # Close the audit tracker if it's open
            try:
                logger.info("Closing audit tracker...")
                if hasattr(self, 'audit_tracker'):
                    self.audit_tracker.on_close()
                logger.info("Audit tracker closed")
            except Exception as e:
                logger.error(f"Error closing audit tracker: {str(e)}")
                logger.error(traceback.format_exc())

            # Save any pending configuration changes
            try:
                logger.info("Saving configuration...")
                self.save_config()
                logger.info("Configuration saved")
            except Exception as e:
                logger.error(f"Error saving configuration: {str(e)}")
                logger.error(traceback.format_exc())

            logger.info("Application shutdown complete, destroying root window")
        except Exception as e:
            logger.error(f"Error during application shutdown: {str(e)}")
            logger.error(traceback.format_exc())
        finally:
            # Close the application even if there were errors
            try:
                self.root.destroy()
            except Exception as e:
                logger.error(f"Error destroying root window: {str(e)}")
                logger.error(traceback.format_exc())
                # Force exit as a last resort
                import os
                os._exit(0)

    def show_audit_tracker(self):
        """Show the audit tracker window"""
        logger.info("Showing audit tracker window")
        self.audit_tracker.show()

    def open_config_window(self):
        """Open the configuration window"""
        logger.info("Opening configuration window")
        config_window = ConfigWindow(self.root, self.config, self.update_config)
        self.root.wait_window(config_window)
        logger.info("Configuration window closed")

    def open_modify_audits_window(self):
        """Open the modify audits window"""
        logger.info("Opening modify audits window")
        try:
            modify_audits_window = ModifyAuditsWindow(self.root, self.config, self.update_config)
            self.root.wait_window(modify_audits_window)
            logger.info("Modify audits window closed")
        except Exception as e:
            logger.error(f"Failed to open Modify Audits window: {str(e)}")
            logger.error(traceback.format_exc())
            messagebox.showerror("Error", f"Failed to open Modify Audits window: {str(e)}")

    def update_config(self, new_config):
        """Update the configuration with values from the config window"""
        logger.info("Updating configuration")
        # Update the configuration
        self.config = new_config
        self.save_config()

        # Update the toolbar panorama dropdown
        self.update_toolbar_panorama_dropdown()
        logger.info("Configuration updated successfully")

    def update_toolbar_panorama_dropdown(self):
        """Update the toolbar panorama dropdown with the current list of instances"""
        panorama_instances = list(self.config["Panoramas"].keys())
        self.toolbar_panorama_dropdown['values'] = panorama_instances
        if panorama_instances and not self.toolbar_panorama_var.get():
            self.toolbar_panorama_var.set(panorama_instances[0])
            self.config["globalConfig"]["currentPanorama"] = panorama_instances[0]
        else:
            # Set to current panorama
            self.toolbar_panorama_var.set(self.config["globalConfig"].get("currentPanorama", ""))

    def on_toolbar_panorama_selected(self, event):
        """Handle selection of a panorama from the toolbar dropdown"""
        selected = self.toolbar_panorama_var.get()
        logger.info(f"Panorama selected from dropdown: {selected}")
        if selected and selected in self.config["Panoramas"]:
            self.config["globalConfig"]["currentPanorama"] = selected
            self.save_config()
            logger.info(f"Generating audits for selected panorama: {selected}")
            # Generate audits for the selected panorama
            self.generateAudits()
        else:
            logger.warning(f"Invalid panorama selection: {selected}")

    def generateAudits(self):
        """Generate audit commands based on the current configuration"""
        logger.info("Generating audit commands")

        # Clear existing audit widgets in audit_window
        self.audit_window.clear_audit_widgets()

        # Use the core_app to generate audits
        self.current_audit_tasks = self.core_app.generate_audits()

        # Iterate over the returned audit_tasks list and add each audit to the UI
        for task in self.current_audit_tasks:
            # Extract necessary information from the task
            cmd_args = task.cmd_args
            metadata = task.metadata
            audit_id = task.audit_id

            # Generate command string
            cmd_string = CommandArgumentHandler.to_command_string(cmd_args)

            # Create section title based on metadata
            if 'audit_number' in metadata and 'audit_name' in metadata:
                title = metadata.get('audit_name', 'Unnamed Audit')
                audit_num = metadata.get('audit_number', '')
                section_title = f"Audit {audit_num} ({title})"
            elif 'spg_name' in metadata and 'audit_name' in metadata:
                title = metadata.get('audit_name', 'Unnamed Audit')
                audit_num = metadata.get('audit_number', '')
                section_title = f"Audit {audit_num} ({title})"
            else:
                section_title = "Unnamed Audit"

            # Add the audit section to the UI with a fixed indent of 40
            self.audit_window.add_audit_section(
                section_title=section_title,
                cmd_string=cmd_string,
                cmd_args=cmd_args,
                section_id=audit_id,
                indent=40  # Fixed indent value as proposed
            )

        logger.info(f"Generated {len(self.current_audit_tasks)} audit tasks")
        return self.current_audit_tasks

    def execute_command(self, cmd_args, metadata=None, audit_id=None):
        """Execute a command with the given arguments

        Args:
            cmd_args (dict): The command arguments as a dictionary
            metadata (dict, optional): Additional metadata for the command
            audit_id (str, optional): A unique identifier for the audit task

        Returns:
            str: The audit_id of the executed task
        """
        # Extract audit title and section number from metadata for logging
        audit_title = metadata.get("audit_name", "Unnamed Audit") if metadata else "Unnamed Audit"
        section_number = metadata.get("section_number", "") if metadata else ""
        logger.info(f"execute_command called with audit_title={audit_title}, section_number={section_number}")

        # Create a single audit dictionary
        audit = {
            'cmd_args': cmd_args,
            'metadata': metadata,
            'audit_id': audit_id
        }

        # Use the core_app to execute the command
        return self.core_app.execute_audits(
            audits=audit,
            audit_tracker=self.audit_tracker
        )

    def execute_all_audits(self):
        """Execute all audit commands"""
        logger.info("execute_all_audits called")

        # Confirm with the user
        if not messagebox.askyesno("Confirm", "Execute all audit commands? This may take a while."):
            logger.info("User cancelled execute_all_audits")
            return

        # Show the audit tracker
        logger.debug("Showing audit tracker for execute_all_audits")
        self.audit_tracker.show()

        # Check if we have audit tasks
        if not hasattr(self, 'current_audit_tasks') or not self.current_audit_tasks:
            logger.warning("No audit tasks available to execute")
            messagebox.showwarning("Warning", "No audit tasks available to execute. Please generate audits first.")
            return

        # Use the core_app to execute all audit tasks
        task_count = self.core_app.execute_audits(
            audits=self.current_audit_tasks,
            audit_tracker=self.audit_tracker
        )
        logger.info(f"Submitted {task_count} audit tasks for execution")

        if task_count > 0:
            messagebox.showinfo("Execution Started", f"Submitted {task_count} audit tasks for execution. You can track progress in the Audit Tracker window.")

    def analyze_output(self):
        """Analyze the output files"""
        logger.info("analyze_output called")

        # Find all Excel files in the output directory
        output_dir = self.output_dir
        excel_files = []
        for filename in os.listdir(output_dir):
            if filename.endswith(".xls"):
                excel_files.append(os.path.join(output_dir, filename))
                logger.debug(f"Found Excel file for analysis: {filename}")

        if not excel_files:
            logger.warning("No output files found to analyze")
            messagebox.showwarning("Warning", "No output files found to analyze.")
            return

        logger.info(f"Found {len(excel_files)} Excel files to analyze")

        # Import the AnalysisProgressWindow
        from src.gui.analysis_window import AnalysisProgressWindow

        # Create and show the analysis progress window
        logger.debug("Creating analysis progress window")
        analysis_window = AnalysisProgressWindow(self.root, excel_files)

        # Define the progress callback
        def progress_callback(file_path, success):
            analysis_window.update_progress(file_path, success)

        # Define the cancel check
        def cancel_check():
            return analysis_window.cancelled

        # Define a function to display the results
        def display_results(success, message, output_file):
            # Check if the operation was cancelled
            if cancel_check():
                return

            if not success:
                messagebox.showerror("Error", message)
                return

            if output_file:
                messagebox.showinfo("Analysis Complete", f"Analysis complete. Results saved to:\n{output_file}")

        # Start a thread to process the files
        def process_files():
            logger.info("Starting file analysis thread")
            try:
                # Set the progress callback in the core app
                self.core_app.set_progress_callback(progress_callback)

                # Use the core app to analyze the output
                success, message, output_file = self.core_app.analyze_output()

                # Schedule the result display on the main thread
                self.root.after(100, lambda: display_results(success, message, output_file))

            except Exception as e:
                logger.error(f"Error during analysis: {str(e)}")
                logger.error(traceback.format_exc())
                messagebox.showerror("Error", f"An error occurred during analysis: {str(e)}")
            finally:
                # Schedule window destruction on the main thread
                self.root.after(200, lambda: close_window_if_exists())

        def close_window_if_exists():
            if analysis_window.winfo_exists():
                logger.debug("Closing analysis progress window")
                analysis_window.destroy()

        # Start the processing thread
        threading.Thread(target=process_files, daemon=True).start()

    def clear_output_files(self):
        """Clear the output files"""
        logger.info("clear_output_files called")

        # Define the confirm callback
        def confirm_callback(message):
            return messagebox.askyesno("Confirm", message)

        # Set the confirm callback in the core app
        self.core_app.set_confirm_callback(confirm_callback)

        # Use the core app to clear the output files
        success, message = self.core_app.clear_output_files()

        # Display the result
        if success:
            messagebox.showinfo("Success", message)
        else:
            if "cancelled" not in message.lower():
                messagebox.showerror("Error", message)

    def copy_to_clipboard(self, text):
        """Copy text to clipboard

        Args:
            text (str): The text to copy to the clipboard
        """
        logger.debug(f"Copying text to clipboard: {text[:50]}...")
        self.root.clipboard_clear()
        self.root.clipboard_append(text)

    def copy_command_to_clipboard(self, cmd_args):
        """Copy a command to the clipboard

        Args:
            cmd_args (dict): The command arguments to copy
        """
        logger.info("Copying command to clipboard")

        # Define the clipboard handler
        def clipboard_handler(text):
            self.copy_to_clipboard(text)

        # Use the core app to copy the command to the clipboard
        success = self.core_app.copy_to_clipboard(
            cmd_args=cmd_args,
            all_tasks=False,
            clipboard_handler=clipboard_handler
        )

        # Display the result
        if success:
            messagebox.showinfo("Copied", "Command copied to clipboard")
        else:
            messagebox.showerror("Error", "Failed to copy command to clipboard")

    def copy_all_commands_to_clipboard(self):
        """Copy all commands to the clipboard"""
        logger.info("Copying all commands to clipboard")

        # Define the clipboard handler
        def clipboard_handler(text):
            self.copy_to_clipboard(text)

        # Use the core app to copy all commands to the clipboard
        success = self.core_app.copy_to_clipboard(
            all_tasks=True,
            clipboard_handler=clipboard_handler
        )

        # Display the result
        if success:
            messagebox.showinfo("Copied", "All commands copied to clipboard")
        else:
            messagebox.showerror("Error", "Failed to copy commands to clipboard")
