"""
Configuration Window Module

This module provides the configuration window for the PAN-OS Audit application.
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import json
import os
import sys

# Add the src directory to the path if running as standalone
if __name__ == "__main__":
    sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

from src.utils.php_validator import validate_php_with_message, validate_pan_os_php_with_message
from src.utils.repo_downloader import update_repository

class ConfigWindow(tk.Toplevel):
    """Configuration window for the Panorama Audit GUI"""
    def __init__(self, parent, config, save_callback):
        super().__init__(parent)
        self.parent = parent
        self.config = config
        self.save_callback = save_callback

        # Set window properties
        self.title("Configuration")
        self.geometry("800x600")
        self.transient(parent)
        self.grab_set()

        # Add maximize and minimize buttons
        self.resizable(True, True)
        # Ensure maximize button is visible on Windows
        self.attributes('-toolwindow', False)  # Disable tool window style
        self.minsize(400, 300)  # Set minimum size

        # Set window style to show maximize button on Windows
        if sys.platform.startswith('win'):
            try:
                import ctypes
                hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
                style = ctypes.windll.user32.GetWindowLongW(hwnd, -16)  # GWL_STYLE
                style |= 0x00010000  # WS_MAXIMIZEBOX
                ctypes.windll.user32.SetWindowLongW(hwnd, -16, style)
            except Exception as e:
                print(f"Error setting window style: {e}")

        # Create a canvas with scrollbar for the main content
        canvas_frame = ttk.Frame(self)
        canvas_frame.pack(fill=tk.BOTH, expand=True)

        # Add vertical scrollbar
        scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Create canvas
        self.main_canvas = tk.Canvas(canvas_frame, yscrollcommand=scrollbar.set)
        self.main_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Configure the scrollbar
        scrollbar.config(command=self.main_canvas.yview)

        # Create a frame inside the canvas to hold all content
        self.main_frame = ttk.Frame(self.main_canvas, padding="10")
        self.main_frame_id = self.main_canvas.create_window((0, 0), window=self.main_frame, anchor=tk.NW)

        # Configure the canvas to resize with the window
        self.main_canvas.bind('<Configure>', self.on_main_canvas_configure)
        self.main_frame.bind('<Configure>', self.on_main_frame_configure)

        # Add mouse wheel scrolling
        self.main_canvas.bind('<MouseWheel>', self._on_main_mousewheel)
        # Bind mousewheel to the window and main frame as well
        self.bind('<MouseWheel>', self._on_main_mousewheel)
        self.main_frame.bind('<MouseWheel>', self._on_main_mousewheel)

        # Add a binding to bind mousewheel to all widgets after they're created
        self.bind('<Map>', self._bind_mousewheel_to_all)

        # Bind mousewheel to the root window to ensure it works everywhere
        self.winfo_toplevel().bind("<MouseWheel>", self._on_global_mousewheel)

        # Create the configuration sections
        self.create_panorama_selection()
        self.create_audit_settings_section()

        # Create buttons frame
        buttons_frame = ttk.Frame(self.main_frame)
        buttons_frame.pack(fill=tk.X, pady=10)

        # Add Save and Cancel buttons
        ttk.Button(buttons_frame, text="Save", command=self.save_config).pack(side=tk.RIGHT, padx=5)
        ttk.Button(buttons_frame, text="Cancel", command=self.destroy).pack(side=tk.RIGHT, padx=5)
        ttk.Button(buttons_frame, text="Validate PHP", command=self.validate_php).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="Validate pan-os-php", command=self.validate_pan_os_php).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="Git pull pan-os-php", command=self.git_pull_pan_os_php).pack(side=tk.LEFT, padx=5)

    def create_panorama_selection(self):
        """Create the Panorama selection section"""
        frame = ttk.LabelFrame(self.main_frame, text="Panorama Specifics", padding="10")
        frame.pack(fill=tk.X, pady=5)

        # Create a grid layout for the frame
        frame.columnconfigure(0, weight=0)  # Label column
        frame.columnconfigure(1, weight=1)  # Dropdown/entry column
        frame.columnconfigure(2, weight=0)  # Button column

        # Panorama dropdown - row 0
        ttk.Label(frame, text="Select Panorama Instance:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.panorama_var = tk.StringVar(value=self.config["globalConfig"]["currentPanorama"])
        self.panorama_dropdown = ttk.Combobox(frame, textvariable=self.panorama_var, width=40)
        self.panorama_dropdown.grid(row=0, column=1, sticky=tk.W, pady=5)
        self.update_panorama_dropdown()

        # Add/Remove/Load/Save buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=0, column=2, padx=10)

        ttk.Button(btn_frame, text="Add", command=self.add_panorama).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Remove", command=self.remove_panorama).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Load", command=self.load_panorama).pack(side=tk.LEFT, padx=5)

        # Device Group section - row 1
        device_group_frame = ttk.Frame(frame)
        device_group_frame.grid(row=1, column=0, columnspan=3, sticky=tk.W+tk.E, pady=5)

        ttk.Label(device_group_frame, text="Device Group / Audit Target:").pack(side=tk.LEFT, padx=5)
        # Initialize with the device group of the current panorama, if available
        current_panorama = self.config["globalConfig"]["currentPanorama"]
        initial_device_group = "any"
        if current_panorama and current_panorama in self.config["Panoramas"]:
            initial_device_group = self.config["Panoramas"][current_panorama]["auditTarget"]

        self.device_group_var = tk.StringVar(value=initial_device_group)
        ttk.Entry(device_group_frame, textvariable=self.device_group_var, width=40).pack(side=tk.LEFT, padx=5)

        # Set button
        btn_frame = ttk.Frame(device_group_frame)
        btn_frame.pack(side=tk.LEFT, padx=5)

        ttk.Button(btn_frame, text="Set", command=self.set_device_group).pack(side=tk.LEFT, padx=5)

        # Get the current Panorama's include disabled rules setting
        include_disabled = False
        if current_panorama and current_panorama in self.config["Panoramas"]:
            include_disabled = self.config["Panoramas"][current_panorama].get("includeDisabledRules", False)

        # Add checkbox for including disabled rules (this is a panorama-specific setting) - row 2
        self.include_disabled_var = tk.BooleanVar(value=include_disabled)
        ttk.Checkbutton(frame, text="Include disabled rules in results", variable=self.include_disabled_var, 
                       command=self.toggle_disabled_rules).grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=5)

        # Security Profile Groups section
        self.create_security_profile_selection(frame)

    def update_panorama_dropdown(self):
        """Update the Panorama dropdown with the current list of instances"""
        panorama_instances = list(self.config["Panoramas"].keys())
        self.panorama_dropdown['values'] = panorama_instances
        if panorama_instances and not self.panorama_var.get():
            self.panorama_var.set(panorama_instances[0])
            self.config["globalConfig"]["currentPanorama"] = panorama_instances[0]

    def add_panorama(self):
        """Add a new Panorama instance"""
        new_panorama = simpledialog.askstring("Add Panorama", "Enter Panorama hostname or IP:")
        if new_panorama:
            if new_panorama not in self.config["Panoramas"]:
                self.config["Panoramas"][new_panorama] = {
                    "auditTarget": "any",
                    "auditSPGs": [],
                    "includeDisabledRules": False
                }
                self.config["globalConfig"]["currentPanorama"] = new_panorama
                self.update_panorama_dropdown()
                self.panorama_var.set(new_panorama)
                # Update device group field
                self.device_group_var.set(self.config["Panoramas"][new_panorama]["auditTarget"])
                # Update SPG listbox
                self.update_spg_listbox()
            else:
                messagebox.showinfo("Info", "This Panorama instance already exists in the list.")

    def remove_panorama(self):
        """Remove the selected Panorama instance"""
        selected = self.panorama_var.get()
        if selected:
            if messagebox.askyesno("Confirm", f"Remove {selected} from the list?"):
                del self.config["Panoramas"][selected]
                self.update_panorama_dropdown()
                # Update current panorama and device group
                if self.config["Panoramas"]:
                    new_current = list(self.config["Panoramas"].keys())[0]
                    self.panorama_var.set(new_current)
                    self.config["globalConfig"]["currentPanorama"] = new_current
                    self.device_group_var.set(self.config["Panoramas"][new_current]["auditTarget"])
                else:
                    self.panorama_var.set("")
                    self.config["globalConfig"]["currentPanorama"] = ""
                    self.device_group_var.set("any")
                # Update the SPG listbox
                self.update_spg_listbox()

    def load_panorama(self):
        """Load the selected Panorama configuration"""
        selected = self.panorama_var.get()
        if selected and selected in self.config["Panoramas"]:
            self.config["globalConfig"]["currentPanorama"] = selected
            self.device_group_var.set(self.config["Panoramas"][selected]["auditTarget"])

            # Update the include_disabled_var with the value for this Panorama
            include_disabled = self.config["Panoramas"][selected].get("includeDisabledRules", False)
            self.include_disabled_var.set(include_disabled)

            # Update the SPG listbox with the SPGs for this Panorama
            self.update_spg_listbox()
            messagebox.showinfo("Info", f"Loaded configuration for {selected}")
        else:
            messagebox.showerror("Error", "Please select a valid Panorama instance")


    def set_device_group(self):
        """Set the device group for the current Panorama"""
        current_panorama = self.config["globalConfig"]["currentPanorama"]
        if not current_panorama:
            messagebox.showerror("Error", "Please select a Panorama instance first")
            return

        device_group = self.device_group_var.get()
        self.config["Panoramas"][current_panorama]["auditTarget"] = device_group
        messagebox.showinfo("Info", f"Device group set for {current_panorama}")

    def create_audit_settings_section(self):
        """Create the audit settings and extra arguments section with two columns"""
        # Create the main frame for this section
        main_frame = ttk.LabelFrame(self.main_frame, text="Global Config Options", padding="10")
        main_frame.pack(fill=tk.X, pady=5)

        # Create a frame for the two columns
        columns_frame = ttk.Frame(main_frame)
        columns_frame.pack(fill=tk.X, expand=True)

        # Create the left column (Audit settings)
        left_column = ttk.LabelFrame(columns_frame, text="Audit settings", padding="10")
        left_column.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")

        # Add maxThreads setting to the left column
        max_threads_frame = ttk.Frame(left_column)
        max_threads_frame.pack(fill=tk.X, pady=5, anchor=tk.W)

        ttk.Label(max_threads_frame, text="Maximum concurrent tasks:").pack(side=tk.LEFT, padx=(0, 5))

        # Get the current maxThreads value from config
        max_threads = self.config["globalConfig"].get("maxThreads", 3)

        # Create a spinbox for maxThreads
        self.max_threads_var = tk.IntVar(value=max_threads)
        max_threads_spinbox = ttk.Spinbox(
            max_threads_frame, 
            from_=1, 
            to=20, 
            width=5, 
            textvariable=self.max_threads_var,
            command=self.update_max_threads
        )
        max_threads_spinbox.pack(side=tk.LEFT)

        # Bind the spinbox to update on key release as well
        max_threads_spinbox.bind("<KeyRelease>", lambda e: self.update_max_threads())

        # Add git repo URL setting to the left column (this is a global config element)
        repo_url_frame = ttk.Frame(left_column)
        repo_url_frame.pack(fill=tk.X, pady=5, anchor=tk.W)

        ttk.Label(repo_url_frame, text="pan-os-php Repository URL:").pack(side=tk.LEFT, padx=(0, 5))

        # Get the current repo URL value from config
        repo_url = self.config["globalConfig"].get("panOsPhpRepoUrl", "https://github.com/swaschkut/pan-os-php")

        # Create an entry field for repo URL
        self.repo_url_var = tk.StringVar(value=repo_url)
        repo_url_entry = ttk.Entry(repo_url_frame, textvariable=self.repo_url_var, width=40)
        repo_url_entry.pack(side=tk.LEFT, padx=5)

        # Bind the entry to update on key release
        repo_url_entry.bind("<KeyRelease>", lambda e: self.update_repo_url())

        # Create the right column (pan-os-php extra arguments)
        right_column = ttk.LabelFrame(columns_frame, text="pan-os-php extra arguments", padding="10")
        right_column.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")

        # Configure the grid to make columns equal width
        columns_frame.columnconfigure(0, weight=1)
        columns_frame.columnconfigure(1, weight=1)

        # Create a canvas with scrollbar for the extra arguments
        canvas_frame = ttk.Frame(right_column)
        canvas_frame.pack(fill=tk.BOTH, expand=True)

        # Add vertical scrollbar
        scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Create canvas
        self.extra_args_canvas = tk.Canvas(canvas_frame, yscrollcommand=scrollbar.set)
        self.extra_args_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Configure the scrollbar
        scrollbar.config(command=self.extra_args_canvas.yview)

        # Create a frame inside the canvas to hold all extra arguments
        self.extra_args_frame = ttk.Frame(self.extra_args_canvas)
        self.extra_args_frame_id = self.extra_args_canvas.create_window((0, 0), window=self.extra_args_frame, anchor=tk.NW)

        # Configure the canvas to resize with the window
        self.extra_args_canvas.bind('<Configure>', self.on_extra_args_canvas_configure)
        self.extra_args_frame.bind('<Configure>', self.on_extra_args_frame_configure)

        # Add mouse wheel scrolling
        self.extra_args_canvas.bind('<MouseWheel>', self._on_extra_args_mousewheel)
        # Bind mousewheel to the extra args frame as well
        self.extra_args_frame.bind('<MouseWheel>', self._on_extra_args_mousewheel)

        # Recursively bind to all children of the extra args frame
        self._bind_to_extra_args_widget_and_children(self.extra_args_frame)

        # Add checkboxes for each extra argument in panAudit.json
        self.extra_args_vars = {}
        self.update_extra_args_ui()

    def update_max_threads(self):
        """Update the maxThreads value in the configuration"""
        try:
            # Get the value from the spinbox
            max_threads = self.max_threads_var.get()

            # Ensure it's a valid integer between 1 and 20
            max_threads = max(1, min(20, max_threads))

            # Update the configuration
            self.config["globalConfig"]["maxThreads"] = max_threads

            # Update the spinbox value in case it was adjusted
            self.max_threads_var.set(max_threads)
        except Exception as e:
            # If there's an error (e.g., non-integer input), reset to default
            self.max_threads_var.set(self.config["globalConfig"].get("maxThreads", 3))
            messagebox.showerror("Error", f"Invalid value for Maximum concurrent tasks: {str(e)}")

    def update_repo_url(self):
        """Update the panOsPhpRepoUrl value in the configuration"""
        try:
            # Get the value from the entry field
            repo_url = self.repo_url_var.get().strip()

            # Basic validation - ensure it's not empty and looks like a URL
            if not repo_url:
                messagebox.showerror("Error", "Repository URL cannot be empty")
                # Reset to default or previous value
                self.repo_url_var.set(self.config["globalConfig"].get("panOsPhpRepoUrl", "https://github.com/swaschkut/pan-os-php"))
                return

            # Update the configuration
            self.config["globalConfig"]["panOsPhpRepoUrl"] = repo_url
        except Exception as e:
            # If there's an error, reset to default
            self.repo_url_var.set(self.config["globalConfig"].get("panOsPhpRepoUrl", "https://github.com/swaschkut/pan-os-php"))
            messagebox.showerror("Error", f"Error updating Repository URL: {str(e)}")

    def on_main_canvas_configure(self, event):
        """Handle main canvas resize event"""
        # Update the scrollregion to encompass the inner frame
        self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all"))
        # Resize the window width to match the canvas width
        self.main_canvas.itemconfig(self.main_frame_id, width=event.width)

    def on_extra_args_canvas_configure(self, event):
        """Handle canvas resize event for extra arguments"""
        # Update the scrollregion to encompass the inner frame
        self.extra_args_canvas.configure(scrollregion=self.extra_args_canvas.bbox("all"))
        # Resize the window width to match the canvas width
        self.extra_args_canvas.itemconfig(self.extra_args_frame_id, width=event.width)

    def on_main_frame_configure(self, event):
        """Handle main frame resize event"""
        # Update the scrollregion to encompass the inner frame
        self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all"))

    def on_extra_args_frame_configure(self, event):
        """Handle frame resize event for extra arguments"""
        # Update the scrollregion to encompass the inner frame
        self.extra_args_canvas.configure(scrollregion=self.extra_args_canvas.bbox("all"))

    def _on_main_mousewheel(self, event):
        """Handle mouse wheel scrolling for main canvas"""
        # Scroll the canvas when the mouse wheel is used
        # The delta value is platform-dependent, so we normalize it
        # Windows: event.delta is in multiples of 120
        self.main_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_extra_args_mousewheel(self, event):
        """Handle mouse wheel scrolling for extra arguments"""
        # Scroll the canvas when the mouse wheel is used
        # The delta value is platform-dependent, so we normalize it
        # Windows: event.delta is in multiples of 120
        self.extra_args_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _bind_mousewheel_to_all(self, event=None):
        """Recursively bind mousewheel event to all widgets"""
        self._bind_to_widget_and_children(self.main_frame)

    def _bind_to_widget_and_children(self, widget):
        """Recursively bind mousewheel event to a widget and all its children"""
        # Bind to this widget
        widget.bind("<MouseWheel>", self._on_main_mousewheel)

        # Recursively bind to all children
        for child in widget.winfo_children():
            self._bind_to_widget_and_children(child)

    def _bind_to_extra_args_widget_and_children(self, widget):
        """Recursively bind mousewheel event to a widget and all its children for extra args"""
        # Bind to this widget
        widget.bind("<MouseWheel>", self._on_extra_args_mousewheel)

        # Recursively bind to all children
        for child in widget.winfo_children():
            self._bind_to_extra_args_widget_and_children(child)

    def _on_spg_listbox_mousewheel(self, event):
        """Handle mouse wheel scrolling for SPG listbox"""
        # Scroll the listbox when the mouse wheel is used
        # The delta value is platform-dependent, so we normalize it
        # Windows: event.delta is in multiples of 120
        self.spg_listbox.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_global_mousewheel(self, event):
        """Handle global mouse wheel scrolling by directing to the appropriate widget"""
        # Get the widget under the mouse cursor
        x, y = event.x_root, event.y_root
        widget = event.widget.winfo_containing(x, y)

        # If no widget is found, use the main canvas
        if not widget:
            self._on_main_mousewheel(event)
            return

        # Check if the widget or any of its parents is the main canvas
        parent = widget
        while parent:
            if parent == self.main_canvas:
                self._on_main_mousewheel(event)
                return
            elif parent == self.extra_args_canvas:
                self._on_extra_args_mousewheel(event)
                return
            elif parent == self.spg_listbox:
                self._on_spg_listbox_mousewheel(event)
                return
            try:
                parent = parent.master
            except:
                break

        # Default to main canvas if no specific widget is found
        self._on_main_mousewheel(event)

    def update_extra_args_ui(self):
        """Update the UI for extra arguments based on the current configuration"""
        # Clear existing widgets
        for widget in self.extra_args_frame.winfo_children():
            widget.destroy()

        # Add checkboxes for each extra argument in panAudit.json
        if "extraArguments" in self.config:
            for arg, status in self.config["extraArguments"].items():
                # Create a variable for this checkbox
                var = tk.StringVar(value=status)
                self.extra_args_vars[arg] = var

                # Create a frame for this argument
                arg_frame = ttk.Frame(self.extra_args_frame)
                arg_frame.pack(fill=tk.X, pady=2)

                # Create a label for the argument name
                ttk.Label(arg_frame, text=arg, width=30, anchor="w").pack(side=tk.LEFT, padx=(0, 10))

                # Create radio buttons with labels
                ttk.Radiobutton(arg_frame, text="Enabled", variable=var, value="enabled", 
                               command=lambda a=arg: self.toggle_extra_arg(a)).pack(side=tk.LEFT, padx=(0, 5))
                ttk.Radiobutton(arg_frame, text="Disabled", variable=var, value="disabled", 
                               command=lambda a=arg: self.toggle_extra_arg(a)).pack(side=tk.LEFT)

        # Rebind mousewheel to all widgets after UI update
        self._bind_to_extra_args_widget_and_children(self.extra_args_frame)

    def toggle_extra_arg(self, arg):
        """Toggle the status of an extra argument"""
        if arg in self.extra_args_vars:
            self.config["extraArguments"][arg] = self.extra_args_vars[arg].get()

    def create_security_profile_selection(self, parent_frame):
        """Create the security profile group selection section"""
        # Create a frame for the SPG section with a label - row 3
        spg_section = ttk.Frame(parent_frame)
        spg_section.grid(row=3, column=0, columnspan=3, sticky=tk.W+tk.E, pady=5)

        # Configure grid for spg_section
        spg_section.columnconfigure(0, weight=1)

        ttk.Label(spg_section, text="Security Profile Groups", font=("TkDefaultFont", 10, "bold")).grid(row=0, column=0, sticky=tk.W, pady=5)

        # Create a frame for the list - row 1
        list_frame = ttk.Frame(spg_section)
        list_frame.grid(row=1, column=0, sticky=tk.W+tk.E+tk.N+tk.S, pady=5)

        # Configure grid for list_frame
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        # Create a listbox to display the SPGs with multiple selection support
        self.spg_listbox = tk.Listbox(list_frame, height=6, width=50, selectmode=tk.EXTENDED)
        self.spg_listbox.grid(row=0, column=0, sticky=tk.W+tk.E+tk.N+tk.S)

        # Add a scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.spg_listbox.yview)
        scrollbar.grid(row=0, column=1, sticky=tk.N+tk.S)
        self.spg_listbox.config(yscrollcommand=scrollbar.set)

        # Add mousewheel scrolling for the listbox
        self.spg_listbox.bind("<MouseWheel>", self._on_spg_listbox_mousewheel)

        # Load SPGs from current Panorama config
        self.update_spg_listbox()

        # Create a frame for the buttons - row 2
        button_frame = ttk.Frame(spg_section)
        button_frame.grid(row=2, column=0, sticky=tk.W+tk.E, pady=5)

        # Configure grid for button_frame
        button_frame.columnconfigure(0, weight=0)  # Label
        button_frame.columnconfigure(1, weight=1)  # Entry
        button_frame.columnconfigure(2, weight=0)  # Plus button
        button_frame.columnconfigure(3, weight=0)  # Minus button

        # Add entry for new SPG
        self.new_spg_var = tk.StringVar()
        ttk.Label(button_frame, text="Security Profile Group:").grid(row=0, column=0, padx=5)
        ttk.Entry(button_frame, textvariable=self.new_spg_var, width=30).grid(row=0, column=1, padx=5, sticky=tk.W)

        # Add Plus and Minus buttons
        ttk.Button(button_frame, text="+", width=3, command=self.add_spg).grid(row=0, column=2, padx=5)
        ttk.Button(button_frame, text="-", width=3, command=self.remove_spg).grid(row=0, column=3, padx=5)

    def update_spg_listbox(self):
        """Update the SPG listbox with the SPGs for the current Panorama"""
        # Clear the listbox
        self.spg_listbox.delete(0, tk.END)

        # Get the current Panorama
        current_panorama = self.config["globalConfig"]["currentPanorama"]
        if not current_panorama or current_panorama not in self.config["Panoramas"]:
            return

        # Ensure the auditSPGs key exists for this Panorama
        if "auditSPGs" not in self.config["Panoramas"][current_panorama]:
            self.config["Panoramas"][current_panorama]["auditSPGs"] = []

        # Add the SPGs to the listbox
        for spg in self.config["Panoramas"][current_panorama]["auditSPGs"]:
            self.spg_listbox.insert(tk.END, spg)

    def add_spg(self):
        """Add a new Security Profile Group to the list"""
        spg = self.new_spg_var.get().strip()
        if spg:
            # Get the current Panorama
            current_panorama = self.config["globalConfig"]["currentPanorama"]
            if not current_panorama:
                messagebox.showerror("Error", "Please select a Panorama instance first")
                return

            # Ensure the auditSPGs key exists for this Panorama
            if "auditSPGs" not in self.config["Panoramas"][current_panorama]:
                self.config["Panoramas"][current_panorama]["auditSPGs"] = []

            # Check if the SPG already exists
            if spg not in self.config["Panoramas"][current_panorama]["auditSPGs"]:
                self.spg_listbox.insert(tk.END, spg)
                self.config["Panoramas"][current_panorama]["auditSPGs"].append(spg)
                self.new_spg_var.set("")  # Clear the entry
            else:
                messagebox.showinfo("Info", "This Security Profile Group already exists in the list.")
        else:
            messagebox.showwarning("Warning", "Please enter a Security Profile Group name.")

    def remove_spg(self):
        """Remove the selected Security Profile Groups from the list"""
        selected_indices = self.spg_listbox.curselection()
        if selected_indices:
            # Get the current Panorama
            current_panorama = self.config["globalConfig"]["currentPanorama"]
            if not current_panorama:
                messagebox.showerror("Error", "Please select a Panorama instance first")
                return

            # Ensure the auditSPGs key exists for this Panorama
            if "auditSPGs" not in self.config["Panoramas"][current_panorama]:
                self.config["Panoramas"][current_panorama]["auditSPGs"] = []
                return

            # Convert to list and sort in reverse order to avoid index shifting during deletion
            indices = sorted(list(selected_indices), reverse=True)

            # Remove each selected SPG
            for index in indices:
                spg = self.spg_listbox.get(index)
                self.spg_listbox.delete(index)
                if spg in self.config["Panoramas"][current_panorama]["auditSPGs"]:
                    self.config["Panoramas"][current_panorama]["auditSPGs"].remove(spg)

            # Show confirmation message with count of removed items
            count = len(indices)
            messagebox.showinfo("Success", f"{count} Security Profile Group{'s' if count > 1 else ''} removed.")
        else:
            messagebox.showwarning("Warning", "Please select at least one Security Profile Group to remove.")

    def toggle_disabled_rules(self):
        """Toggle the inclusion of disabled rules in the audit"""
        current_panorama = self.config["globalConfig"]["currentPanorama"]
        if current_panorama and current_panorama in self.config["Panoramas"]:
            self.config["Panoramas"][current_panorama]["includeDisabledRules"] = self.include_disabled_var.get()


    def validate_php(self):
        """Validate PHP installation"""
        validate_php_with_message(self)

    def validate_pan_os_php(self):
        """Validate pan-os-php installation"""
        validate_pan_os_php_with_message(self)

    def git_pull_pan_os_php(self):
        """Update the pan-os-php repository using git pull"""
        # Define a callback function to handle messages from the update_repository function
        def message_callback(message, success):
            if success:
                messagebox.showinfo("Git Pull", message)
            else:
                messagebox.showerror("Git Pull Error", message)

        # Get the utils directory path
        app_dir = os.getcwd()
        utils_dir = os.path.join(app_dir, "panPHP")

        # Get the repo URL from the config
        repo_url = self.config["globalConfig"].get("panOsPhpRepoUrl", "https://github.com/swaschkut/pan-os-php")

        # Update the repository
        update_repository(
            repo_url=repo_url,
            target_dir=utils_dir,
            message_callback=message_callback
        )

    def save_config(self):
        """Save the configuration and close the window"""
        # Update the UI with any changes to the extraArguments section
        self.update_extra_args_ui()
        # Call the save callback to update the main application's config
        self.save_callback(self.config)
        # Close the window
        self.destroy()
