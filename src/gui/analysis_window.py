"""
Analysis Window Module

This module provides the analysis progress window for the PAN-OS Audit application.
"""

import tkinter as tk
from tkinter import ttk
import os
import sys

# Add the src directory to the path if running as standalone
if __name__ == "__main__":
    sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

class AnalysisProgressWindow(tk.Toplevel):
    """A window for showing the progress of the analysis"""
    def __init__(self, parent, output_files):
        super().__init__(parent)
        self.parent = parent
        self.output_files = output_files
        self.processed_files = []

        # Add a flag to track if the window is being destroyed
        self.is_destroying = False

        # Bind the destroy event to set the flag
        self.bind("<Destroy>", self._on_destroy)

        # Set window properties
        self.title("Analysis Progress")
        self.geometry("600x400")
        self.transient(parent)
        self.grab_set()

        # Create the main frame
        self.main_frame = ttk.Frame(self, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Add a title
        title_label = ttk.Label(self.main_frame, text="Analyzing Output Files", font=("TkDefaultFont", 14, "bold"))
        title_label.pack(pady=(0, 10))

        # Add a progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(self.main_frame, variable=self.progress_var, maximum=len(output_files))
        self.progress_bar.pack(fill=tk.X, pady=(0, 10))

        # Add a status label
        self.status_var = tk.StringVar(value="Preparing to process files...")
        status_label = ttk.Label(self.main_frame, textvariable=self.status_var)
        status_label.pack(pady=(0, 10))

        # Create frames for file lists
        lists_frame = ttk.Frame(self.main_frame)
        lists_frame.pack(fill=tk.BOTH, expand=True)

        # Pending files frame
        pending_frame = ttk.LabelFrame(lists_frame, text="Pending Files")
        pending_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        # Create a canvas with scrollbar for pending files
        pending_canvas_frame = ttk.Frame(pending_frame)
        pending_canvas_frame.pack(fill=tk.BOTH, expand=True)

        pending_scrollbar = ttk.Scrollbar(pending_canvas_frame, orient=tk.VERTICAL)
        pending_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.pending_canvas = tk.Canvas(pending_canvas_frame, yscrollcommand=pending_scrollbar.set)
        self.pending_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        pending_scrollbar.config(command=self.pending_canvas.yview)

        self.pending_frame_inner = ttk.Frame(self.pending_canvas)
        self.pending_frame_id = self.pending_canvas.create_window((0, 0), window=self.pending_frame_inner, anchor=tk.NW)

        self.pending_canvas.bind('<Configure>', lambda e: self.pending_canvas.configure(scrollregion=self.pending_canvas.bbox("all")))
        self.pending_frame_inner.bind('<Configure>', lambda e: self.pending_canvas.configure(scrollregion=self.pending_canvas.bbox("all")))

        # Completed files frame
        completed_frame = ttk.LabelFrame(lists_frame, text="Completed Files")
        completed_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))

        # Create a canvas with scrollbar for completed files
        completed_canvas_frame = ttk.Frame(completed_frame)
        completed_canvas_frame.pack(fill=tk.BOTH, expand=True)

        completed_scrollbar = ttk.Scrollbar(completed_canvas_frame, orient=tk.VERTICAL)
        completed_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.completed_canvas = tk.Canvas(completed_canvas_frame, yscrollcommand=completed_scrollbar.set)
        self.completed_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        completed_scrollbar.config(command=self.completed_canvas.yview)

        self.completed_frame_inner = ttk.Frame(self.completed_canvas)
        self.completed_frame_id = self.completed_canvas.create_window((0, 0), window=self.completed_frame_inner, anchor=tk.NW)

        self.completed_canvas.bind('<Configure>', lambda e: self.completed_canvas.configure(scrollregion=self.completed_canvas.bbox("all")))
        self.completed_frame_inner.bind('<Configure>', lambda e: self.completed_canvas.configure(scrollregion=self.completed_canvas.bbox("all")))

        # Populate the pending files list
        self.pending_labels = {}
        for i, file_path in enumerate(output_files):
            file_name = os.path.basename(file_path)
            label = ttk.Label(self.pending_frame_inner, text=file_name)
            label.pack(anchor=tk.W, pady=2)
            self.pending_labels[file_path] = label

        # Add a cancel button
        self.cancel_button = ttk.Button(self.main_frame, text="Cancel", command=self.on_cancel)
        self.cancel_button.pack(pady=(10, 0))

        # Flag to track if the operation was cancelled
        self.cancelled = False

        # Update the window
        self.update()

    def _on_destroy(self, event):
        """Handle destroy event

        Args:
            event: The destroy event
        """
        # Only set the flag if this window is being destroyed (not a child widget)
        if event.widget == self:
            self.is_destroying = True

    def update_progress(self, file_path, success=True):
        """Update the progress for a file

        Args:
            file_path (str): The path to the file that was processed
            success (bool, optional): Whether the file was processed successfully. Defaults to True.
        """
        # Check if the window is being destroyed before updating
        if self.is_destroying:
            return

        # Use after() to schedule the update on the main thread
        self.after_idle(lambda: self._do_update_progress(file_path, success))

    def _do_update_progress(self, file_path, success=True):
        """Internal method to perform the actual update

        Args:
            file_path (str): The path to the file that was processed
            success (bool, optional): Whether the file was processed successfully. Defaults to True.
        """
        # Check again in case destruction started during the wait
        if self.is_destroying:
            return

        # Move the file from pending to completed
        if file_path in self.pending_labels:
            # Remove from pending
            self.pending_labels[file_path].destroy()
            del self.pending_labels[file_path]

            # Add to completed
            file_name = os.path.basename(file_path)
            if success:
                label = ttk.Label(self.completed_frame_inner, text=file_name)
            else:
                label = ttk.Label(self.completed_frame_inner, text=f"{file_name} (Error)", foreground="red")
            label.pack(anchor=tk.W, pady=2)

            # Add to processed files
            self.processed_files.append(file_path)

            # Update progress bar
            progress = len(self.processed_files) / len(self.output_files)
            self.progress_var.set(len(self.processed_files))

            # Update status
            remaining = len(self.output_files) - len(self.processed_files)
            self.status_var.set(f"Processed {len(self.processed_files)} of {len(self.output_files)} files. {remaining} remaining.")

    def on_cancel(self):
        """Handle cancel button click"""
        self.cancelled = True
        self.destroy()
