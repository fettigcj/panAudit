import tkinter as tk
import logging
import os
from datetime import datetime
from src.core.application import PanAuditApplication
from src.gui.main_window import PanoramaAuditGUI

# Configure logging
try:
    # Ensure log directory exists
    log_dir = os.path.join(os.getcwd(), "log")
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Ensure the log file can be written to
    log_file_path = os.path.join(log_dir, 'panaudit.log')
    with open(log_file_path, 'a') as f:
        f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Logging initialized\n")

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        filename=log_file_path,
        filemode='a'
    )
    logger = logging.getLogger('PanAuditGUI')
    logger.info("Logging system initialized successfully")

    # Redirect warnings to the logging system
    import warnings
    logging.captureWarnings(True)
except Exception as e:
    print(f"Error setting up logging: {str(e)}")
    # Set up a console logger as fallback
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger('PanAuditGUI')
    logger.error(f"Failed to set up file logging: {str(e)}")
    logger.error("Logging to console instead")

    # Redirect warnings to the logging system (fallback)
    import warnings
    logging.captureWarnings(True)

def main():
    """Main entry point for the application"""
    try:
        # Initialize the core application
        core_app = PanAuditApplication()

        # Create the root window
        root = tk.Tk()

        # Create the main application window, passing the core app
        app = PanoramaAuditGUI(root, core_app)

        # Start the main event loop
        root.mainloop()
    except Exception as e:
        logger.error(f"Error in main application: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise

if __name__ == "__main__":
    main()
