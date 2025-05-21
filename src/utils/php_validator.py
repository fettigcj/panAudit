"""
PHP Validator Module

This module provides functionality to validate PHP installation by executing
the 'php -i' command and checking the result.

It also provides functionality to validate the pan-os-php installation by executing
the 'php pan-os-php.php version' command and checking the result.
"""

import subprocess
import tkinter as tk
import os
from tkinter import messagebox

def validate_php():
    """
    Validates PHP installation by executing the 'php -i' command.

    Returns:
        bool: True if PHP is installed and working, False otherwise
    """
    try:
        # Execute the 'php -i' command
        result = subprocess.run(
            ["php", "-i"],
            check=True,
            capture_output=True,
            text=True
        )

        # Check if the output contains PHP information
        if "PHP Version" in result.stdout:
            return True
        else:
            return False
    except subprocess.CalledProcessError as e:
        print(f"Error executing PHP command: {e}")
        print(f"Output: {e.stdout}")
        print(f"Error: {e.stderr}")
        return False
    except FileNotFoundError:
        print("PHP command not found.")
        return False

def validate_php_with_message(parent_window=None):
    """
    Validates PHP installation and displays a message box with the result.

    Args:
        parent_window (tk.Tk, optional): The parent window for the message box

    Returns:
        bool: True if PHP is installed and working, False otherwise
    """
    is_valid = validate_php()

    if is_valid:
        messagebox.showinfo("PHP Validation", "PHP is installed and working correctly!")
    else:
        messagebox.showerror("PHP Validation", "PHP not found. Please install PHP to continue.")

    return is_valid

def validate_pan_os_php():
    """
    Validates pan-os-php installation by executing the 'php pan-os-php.php version' command.

    Returns:
        tuple: (is_valid, version_info) where:
            - is_valid (bool): True if pan-os-php is installed and working, False otherwise
            - version_info (dict): A dictionary containing version information:
                - pan_os_php_version: The pan-os-php version
                - utils_folder: The utils folder path
                - php_version: The PHP version
    """
    try:
        # Get the utils directory path
        app_dir = os.getcwd()
        utils_dir = os.path.join(app_dir, "panPHP", "utils")
        php_script_path = os.path.join(utils_dir, "pan-os-php.php")

        # Execute the 'php pan-os-php.php version' command
        result = subprocess.run(
            ["php", php_script_path, "version"],
            check=True,
            capture_output=True,
            text=True
        )

        # Initialize version info dictionary
        version_info = {
            "pan_os_php_version": "Unknown",
            "utils_folder": utils_dir,
            "php_version": "Unknown"
        }

        # Parse the output to extract version information
        output_lines = result.stdout.splitlines()
        for line in output_lines:
            if "PAN-OS-PHP version:" in line:
                version_info["pan_os_php_version"] = line.split(":", 1)[1].strip() if ":" in line else "Unknown"
            elif "PHP version" in line:
                version_info["php_version"] = line.split(":", 1)[1].strip() if ":" in line else "Unknown"

        return True, version_info
    except subprocess.CalledProcessError as e:
        print(f"Error executing pan-os-php command: {e}")
        print(f"Output: {e.stdout}")
        print(f"Error: {e.stderr}")
        return False, {}
    except FileNotFoundError:
        print("PHP command or pan-os-php.php script not found.")
        return False, {}
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False, {}

def validate_pan_os_php_with_message(parent_window=None):
    """
    Validates pan-os-php installation and displays a message box with the result.

    Args:
        parent_window (tk.Tk, optional): The parent window for the message box

    Returns:
        bool: True if pan-os-php is installed and working, False otherwise
    """
    is_valid, version_info = validate_pan_os_php()

    if is_valid:
        message = f"pan-os-php is installed and working correctly!\n\n"
        message += f"pan-os-php version: {version_info.get('pan_os_php_version', 'Unknown')}\n"
        message += f"utils folder: {version_info.get('utils_folder', 'Unknown')}\n"
        message += f"PHP version: {version_info.get('php_version', 'Unknown')}"
        messagebox.showinfo("pan-os-php Validation", message)
    else:
        messagebox.showerror("pan-os-php Validation", "pan-os-php not found or not working correctly. Please check your installation.")

    return is_valid

if __name__ == "__main__":
    # Test the validation functions
    root = tk.Tk()
    root.withdraw()  # Hide the root window

    php_result = validate_php_with_message(root)
    print(f"PHP validation result: {php_result}")

    pan_os_php_result = validate_pan_os_php_with_message(root)
    print(f"pan-os-php validation result: {pan_os_php_result}")

    root.destroy()
