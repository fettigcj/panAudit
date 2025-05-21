import tkinter as tk
from tkinter import ttk, messagebox
import os
import logging
import traceback

from src.core.command_handler import CommandArgumentHandler

# Configure logging
logger = logging.getLogger(__name__)

class AuditWindow:
    """A window for displaying and executing audit commands"""

    def __init__(self, parent, main_window):
        """Initialize the audit window

        Args:
            parent: The parent widget
            main_window: The main application window
        """
        self.parent = parent
        self.main_window = main_window

        # Create the audit output section with individual audit boxes
        self.create_audit_output()

        # Dictionary to store audit widgets for later access
        self.audit_widgets = {}

    def create_audit_output(self):
        """Create the audit output section with individual audit boxes"""
        # Main frame for all audits
        self.audits_frame = ttk.LabelFrame(self.parent, text="Generated Audits", padding="10")
        self.audits_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # Create a canvas with scrollbar for scrolling through audits
        canvas_frame = ttk.Frame(self.audits_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True)

        # Add scrollbars
        y_scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL)
        y_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Create canvas
        self.audits_canvas = tk.Canvas(canvas_frame, yscrollcommand=y_scrollbar.set)
        self.audits_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Configure the scrollbar
        y_scrollbar.config(command=self.audits_canvas.yview)

        # Create a frame inside the canvas to hold all audit sections
        self.scrollable_frame = ttk.Frame(self.audits_canvas)
        self.scrollable_frame_id = self.audits_canvas.create_window((0, 0), window=self.scrollable_frame, anchor=tk.NW)

        # Configure the canvas to resize with the window
        self.audits_canvas.bind('<Configure>', self.on_canvas_configure)
        self.scrollable_frame.bind('<Configure>', self.on_frame_configure)

        # Add mouse wheel scrolling
        # Bind to the canvas
        self.audits_canvas.bind('<MouseWheel>', self._on_mousewheel)
        # Bind to the main window to ensure scrolling works when mouse is anywhere in the window
        self.main_window.root.bind('<MouseWheel>', self._on_mousewheel)

        # Create a frame for buttons at the top
        buttons_frame = ttk.Frame(self.audits_frame)
        buttons_frame.pack(anchor=tk.NE, padx=5, pady=5)

        # Add a "Copy All Audits" button
        copy_all_button = ttk.Button(buttons_frame, text="Copy All To Clipboard", command=self.main_window.copy_all_commands_to_clipboard)
        copy_all_button.pack(side=tk.LEFT, padx=5)

        # Add an "Execute All Audits" button
        execute_all_button = ttk.Button(buttons_frame, text="Execute All", command=self.main_window.execute_all_audits)
        execute_all_button.pack(side=tk.LEFT, padx=5)

        # Add an "Analyze Output" button
        analyze_button = ttk.Button(buttons_frame, text="Analyze Output Files", command=self.main_window.analyze_output)
        analyze_button.pack(side=tk.LEFT, padx=5)

        # Add a "Clear Output Files" button
        clear_button = ttk.Button(buttons_frame, text="Clear Output Files", command=self.main_window.clear_output_files)
        clear_button.pack(side=tk.LEFT, padx=5)

    def on_canvas_configure(self, event):
        """Handle canvas resize event"""
        # Update the scrollregion to encompass the inner frame
        self.audits_canvas.configure(scrollregion=self.audits_canvas.bbox("all"))
        # Resize the window width to match the canvas width
        self.audits_canvas.itemconfig(self.scrollable_frame_id, width=event.width)

    def on_frame_configure(self, event):
        """Handle frame resize event"""
        # Update the scrollregion to encompass the inner frame
        self.audits_canvas.configure(scrollregion=self.audits_canvas.bbox("all"))

    def _on_mousewheel(self, event):
        """Handle mouse wheel scrolling

        Args:
            event: The mouse wheel event
        """
        # Scroll the canvas when the mouse wheel is used
        # The delta value is platform-dependent, so we normalize it
        # Windows: event.delta is in multiples of 120
        self.audits_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def add_header_section(self, section_title, text, indent=0):
        """Add a header section with text but no buttons

        Args:
            section_title (str): The title of the section
            text (str): The text to display
            indent (int): The amount of indentation to apply to the section (default: 0)
        """
        # Tab indent text, even if it is multi-line
        text = "\n".join(["\t" + line for line in text.splitlines()])

        # Create a frame for this section with padding on the left
        section_frame = ttk.Frame(self.scrollable_frame, padding="5")
        section_frame.pack(fill=tk.X, expand=True, padx=(indent, 5))  # Apply indent to left padding

        # Create a container frame for title and text
        container_frame = ttk.Frame(section_frame)
        container_frame.pack(fill=tk.X, expand=True)

        # Create a label for the section title
        title_label = ttk.Label(container_frame, text=f"{section_title}\n{text}", font=("TkDefaultFont", 12, "bold"))
        title_label.pack(side=tk.LEFT, padx=5, pady=5)

        # Generate a unique ID for this header section
        section_id = f"header_{len(self.audit_widgets)}"

        # Store the widgets for later access
        self.audit_widgets[section_id] = {
            "frame": section_frame,
            "title_label": title_label,
            "type": "header"
        }

        return section_frame

    def add_audit_section(self, section_title, cmd_string, cmd_args, section_id, indent=0):
        """Add a new audit section with its own textbox and buttons

        Args:
            section_title (str): The title of the section
            cmd_string (str): The command string to execute
            cmd_args (dict): The command arguments as a dictionary
            section_id (str): A unique identifier for this section
            indent (int): The amount of indentation to apply to the section (default: 0)
        """

        def on_resize(event):
            # Get the updated width of the window
            window_width = event.width

            # Calculate the new positions and sizes based on window dimensions
            offset = int(0.1 * window_width)
            container_width = int(0.3 * window_width)

            # Update the padding to move section_frame to the right
            section_frame.pack_configure(padx=(indent, 5))  # Preserve indent during resize

            # Update the width of command_container
            command_text_widget.pack_propagate(False)
            command_text_widget.config(width=container_width)

        # Create a frame for this section
        section_frame = ttk.Frame(self.scrollable_frame, padding="5")
        section_frame.pack(fill=tk.X, expand=True, pady=0, padx=(indent, 5))  # Apply indent to left padding

        # Create a container frame for title, audit command, and buttons
        container_frame = ttk.Frame(section_frame)
        container_frame.pack(fill=tk.X, expand=True, pady=0)

        # Create a label for the section title
        title_label = ttk.Label(container_frame, text=section_title, font=("TkDefaultFont", 10, "bold"))
        title_label.pack(side=tk.TOP, padx=5, anchor="w")

        # Create an audit command container frame
        command_container = ttk.Frame(container_frame)
        command_container.pack(fill=tk.X, expand=True)

        # Create a text widget for the audit command
        command_text_widget = tk.Text(command_container, wrap=tk.NONE, height=1)
        command_text_widget.insert(tk.END, cmd_string)
        command_text_widget.configure(state="disabled")  # Make it read-only
        command_text_widget.pack(side=tk.TOP, fill=tk.BOTH, expand=False, padx=5, pady=1)

        # Create a horizontal scrollbar for the text widget
        scrollbar_x = ttk.Scrollbar(command_container, orient=tk.HORIZONTAL, command=command_text_widget.xview)
        command_text_widget.config(xscrollcommand=scrollbar_x.set)
        scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)

        # Create a frame for the buttons
        button_frame = ttk.Frame(container_frame)
        button_frame.pack(fill=tk.X, pady=(0, 0))

        # Add Copy button
        copy_button = ttk.Button(
            button_frame,
            text="Copy to Clipboard",
            command=lambda cmd=cmd_args: self.main_window.copy_command_to_clipboard(cmd)
        )
        copy_button.pack(side=tk.LEFT, padx=5, pady=2)

        # Extract metadata from section_title and section_id
        metadata = {}

        # Parse section_title to extract section number and audit name
        if "Section" in section_title and ":" in section_title:
            try:
                section_parts = section_title.split(":")
                section_num = section_parts[0].replace("Section", "").strip()
                audit_name = section_parts[1].strip()
                metadata["section_number"] = section_num
                metadata["audit_name"] = audit_name
            except Exception:
                # If parsing fails, use the whole section_title as the audit name
                metadata["audit_name"] = section_title
        else:
            metadata["audit_name"] = section_title

        # Add Execute button
        execute_button = ttk.Button(
            button_frame,
            text="Execute",
            command=lambda cmd=cmd_args, meta=metadata: self.main_window.execute_command(cmd, meta)
        )
        execute_button.pack(side=tk.LEFT, padx=5, pady=2)

        # Store the widgets for later access
        self.audit_widgets[section_id] = {
            "frame": section_frame,
            "title_label": title_label,
            "command_text_widget": command_text_widget,
            "copy_button": copy_button,
            "execute_button": execute_button,
            "cmd_args": cmd_args,
            "metadata": metadata,
            "type": "audit"
        }

        return section_frame

    # Removed redundant methods that have been moved to audit_manager.py
    # copy_audit_to_clipboard - now using main_window.copy_command_to_clipboard
    # execute_command - now using main_window.execute_command


    def clear_audit_widgets(self):
        """Clear existing audit widgets"""
        logger.debug("Clearing existing audit widgets")
        widget_count = len(self.audit_widgets)
        for widget_id in list(self.audit_widgets.keys()):
            if widget_id in self.audit_widgets:
                self.audit_widgets[widget_id]["frame"].destroy()
        self.audit_widgets.clear()
        logger.debug(f"Cleared {widget_count} existing audit widgets")


    # Removed redundant methods that have been moved to audit_manager.py or main_window.py
    # copy_to_clipboard - now using main_window.copy_all_commands_to_clipboard
    # execute_all_audits - now using main_window.execute_all_audits
    # clear_output_files - now using main_window.clear_output_files
    # analyze_output - now using main_window.analyze_output
    # display_analysis_results - now handled in main_window.analyze_output
