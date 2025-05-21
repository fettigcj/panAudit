# PAN-OS Audit - Rules Auditor

A Python GUI application for generating PAN-OS-PHP commands to audit security policies and report non-compliant policies


## Overview

This application allows network administrators to:

1. Populate and select from a list of Panorama to be audited
1. Specify a device group to audit (default is "any" to audit entire Panorama portfolio)
1. Choose whether to include disabled rules in the audit (Default: No)
1. View and manage audit suite either within the GUI or in audits.json 
1. Generate CLI commands based on those audits, which can be executed locally or copied to clipboard and executed independently
1. If audit commands are executed directly from the application post-audit analysis report will also be generated

## Components

The application consists of several key components:

1. **Main GUI Application** (`pan_audit_gui.py`): The primary interface for interacting with the application
2. **Audit Modification Window** (`modify_audits_window.py`): Allows customization of audit commands and filters
3. **Task Queue** (`task_queue.py`): Manages the execution of audit commands in a thread pool
4. **Repository Downloader** (`repo_downloader.py`): Downloads the required PAN-OS-PHP repository
5. **Executable Creation** (`make_executable.py`): Creates a standalone executable version of the application

## Requirements

- Python 3.6 or higher
- Tkinter (included with most Python installations)
- Git (optional, falls back to direct download if not available)
- PHP (required for executing audit commands)

## Installation

1. Ensure Python is installed on your system
2. Clone or download this repository
3. Run the application:
   ```
   python pan_audit_gui.py
   ```
4. The application will automatically download the required PAN-OS-PHP repository if it's not already present

## Documentation

For more detailed information about specific components, please refer to:

- [GUI Documentation](README_GUI.md): Detailed information about the GUI application and its features
- [Executable Documentation](README_EXECUTABLE.md): Instructions for creating a standalone executable version of the application

## Repository Downloader

The application includes a module to download the source code from the [pan-os-php](https://github.com/swaschkut/pan-os-php) GitHub repository:

- Downloads the pan-os-php repository to a local directory
- Provides two download methods:
  - Primary: Uses Git to clone the repository (requires Git to be installed)
  - Fallback: Downloads the repository as a ZIP file using Python's requests library (when Git is not available)

You can also use this module directly:

```python
from src.utils.repo_downloader import download_repository

# Download the repository
success = download_repository(
    "https://github.com/swaschkut/pan-os-php",
    "panPHP"
)
```

## Task Queue

The application includes a task queue system that:

- Manages a queue of audit tasks to be executed
- Executes tasks in separate threads for improved performance
- Provides status updates via callbacks
- Supports configurable number of worker threads
- Has an option to use separate windows for task execution

## Customization

The application allows customization of:

- Main configuration menu:
  - Panorama / Device Group to be audited
    - Add Panorama by IP or FQDN, select from drop list after added
    - Limit audits to specific device group by typing DG (Location in pan-os-php) name 
    - Include disabled rules in audits / reports
    - Add relevant Security Profile Groups for SPG specific audits
  - Limit number of threads if executing audits locally
  - Enable/Disable various "shadow" options to control pan-os-php behavior
    - Script will adapt to additions/removal of shadow arguments in JSON if needed

- Audit commands and filters
  - Add/Remove sections to group audits topoically
  - Specify a workbookname for the XLS output files of each audit
    - use variables in workbook name to generate dynamic names to match audit framework as desired
    - (Use "Name" variables sparingly unless extremely long workbook names are desired)
      - {sectNum}, {sectName}, {auditNum}, {auditName}, {spgNum}, {spgName}
  - Set the 'baseFilter' according to desired pan-os-php available filters for each audit
    - Use parenthesis to make filter criteria groups more obvious
    - Use ! to negate a filter / parenthesis-enclosed filter group

## License

This project is open-source, copyleft rights are granted as specified by GPL 3.0
