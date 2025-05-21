"""
Repository Downloader Module

This module provides functionality to download source code from a GitHub repository
and store it locally, as well as update existing repositories.

Usage:
    python repo_downloader.py
"""

import os
import subprocess
import sys
import shutil
import tempfile
import zipfile
import json
from pathlib import Path
import requests
import logging

# Configure logging
logger = logging.getLogger(__name__)


def download_repository(repo_url, target_dir):
    """
    Downloads a repository from the given URL and stores it in the target directory.

    Args:
        repo_url (str): The URL of the repository to download
        target_dir (str): The local directory where the repository should be stored

    Returns:
        bool: True if successful, False otherwise
    """
    target_path = Path(target_dir)

    # Create the target directory if it doesn't exist
    if not target_path.exists():
        try:
            target_path.mkdir(parents=True)
            print(f"Created directory: {target_dir}")
        except Exception as e:
            print(f"Error creating directory {target_dir}: {e}")
            return False

    # Check if the directory is empty
    if any(target_path.iterdir()):
        print(f"Warning: Target directory {target_dir} is not empty.")
        user_input = input("Do you want to clear the directory before downloading? (y/n): ")
        if user_input.lower() == 'y':
            try:
                # Remove all contents of the directory
                for item in target_path.iterdir():
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()
                print(f"Cleared directory: {target_dir}")
            except Exception as e:
                print(f"Error clearing directory {target_dir}: {e}")
                return False

    # Try to use git to clone the repository
    try:
        print(f"Downloading repository from {repo_url}...")
        result = subprocess.run(
            ["git", "clone", repo_url, target_dir],
            check=True,
            capture_output=True,
            text=True
        )
        print("Repository downloaded successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error executing git command: {e}")
        print(f"Output: {e.stdout}")
        print(f"Error: {e.stderr}")
        return False
    except FileNotFoundError:
        print("Git command not found. Falling back to direct download method...")
        return download_repository_fallback(repo_url, target_dir)


def download_repository_fallback(repo_url, target_dir):
    """
    Alternative method to download a repository when git is not available.
    Downloads the repository as a zip file and extracts it to the target directory.

    Args:
        repo_url (str): The URL of the repository to download
        target_dir (str): The local directory where the repository should be stored

    Returns:
        bool: True if successful, False otherwise
    """
    # Convert GitHub URL to zip download URL
    if "github.com" in repo_url:
        # Extract username and repository name from URL
        parts = repo_url.rstrip('/').split('/')
        if len(parts) >= 5:  # https://github.com/username/repo
            username = parts[-2]
            repo_name = parts[-1]
            zip_url = f"https://github.com/{username}/{repo_name}/archive/refs/heads/master.zip"
        else:
            print(f"Invalid GitHub URL format: {repo_url}")
            return False
    else:
        print(f"Only GitHub repositories are supported for direct download: {repo_url}")
        return False

    try:
        # Create a temporary directory to store the zip file
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = os.path.join(temp_dir, "repo.zip")

            # Download the zip file
            print(f"Downloading repository as zip from {zip_url}...")
            response = requests.get(zip_url, stream=True)

            # Check if the request was successful
            if response.status_code != 200:
                # Try with 'main' branch if 'master' fails
                zip_url = zip_url.replace('/master.zip', '/main.zip')
                print(f"Master branch not found, trying main branch: {zip_url}")
                response = requests.get(zip_url, stream=True)

                if response.status_code != 200:
                    print(f"Failed to download repository. Status code: {response.status_code}")
                    return False

            # Save the zip file
            with open(zip_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            # Extract the zip file
            print("Extracting repository...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # Get the name of the root directory in the zip file
                root_dir = zip_ref.namelist()[0].split('/')[0]

                # Extract to temporary directory first
                zip_ref.extractall(temp_dir)

                # Move contents from the extracted directory to the target directory
                extracted_dir = os.path.join(temp_dir, root_dir)

                # Copy all contents to the target directory
                shutil.copytree(extracted_dir, target_dir, dirs_exist_ok=True)

        print("Repository downloaded and extracted successfully!")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error downloading repository: {e}")
        return False
    except zipfile.BadZipFile:
        print("Error: Downloaded file is not a valid zip file.")
        return False
    except Exception as e:
        print(f"Unexpected error during download: {e}")
        return False


def update_repository(repo_url, target_dir, message_callback=None):
    """
    Updates an existing repository using git pull or downloads it if it doesn't exist.

    Args:
        repo_url (str): The URL of the repository to update
        target_dir (str): The local directory where the repository is stored
        message_callback (callable, optional): A callback function to handle messages
            The function should accept a string message and a boolean success flag

    Returns:
        bool: True if successful, False otherwise
    """
    target_path = Path(target_dir)

    # Helper function to log and call the message callback if provided
    def log_message(message, success=True):
        if success:
            logger.info(message)
        else:
            logger.error(message)
        if message_callback:
            message_callback(message, success)
        else:
            print(message)

    # Check if the target directory exists
    if not target_path.exists():
        log_message(f"Target directory {target_dir} does not exist. Downloading repository...", True)
        return download_repository(repo_url, target_dir)

    # Check if the target directory is a git repository
    git_dir = target_path / ".git"
    if not git_dir.exists():
        log_message(f"Target directory {target_dir} is not a git repository. Downloading repository...", True)
        return download_repository(repo_url, target_dir)

    # Try to use git to pull the repository
    try:
        log_message(f"Updating repository in {target_dir}...", True)

        # Change to the target directory
        original_dir = os.getcwd()
        os.chdir(target_dir)

        try:
            # Run git pull
            result = subprocess.run(
                ["git", "pull"],
                check=True,
                capture_output=True,
                text=True
            )

            # Check the output to determine if changes were made
            if "Already up to date" in result.stdout:
                log_message("Repository is already up to date.", True)
            else:
                log_message("Repository updated successfully!", True)

            return True
        finally:
            # Change back to the original directory
            os.chdir(original_dir)
    except subprocess.CalledProcessError as e:
        log_message(f"Error executing git pull command: {e}", False)
        log_message(f"Output: {e.stdout}", False)
        log_message(f"Error: {e.stderr}", False)
        return False
    except FileNotFoundError:
        log_message("Git command not found. Cannot update repository.", False)
        return False
    except Exception as e:
        log_message(f"Unexpected error during repository update: {e}", False)
        return False


def get_repo_url_from_config():
    """
    Attempts to read the repository URL from the config file.

    Returns:
        str: The repository URL from the config file, or the default URL if not found
    """
    default_url = "https://github.com/swaschkut/pan-os-php"

    try:
        # Try to find and load the config file
        config_path = os.path.join(os.getcwd(), "config", "panAudit.json")
        if not os.path.exists(config_path):
            # Try relative path if running from utils directory
            config_path = os.path.join(os.getcwd(), "..", "..", "config", "panAudit.json")

        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = json.loads(f.read())
                # Get the repo URL from the config
                if "globalConfig" in config and "panOsPhpRepoUrl" in config["globalConfig"]:
                    return config["globalConfig"]["panOsPhpRepoUrl"]
    except Exception as e:
        logger.error(f"Error reading config file: {e}")

    # Return default URL if config file not found or error occurred
    return default_url

if __name__ == "__main__":
    # Repository URL and target directory
    REPO_URL = get_repo_url_from_config()
    TARGET_DIR = "../../panPHP"

    # Check if the user wants to update or download
    if len(sys.argv) > 1 and sys.argv[1] == "update":
        # Update the repository
        success = update_repository(REPO_URL, TARGET_DIR)

        if success:
            print(f"Repository has been updated in {TARGET_DIR}")
            sys.exit(0)
        else:
            print("Failed to update the repository.")
            sys.exit(1)
    else:
        # Download the repository
        success = download_repository(REPO_URL, TARGET_DIR)

        if success:
            print(f"Repository has been downloaded to {TARGET_DIR}")
            sys.exit(0)
        else:
            print("Failed to download the repository.")
            sys.exit(1)
