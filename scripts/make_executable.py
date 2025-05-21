"""
Make Executable Script

This script packages the Panorama Security Profile Group Auditor GUI application
into a standalone executable using PyInstaller.

Usage:
    python make_executable.py
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def check_pyinstaller():
    """
    Check if PyInstaller is installed, and install it if it's not.

    Returns:
        bool: True if PyInstaller is installed or was successfully installed, False otherwise
    """
    try:
        # Try to import PyInstaller
        import PyInstaller
        print("PyInstaller is already installed.")
        return True
    except ImportError:
        print("PyInstaller is not installed. Installing...")
        try:
            # Install PyInstaller using pip
            subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
            print("PyInstaller installed successfully.")
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error installing PyInstaller: {e}")
            return False

def create_executable():
    """
    Create a standalone executable of the Panorama Security Profile Group Auditor GUI application.

    Returns:
        bool: True if the executable was created successfully, False otherwise
    """
    try:
        print("Creating executable...")

        # Define the PyInstaller command
        pyinstaller_cmd = [
            sys.executable, 
            "-m", 
            "PyInstaller",
            "--name=PanoramaAuditor",
            "--onefile",  # Create a single executable file
            "--windowed",  # Don't show the console window when running the app
            "--add-data", f"config{os.pathsep}config",  # Include the configuration directory
            "--add-data", f"src{os.pathsep}src",  # Include the source code directory
            "--icon=NONE",  # No icon for now, can be customized later
            "pan_audit_gui.py"  # The main script to package
        ]

        # Convert paths to use backslashes on Windows
        if os.name == 'nt':
            pyinstaller_cmd[9] = f"config{os.pathsep}config".replace('/', '\\')
            pyinstaller_cmd[11] = f"src{os.pathsep}src".replace('/', '\\')

        # Run PyInstaller
        subprocess.run(pyinstaller_cmd, check=True)

        print("Executable created successfully.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error creating executable: {e}")
        return False

def copy_additional_files():
    """
    Copy any additional files needed by the executable.

    Returns:
        bool: True if all files were copied successfully, False otherwise
    """
    try:
        print("Copying additional files...")

        # Create the dist/panPHP directory if it doesn't exist
        dist_panphp_dir = Path("dist/panPHP")
        if not dist_panphp_dir.exists():
            dist_panphp_dir.mkdir(parents=True)
            print(f"Created directory: {dist_panphp_dir}")

        # Create the dist/log directory if it doesn't exist
        dist_log_dir = Path("dist/log")
        if not dist_log_dir.exists():
            dist_log_dir.mkdir(parents=True)
            print(f"Created directory: {dist_log_dir}")

        # Create the dist/output directory if it doesn't exist
        dist_output_dir = Path("dist/output")
        if not dist_output_dir.exists():
            dist_output_dir.mkdir(parents=True)
            print(f"Created directory: {dist_output_dir}")

        # Copy the panPHP directory if it exists
        panphp_dir = Path("panPHP")
        if panphp_dir.exists() and panphp_dir.is_dir():
            # Use shutil.copytree with dirs_exist_ok=True for Python 3.8+
            # For earlier versions, we would need to remove the directory first
            try:
                shutil.copytree(panphp_dir, dist_panphp_dir, dirs_exist_ok=True)
            except TypeError:
                # For Python < 3.8
                if dist_panphp_dir.exists():
                    shutil.rmtree(dist_panphp_dir)
                shutil.copytree(panphp_dir, dist_panphp_dir)
            print(f"Copied {panphp_dir} to {dist_panphp_dir}")
        else:
            print(f"Warning: {panphp_dir} does not exist or is not a directory.")
            print("The executable will still work, but you'll need to download the PAN-OS-PHP repository separately.")

        print("Additional files copied successfully.")
        return True
    except Exception as e:
        print(f"Error copying additional files: {e}")
        return False

def cleanup():
    """
    Clean up temporary files created during the packaging process.
    """
    try:
        print("Cleaning up temporary files...")

        # Remove the build directory
        build_dir = Path("build")
        if build_dir.exists():
            shutil.rmtree(build_dir)
            print(f"Removed {build_dir}")

        # Remove the .spec file
        spec_file = Path("PanoramaAuditor.spec")
        if spec_file.exists():
            spec_file.unlink()
            print(f"Removed {spec_file}")

        print("Cleanup completed successfully.")
    except Exception as e:
        print(f"Error during cleanup: {e}")

def main():
    """
    Main function to create the executable.
    """
    print("Starting the packaging process...")

    # Check if PyInstaller is installed
    if not check_pyinstaller():
        print("Failed to install PyInstaller. Exiting.")
        return 1

    # Create the executable
    if not create_executable():
        print("Failed to create the executable. Exiting.")
        return 1

    # Copy additional files
    if not copy_additional_files():
        print("Failed to copy additional files. The executable may not work correctly.")

    # Clean up temporary files
    cleanup()

    print("\nPackaging completed successfully!")
    print("\nThe executable is located in the 'dist' directory.")
    print("To use the executable:")
    print("1. Copy the entire 'dist' directory to the target machine")
    print("2. Run 'PanoramaAuditor.exe' from the 'dist' directory")
    print("3. If the panPHP directory is not included, you'll need to download it separately")
    print("   using the repo_downloader.py script or by cloning the repository manually.")

    return 0

if __name__ == "__main__":
    sys.exit(main())
