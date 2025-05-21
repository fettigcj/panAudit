import tkinter as tk
from tkinter import ttk
import time
import threading
import datetime
import os

class AuditTracker(tk.Toplevel):
    """A window for tracking the progress of audit tasks"""
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent

        # Set window properties
        self.title("Audit Tracker")
        self.geometry("800x600")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # Dictionary to store audit tasks
        # Key: audit_id, Value: dict with task info (start_time, status, result, etc.)
        self.audit_tasks = {}

        # Lock for thread-safe operations on audit_tasks
        self.tasks_lock = threading.Lock()

        # Create the main frame
        self.main_frame = ttk.Frame(self, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Create the header
        self.create_header()

        # Create the tasks frame with scrollbar
        self.create_tasks_frame()

        # Start the timer update thread
        self.timer_running = True
        self.timer_thread = threading.Thread(target=self.update_timers)
        self.timer_thread.daemon = True
        self.timer_thread.start()

    def create_header(self):
        """Create the header section of the tracker window"""
        header_frame = ttk.Frame(self.main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))

        # Add a title
        title_label = ttk.Label(header_frame, text="Audit Tasks Progress", font=("TkDefaultFont", 14, "bold"))
        title_label.pack(side=tk.LEFT, padx=5)

        # Add a close button
        close_button = ttk.Button(header_frame, text="Close", command=self.on_close)
        close_button.pack(side=tk.RIGHT, padx=5)

    def create_tasks_frame(self):
        """Create the frame for displaying audit tasks"""
        # Create a frame with a canvas for scrolling
        container_frame = ttk.Frame(self.main_frame)
        container_frame.pack(fill=tk.BOTH, expand=True)

        # Add a canvas with scrollbar
        self.canvas = tk.Canvas(container_frame)
        scrollbar = ttk.Scrollbar(container_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Create a frame inside the canvas for the tasks
        self.tasks_frame = ttk.Frame(self.canvas)
        self.tasks_frame_id = self.canvas.create_window((0, 0), window=self.tasks_frame, anchor=tk.NW)

        # Configure the canvas to resize with the window
        self.canvas.bind('<Configure>', self.on_canvas_configure)
        self.tasks_frame.bind('<Configure>', self.on_frame_configure)

        # Add mouse wheel scrolling
        self.canvas.bind('<MouseWheel>', self._on_mousewheel)

        # Create column headers
        headers_frame = ttk.Frame(self.tasks_frame)
        headers_frame.pack(fill=tk.X, pady=(0, 5))

        # Define column widths in pixels for consistent sizing
        self.column_widths = {
            "section": 100,    # Width in pixels for section number
            "audit": 200,      # Width in pixels for audit name
            "status": 100,     # Width in pixels for status
            "time": 100,       # Width in pixels for elapsed time
            "result": 300,     # Width in pixels for result
            "button": 100      # Width in pixels for button
        }

        # Configure grid columns in headers frame
        headers_frame.columnconfigure(0, minsize=self.column_widths["section"])
        headers_frame.columnconfigure(1, minsize=self.column_widths["audit"])
        headers_frame.columnconfigure(2, minsize=self.column_widths["status"])
        headers_frame.columnconfigure(3, minsize=self.column_widths["time"])
        headers_frame.columnconfigure(4, minsize=self.column_widths["result"], weight=1)
        headers_frame.columnconfigure(5, minsize=self.column_widths["button"])

        # Add column headers using grid
        ttk.Label(headers_frame, text="Section", font=("TkDefaultFont", 10, "bold")).grid(row=0, column=0, padx=5, sticky="w")
        ttk.Label(headers_frame, text="Audit", font=("TkDefaultFont", 10, "bold")).grid(row=0, column=1, padx=5, sticky="w")
        ttk.Label(headers_frame, text="Status", font=("TkDefaultFont", 10, "bold")).grid(row=0, column=2, padx=5, sticky="w")
        ttk.Label(headers_frame, text="Time", font=("TkDefaultFont", 10, "bold")).grid(row=0, column=3, padx=5, sticky="w")
        ttk.Label(headers_frame, text="Result", font=("TkDefaultFont", 10, "bold")).grid(row=0, column=4, padx=5, sticky="w")
        ttk.Label(headers_frame, text="", font=("TkDefaultFont", 10, "bold")).grid(row=0, column=5, padx=5, sticky="e")

        # Add a separator
        separator_frame = ttk.Frame(self.tasks_frame)
        separator_frame.pack(fill=tk.X, pady=5)
        ttk.Separator(separator_frame, orient=tk.HORIZONTAL).pack(fill=tk.X)

    def on_canvas_configure(self, event):
        """Handle canvas resize event"""
        # Update the scrollregion to encompass the inner frame
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        # Resize the window width to match the canvas width
        self.canvas.itemconfig(self.tasks_frame_id, width=event.width)

    def on_frame_configure(self, event):
        """Handle frame resize event"""
        # Update the scrollregion to encompass the inner frame
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_mousewheel(self, event):
        """Handle mouse wheel scrolling"""
        # Scroll the canvas when the mouse wheel is used
        # The delta value is platform-dependent, so we normalize it
        # Windows: event.delta is in multiples of 120
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def add_audit_task(self, audit_id, audit_name, command_str, section_number=None):
        """Add a new audit task to the tracker

        Args:
            audit_id (str): A unique identifier for the audit task
            audit_name (str): The display name of the audit
            command_str (str): The command string being executed
            section_number (str, optional): The section number of the audit. Defaults to None.

        Returns:
            str: The audit_id of the added task
        """
        with self.tasks_lock:
            # Create a new task entry
            task_info = {
                "audit_name": audit_name,
                "command": command_str,
                "start_time": time.time(),
                "status": "Queued",  # Initial status is Queued, will be updated to Running when task starts
                "result": "",
                "full_output": "",  # Store the full command output
                "log_file": None,   # Path to the log file
                "err_file": None,   # Path to the error file
                "section_number": section_number,
                "frame": None,  # Will be set when the UI is created
                "time_label": None,  # Will be set when the UI is created
                "status_label": None,  # Will be set when the UI is created
                "result_label": None,  # Will be set when the UI is created
                "section_label": None,  # Will be set when the UI is created
                "view_output_button": None  # Will be set when the UI is created
            }

            # Add to the tasks dictionary
            self.audit_tasks[audit_id] = task_info

            # Create the UI for this task
            self._create_task_ui(audit_id)

            return audit_id

    def _create_task_ui(self, audit_id):
        """Create the UI elements for a task

        Args:
            audit_id (str): The unique identifier for the audit task
        """
        task_info = self.audit_tasks[audit_id]

        # Create a frame for this task
        task_frame = ttk.Frame(self.tasks_frame)
        task_frame.pack(fill=tk.X, pady=2)

        # Store the frame reference
        task_info["frame"] = task_frame

        # Configure grid columns to match headers
        task_frame.columnconfigure(0, minsize=self.column_widths["section"])
        task_frame.columnconfigure(1, minsize=self.column_widths["audit"])
        task_frame.columnconfigure(2, minsize=self.column_widths["status"])
        task_frame.columnconfigure(3, minsize=self.column_widths["time"])
        task_frame.columnconfigure(4, minsize=self.column_widths["result"], weight=1)
        task_frame.columnconfigure(5, minsize=self.column_widths["button"])

        # Create labels for each column using grid
        section_label = ttk.Label(task_frame, text=task_info.get("section_number", ""))
        section_label.grid(row=0, column=0, padx=5, sticky="w")
        task_info["section_label"] = section_label

        audit_label = ttk.Label(task_frame, text=task_info["audit_name"], wraplength=self.column_widths["audit"]-10)
        audit_label.grid(row=0, column=1, padx=5, sticky="w")

        status_label = ttk.Label(task_frame, text=task_info["status"])
        status_label.grid(row=0, column=2, padx=5, sticky="w")
        task_info["status_label"] = status_label

        time_label = ttk.Label(task_frame, text="0:00")
        time_label.grid(row=0, column=3, padx=5, sticky="w")
        task_info["time_label"] = time_label

        result_label = ttk.Label(task_frame, text=task_info["result"], wraplength=self.column_widths["result"]-10)
        result_label.grid(row=0, column=4, padx=5, sticky="w")
        task_info["result_label"] = result_label

        # Add a "View output" button
        view_output_button = ttk.Button(
            task_frame, 
            text="View output", 
            command=lambda aid=audit_id: self.show_full_output(aid),
            state="disabled"  # Initially disabled until output is available
        )
        view_output_button.grid(row=0, column=5, padx=5, sticky="e")
        task_info["view_output_button"] = view_output_button

        # Add a separator
        separator_frame = ttk.Frame(self.tasks_frame)
        separator_frame.pack(fill=tk.X, pady=2)
        ttk.Separator(separator_frame, orient=tk.HORIZONTAL).pack(fill=tk.X)

    def update_audit_task(self, audit_id, status=None, result=None, full_output=None, log_file=None, err_file=None):
        """Update the status and result of an audit task

        Args:
            audit_id (str): The unique identifier for the audit task
            status (str, optional): The new status of the task. Defaults to None.
            result (str, optional): The new result of the task. Defaults to None.
            full_output (str, optional): The full output of the command. Defaults to None.
            log_file (str, optional): Path to the log file. Defaults to None.
            err_file (str, optional): Path to the error file. Defaults to None.
        """
        with self.tasks_lock:
            if audit_id not in self.audit_tasks:
                return

            task_info = self.audit_tasks[audit_id]

            # Update status if provided
            if status is not None:
                task_info["status"] = status
                if task_info["status_label"]:
                    task_info["status_label"].config(text=status)

            # Update result if provided
            if result is not None:
                task_info["result"] = result
                if task_info["result_label"]:
                    task_info["result_label"].config(text=result)

            # Update full output if provided
            if full_output is not None:
                task_info["full_output"] = full_output

            # Update log file path if provided
            if log_file is not None:
                task_info["log_file"] = log_file

            # Update error file path if provided
            if err_file is not None:
                task_info["err_file"] = err_file

            # Enable the view output button if we have log files
            if task_info["view_output_button"] and (log_file is not None or err_file is not None or full_output is not None):
                task_info["view_output_button"].config(state="normal")

    def update_timers(self):
        """Update the elapsed time for all running tasks"""
        while self.timer_running:
            with self.tasks_lock:
                for audit_id, task_info in self.audit_tasks.items():
                    if task_info["status"] == "Running" and task_info["time_label"]:
                        elapsed = time.time() - task_info["start_time"]
                        elapsed_str = str(datetime.timedelta(seconds=int(elapsed)))
                        task_info["time_label"].config(text=elapsed_str)

            # Sleep for a short time to avoid consuming too much CPU
            time.sleep(1)

    def on_close(self):
        """Handle window close event"""
        # Stop the timer thread
        self.timer_running = False
        if self.timer_thread.is_alive():
            self.timer_thread.join(timeout=1.0)

        # Hide the window instead of destroying it
        self.withdraw()

    def show(self):
        """Show the tracker window"""
        self.deiconify()
        self.lift()

    def show_full_output(self, audit_id):
        """Show the full output of a task in a new window

        Args:
            audit_id (str): The unique identifier for the audit task
        """
        if audit_id not in self.audit_tasks:
            return

        task_info = self.audit_tasks[audit_id]

        # Create a new window
        output_window = tk.Toplevel(self)
        output_window.title(f"Output: {task_info['audit_name']}")
        output_window.geometry("800x600")

        # Create a frame with padding
        frame = ttk.Frame(output_window, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)

        # Add a label with the task name
        ttk.Label(
            frame, 
            text=f"Output for: {task_info['audit_name']}", 
            font=("TkDefaultFont", 12, "bold")
        ).pack(anchor=tk.W, pady=(0, 10))

        # Create a notebook for tabs
        notebook = ttk.Notebook(frame)
        notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Create a tab for standard output
        stdout_frame = ttk.Frame(notebook)
        notebook.add(stdout_frame, text="Standard Output")

        # Create a tab for error output
        stderr_frame = ttk.Frame(notebook)
        notebook.add(stderr_frame, text="Error Output")

        # Add text widgets with scrollbars to each tab
        stdout_text = self._create_scrolled_text(stdout_frame)
        stderr_text = self._create_scrolled_text(stderr_frame)

        # Function to update the output display
        def update_output():
            # Check if the window still exists
            if not output_window.winfo_exists():
                return

            # Update standard output
            if task_info.get("log_file") and os.path.exists(task_info["log_file"]):
                try:
                    with open(task_info["log_file"], 'r', encoding='utf-8') as f:
                        content = f.read()

                    # Save current position
                    current_pos = stdout_text.yview()[0]

                    # Update content
                    stdout_text.config(state=tk.NORMAL)
                    stdout_text.delete(1.0, tk.END)
                    stdout_text.insert(tk.END, content)
                    stdout_text.config(state=tk.DISABLED)

                    # Restore position if not at the end
                    if current_pos < 1.0:
                        stdout_text.yview_moveto(current_pos)
                    else:
                        stdout_text.see(tk.END)  # Scroll to the end
                except Exception as e:
                    stdout_text.config(state=tk.NORMAL)
                    stdout_text.delete(1.0, tk.END)
                    stdout_text.insert(tk.END, f"Error reading log file: {str(e)}")
                    stdout_text.config(state=tk.DISABLED)
            elif task_info.get("full_output"):
                stdout_text.config(state=tk.NORMAL)
                stdout_text.delete(1.0, tk.END)
                stdout_text.insert(tk.END, task_info["full_output"])
                stdout_text.config(state=tk.DISABLED)
            else:
                stdout_text.config(state=tk.NORMAL)
                stdout_text.delete(1.0, tk.END)
                stdout_text.insert(tk.END, "No output available")
                stdout_text.config(state=tk.DISABLED)

            # Update error output
            if task_info.get("err_file") and os.path.exists(task_info["err_file"]):
                try:
                    with open(task_info["err_file"], 'r', encoding='utf-8') as f:
                        content = f.read()

                    # Save current position
                    current_pos = stderr_text.yview()[0]

                    # Update content
                    stderr_text.config(state=tk.NORMAL)
                    stderr_text.delete(1.0, tk.END)
                    stderr_text.insert(tk.END, content)
                    stderr_text.config(state=tk.DISABLED)

                    # Restore position if not at the end
                    if current_pos < 1.0:
                        stderr_text.yview_moveto(current_pos)
                    else:
                        stderr_text.see(tk.END)  # Scroll to the end
                except Exception as e:
                    stderr_text.config(state=tk.NORMAL)
                    stderr_text.delete(1.0, tk.END)
                    stderr_text.insert(tk.END, f"Error reading error file: {str(e)}")
                    stderr_text.config(state=tk.DISABLED)
            else:
                stderr_text.config(state=tk.NORMAL)
                stderr_text.delete(1.0, tk.END)
                stderr_text.insert(tk.END, "No error output available")
                stderr_text.config(state=tk.DISABLED)

            # Schedule the next update if the task is still running
            if task_info["status"] == "Running" and output_window.winfo_exists():
                output_window.after(1000, update_output)  # Update every second

        # Initial update
        update_output()

        # Add buttons
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X, pady=(0, 0))

        # Add a refresh button
        refresh_button = ttk.Button(button_frame, text="Refresh", command=update_output)
        refresh_button.pack(side=tk.LEFT, padx=5)

        # Add a close button
        close_button = ttk.Button(button_frame, text="Close", command=output_window.destroy)
        close_button.pack(side=tk.RIGHT, padx=5)

        # Schedule periodic updates if the task is running
        if task_info["status"] == "Running":
            output_window.after(1000, update_output)  # Update every second

    def _create_scrolled_text(self, parent):
        """Create a scrolled text widget

        Args:
            parent: The parent widget

        Returns:
            tk.Text: The text widget
        """
        # Create a frame for the text widget and scrollbars
        text_frame = ttk.Frame(parent)
        text_frame.pack(fill=tk.BOTH, expand=True)

        # Create the text widget
        text_widget = tk.Text(text_frame, wrap=tk.WORD)
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Add vertical scrollbar
        scrollbar_y = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=text_widget.yview)
        text_widget.config(yscrollcommand=scrollbar_y.set)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

        # Add horizontal scrollbar
        scrollbar_x = ttk.Scrollbar(parent, orient=tk.HORIZONTAL, command=text_widget.xview)
        text_widget.config(xscrollcommand=scrollbar_x.set)
        scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)

        return text_widget
