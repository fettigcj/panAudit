"""
Audit Manager Module

This module provides functionality for generating and executing audit commands.
"""

import os
import json
import logging
import traceback
import shutil
from datetime import datetime
import sys

# Add the src directory to the path if running as standalone
if __name__ == "__main__":
    sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

from src.core.command_handler import CommandArgumentHandler, AuditTask

# Configure logging
logger = logging.getLogger('AuditManager')

class AuditManager:
    """
    Manages the generation and execution of audit commands.
    """

    def __init__(self, config, task_queue):
        """
        Initialize the audit manager.

        Args:
            config (dict): The application configuration
            task_queue: The task queue for executing commands
        """
        self.config = config
        self.task_queue = task_queue
        self.output_dir = os.path.join(os.getcwd(), "output")
        self.current_audit_tasks = []

        # Ensure output directory exists
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def generate_filter_string(self, base_filter, include_disabled):
        """Generate a filter string with the disabled rules logic applied

        Args:
            base_filter (str): The base filter string to start with
            include_disabled (bool): Whether to include disabled rules in the filter

        Returns:
            str: The complete filter string with disabled rules logic applied
        """
        if not base_filter:
            # If there's no base filter, just return the disabled filter if needed
            return "" if include_disabled else "!(rule is.disabled)"

        # If there is a base filter, append the disabled filter if needed
        if include_disabled:
            return base_filter
        else:
            return f"{base_filter} and !(rule is.disabled)"

    def generate_audit_commands(self, panorama, device_group, workbook_name, filter_string, ruletype="Security"):
        """Generate an audit command arguments dictionary and command string with the specified parameters

        Args:
            panorama (str): The Panorama hostname or IP address
            device_group (str): The device group name
            workbook_name (str): The name of the Excel workbook to export to
            filter_string (str): The filter string to apply (without 'filter=' prefix)
            ruletype (str, optional): The rule type to filter on. Defaults to "Security".

        Returns:
            tuple: A tuple containing (cmd_args, cmd_string) where:
                - cmd_args (dict): A dictionary of command arguments
                - cmd_string (str): The full command string
        """
        # Create the command arguments dictionary
        cmd_args = {
            "type": "rule",
            "in": f"api://{panorama}",
            "location": device_group,
            "ruletype": ruletype,
            "actions": f"exporttoexcel:{workbook_name}",
            "filter": f"\"{filter_string}\"",
            "extraArgs": ""  # Initialize extraArgs key
        }

        # Add enabled extra arguments from configuration
        if "extraArguments" in self.config:
            for arg, status in self.config["extraArguments"].items():
                if status == "enabled":
                    cmd_args["extraArgs"] += f"{arg} "  # Add to extraArgs string with space

        # Trim trailing space if any
        cmd_args["extraArgs"] = cmd_args["extraArgs"].strip()

        # Use CommandArgumentHandler to generate the command string
        cmd_string = CommandArgumentHandler.to_command_string(cmd_args)

        return cmd_args, cmd_string

    def generate_workbook_name(self, workbook_name, sect_num=None, sect_name=None, 
                              audit_num=None, audit_name=None, spg_num=None, spg_name=None):
        """
        Generate a workbook name with variables replaced by their values.

        Args:
            workbook_name (str): The template workbook name with variables
            sect_num (str, optional): The section number
            sect_name (str, optional): The section name
            audit_num (str, optional): The audit number
            audit_name (str, optional): The audit name
            spg_num (str, optional): The SPG number
            spg_name (str, optional): The SPG name

        Returns:
            str: The workbook name with variables replaced
        """
        # Replace variables found in the JSON file with values from the actual name/number in the code base
        if sect_num is not None: workbook_name = workbook_name.replace("{sectNum}", str(sect_num))
        if sect_name is not None: workbook_name = workbook_name.replace("{sectName}", str(sect_name))
        if audit_num is not None: workbook_name = workbook_name.replace("{auditNum}", str(audit_num))
        if audit_name is not None: workbook_name = workbook_name.replace("{auditName}", str(audit_name))
        if spg_num is not None: workbook_name = workbook_name.replace("{spgNum}", str(spg_num))
        if spg_name is not None: workbook_name = workbook_name.replace("{spgName}", str(spg_name))
        return workbook_name

    def generate_audits(self, callback=None):
        """
        Generate audit tasks based on configuration.

        Args:
            callback (function, optional): A callback function to be called for each audit task
                The callback should accept the following parameters:
                - section_title (str): The title of the section
                - cmd_string (str): The command string
                - cmd_args (dict): The command arguments
                - audit_id (str): The audit ID
                - metadata (dict): Metadata about the audit

        Returns:
            list: A list of AuditTask objects
        """
        # Get the current Panorama from the configuration
        panorama = self.config["globalConfig"].get("currentPanorama", "")

        if not panorama:
            logger.error("No Panorama instance selected")
            return []

        if panorama not in self.config["Panoramas"]:
            logger.error(f"Selected Panorama instance '{panorama}' not found in configuration")
            return []

        # Get device group from the configuration for the selected Panorama
        device_group = self.config["Panoramas"][panorama]["auditTarget"]

        # Ensure the auditSPGs key exists for this Panorama
        if "auditSPGs" not in self.config["Panoramas"][panorama]:
            self.config["Panoramas"][panorama]["auditSPGs"] = []

        # Get security profile groups from the configuration for the selected Panorama
        spgs = self.config["Panoramas"][panorama]["auditSPGs"]

        # Get the disabled rules setting for this Panorama
        include_disabled = self.config["Panoramas"][panorama].get("includeDisabledRules", False)

        # List to store all generated audit tasks
        audit_tasks = []

        # Clear the current audit tasks list
        self.current_audit_tasks = []

        # Process audits by section
        if "AuditSections" in self.config:
            for section_id, (section_name, section_data) in enumerate(self.config["AuditSections"].items(), start=0):
                # Process audits in this section
                if "sectionAudits" in section_data:
                    for audit_id, (audit_name, audit_data) in enumerate(section_data["sectionAudits"].items(), start=1):
                        # Get audit details from configuration
                        title = audit_data.get("title", audit_name)
                        workbook_name = self.generate_workbook_name(
                            audit_data.get("workbookName", f"{audit_name}.xls"),
                            sect_num=section_id, 
                            sect_name=section_name, 
                            audit_num=audit_id, 
                            audit_name=audit_name
                        )
                        base_filter = audit_data.get("baseFilter", "")

                        # Create filter string
                        filter_string = self.generate_filter_string(base_filter, include_disabled)

                        # Generate the command for this audit
                        cmd_args, cmd_string = self.generate_audit_commands(
                            panorama, 
                            device_group, 
                            workbook_name, 
                            filter_string,
                            audit_data.get("ruletype", "Security")  # Get ruletype from audit data or default to "Security"
                        )

                        # Create metadata dictionary
                        metadata = {
                            'section_number': section_id,
                            'section_name': section_name,
                            'audit_number': audit_id,
                            'audit_name': audit_name
                        }

                        # Create a unique audit ID
                        unique_id = f"section_{section_id}_{audit_name}"

                        # Create an AuditTask object
                        task = AuditTask(unique_id, cmd_args, metadata)
                        audit_tasks.append(task)

                        # Call the callback if provided
                        if callback:
                            section_title = f"Audit {audit_id} ({title})"
                            callback(section_title, cmd_string, cmd_args, unique_id, metadata)

        # Process SPG audits from configuration
        for spg_num, spg in enumerate(spgs, start=1):
            for audit_id, (audit_name, audit_data) in enumerate(self.config["SPG_Audits"].items(), start=1):
                # Get audit details from configuration
                title = audit_data.get("title", audit_name)
                workbook_name = self.generate_workbook_name(
                    audit_data.get("workbookName", f"{audit_name}.xls"),
                    spg_num=spg_num, 
                    spg_name=spg, 
                    audit_num=audit_id, 
                    audit_name=audit_name
                )
                base_filter = f'{audit_data.get("baseFilter", "")} and (secprof group.is {spg})'

                # Create filter string
                filter_string = self.generate_filter_string(base_filter, include_disabled)

                # Generate the command for this audit
                cmd_args, cmd_string = self.generate_audit_commands(
                    panorama, 
                    device_group, 
                    workbook_name, 
                    filter_string,
                    audit_data.get("ruletype", "Security")  # Get ruletype from audit data or default to "Security"
                )

                # Create metadata dictionary
                metadata = {
                    'spg_number': spg_num,
                    'spg_name': spg,
                    'audit_number': audit_id,
                    'audit_name': audit_name
                }

                # Create a unique audit ID
                unique_id = f"{spg}_{audit_name}"

                # Create an AuditTask object
                task = AuditTask(unique_id, cmd_args, metadata)
                audit_tasks.append(task)

                # Call the callback if provided
                if callback:
                    section_title = f"Audit {audit_id} ({title})"
                    callback(section_title, cmd_string, cmd_args, unique_id, metadata)

        # Store the audit tasks for later use
        self.current_audit_tasks = audit_tasks

        return audit_tasks

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
        # Handle single audit case
        if not isinstance(audits, list):
            # Extract parameters from the single audit
            cmd_args = audits.get('cmd_args', {})
            metadata = audits.get('metadata', {})
            audit_id = audits.get('audit_id')

            # Generate a unique ID if not provided
            if audit_id is None:
                # Use timestamp as a unique identifier
                from datetime import datetime
                audit_id = f"audit_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
                logger.debug(f"Generated new audit_id: {audit_id}")

            # Create an AuditTask object with output directory information
            task = AuditTask(
                audit_id=audit_id,
                cmd_args=cmd_args,
                metadata={
                    "log_dir": os.path.join(os.getcwd(), "log"),
                    "output_dir": self.output_dir,
                    **(metadata or {})
                }
            )
            logger.debug(f"Created AuditTask object for audit_id={audit_id}")

            # Convert to a list with a single task
            audit_tasks = [task]
            return_single = True

            # Log the command string
            cmd_string = CommandArgumentHandler.to_command_string(cmd_args)
            logger.debug(f"Command string for audit_id={audit_id}: {cmd_string}")

            # Extract audit name and section number from metadata for logging
            audit_name = metadata.get("audit_name", "Unnamed Audit") if metadata else "Unnamed Audit"
            section_number = metadata.get("section_number", "") if metadata else ""
            logger.info(f"Executing command for audit_id={audit_id}, audit_name={audit_name}, section_number={section_number}")
        else:
            # Multiple audits case
            audit_tasks = audits
            return_single = False

            # Check if we have any tasks
            if not audit_tasks:
                logger.warning("No audit tasks to execute")
                return 0

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
                logger.debug(f"Added task to audit tracker: audit_id={task.audit_id}")

            # Show the audit tracker window
            audit_tracker.show()
            logger.debug("Showing audit tracker window")

        # Submit tasks to the task queue with a small delay between submissions
        # to prevent overwhelming the thread pool and allow the UI to update
        import time
        for i, task in enumerate(audit_tasks):
            self.task_queue.add_task(
                audit_id=task.audit_id,
                cmd_args=task.cmd_args,
                metadata=task.metadata
            )

            # Add a small delay every few tasks to allow the UI to update
            # This helps prevent the app from freezing when executing many tasks
            if i > 0 and i % 3 == 0:
                time.sleep(0.2)  # 200ms delay every 3 tasks

        # Return appropriate value based on input type
        if return_single:
            logger.info(f"Task added to processor: audit_id={audit_tasks[0].audit_id}")
            return audit_tasks[0].audit_id
        else:
            logger.info(f"Submitted {len(audit_tasks)} audit tasks for execution")
            return len(audit_tasks)

    def clear_output_files(self, confirm_callback=None):
        """Clear the output files

        Args:
            confirm_callback (function, optional): A callback function to confirm the operation with the user
                The callback should return True if the user confirms, False otherwise

        Returns:
            tuple: A tuple containing (success, message) where:
                - success (bool): Whether the operation was successful
                - message (str): A message describing the result
        """
        logger.info("clear_output_files called")

        # Confirm with the user if a callback is provided
        if confirm_callback and not confirm_callback("Delete all output files? This cannot be undone."):
            logger.info("User cancelled clear_output_files")
            return False, "Operation cancelled by user"

        # Get the output directory
        output_dir = self.output_dir
        logger.debug(f"Clearing files from output directory: {output_dir}")

        # Delete all files in the output directory
        try:
            file_count = 0
            dir_count = 0
            for filename in os.listdir(output_dir):
                file_path = os.path.join(output_dir, filename)
                if os.path.isfile(file_path):
                    logger.debug(f"Deleting file: {file_path}")
                    os.unlink(file_path)
                    file_count += 1
                elif os.path.isdir(file_path):
                    logger.debug(f"Deleting directory: {file_path}")
                    shutil.rmtree(file_path)
                    dir_count += 1

            logger.info(f"Successfully deleted {file_count} files and {dir_count} directories from output directory")
            return True, f"Successfully deleted {file_count} files and {dir_count} directories"
        except Exception as e:
            logger.error(f"Failed to delete output files: {str(e)}")
            logger.error(traceback.format_exc())
            return False, f"Failed to delete output files: {str(e)}"

    def copy_to_clipboard(self, cmd_args=None, all_tasks=False, clipboard_handler=None):
        """Copy command(s) to the clipboard

        Args:
            cmd_args (dict, optional): The command arguments to copy (if copying a single command)
            all_tasks (bool, optional): Whether to copy all tasks (if True, cmd_args is ignored)
            clipboard_handler (function, optional): A function to handle clipboard operations
                The function should accept a string to copy to the clipboard

        Returns:
            tuple: A tuple containing (success, message) where:
                - success (bool): Whether the operation was successful
                - message (str): A message describing the result
        """
        if not clipboard_handler:
            return False, "No clipboard handler provided"

        try:
            if all_tasks:
                # Copy all commands
                logger.info("Copying all audit commands to clipboard")

                # Get all tasks
                tasks = self.current_audit_tasks if hasattr(self, 'current_audit_tasks') else []

                if not tasks:
                    return False, "No audit tasks available to copy"

                # Build a string with all commands
                cmd_strings = []
                for task in tasks:
                    cmd_handler = CommandArgumentHandler()
                    cmd_string = cmd_handler.to_command_string(task.cmd_args)
                    cmd_strings.append(cmd_string)

                # Join all commands with newlines
                all_commands = "\n".join(cmd_strings)
                logger.debug(f"Total commands copied: {len(cmd_strings)}")

                # Copy to clipboard
                clipboard_handler(all_commands)
                logger.info("All commands copied to clipboard successfully")
                return True, "All commands copied to clipboard"
            else:
                # Copy a single command
                if not cmd_args:
                    return False, "No command arguments provided"

                # Convert the command to a string
                cmd_handler = CommandArgumentHandler()
                cmd_string = cmd_handler.to_command_string(cmd_args)

                # Copy to clipboard
                clipboard_handler(cmd_string)
                logger.info("Command copied to clipboard successfully")
                return True, "Command copied to clipboard"
        except Exception as e:
            logger.error(f"Failed to copy to clipboard: {str(e)}")
            logger.error(traceback.format_exc())
            return False, f"Failed to copy to clipboard: {str(e)}"

    def find_audit_description(self, filename):
        """
        Find the audit description for a filename by extracting the audit name
        and matching it against the audits.json config.

        Args:
            filename (str): The filename without extension

        Returns:
            str: The description of the matching audit, or a default message if not found
        """
        # Default description if no match is found
        description = "Filename did not end with _{auditName} - No description available"

        try:
            # Extract audit name from filename
            if '_' in filename:
                # Split at underscore and take the last part (the audit name)
                audit_name = filename.split('_')[-1]

                # Search for matching audit in AuditSections
                for section_data in self.config["AuditSections"].values():
                    if "sectionAudits" in section_data:
                        for audit_key, audit_data in section_data["sectionAudits"].items():
                            # Check if audit key matches the extracted name
                            if audit_key == audit_name:
                                return audit_data.get("description", description)

                # If not found in AuditSections, check SPG_Audits
                for audit_key, audit_data in self.config["SPG_Audits"].items():
                    # Extract the audit name part from SPG audit key
                    spg_audit_name = audit_key.split('_')[-1]
                    if spg_audit_name == audit_name:
                        return audit_data.get("description", description)
        except Exception as e:
            logger.debug(f"Error finding description for {filename}: {str(e)}")

        return description

    def analyze_output(self, progress_callback=None, cancel_check=None):
        """
        Analyze the output files and create a consolidated Excel workbook.

        Args:
            progress_callback (function, optional): A callback function to be called with progress updates
                The callback should accept the following parameters:
                - file_path (str): The path to the file being processed
                - success (bool): Whether the file was processed successfully
            cancel_check (function, optional): A function that returns True if the operation should be cancelled

        Returns:
            tuple: A tuple containing (success, message, output_file) where:
                - success (bool): Whether the analysis was successful
                - message (str): A message describing the result
                - output_file (str): The path to the output file if successful, None otherwise
        """
        # Scan the output directory for files
        output_files = []
        if os.path.exists(self.output_dir):
            for file in os.listdir(self.output_dir):
                if file.endswith('.xls'):
                    output_files.append(os.path.join(self.output_dir, file))

        if not output_files:
            return False, "No output files available for analysis", None

        try:
            # Import necessary libraries for HTML/XML parsing and Excel creation
            from bs4 import BeautifulSoup
            import pandas as pd
            from io import StringIO

            # Create a default output file name
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            excel_file = os.path.join(self.output_dir, f"consolidated_output_{timestamp}.xlsx")

            # First pass: collect rule counts and identify "all rules" reports
            rule_counts = {}
            all_rules_count = 0
            spg_all_rules_counts = {}  # Dictionary to store SPG-specific "all rules" counts

            for file_path in output_files:
                # Check if the operation was cancelled
                if cancel_check and cancel_check():
                    return False, "Analysis was cancelled", None

                try:
                    # Get the filename without extension
                    filename = os.path.basename(file_path).replace('.xls', '')

                    # Read the HTML file
                    with open(file_path, 'r', encoding='utf-8') as file:
                        content = file.read()

                    # Parse the HTML content
                    soup = BeautifulSoup(content, 'html.parser')

                    # Find all tables in the document
                    tables = soup.find_all('table')

                    if not tables:
                        continue

                    # For each table in the file, count the rows (excluding header)
                    for table in tables:
                        # Convert HTML table to DataFrame
                        df = pd.read_html(StringIO(str(table)))[0]

                        # Store the row count (excluding header)
                        row_count = len(df) - 1 if len(df) > 0 else 0
                        rule_counts[filename] = row_count

                        # Check if this is the main "All Rules" report
                        if filename == "S0A1_AllRules":
                            all_rules_count = row_count

                        # Check if this is an SPG-specific "All Rules" report
                        elif filename.startswith("spg") and "AllRules" in filename:
                            # Extract SPG number from filename (e.g., "spg1A1_AllRules" -> "1")
                            spg_num = filename.split("spg")[1].split("A")[0]
                            spg_all_rules_counts[spg_num] = row_count

                except Exception as e:
                    logger.error(f"Error processing file {file_path} during rule counting: {str(e)}")
                    continue

            # Create a Pandas Excel writer using XlsxWriter as the engine
            with pd.ExcelWriter(excel_file, engine='xlsxwriter') as writer:
                # Create summary data
                summary_data = []

                for filename, count in rule_counts.items():
                    # Determine which "all rules" count to use for percentage calculation
                    denominator = all_rules_count
                    percentage = 0

                    # If this is an SPG-specific report, use the corresponding SPG "all rules" count
                    if filename.startswith("spg"):
                        spg_num = filename.split("spg")[1].split("A")[0]
                        if spg_num in spg_all_rules_counts:
                            denominator = spg_all_rules_counts[spg_num]

                    # Calculate percentage if denominator is not zero
                    if denominator > 0:
                        percentage = (count / denominator) * 100

                    # Find the audit description
                    description = self.find_audit_description(filename)

                    # Add to summary data
                    summary_data.append({
                        "Workbook": filename,
                        "Rule Count": count,
                        "Percentage": f"{percentage:.4f}%",
                        "Description": description
                    })

                # Create summary DataFrame and sort it
                summary_df = pd.DataFrame(summary_data)

                # Sort by workbook name to group related audits together
                summary_df = summary_df.sort_values("Workbook")

                # Write summary to the first worksheet
                summary_df.to_excel(writer, sheet_name="Summary", index=False)

                # Get the xlsxwriter workbook and worksheet objects for the summary
                workbook = writer.book
                worksheet = writer.sheets["Summary"]

                # Set column widths for summary
                worksheet.set_column(0, 0, 30)  # Workbook column
                worksheet.set_column(1, 1, 15)  # Rule Count column
                worksheet.set_column(2, 2, 15)  # Percentage column
                worksheet.set_column(3, 3, 50)  # Description column

                # Add a header format
                header_format = workbook.add_format({
                    'bold': True,
                    'text_wrap': True,
                    'valign': 'top',
                    'border': 1
                })

                # Write the column headers with the header format
                for col_num, value in enumerate(summary_df.columns.values):
                    worksheet.write(0, col_num, value, header_format)

                # Process each output file for detailed worksheets
                for file_path in output_files:
                    # Check if the operation was cancelled
                    if cancel_check and cancel_check():
                        return False, "Analysis was cancelled", None

                    try:
                        # Read the HTML file
                        with open(file_path, 'r', encoding='utf-8') as file:
                            content = file.read()

                        # Parse the HTML content
                        soup = BeautifulSoup(content, 'html.parser')

                        # Find all tables in the document
                        tables = soup.find_all('table')

                        if not tables:
                            if progress_callback:
                                progress_callback(file_path, False)
                            continue

                        # Use the filename (without extension) as sheet name
                        sheet_name = os.path.basename(file_path).replace('.xls', '')

                        # Excel worksheet names have a 31 character limit
                        if len(sheet_name) > 31:
                            sheet_name = sheet_name[:31]

                        # For each table in the file, create a DataFrame and write to Excel
                        for i, table in enumerate(tables):
                            # Convert HTML table to DataFrame
                            df = pd.read_html(StringIO(str(table)))[0]

                            # If there are multiple tables, add table number to sheet name
                            if i == 0:
                                current_sheet_name = sheet_name
                            else:
                                # Ensure the sheet name with suffix is within 31 characters
                                base_name = sheet_name[:27] if len(sheet_name) > 27 else sheet_name
                                current_sheet_name = f"{base_name}_{i+1}"

                            # Write DataFrame to Excel worksheet
                            df.to_excel(writer, sheet_name=current_sheet_name, index=False)

                            # Get the xlsxwriter workbook and worksheet objects
                            worksheet = writer.sheets[current_sheet_name]

                            # Set column widths based on content
                            for j, col in enumerate(df.columns):
                                # Find the maximum length in the column
                                max_len = max(
                                    df[col].astype(str).map(len).max(),  # max length of values
                                    len(str(col))  # length of column name
                                ) + 2  # add a little extra space

                                # Set the column width
                                worksheet.set_column(j, j, max_len)

                        # Update progress
                        if progress_callback:
                            progress_callback(file_path, True)

                    except Exception as e:
                        logger.error(f"Error processing file {file_path}: {str(e)}")
                        if progress_callback:
                            progress_callback(file_path, False)
                        continue

            return True, f"Analysis completed successfully. Output saved to {excel_file}", excel_file

        except ImportError as e:
            error_message = "Required libraries not found. Please install the following packages:\n"
            error_message += "- pandas (pip install pandas)\n"
            error_message += "- beautifulsoup4 (pip install beautifulsoup4)\n"
            error_message += f"\nError details: {str(e)}"
            return False, error_message, None

        except Exception as e:
            logger.error(f"Error in analyze_output: {str(e)}")
            return False, f"Failed to analyze output files: {str(e)}", None
