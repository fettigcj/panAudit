import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import json
import os
from collections import OrderedDict

class ModifyAuditsWindow(tk.Toplevel):
    """Window for modifying audit sections and audits in the configuration"""
    def __init__(self, parent, config, save_callback):
        super().__init__(parent)
        self.parent = parent
        self.config = config
        self.save_callback = save_callback

        # Set window properties
        self.title("Modify Audits")
        self.geometry("900x700")
        self.transient(parent)
        self.grab_set()

        # Create the main frame
        self.main_frame = ttk.Frame(self, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Create a toggle for switching between Audits and SPG Audits
        self.create_toggle_frame()

        # Create frames for Audits and SPG Audits
        self.create_audits_frame()
        self.create_spg_audits_frame()

        # Initially show the Audits frame
        self.show_audits_frame()

        # Create buttons frame
        buttons_frame = ttk.Frame(self.main_frame)
        buttons_frame.pack(fill=tk.X, pady=10)

        # Add Save and Cancel buttons
        ttk.Button(buttons_frame, text="Save", command=self.save_config).pack(side=tk.RIGHT, padx=5)
        ttk.Button(buttons_frame, text="Cancel", command=self.destroy).pack(side=tk.RIGHT, padx=5)

    def create_toggle_frame(self):
        """Create a frame with toggle buttons for switching between Audits and SPG Audits"""
        toggle_frame = ttk.Frame(self.main_frame)
        toggle_frame.pack(fill=tk.X, pady=5)

        # Create a variable to track the current view
        self.view_var = tk.StringVar(value="Audits")

        # Create toggle buttons
        ttk.Radiobutton(toggle_frame, text="Audits", variable=self.view_var, 
                       value="Audits", command=self.show_audits_frame).pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(toggle_frame, text="SPG Audits", variable=self.view_var, 
                       value="SPG_Audits", command=self.show_spg_audits_frame).pack(side=tk.LEFT, padx=10)

    def create_audits_frame(self):
        """Create the frame for editing regular audits"""
        self.audits_frame = ttk.LabelFrame(self.main_frame, text="Audit Sections", padding="10")

        # Create a frame for the section list and buttons
        sections_frame = ttk.Frame(self.audits_frame)
        sections_frame.pack(fill=tk.BOTH, expand=True, side=tk.LEFT, padx=(0, 10))

        # Create a label for the sections list
        ttk.Label(sections_frame, text="Sections:").pack(anchor=tk.W, pady=(0, 5))

        # Create a listbox for the sections
        self.sections_listbox = tk.Listbox(sections_frame, height=15, width=30)
        self.sections_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.sections_listbox.bind('<<ListboxSelect>>', self.on_section_selected)

        # Add a scrollbar to the sections listbox
        sections_scrollbar = ttk.Scrollbar(sections_frame, orient=tk.VERTICAL, command=self.sections_listbox.yview)
        sections_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.sections_listbox.config(yscrollcommand=sections_scrollbar.set)

        # Create a frame for the section buttons
        section_buttons_frame = ttk.Frame(sections_frame)
        section_buttons_frame.pack(fill=tk.X, pady=5)

        # Add buttons for adding and removing sections
        ttk.Button(section_buttons_frame, text="Add Section", command=self.add_section).pack(side=tk.LEFT, padx=5)
        ttk.Button(section_buttons_frame, text="Remove Section", command=self.remove_section).pack(side=tk.LEFT, padx=5)

        # Create a frame for the section details
        self.section_details_frame = ttk.LabelFrame(self.audits_frame, text="Section Details", padding="10")
        self.section_details_frame.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

        # Create a frame for the section properties
        section_props_frame = ttk.Frame(self.section_details_frame)
        section_props_frame.pack(fill=tk.X, pady=5)

        # Add fields for section name and description
        ttk.Label(section_props_frame, text="Section Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.section_name_var = tk.StringVar()
        ttk.Entry(section_props_frame, textvariable=self.section_name_var, width=40).grid(row=0, column=1, sticky=tk.W, pady=5)

        ttk.Label(section_props_frame, text="Description:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.section_desc_var = tk.StringVar()
        ttk.Entry(section_props_frame, textvariable=self.section_desc_var, width=40).grid(row=1, column=1, sticky=tk.W, pady=5)

        # Add a button to update section properties
        ttk.Button(section_props_frame, text="Update Section", command=self.update_section).grid(row=2, column=1, sticky=tk.W, pady=5)

        # Create a separator
        ttk.Separator(self.section_details_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        # Create a frame for the audits list and buttons
        audits_list_frame = ttk.Frame(self.section_details_frame)
        audits_list_frame.pack(fill=tk.BOTH, expand=True)

        # Create a label for the audits list
        ttk.Label(audits_list_frame, text="Audits in Section:").pack(anchor=tk.W, pady=(0, 5))

        # Create a listbox for the audits
        self.audits_listbox = tk.Listbox(audits_list_frame, height=10, width=40)
        self.audits_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.audits_listbox.bind('<<ListboxSelect>>', self.on_audit_selected)

        # Add a scrollbar to the audits listbox
        audits_scrollbar = ttk.Scrollbar(audits_list_frame, orient=tk.VERTICAL, command=self.audits_listbox.yview)
        audits_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.audits_listbox.config(yscrollcommand=audits_scrollbar.set)

        # Create a frame for the audit buttons
        audit_buttons_frame = ttk.Frame(audits_list_frame)
        audit_buttons_frame.pack(fill=tk.X, pady=5)

        # Add buttons for adding and removing audits
        ttk.Button(audit_buttons_frame, text="Add Audit", command=self.add_audit).pack(side=tk.LEFT, padx=5)
        ttk.Button(audit_buttons_frame, text="Remove Audit", command=self.remove_audit).pack(side=tk.LEFT, padx=5)

        # Create a frame for the audit details
        self.audit_details_frame = ttk.LabelFrame(self.section_details_frame, text="Audit Details", padding="10")
        self.audit_details_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        # Add fields for audit properties
        ttk.Label(self.audit_details_frame, text="Audit Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.audit_name_var = tk.StringVar()
        ttk.Entry(self.audit_details_frame, textvariable=self.audit_name_var, width=40).grid(row=0, column=1, sticky=tk.W, pady=5)

        ttk.Label(self.audit_details_frame, text="Title:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.audit_title_var = tk.StringVar()
        ttk.Entry(self.audit_details_frame, textvariable=self.audit_title_var, width=40).grid(row=1, column=1, sticky=tk.W, pady=5)

        ttk.Label(self.audit_details_frame, text="Workbook Name:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.audit_workbook_var = tk.StringVar()
        ttk.Entry(self.audit_details_frame, textvariable=self.audit_workbook_var, width=40).grid(row=2, column=1, sticky=tk.W, pady=5)

        ttk.Label(self.audit_details_frame, text="Base Filter:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.audit_filter_var = tk.StringVar()
        ttk.Entry(self.audit_details_frame, textvariable=self.audit_filter_var, width=40).grid(row=3, column=1, sticky=tk.W, pady=5)

        ttk.Label(self.audit_details_frame, text="Description:").grid(row=4, column=0, sticky=tk.NW, pady=5)
        self.audit_desc_text = tk.Text(self.audit_details_frame, height=4, width=40, wrap=tk.WORD)
        self.audit_desc_text.grid(row=4, column=1, sticky=tk.W, pady=5)

        # Add a button to update audit properties
        ttk.Button(self.audit_details_frame, text="Update Audit", command=self.update_audit).grid(row=5, column=1, sticky=tk.W, pady=5)

        # Populate the sections listbox
        self.populate_sections_listbox()

    def create_spg_audits_frame(self):
        """Create the frame for editing SPG audits"""
        self.spg_audits_frame = ttk.LabelFrame(self.main_frame, text="SPG Audits", padding="10")

        # Create a frame for the SPG audits list and buttons
        spg_audits_frame = ttk.Frame(self.spg_audits_frame)
        spg_audits_frame.pack(fill=tk.BOTH, expand=True, side=tk.LEFT, padx=(0, 10))

        # Create a label for the SPG audits list
        ttk.Label(spg_audits_frame, text="SPG Audits:").pack(anchor=tk.W, pady=(0, 5))

        # Create a listbox for the SPG audits
        self.spg_audits_listbox = tk.Listbox(spg_audits_frame, height=15, width=30)
        self.spg_audits_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.spg_audits_listbox.bind('<<ListboxSelect>>', self.on_spg_audit_selected)

        # Add a scrollbar to the SPG audits listbox
        spg_audits_scrollbar = ttk.Scrollbar(spg_audits_frame, orient=tk.VERTICAL, command=self.spg_audits_listbox.yview)
        spg_audits_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.spg_audits_listbox.config(yscrollcommand=spg_audits_scrollbar.set)

        # Create a frame for the SPG audit buttons
        spg_audit_buttons_frame = ttk.Frame(spg_audits_frame)
        spg_audit_buttons_frame.pack(fill=tk.X, pady=5)

        # Add buttons for adding and removing SPG audits
        ttk.Button(spg_audit_buttons_frame, text="Add SPG Audit", command=self.add_spg_audit).pack(side=tk.LEFT, padx=5)
        ttk.Button(spg_audit_buttons_frame, text="Remove SPG Audit", command=self.remove_spg_audit).pack(side=tk.LEFT, padx=5)

        # Create a frame for the SPG audit details
        self.spg_audit_details_frame = ttk.LabelFrame(self.spg_audits_frame, text="SPG Audit Details", padding="10")
        self.spg_audit_details_frame.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

        # Add fields for SPG audit properties
        ttk.Label(self.spg_audit_details_frame, text="Audit Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.spg_audit_name_var = tk.StringVar()
        ttk.Entry(self.spg_audit_details_frame, textvariable=self.spg_audit_name_var, width=40).grid(row=0, column=1, sticky=tk.W, pady=5)

        ttk.Label(self.spg_audit_details_frame, text="Title:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.spg_audit_title_var = tk.StringVar()
        ttk.Entry(self.spg_audit_details_frame, textvariable=self.spg_audit_title_var, width=40).grid(row=1, column=1, sticky=tk.W, pady=5)

        ttk.Label(self.spg_audit_details_frame, text="Workbook Name:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.spg_audit_workbook_var = tk.StringVar()
        ttk.Entry(self.spg_audit_details_frame, textvariable=self.spg_audit_workbook_var, width=40).grid(row=2, column=1, sticky=tk.W, pady=5)

        ttk.Label(self.spg_audit_details_frame, text="Base Filter:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.spg_audit_filter_var = tk.StringVar()
        ttk.Entry(self.spg_audit_details_frame, textvariable=self.spg_audit_filter_var, width=40).grid(row=3, column=1, sticky=tk.W, pady=5)

        ttk.Label(self.spg_audit_details_frame, text="Description:").grid(row=4, column=0, sticky=tk.NW, pady=5)
        self.spg_audit_desc_text = tk.Text(self.spg_audit_details_frame, height=4, width=40, wrap=tk.WORD)
        self.spg_audit_desc_text.grid(row=4, column=1, sticky=tk.W, pady=5)

        # Add a button to update SPG audit properties
        ttk.Button(self.spg_audit_details_frame, text="Update SPG Audit", command=self.update_spg_audit).grid(row=5, column=1, sticky=tk.W, pady=5)

        # Populate the SPG audits listbox
        self.populate_spg_audits_listbox()

    def show_audits_frame(self):
        """Show the Audits frame and hide the SPG Audits frame"""
        self.spg_audits_frame.pack_forget()
        self.audits_frame.pack(fill=tk.BOTH, expand=True, pady=5)

    def show_spg_audits_frame(self):
        """Show the SPG Audits frame and hide the Audits frame"""
        self.audits_frame.pack_forget()
        self.spg_audits_frame.pack(fill=tk.BOTH, expand=True, pady=5)

    def populate_sections_listbox(self):
        """Populate the sections listbox with the sections from the configuration"""
        self.sections_listbox.delete(0, tk.END)
        if "AuditSections" in self.config:
            for section_name in self.config["AuditSections"]:
                self.sections_listbox.insert(tk.END, section_name)

    def populate_spg_audits_listbox(self):
        """Populate the SPG audits listbox with the SPG audits from the configuration"""
        self.spg_audits_listbox.delete(0, tk.END)
        if "SPG_Audits" in self.config:
            for audit_name in self.config["SPG_Audits"]:
                self.spg_audits_listbox.insert(tk.END, audit_name)

    def on_section_selected(self, event):
        """Handle selection of a section in the sections listbox"""
        selection = self.sections_listbox.curselection()
        if not selection:
            return

        section_name = self.sections_listbox.get(selection[0])
        section_data = self.config["AuditSections"].get(section_name, {})

        # Update the section details
        self.section_name_var.set(section_name)
        self.section_desc_var.set(section_data.get("sectionDescription", ""))

        # Populate the audits listbox
        self.audits_listbox.delete(0, tk.END)
        if "sectionAudits" in section_data:
            for audit_name in section_data["sectionAudits"]:
                self.audits_listbox.insert(tk.END, audit_name)

    def on_audit_selected(self, event):
        """Handle selection of an audit in the audits listbox"""
        audit_selection = self.audits_listbox.curselection()
        if not audit_selection:
            return

        # Get section name either from selection or from section_name_var
        section_selection = self.sections_listbox.curselection()
        if section_selection:
            section_name = self.sections_listbox.get(section_selection[0])
        else:
            section_name = self.section_name_var.get()
            if not section_name or section_name not in self.config["AuditSections"]:
                messagebox.showwarning("Warning", "No section is selected or available.")
                return

        audit_name = self.audits_listbox.get(audit_selection[0])

        audit_data = self.config["AuditSections"][section_name]["sectionAudits"].get(audit_name, {})

        # Update the audit details
        self.audit_name_var.set(audit_name)
        self.audit_title_var.set(audit_data.get("title", ""))
        self.audit_workbook_var.set(audit_data.get("workbookName", ""))
        self.audit_filter_var.set(audit_data.get("baseFilter", ""))

        # Clear and update the description text
        self.audit_desc_text.delete(1.0, tk.END)
        self.audit_desc_text.insert(tk.END, audit_data.get("description", ""))

    def on_spg_audit_selected(self, event):
        """Handle selection of an SPG audit in the SPG audits listbox"""
        selection = self.spg_audits_listbox.curselection()
        if not selection:
            return

        audit_name = self.spg_audits_listbox.get(selection[0])
        audit_data = self.config["SPG_Audits"].get(audit_name, {})

        # Update the SPG audit details
        self.spg_audit_name_var.set(audit_name)
        self.spg_audit_title_var.set(audit_data.get("title", ""))
        self.spg_audit_workbook_var.set(audit_data.get("workbookName", ""))
        self.spg_audit_filter_var.set(audit_data.get("baseFilter", ""))

        # Clear and update the description text
        self.spg_audit_desc_text.delete(1.0, tk.END)
        self.spg_audit_desc_text.insert(tk.END, audit_data.get("description", ""))

    def add_section(self):
        """Add a new section to the configuration"""
        section_name = simpledialog.askstring("Add Section", "Enter section name:")
        if not section_name:
            return

        if section_name in self.config["AuditSections"]:
            messagebox.showinfo("Info", "This section already exists.")
            return

        # Add the new section to the configuration
        self.config["AuditSections"][section_name] = {
            "sectionDescription": "",
            "sectionAudits": {}
        }

        # Update the sections listbox
        self.populate_sections_listbox()

        # Select the new section
        index = list(self.config["AuditSections"].keys()).index(section_name)
        self.sections_listbox.selection_clear(0, tk.END)
        self.sections_listbox.selection_set(index)
        self.sections_listbox.see(index)
        self.on_section_selected(None)

    def remove_section(self):
        """Remove the selected section from the configuration"""
        selection = self.sections_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a section to remove.")
            return

        section_name = self.sections_listbox.get(selection[0])
        section_data = self.config["AuditSections"].get(section_name, {})

        # Check if the section has audits
        if "sectionAudits" in section_data and section_data["sectionAudits"]:
            confirm = messagebox.askyesno(
                "Confirm Deletion",
                f"The section '{section_name}' contains audits. Are you sure you want to remove it?"
            )
            if not confirm:
                return

        # Remove the section from the configuration
        del self.config["AuditSections"][section_name]

        # Update the sections listbox
        self.populate_sections_listbox()

        # Clear the section details
        self.section_name_var.set("")
        self.section_desc_var.set("")
        self.audits_listbox.delete(0, tk.END)

    def update_section(self):
        """Update the selected section with the current values"""
        selection = self.sections_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a section to update.")
            return

        old_section_name = self.sections_listbox.get(selection[0])
        new_section_name = self.section_name_var.get()

        if not new_section_name:
            messagebox.showwarning("Warning", "Section name cannot be empty.")
            return

        if new_section_name != old_section_name and new_section_name in self.config["AuditSections"]:
            messagebox.showinfo("Info", "A section with this name already exists.")
            return

        # Get the section data
        section_data = self.config["AuditSections"][old_section_name]

        # Update the section description
        section_data["sectionDescription"] = self.section_desc_var.get()

        # If the section name has changed, update it
        if new_section_name != old_section_name:
            # Create a new section with the new name
            self.config["AuditSections"][new_section_name] = section_data
            # Remove the old section
            del self.config["AuditSections"][old_section_name]

            # Update the sections listbox
            self.populate_sections_listbox()

            # Select the new section
            index = list(self.config["AuditSections"].keys()).index(new_section_name)
            self.sections_listbox.selection_clear(0, tk.END)
            self.sections_listbox.selection_set(index)
            self.sections_listbox.see(index)

        messagebox.showinfo("Success", "Section updated successfully.")

    def add_audit(self):
        """Add a new audit to the selected section"""
        section_selection = self.sections_listbox.curselection()
        if not section_selection:
            # Try to get the current section from the section_name_var
            section_name = self.section_name_var.get()
            if not section_name or section_name not in self.config["AuditSections"]:
                messagebox.showwarning("Warning", "Please select a section to add an audit to.")
                return
        else:
            section_name = self.sections_listbox.get(section_selection[0])

        audit_name = simpledialog.askstring("Add Audit", "Enter audit name:")
        if not audit_name:
            return

        if audit_name in self.config["AuditSections"][section_name].get("sectionAudits", {}):
            messagebox.showinfo("Info", "This audit already exists in the selected section.")
            return

        # Ensure sectionAudits exists
        if "sectionAudits" not in self.config["AuditSections"][section_name]:
            self.config["AuditSections"][section_name]["sectionAudits"] = {}

        # Add the new audit to the configuration
        self.config["AuditSections"][section_name]["sectionAudits"][audit_name] = {
            "title": audit_name,
            "workbookName": f"S{{sectNum}}A{{auditNum}}_{audit_name}.xls",
            "baseFilter": "",
            "description": ""
        }

        # Update the audits listbox
        self.audits_listbox.delete(0, tk.END)
        for audit in self.config["AuditSections"][section_name]["sectionAudits"]:
            self.audits_listbox.insert(tk.END, audit)

        # Select the new audit
        index = list(self.config["AuditSections"][section_name]["sectionAudits"].keys()).index(audit_name)
        self.audits_listbox.selection_clear(0, tk.END)
        self.audits_listbox.selection_set(index)
        self.audits_listbox.see(index)
        self.on_audit_selected(None)

    def remove_audit(self):
        """Remove the selected audit from the selected section"""
        audit_selection = self.audits_listbox.curselection()
        if not audit_selection:
            messagebox.showwarning("Warning", "Please select an audit to remove.")
            return

        # Get section name either from selection or from section_name_var
        section_selection = self.sections_listbox.curselection()
        if section_selection:
            section_name = self.sections_listbox.get(section_selection[0])
        else:
            section_name = self.section_name_var.get()
            if not section_name or section_name not in self.config["AuditSections"]:
                messagebox.showwarning("Warning", "No section is selected or available.")
                return

        audit_name = self.audits_listbox.get(audit_selection[0])

        confirm = messagebox.askyesno(
            "Confirm Deletion",
            f"Are you sure you want to remove the audit '{audit_name}' from section '{section_name}'?"
        )
        if not confirm:
            return

        # Remove the audit from the configuration
        del self.config["AuditSections"][section_name]["sectionAudits"][audit_name]

        # Update the audits listbox
        self.audits_listbox.delete(0, tk.END)
        for audit in self.config["AuditSections"][section_name]["sectionAudits"]:
            self.audits_listbox.insert(tk.END, audit)

        # Clear the audit details
        self.audit_name_var.set("")
        self.audit_title_var.set("")
        self.audit_workbook_var.set("")
        self.audit_filter_var.set("")
        self.audit_desc_text.delete(1.0, tk.END)

    def update_audit(self):
        """Update the selected audit with the current values"""
        audit_selection = self.audits_listbox.curselection()
        if not audit_selection:
            messagebox.showwarning("Warning", "Please select an audit to update.")
            return

        # Get section name either from selection or from section_name_var
        section_selection = self.sections_listbox.curselection()
        if section_selection:
            section_name = self.sections_listbox.get(section_selection[0])
        else:
            section_name = self.section_name_var.get()
            if not section_name or section_name not in self.config["AuditSections"]:
                messagebox.showwarning("Warning", "No section is selected or available.")
                return

        old_audit_name = self.audits_listbox.get(audit_selection[0])
        new_audit_name = self.audit_name_var.get()

        if not new_audit_name:
            messagebox.showwarning("Warning", "Audit name cannot be empty.")
            return

        if new_audit_name != old_audit_name and new_audit_name in self.config["AuditSections"][section_name]["sectionAudits"]:
            messagebox.showinfo("Info", "An audit with this name already exists in the selected section.")
            return

        # Get the audit data
        audit_data = self.config["AuditSections"][section_name]["sectionAudits"][old_audit_name]

        # Update the audit properties
        audit_data["title"] = self.audit_title_var.get()
        audit_data["workbookName"] = self.audit_workbook_var.get()
        audit_data["baseFilter"] = self.audit_filter_var.get()
        audit_data["description"] = self.audit_desc_text.get(1.0, tk.END).strip()

        # If the audit name has changed, update it
        if new_audit_name != old_audit_name:
            # Create a new audit with the new name
            self.config["AuditSections"][section_name]["sectionAudits"][new_audit_name] = audit_data
            # Remove the old audit
            del self.config["AuditSections"][section_name]["sectionAudits"][old_audit_name]

            # Update the audits listbox
            self.audits_listbox.delete(0, tk.END)
            for audit in self.config["AuditSections"][section_name]["sectionAudits"]:
                self.audits_listbox.insert(tk.END, audit)

            # Select the new audit
            index = list(self.config["AuditSections"][section_name]["sectionAudits"].keys()).index(new_audit_name)
            self.audits_listbox.selection_clear(0, tk.END)
            self.audits_listbox.selection_set(index)
            self.audits_listbox.see(index)

        messagebox.showinfo("Success", "Audit updated successfully.")

    def add_spg_audit(self):
        """Add a new SPG audit to the configuration"""
        audit_name = simpledialog.askstring("Add SPG Audit", "Enter SPG audit name:")
        if not audit_name:
            return

        if audit_name in self.config["SPG_Audits"]:
            messagebox.showinfo("Info", "This SPG audit already exists.")
            return

        # Add the new SPG audit to the configuration
        self.config["SPG_Audits"][audit_name] = {
            "title": audit_name,
            "workbookName": f"spg{{spgNum}}A{{auditNum}}_{audit_name}.xls",
            "baseFilter": "",
            "description": ""
        }

        # Update the SPG audits listbox
        self.populate_spg_audits_listbox()

        # Select the new SPG audit
        index = list(self.config["SPG_Audits"].keys()).index(audit_name)
        self.spg_audits_listbox.selection_clear(0, tk.END)
        self.spg_audits_listbox.selection_set(index)
        self.spg_audits_listbox.see(index)
        self.on_spg_audit_selected(None)

    def remove_spg_audit(self):
        """Remove the selected SPG audit from the configuration"""
        selection = self.spg_audits_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an SPG audit to remove.")
            return

        audit_name = self.spg_audits_listbox.get(selection[0])

        confirm = messagebox.askyesno(
            "Confirm Deletion",
            f"Are you sure you want to remove the SPG audit '{audit_name}'?"
        )
        if not confirm:
            return

        # Remove the SPG audit from the configuration
        del self.config["SPG_Audits"][audit_name]

        # Update the SPG audits listbox
        self.populate_spg_audits_listbox()

        # Clear the SPG audit details
        self.spg_audit_name_var.set("")
        self.spg_audit_title_var.set("")
        self.spg_audit_workbook_var.set("")
        self.spg_audit_filter_var.set("")
        self.spg_audit_desc_text.delete(1.0, tk.END)

    def update_spg_audit(self):
        """Update the selected SPG audit with the current values"""
        selection = self.spg_audits_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an SPG audit to update.")
            return

        old_audit_name = self.spg_audits_listbox.get(selection[0])
        new_audit_name = self.spg_audit_name_var.get()

        if not new_audit_name:
            messagebox.showwarning("Warning", "SPG audit name cannot be empty.")
            return

        if new_audit_name != old_audit_name and new_audit_name in self.config["SPG_Audits"]:
            messagebox.showinfo("Info", "An SPG audit with this name already exists.")
            return

        # Get the SPG audit data
        audit_data = self.config["SPG_Audits"][old_audit_name]

        # Update the SPG audit properties
        audit_data["title"] = self.spg_audit_title_var.get()
        audit_data["workbookName"] = self.spg_audit_workbook_var.get()
        audit_data["baseFilter"] = self.spg_audit_filter_var.get()
        audit_data["description"] = self.spg_audit_desc_text.get(1.0, tk.END).strip()

        # If the SPG audit name has changed, update it
        if new_audit_name != old_audit_name:
            # Create a new SPG audit with the new name
            self.config["SPG_Audits"][new_audit_name] = audit_data
            # Remove the old SPG audit
            del self.config["SPG_Audits"][old_audit_name]

            # Update the SPG audits listbox
            self.populate_spg_audits_listbox()

            # Select the new SPG audit
            index = list(self.config["SPG_Audits"].keys()).index(new_audit_name)
            self.spg_audits_listbox.selection_clear(0, tk.END)
            self.spg_audits_listbox.selection_set(index)
            self.spg_audits_listbox.see(index)

        messagebox.showinfo("Success", "SPG audit updated successfully.")

    def save_config(self):
        """Save the configuration and close the window"""
        try:
            # Call the save callback to update the main application's config
            self.save_callback(self.config)
            # Close the window
            self.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save configuration: {str(e)}")
