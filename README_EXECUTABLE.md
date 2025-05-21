# Creating a Standalone Executable

This document explains how to create a standalone executable for the Panorama Security Profile Group Auditor GUI application.

## Overview

The Panorama Security Profile Group Auditor GUI application can be packaged into a standalone executable that can run without requiring Python to be installed on the target machine. This is useful for distributing the application to users who don't have Python installed or who prefer not to install it.

## Requirements

- Python 3.6 or higher
- Internet connection (to download PyInstaller if it's not already installed)

## Creating the Executable

There are three ways to create the executable:

### Method 1: All-in-One (Create and Test) - Windows

1. Open a Command Prompt window
2. Navigate to the directory containing the application files
3. Run the batch file:
   ```
   create_and_test_executable.bat
   ```
4. Wait for the process to complete
5. Follow the prompts to verify the application is working correctly
6. The executable will be created in the `dist` directory

### Method 2: Using the Batch File (Windows)

1. Open a Command Prompt window
2. Navigate to the directory containing the application files
3. Run the batch file:
   ```
   make_executable.bat
   ```
4. Wait for the process to complete
5. The executable will be created in the `dist` directory

### Method 3: Using the Python Script

1. Open a Command Prompt or Terminal window
2. Navigate to the directory containing the application files
3. Run the Python script:
   ```
   python make_executable.py
   ```
4. Wait for the process to complete
5. The executable will be created in the `dist` directory

## What the Scripts Do

The scripts perform the following actions:

1. Check if PyInstaller is installed, and install it if it's not
2. Create a standalone executable using PyInstaller
3. Copy the necessary files to the `dist` directory
4. Clean up temporary files created during the packaging process

## Using the Executable

To use the executable:

1. Copy the entire `dist` directory to the target machine
2. Run `PanoramaAuditor.exe` from the `dist` directory
3. If the panPHP directory is not included, you'll need to download it separately using the `repo_downloader.py` script or by cloning the repository manually

## Testing the Executable

After creating the executable, you can test it to ensure it works correctly:

### Method 1: Using the Batch File (Windows)

1. Open a Command Prompt window
2. Navigate to the directory containing the application files
3. Run the batch file:
   ```
   test_executable.bat
   ```
4. Follow the prompts to verify the application is working correctly

### Method 2: Using the Python Script

1. Open a Command Prompt or Terminal window
2. Navigate to the directory containing the application files
3. Run the Python script:
   ```
   python test_executable.py
   ```
4. Follow the prompts to verify the application is working correctly

## Troubleshooting

If you encounter issues with the executable:

1. Make sure all required files are in the correct locations
2. Check that PHP is installed on the target machine (required for executing commands)
3. If the application fails to start, try running it from a Command Prompt to see any error messages:
   ```
   cd path\to\dist
   PanoramaAuditor.exe
   ```

## Customizing the Executable

If you want to customize the executable (e.g., add an icon, change the name), you can modify the `make_executable.py` script. Look for the `pyinstaller_cmd` variable and adjust the parameters as needed.
