"""
Command Handler Module

This module provides utilities for handling command arguments and formatting them
for use with the PAN-OS-PHP command line interface.
"""

import logging

# Configure logging
logger = logging.getLogger('CommandHandler')

class CommandArgumentHandler:
    """
    A utility class for handling command arguments and formatting them
    for use with the PAN-OS-PHP command line interface.

    This class centralizes the command argument handling logic that was previously
    duplicated across multiple methods in the application.
    """

    @staticmethod
    def format_command_args(cmd_args):
        """
        Convert command arguments dictionary to formatted string parts

        Args:
            cmd_args (dict): A dictionary of command arguments

        Returns:
            list: A list of formatted command argument strings
        """
        command_parts = []
        for key, value in cmd_args.items():
            if key == "extraArgs":
                # Handle extraArgs separately
                if value:
                    # Add each extra argument as a separate part
                    for arg in value.split():
                        command_parts.append(arg)
            elif value:  # Only include non-empty values
                if key == "filter":
                    # Wrap filter value in quotes
                    command_parts.append(f"'{key}={value}'")
                else:
                    command_parts.append(f"{key}={value}")
        return command_parts

    @staticmethod
    def to_command_string(cmd_args):
        """
        Convert command arguments to a full command string

        Args:
            cmd_args (dict): A dictionary of command arguments

        Returns:
            str: A formatted command string
        """
        command_parts = CommandArgumentHandler.format_command_args(cmd_args)
        return "php pan-os-php.php " + " ".join(command_parts)


    @staticmethod
    def to_php_args(cmd_args):
        """
        Convert command arguments to a list of arguments for subprocess

        Args:
            cmd_args (dict): A dictionary of command arguments

        Returns:
            list: A list of command arguments for subprocess
        """
        php_args = ["php", "pan-os-php.php"]

        # Add each argument from the cmd_args dictionary
        for key, value in cmd_args.items():
            if key == "extraArgs":
                # Handle extraArgs separately
                if value:
                    # Add each extra argument as a separate part
                    for arg in value.split():
                        php_args.append(arg)
            elif value:  # Only include non-empty values
                if key == "filter":
                    # Wrap filter value in quotes
                    php_args.append(f"filter={value}")
                else:
                    php_args.append(f"{key}={value}")

        return php_args

class AuditTask:
    """
    Represents an audit task with all necessary information

    This class standardizes the data structure for passing audit task information
    between components of the application.
    """

    def __init__(self, audit_id, cmd_args, metadata=None):
        """
        Initialize an audit task

        Args:
            audit_id (str): A unique identifier for the audit task
            cmd_args (dict): A dictionary of command arguments
            metadata (dict, optional): A dictionary containing metadata about the audit:
                - section_number (str, optional): The section number
                - section_name (str, optional): The section name
                - audit_number (str, optional): The audit number
                - audit_name (str, optional): The audit name
                - spg_number (str, optional): The SPG number
                - spg_name (str, optional): The SPG name
        """
        self.audit_id = audit_id
        self.cmd_args = cmd_args
        self.metadata = metadata or {}
        self.timestamp = None  # Will be set when the task is submitted
        self.status = "Pending"
        self.result = None
        self.log_file = None
        self.err_file = None
