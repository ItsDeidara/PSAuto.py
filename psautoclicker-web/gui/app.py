import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import json
import os
import threading
import queue
from .remote import SessionWorker
from .controller import BUTTON_MAP
from .controls import MANUAL_CONTROLS
from .autoclicker import Autoclicker
from .macro import Macro, MacroRunner
import glob
from colorama import init as colorama_init, Fore, Style
import sys
import requests
import shutil

def resource_path(filename):
    """Get absolute path to resource, works for dev and for PyInstaller bundle."""
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, filename)

SAVED_IPS_PATH = resource_path('saved_ips.json')

# Initialize colorama for colored terminal output
colorama_init(autoreset=True)

# Tooltip helper
class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)
    def show(self, event=None):
        if self.tipwindow or not self.text:
            return
        # Default position
        x = self.widget.winfo_rootx() + 25
        y = self.widget.winfo_rooty() + 20
        # Try to use bbox("insert") only for Entry/Text widgets
        try:
            if isinstance(self.widget, (tk.Entry, tk.Text)):
                bbox = self.widget.bbox("insert")
                if bbox:
                    x = bbox[0] + self.widget.winfo_rootx() + 25
                    y = bbox[1] + self.widget.winfo_rooty() + 20
        except Exception:
            pass
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(1)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=self.text, justify=tk.LEFT,
                         background="#ffffe0", relief=tk.SOLID, borderwidth=1,
                         font=("tahoma", "8", "normal"))
        label.pack(ipadx=1)
    def hide(self, event=None):
        tw = self.tipwindow
        self.tipwindow = None
        if tw:
            tw.destroy()

class ScrollableFrame(ttk.Frame):
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)
        self.scrollable_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

class PSRemotePlayGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        # Set window/taskbar/dock icon for Windows and macOS
        import sys, os
        try:
            if getattr(sys, 'frozen', False):
                base_path = sys._MEIPASS
            else:
                base_path = os.path.dirname(os.path.abspath(__file__))
            ico_path = os.path.join(base_path, '..', 'app_icon.ico')
            png_path = os.path.join(base_path, '..', 'app_icon.png')
            # Try .ico for Windows
            if os.path.exists(ico_path):
                self.iconbitmap(ico_path)
            # Try .png for iconphoto (cross-platform)
            if os.path.exists(png_path):
                try:
                    from PIL import Image, ImageTk
                    img = ImageTk.PhotoImage(file=png_path)
                    self.iconphoto(True, img)
                except Exception:
                    pass
        except Exception as e:
            print(f"Could not set icon: {e}")
        self.title("PSAuto-py")
        self.geometry("900x600")
        self.minsize(700, 400)
        self.command_queue = queue.Queue()
        self.worker = None
        self.autoclicker = None
        self.current_macro_runner = None
        self.macros = {}
        self.running_macros = {}
        self.current_macro_name = None
        self.current_macro_steps = []
        self.current_eol_macro_steps = []
        self.macro_name_var = tk.StringVar()
        self.hosts = {}
        self.left_stick_duration_var = tk.StringVar(value="1000")
        self.right_stick_duration_var = tk.StringVar(value="1000")
        self._build_widgets()
        self._load_hosts()
        self.connected = False
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.refresh_macro_list()

    def _build_widgets(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        nb = ttk.Notebook(self)
        nb.grid(row=0, column=0, sticky="nsew")

        # --- Controls Tab ---
        controls_tab = ttk.Frame(nb)
        nb.add(controls_tab, text="Controls")
        controls_tab.grid_rowconfigure(0, weight=1)
        controls_tab.grid_columnconfigure(0, weight=1)
        controls_scroll = ScrollableFrame(controls_tab)
        controls_scroll.pack(fill="both", expand=True)
        frm = controls_scroll.scrollable_frame
        # Host selection
        host_frm = ttk.Frame(frm)
        host_frm.pack(fill="x", pady=(5, 0))
        host_label = ttk.Label(host_frm, text="Select Host:")
        host_label.pack(side="left")
        ToolTip(host_label, "Choose the PlayStation or device you want to control.")
        self.host_var = tk.StringVar()
        self.host_combo = ttk.Combobox(host_frm, textvariable=self.host_var, state="readonly")
        self.host_combo.pack(side="left", fill="x", expand=True, padx=5)
        ToolTip(self.host_combo, "Pick from your saved devices.")
        # Host CRUD buttons
        add_btn = ttk.Button(host_frm, text="Add", command=self.add_host_dialog)
        add_btn.pack(side="left", padx=2)
        ToolTip(add_btn, "Add a new PlayStation or device.")
        edit_btn = ttk.Button(host_frm, text="Edit", command=self.edit_host_dialog)
        edit_btn.pack(side="left", padx=2)
        ToolTip(edit_btn, "Edit the selected device's info.")
        del_btn = ttk.Button(host_frm, text="Delete", command=self.delete_host)
        del_btn.pack(side="left", padx=2)
        ToolTip(del_btn, "Remove the selected device from your list.")
        self.connect_btn = ttk.Button(host_frm, text="Connect", command=self.on_connect)
        self.connect_btn.pack(side="left", padx=5)
        ToolTip(self.connect_btn, "Connect to the selected device.")
        self.disconnect_btn = ttk.Button(host_frm, text="Disconnect", command=self.on_disconnect, state=tk.DISABLED)
        self.disconnect_btn.pack(side="left", padx=5)
        ToolTip(self.disconnect_btn, "Disconnect from the current device.")
        self.status_var = tk.StringVar(value="Disconnected")
        status_label = ttk.Label(frm, textvariable=self.status_var, foreground="blue")
        status_label.pack(anchor="w", pady=(2, 5))
        ToolTip(status_label, "Shows if you are connected or not.")
        # Manual Controls (grouped)
        self.left_stick_duration_var = tk.StringVar(value="1000")
        self.right_stick_duration_var = tk.StringVar(value="1000")
        for group in MANUAL_CONTROLS:
            group_frm = ttk.LabelFrame(frm, text=group["label"])
            group_frm.pack(fill="x", pady=(8, 0), padx=2)
            for i, (display, code) in enumerate(group["buttons"]):
                btn = ttk.Button(group_frm, text=display, width=12, command=lambda c=code: self.send_button(c))
                btn.grid(row=0, column=i, padx=2, pady=2, sticky="ew")
                ToolTip(btn, f"Send {display} command to the PlayStation.")
            group_frm.grid_columnconfigure(tuple(range(len(group["buttons"]))), weight=1)
            # Add duration entry for stick groups
            if group["label"] == "Left Stick":
                dur_label = ttk.Label(group_frm, text="Duration (ms):")
                dur_label.grid(row=1, column=0, sticky="e", padx=2)
                ToolTip(dur_label, "How long the left stick stays in the chosen direction before returning to center.")
                dur_entry = tk.Entry(group_frm, textvariable=self.left_stick_duration_var, width=8)
                dur_entry.grid(row=1, column=1, sticky="w", padx=2)
                ToolTip(dur_entry, "Enter the time in milliseconds (1000 ms = 1 second).")
            elif group["label"] == "Right Stick":
                dur_label = ttk.Label(group_frm, text="Duration (ms):")
                dur_label.grid(row=1, column=0, sticky="e", padx=2)
                ToolTip(dur_label, "How long the right stick stays in the chosen direction before returning to center.")
                dur_entry = tk.Entry(group_frm, textvariable=self.right_stick_duration_var, width=8)
                dur_entry.grid(row=1, column=1, sticky="w", padx=2)
                ToolTip(dur_entry, "Enter the time in milliseconds (1000 ms = 1 second).")
        # Autoclicker section (now in Controls tab)
        auto_frm = ttk.LabelFrame(frm, text="Autoclicker")
        auto_frm.pack(fill="x", pady=(10, 0), padx=2)
        ToolTip(auto_frm, "Automatically press a button or move a stick repeatedly.")
        auto_btn_label = ttk.Label(auto_frm, text="Button/Stick:")
        auto_btn_label.grid(row=0, column=0, sticky="w")
        ToolTip(auto_btn_label, "Choose which button or stick to autoclick.")
        btn_choices = [display for group in MANUAL_CONTROLS for display, _ in group["buttons"]]
        self.auto_btn_var = tk.StringVar(value="CROSS")
        self.auto_btn_combo = ttk.Combobox(auto_frm, textvariable=self.auto_btn_var, values=btn_choices, state="readonly", width=14)
        self.auto_btn_combo.grid(row=0, column=1, padx=2)
        ToolTip(self.auto_btn_combo, "Pick the button or stick to autoclick.")
        auto_interval_label = ttk.Label(auto_frm, text="Interval (ms):")
        auto_interval_label.grid(row=0, column=2, sticky="w")
        ToolTip(auto_interval_label, "How often to press the button or move the stick (in milliseconds). Lower = faster.")
        self.auto_interval_var = tk.StringVar(value="100")
        self.auto_interval_entry = ttk.Entry(auto_frm, textvariable=self.auto_interval_var, width=6)
        self.auto_interval_entry.grid(row=0, column=3, padx=2)
        ToolTip(self.auto_interval_entry, "Enter the time between presses (100 ms = 0.1 second). Minimum is 10 ms.")
        self.auto_start_btn = ttk.Button(auto_frm, text="Start", command=self.start_autoclicker)
        self.auto_start_btn.grid(row=0, column=4, padx=2)
        ToolTip(self.auto_start_btn, "Start the autoclicker.")
        self.auto_stop_btn = ttk.Button(auto_frm, text="Stop", command=self.stop_autoclicker, state=tk.DISABLED)
        self.auto_stop_btn.grid(row=0, column=5, padx=2)
        ToolTip(self.auto_stop_btn, "Stop the autoclicker.")
        # Log area (now in Controls tab)
        self.log_area = scrolledtext.ScrolledText(frm, height=8, state=tk.DISABLED)
        self.log_area.pack(fill="both", expand=True, padx=5, pady=10)
        ToolTip(self.log_area, "Shows messages, errors, and what the app is doing.")

        # --- Macro Manager Tab ---
        macro_tab = ttk.Frame(nb)
        nb.add(macro_tab, text="Macro Manager")
        macro_tab.grid_rowconfigure(0, weight=1)
        macro_tab.grid_columnconfigure(0, weight=1)
        macro_pane = ttk.PanedWindow(macro_tab, orient=tk.HORIZONTAL)
        macro_pane.pack(fill="both", expand=True)
        # Macro List (left)
        macro_list_frm = ttk.Frame(macro_pane)
        macro_list_frm.pack(fill="both", expand=True)
        macro_list_label = ttk.Label(macro_list_frm, text="Saved Macros:")
        macro_list_label.pack(anchor="w", padx=4, pady=(4, 0))
        ToolTip(macro_list_label, "List of all your saved macros. Select one to edit or run.")
        self.macro_listbox = tk.Listbox(macro_list_frm, selectmode=tk.EXTENDED, height=12)
        self.macro_listbox.pack(fill="both", expand=True, padx=4, pady=2)
        macro_list_btns = ttk.Frame(macro_list_frm)
        macro_list_btns.pack(fill="x", padx=4, pady=2)
        load_btn = ttk.Button(macro_list_btns, text="Load", command=self.on_macro_select)
        load_btn.pack(side="left", padx=2)
        ToolTip(load_btn, "Load the selected macro for editing or running.")
        save_btn = ttk.Button(macro_list_btns, text="Save", command=self.save_macro)
        save_btn.pack(side="left", padx=2)
        ToolTip(save_btn, "Save your changes to the current macro.")
        import_btn = ttk.Button(macro_list_btns, text="Import", command=self.import_macro)
        import_btn.pack(side="left", padx=2)
        ToolTip(import_btn, "Import macros from files.")
        export_btn = ttk.Button(macro_list_btns, text="Export", command=self.export_macro)
        export_btn.pack(side="left", padx=2)
        ToolTip(export_btn, "Export the selected macro to a file.")
        run_btn = ttk.Button(macro_list_btns, text="Run Selected", command=self.run_selected_macros)
        run_btn.pack(side="left", padx=2)
        ToolTip(run_btn, "Start the selected macro(s).")
        stop_btn = ttk.Button(macro_list_btns, text="Stop Selected", command=self.stop_selected_macros)
        stop_btn.pack(side="left", padx=2)
        ToolTip(stop_btn, "Stop the selected macro(s).")
        # Add Download Macros from Git button
        download_git_btn = ttk.Button(macro_list_btns, text="Download Macros from Git", command=self.download_macros_from_github)
        download_git_btn.pack(side="left", padx=2)
        ToolTip(download_git_btn, "Download the latest macros from the official GitHub repository. Any macros with the same name will be replaced.")
        # Optionally, auto-load on selection:
        self.macro_listbox.bind('<<ListboxSelect>>', self.on_macro_select)
        macro_pane.add(macro_list_frm, weight=1)
        # Macro Step Editor (right)
        macro_edit_frm = ttk.Frame(macro_pane)
        macro_edit_frm.pack(fill="both", expand=True)
        macro_steps_label = ttk.Label(macro_edit_frm, text="Macro Steps:")
        macro_steps_label.pack(anchor="w", padx=4, pady=(4, 0))
        ToolTip(macro_steps_label, "Steps in the selected macro. Each step is a button press, stick move, or autoclicker.")
        self.macro_steps_tree = ttk.Treeview(macro_edit_frm, columns=("Type", "Name/Dir", "Mag", "Delay", "Comment"), show="headings", selectmode="browse", height=10)
        self.macro_steps_tree.heading("Type", text="Type")
        self.macro_steps_tree.heading("Name/Dir", text="Name/Direction")
        self.macro_steps_tree.heading("Mag", text="Magnitude")
        self.macro_steps_tree.heading("Delay", text="Delay (ms)")
        self.macro_steps_tree.heading("Comment", text="Comment")
        self.macro_steps_tree.column("Type", width=70)
        self.macro_steps_tree.column("Name/Dir", width=120)
        self.macro_steps_tree.column("Mag", width=70)
        self.macro_steps_tree.column("Delay", width=80)
        self.macro_steps_tree.column("Comment", width=180)
        self.macro_steps_tree.pack(fill="both", expand=True, padx=4, pady=2)
        ToolTip(self.macro_steps_tree, "Shows all the steps in your macro. Double-click to edit. Comments explain each step.")
        # Loop count controls
        loop_frm = ttk.Frame(macro_edit_frm)
        loop_frm.pack(fill="x", padx=4, pady=2)
        loop_label = ttk.Label(loop_frm, text="Loop Count:")
        loop_label.pack(side="left")
        ToolTip(loop_label, "How many times to repeat the macro. Use 'Infinite' for endless loops.")
        self.macro_loop_count_var = tk.StringVar(value="1")
        self.macro_infinite_var = tk.BooleanVar(value=False)
        loop_entry = ttk.Entry(loop_frm, textvariable=self.macro_loop_count_var, width=5)
        loop_entry.pack(side="left", padx=2)
        ToolTip(loop_entry, "Enter the number of times to run the macro. -1 means infinite.")
        inf_check = ttk.Checkbutton(loop_frm, text="Infinite", variable=self.macro_infinite_var, command=lambda: self.macro_loop_count_var.set("-1") if self.macro_infinite_var.get() else self.macro_loop_count_var.set("1"))
        inf_check.pack(side="left", padx=2)
        ToolTip(inf_check, "Check for infinite macro looping.")
        # End-of-loop macro controls
        eol_frm = ttk.LabelFrame(macro_edit_frm, text="End-of-Loop Macro")
        eol_frm.pack(fill="x", padx=4, pady=4)
        ToolTip(eol_frm, "Add extra steps or another macro to run at the end of each loop.")
        eol_label = ttk.Label(eol_frm, text="Use saved macro:")
        eol_label.pack(side="left")
        ToolTip(eol_label, "Choose a macro to run at the end of each loop, or pick 'Custom' to make your own.")
        self.eol_macro_var = tk.StringVar(value="None")
        eol_macro_choices = ["None", "Custom"] + sorted(self.macros.keys())
        self.eol_macro_combo = ttk.Combobox(eol_frm, textvariable=self.eol_macro_var, values=eol_macro_choices, state="readonly", width=16)
        self.eol_macro_combo.pack(side="left", padx=2)
        ToolTip(self.eol_macro_combo, "Pick a macro or 'Custom' for your own steps.")
        edit_eol_btn = ttk.Button(eol_frm, text="Edit Custom", command=self.edit_eol_macro_dialog)
        edit_eol_btn.pack(side="left", padx=2)
        ToolTip(edit_eol_btn, "Edit the custom end-of-loop steps.")
        self.eol_macro_steps_tree = ttk.Treeview(eol_frm, columns=("Type", "Name/Dir", "Mag", "Delay", "Comment"), show="headings", height=4)
        for col in ("Type", "Name/Dir", "Mag", "Delay", "Comment"):
            self.eol_macro_steps_tree.heading(col, text=col)
            self.eol_macro_steps_tree.column(col, width=70 if col!="Name/Dir" and col!="Comment" else 120 if col=="Name/Dir" else 180)
        self.eol_macro_steps_tree.pack(fill="x", padx=2, pady=2)
        ToolTip(self.eol_macro_steps_tree, "Shows the steps for the end-of-loop macro.")
        self.eol_macro_var.trace_add("write", lambda *_: self.update_eol_macro_steps_tree())
        macro_step_btns = ttk.Frame(macro_edit_frm)
        macro_step_btns.pack(fill="x", padx=4, pady=2)
        add_step_btn = ttk.Button(macro_step_btns, text="Add Step", command=self.add_macro_step_dialog)
        add_step_btn.pack(side="left", padx=2)
        ToolTip(add_step_btn, "Add a new step to the macro.")
        edit_step_btn = ttk.Button(macro_step_btns, text="Edit Step", command=self.edit_macro_step)
        edit_step_btn.pack(side="left", padx=2)
        ToolTip(edit_step_btn, "Edit the selected step.")
        remove_step_btn = ttk.Button(macro_step_btns, text="Remove Step", command=self.remove_macro_step)
        remove_step_btn.pack(side="left", padx=2)
        ToolTip(remove_step_btn, "Delete the selected step from the macro.")
        move_up_btn = ttk.Button(macro_step_btns, text="Move Up", command=self.move_macro_step_up)
        move_up_btn.pack(side="left", padx=2)
        ToolTip(move_up_btn, "Move the selected step up.")
        move_down_btn = ttk.Button(macro_step_btns, text="Move Down", command=self.move_macro_step_down)
        move_down_btn.pack(side="left", padx=2)
        ToolTip(move_down_btn, "Move the selected step down.")
        repeat_btn = ttk.Button(macro_step_btns, text="Repeat Step", command=self.repeat_macro_step)
        repeat_btn.pack(side="left", padx=2)
        ToolTip(repeat_btn, "Duplicate the selected step.")
        macro_edit_frm.grid_rowconfigure(1, weight=1)
        macro_edit_frm.grid_columnconfigure(0, weight=1)
        macro_pane.add(macro_edit_frm, weight=3)
        # Macro state
        self.refresh_macro_list()
        self.update_eol_macro_steps_tree()
        # Macro-level description field
        macro_desc_label = ttk.Label(macro_edit_frm, text="Macro Description:")
        macro_desc_label.pack(anchor="w", padx=4, pady=(4, 0))
        ToolTip(macro_desc_label, "Describe the purpose of this macro.")
        # Replace single-line Entry with a multi-line, word-wrapped ScrolledText
        self.macro_desc_text = scrolledtext.ScrolledText(macro_edit_frm, wrap=tk.WORD, width=40, height=4)
        self.macro_desc_text.pack(fill="x", padx=4, pady=(0, 4))
        ToolTip(self.macro_desc_text, "This description will be saved with the macro and shown in the preview.")

        # ... after macro_edit_frm.pack(fill="both", expand=True)
        self.macro_status_var = tk.StringVar(value="No macro selected.")
        self.macro_status_label = ttk.Label(macro_tab, textvariable=self.macro_status_var, anchor="w", font=("Segoe UI", 10, "bold"))
        self.macro_status_label.pack(fill="x", side="bottom", padx=4, pady=2)

    def set_macro_status(self, status, color="black"):
        self.macro_status_var.set(status)
        self.macro_status_label.config(foreground=color)

    def _load_hosts(self):
        # Ensure saved_ips.json exists for safety
        if not os.path.exists(SAVED_IPS_PATH):
            with open(SAVED_IPS_PATH, 'w') as f:
                json.dump({}, f)
        self.hosts = self._read_hosts()
        host_list = [entry['host'] if not entry.get('label') else f"{entry['label']} ({entry['host']})" for entry in self.hosts.values()]
        self.host_combo['values'] = host_list
        if host_list:
            self.host_combo.current(0)

    def _read_hosts(self):
        if os.path.exists(SAVED_IPS_PATH):
            with open(SAVED_IPS_PATH, 'r') as f:
                return json.load(f)
        return {}

    def _write_hosts(self):
        with open(SAVED_IPS_PATH, 'w') as f:
            json.dump(self.hosts, f, indent=2)

    def log(self, msg, level="info"):
        self.log_area.config(state=tk.NORMAL)
        tag = level
        if not self.log_area.tag_names():
            self.log_area.tag_configure("info", foreground="black")
            self.log_area.tag_configure("success", foreground="green")
            self.log_area.tag_configure("warning", foreground="orange")
            self.log_area.tag_configure("error", foreground="red")
        self.log_area.insert(tk.END, msg + '\n', tag)
        self.log_area.see(tk.END)
        self.log_area.config(state=tk.DISABLED)
        # Also print to terminal with color
        if level == "info":
            print(Fore.WHITE + msg)
        elif level == "success":
            print(Fore.GREEN + msg)
        elif level == "warning":
            print(Fore.YELLOW + msg)
        elif level == "error":
            print(Fore.RED + msg)
        else:
            print(msg)

    def set_status(self, status):
        self.status_var.set(status)

    def on_connect(self):
        host = self.host_var.get()
        if not host:
            messagebox.showerror("No Host", "Please select a host.")
            return
        self.connect_btn.config(state=tk.DISABLED)
        self.disconnect_btn.config(state=tk.NORMAL)
        self.set_status("Connecting...")
        self.log(f"Connecting to {host}...", level="info")
        self.worker = SessionWorker(host, self.command_queue, self.log, self.on_connected, self.on_disconnected)
        self.worker.start()

    def on_disconnect(self):
        if self.worker:
            self.worker.disconnect()
        self.set_status("Disconnecting...")
        self.log("Disconnecting...", level="info")
        self.connect_btn.config(state=tk.NORMAL)
        self.disconnect_btn.config(state=tk.DISABLED)

    def on_connected(self):
        self.set_status("Connected")
        self.log("Connected!", level="success")
        self.connected = True

    def on_disconnected(self):
        self.set_status("Disconnected")
        self.log("Disconnected.", level="warning")
        self.connect_btn.config(state=tk.NORMAL)
        self.disconnect_btn.config(state=tk.DISABLED)
        self.connected = False

    def send_button(self, btn):
        if not self.connected:
            self.log("Not connected.", level="warning")
            return
        # btn can be a button code or a stick tuple
        self.command_queue.put(btn)
        if isinstance(btn, tuple):
            stick, direction, magnitude = btn
            self.log(f"Enqueued stick: {stick} {direction} {magnitude}", level="info")
            # Only auto-reset for manual control (not macro/autoclicker)
            if direction != "NEUTRAL":
                if stick == "LEFT_STICK":
                    try:
                        duration = int(self.left_stick_duration_var.get())
                    except Exception:
                        duration = 1000
                elif stick == "RIGHT_STICK":
                    try:
                        duration = int(self.right_stick_duration_var.get())
                    except Exception:
                        duration = 1000
                else:
                    duration = 1000
                if duration > 0:
                    def reset_stick():
                        import time
                        time.sleep(duration / 1000.0)
                        self.command_queue.put((stick, "NEUTRAL", 0.0))
                        self.log(f"Auto-reset {stick} to NEUTRAL after {duration}ms", level="info")
                    threading.Thread(target=reset_stick, daemon=True).start()
        else:
            self.log(f"Enqueued button: {btn}", level="info")

    def start_autoclicker(self):
        if self.autoclicker and self.autoclicker._thread and self.autoclicker._thread.is_alive():
            self.log("Autoclicker already running.", level="warning")
            return
        btn_display = self.auto_btn_var.get()
        btn_code = None
        for group in MANUAL_CONTROLS:
            for display, code in group["buttons"]:
                if display == btn_display:
                    btn_code = code
        if btn_code is None:
            self.log(f"Invalid button/stick for autoclicker: {btn_display}", level="error")
            return
        try:
            interval = int(self.auto_interval_var.get())
            if interval < 10:
                self.log("Interval too low (min 10 ms).", level="warning")
                return
        except ValueError:
            self.log("Invalid interval.", level="error")
            return
        self.autoclicker = Autoclicker(self.command_queue, btn_code, interval, self.log)
        self.autoclicker.start()
        self.auto_start_btn.config(state=tk.DISABLED)
        self.auto_stop_btn.config(state=tk.NORMAL)

    def stop_autoclicker(self):
        if self.autoclicker:
            self.autoclicker.stop()
        self.auto_start_btn.config(state=tk.NORMAL)
        self.auto_stop_btn.config(state=tk.DISABLED)

    def add_macro_step_dialog(self):
        # Dialog for adding a macro step (button, stick, or autoclicker, or multiple simultaneous actions)
        dialog = tk.Toplevel(self)
        dialog.title("Add Macro Step")
        dialog.grab_set()
        dialog.resizable(False, False)
        # Simultaneous Actions Mode
        simultaneous_mode_var = tk.BooleanVar(value=False)
        sim_check = ttk.Checkbutton(dialog, text="Simultaneous Actions Mode", variable=simultaneous_mode_var)
        sim_check.grid(row=0, column=0, columnspan=4, sticky="w", padx=4, pady=(4,0))
        ToolTip(sim_check, "When enabled, all actions you add will be grouped as a single simultaneous step.")
        ttk.Label(dialog, text="Type:").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        type_var = tk.StringVar(value="Button")
        type_frame = ttk.Frame(dialog)
        type_frame.grid(row=1, column=1, columnspan=3, sticky="w")
        ttk.Radiobutton(type_frame, text="Button", variable=type_var, value="Button").pack(side="left", padx=2)
        ttk.Radiobutton(type_frame, text="Stick", variable=type_var, value="Stick").pack(side="left", padx=2)
        ttk.Radiobutton(type_frame, text="Autoclicker", variable=type_var, value="Autoclicker").pack(side="left", padx=2)
        # Button selection
        ttk.Label(dialog, text="Button:").grid(row=2, column=0, sticky="w", padx=4)
        btn_choices = [display for group in MANUAL_CONTROLS if group["label"] not in ("Left Stick", "Right Stick") for display, _ in group["buttons"]]
        btn_var = tk.StringVar(value=btn_choices[0])
        btn_combo = ttk.Combobox(dialog, textvariable=btn_var, values=btn_choices, state="readonly", width=14)
        btn_combo.grid(row=2, column=1, columnspan=2, sticky="ew", padx=2)
        # Stick selection
        ttk.Label(dialog, text="Stick:").grid(row=3, column=0, sticky="w", padx=4)
        stick_var = tk.StringVar(value="LEFT_STICK")
        stick_combo = ttk.Combobox(dialog, textvariable=stick_var, values=["LEFT_STICK", "RIGHT_STICK"], state="readonly", width=10)
        stick_combo.grid(row=3, column=1, sticky="ew", padx=2)
        dir_var = tk.StringVar(value="UP")
        dir_combo = ttk.Combobox(dialog, textvariable=dir_var, values=["UP", "DOWN", "LEFT", "RIGHT", "NEUTRAL"], state="readonly", width=10)
        dir_combo.grid(row=3, column=2, sticky="ew", padx=2)
        ttk.Label(dialog, text="Magnitude:").grid(row=4, column=0, sticky="w", padx=4)
        mag_var = tk.DoubleVar(value=1.0)
        mag_entry = ttk.Entry(dialog, textvariable=mag_var, width=6)
        mag_entry.grid(row=4, column=1, sticky="ew", padx=2)
        # Interval label with tooltip
        interval_label = ttk.Label(dialog, text="Interval (ms):")
        interval_label.grid(row=5, column=0, sticky="w", padx=4)
        ToolTip(interval_label, "Interval (ms): How often to press the button. Lower = faster. Minimum 10ms.")
        auto_interval_var = tk.StringVar(value="100")
        auto_interval_entry = ttk.Entry(dialog, textvariable=auto_interval_var, width=8)
        auto_interval_entry.grid(row=5, column=1, sticky="ew", padx=2)
        # Duration label with tooltip
        duration_label = ttk.Label(dialog, text="Duration (ms, blank=until macro stops):")
        duration_label.grid(row=5, column=2, sticky="w", padx=4)
        ToolTip(duration_label, "How long to run the autoclicker for this step (in milliseconds). Leave blank to run until the macro or autoclicker is stopped.")
        auto_duration_var = tk.StringVar(value="")
        auto_duration_entry = ttk.Entry(dialog, textvariable=auto_duration_var, width=10)
        auto_duration_entry.grid(row=5, column=3, sticky="ew", padx=2)
        # Delay
        delay_label = ttk.Label(dialog, text="Delay (ms):")
        delay_label.grid(row=6, column=0, sticky="w", padx=4)
        ToolTip(delay_label, "How long to wait after this step before the next step (in milliseconds).")
        delay_var = tk.StringVar(value="100")
        delay_entry = ttk.Entry(dialog, textvariable=delay_var, width=8)
        delay_entry.grid(row=6, column=1, sticky="ew", padx=2)
        # Comment
        comment_label = ttk.Label(dialog, text="Comment:")
        comment_label.grid(row=6, column=2, sticky="w", padx=4)
        ToolTip(comment_label, "Optional: Explain what this step does.")
        comment_var = tk.StringVar(value="")
        comment_entry = ttk.Entry(dialog, textvariable=comment_var, width=24)
        comment_entry.grid(row=6, column=3, sticky="ew", padx=2)
        # Simultaneous actions UI
        ttk.Label(dialog, text="Actions for this step:").grid(row=7, column=0, sticky="w", padx=4, pady=(8,0))
        actions_listbox = tk.Listbox(dialog, height=4, width=40)
        actions_listbox.grid(row=8, column=0, columnspan=4, sticky="ew", padx=4)
        actions = []
        def add_action():
            if type_var.get() == "Button":
                btn_display = btn_var.get()
                btn_code = None
                for group in MANUAL_CONTROLS:
                    for display, code in group["buttons"]:
                        if display == btn_display:
                            btn_code = code
                if btn_code is None:
                    self.log(f"Invalid button: {btn_display}", level="error")
                    return
                actions.append(btn_code)
                actions_listbox.insert(tk.END, f"Button: {btn_code}")
            elif type_var.get() == "Stick":
                stick = stick_var.get()
                direction = dir_var.get()
                try:
                    magnitude = float(mag_var.get())
                except Exception:
                    self.log("Invalid magnitude.", level="error")
                    return
                actions.append((stick, direction, magnitude))
                actions_listbox.insert(tk.END, f"Stick: {stick} {direction} {magnitude}")
            else:  # Autoclicker
                btn_display = btn_var.get()
                btn_code = None
                for group in MANUAL_CONTROLS:
                    for display, code in group["buttons"]:
                        if display == btn_display:
                            btn_code = code
                if btn_code is None:
                    self.log(f"Invalid button: {btn_display}", level="error")
                    return
                try:
                    interval = int(auto_interval_var.get())
                    if interval < 10:
                        self.log("Interval too low (min 10 ms).", level="warning")
                        return
                except Exception:
                    self.log("Invalid autoclicker interval.", level="error")
                    return
                duration = None
                if auto_duration_var.get().strip():
                    try:
                        duration = int(auto_duration_var.get())
                        if duration < 0:
                            raise ValueError
                    except Exception:
                        self.log("Invalid autoclicker duration.", level="error")
                        return
                actions.append({"type": "autoclicker", "button": btn_code, "interval": interval, "duration": duration})
                actions_listbox.insert(tk.END, f"Autoclicker: {btn_code} {interval}ms dur={duration}")
        def remove_action():
            sel = actions_listbox.curselection()
            if not sel:
                return
            idx = sel[0]
            actions.pop(idx)
            actions_listbox.delete(idx)
        add_btn = ttk.Button(dialog, text="+ Add Action", command=add_action)
        add_btn.grid(row=9, column=0, pady=4)
        remove_btn = ttk.Button(dialog, text="Remove Selected", command=remove_action)
        remove_btn.grid(row=9, column=1, pady=4)
        def update_fields(*_):
            if type_var.get() == "Button":
                btn_combo.config(state="readonly")
                stick_combo.config(state="disabled")
                dir_combo.config(state="disabled")
                mag_entry.config(state="disabled")
                auto_interval_entry.config(state="disabled")
                auto_duration_entry.config(state="disabled")
            elif type_var.get() == "Stick":
                btn_combo.config(state="disabled")
                stick_combo.config(state="readonly")
                dir_combo.config(state="readonly")
                mag_entry.config(state="normal")
                auto_interval_entry.config(state="disabled")
                auto_duration_entry.config(state="disabled")
            else:  # Autoclicker
                btn_combo.config(state="readonly")
                stick_combo.config(state="disabled")
                dir_combo.config(state="disabled")
                mag_entry.config(state="disabled")
                auto_interval_entry.config(state="normal")
                auto_duration_entry.config(state="normal")
        type_var.trace_add("write", update_fields)
        update_fields()
        def on_ok():
            try:
                delay = int(delay_var.get())
                if delay < 0:
                    raise ValueError
            except Exception:
                self.log("Invalid delay.", level="error")
                return
            if not actions:
                self.log("No actions added for this step.", level="error")
                return
            comment = comment_var.get().strip() or None
            # Save as a list if simultaneous mode and >1 action, or as a single action for compatibility
            if simultaneous_mode_var.get() and len(actions) > 1:
                step = actions
            else:
                step = actions[0]
            if comment is not None:
                self.current_macro_steps.append((step, delay, comment))
            else:
                self.current_macro_steps.append((step, delay))
            self.update_macro_steps_tree()
            dialog.destroy()
        ttk.Button(dialog, text="OK", command=on_ok).grid(row=10, column=1, pady=8)
        ttk.Button(dialog, text="Cancel", command=dialog.destroy).grid(row=10, column=2, pady=8)
        dialog.wait_window()

    def update_macro_steps_tree(self):
        self.macro_steps_tree.delete(*self.macro_steps_tree.get_children())
        for i, step_tuple in enumerate(self.current_macro_steps):
            # Support (code, delay) or (code, delay, comment)
            if len(step_tuple) == 3:
                code, delay, comment = step_tuple
            else:
                code, delay = step_tuple
                comment = ""
            if isinstance(code, list):
                label = "Simultaneous: ["
                parts = []
                for action in code:
                    if isinstance(action, dict) and action.get('type') == 'autoclicker':
                        parts.append(f"Autoclicker {action['button']} {action['interval']}ms")
                    elif isinstance(action, tuple):
                        stick, direction, magnitude = action
                        parts.append(f"Stick {stick} {direction} {magnitude:.2f}")
                    else:
                        parts.append(f"Button {action}")
                label += ", ".join(parts) + "]"
                self.macro_steps_tree.insert("", "end", iid=str(i), values=("Simultaneous", label, "-", str(delay), comment))
            elif isinstance(code, dict) and code.get('type') == 'autoclicker':
                label = f"Autoclicker {code['button']} {code['interval']}ms"
                mag = code.get('duration', '-')
                self.macro_steps_tree.insert("", "end", iid=str(i), values=("Autoclicker", label, mag, str(delay), comment))
            elif isinstance(code, tuple):
                stick, direction, magnitude = code
                self.macro_steps_tree.insert("", "end", iid=str(i), values=("Stick", f"{stick} {direction}", f"{magnitude:.2f}", str(delay), comment))
            else:
                self.macro_steps_tree.insert("", "end", iid=str(i), values=("Button", str(code), "-", str(delay), comment))

    def edit_macro_step(self):
        sel = self.macro_steps_tree.selection()
        if not sel:
            self.log("No macro step selected to edit.", level="warning")
            return
        idx = int(sel[0])
        step_tuple = self.current_macro_steps[idx]
        if len(step_tuple) == 3:
            code, delay, comment = step_tuple
        else:
            code, delay = step_tuple
            comment = ""
        dialog = tk.Toplevel(self)
        dialog.title("Edit Macro Step")
        dialog.grab_set()
        dialog.resizable(False, False)
        # Simultaneous Actions Mode
        is_multi = isinstance(code, list)
        simultaneous_mode_var = tk.BooleanVar(value=is_multi)
        sim_check = ttk.Checkbutton(dialog, text="Simultaneous Actions Mode", variable=simultaneous_mode_var)
        sim_check.grid(row=0, column=0, columnspan=4, sticky="w", padx=4, pady=(4,0))
        ToolTip(sim_check, "When enabled, all actions you add will be grouped as a single simultaneous step.")
        ttk.Label(dialog, text="Type:").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        type_var = tk.StringVar(value="Button")
        type_frame = ttk.Frame(dialog)
        type_frame.grid(row=1, column=1, columnspan=3, sticky="w")
        ttk.Radiobutton(type_frame, text="Button", variable=type_var, value="Button").pack(side="left", padx=2)
        ttk.Radiobutton(type_frame, text="Stick", variable=type_var, value="Stick").pack(side="left", padx=2)
        ttk.Radiobutton(type_frame, text="Autoclicker", variable=type_var, value="Autoclicker").pack(side="left", padx=2)
        btn_choices = [display for group in MANUAL_CONTROLS if group["label"] not in ("Left Stick", "Right Stick") for display, _ in group["buttons"]]
        btn_var = tk.StringVar(value="")
        stick_var = tk.StringVar(value="LEFT_STICK")
        dir_var = tk.StringVar(value="UP")
        mag_var = tk.DoubleVar(value=1.0)
        auto_interval_var = tk.StringVar(value="100")
        auto_duration_var = tk.StringVar(value="")
        actions = code.copy() if is_multi else [code]
        btn_combo = ttk.Combobox(dialog, textvariable=btn_var, values=btn_choices, state="readonly", width=14)
        btn_combo.grid(row=2, column=1, columnspan=2, sticky="ew", padx=2)
        stick_combo = ttk.Combobox(dialog, textvariable=stick_var, values=["LEFT_STICK", "RIGHT_STICK"], state="readonly", width=10)
        stick_combo.grid(row=3, column=1, sticky="ew", padx=2)
        dir_combo = ttk.Combobox(dialog, textvariable=dir_var, values=["UP", "DOWN", "LEFT", "RIGHT", "NEUTRAL"], state="readonly", width=10)
        dir_combo.grid(row=3, column=2, sticky="ew", padx=2)
        ttk.Label(dialog, text="Magnitude:").grid(row=4, column=0, sticky="w", padx=4)
        mag_entry = ttk.Entry(dialog, textvariable=mag_var, width=6)
        mag_entry.grid(row=4, column=1, sticky="ew", padx=2)
        interval_label = ttk.Label(dialog, text="Interval (ms):")
        interval_label.grid(row=5, column=0, sticky="w", padx=4)
        ToolTip(interval_label, "Interval (ms): How often to press the button. Lower = faster. Minimum 10ms.")
        auto_interval_entry = ttk.Entry(dialog, textvariable=auto_interval_var, width=8)
        auto_interval_entry.grid(row=5, column=1, sticky="ew", padx=2)
        duration_label = ttk.Label(dialog, text="Duration (ms, blank=until macro stops):")
        duration_label.grid(row=5, column=2, sticky="w", padx=4)
        ToolTip(duration_label, "How long to run the autoclicker for this step (in milliseconds). Leave blank to run until the macro or autoclicker is stopped.")
        auto_duration_entry = ttk.Entry(dialog, textvariable=auto_duration_var, width=10)
        auto_duration_entry.grid(row=5, column=3, sticky="ew", padx=2)
        delay_label = ttk.Label(dialog, text="Delay (ms):")
        delay_label.grid(row=6, column=0, sticky="w", padx=4)
        ToolTip(delay_label, "How long to wait after this step before the next step (in milliseconds).")
        delay_var = tk.StringVar(value=str(delay))
        delay_entry = ttk.Entry(dialog, textvariable=delay_var, width=8)
        delay_entry.grid(row=6, column=1, sticky="ew", padx=2)
        comment_label = ttk.Label(dialog, text="Comment:")
        comment_label.grid(row=6, column=2, sticky="w", padx=4)
        ToolTip(comment_label, "Optional: Explain what this step does.")
        comment_var = tk.StringVar(value=comment)
        comment_entry = ttk.Entry(dialog, textvariable=comment_var, width=24)
        comment_entry.grid(row=6, column=3, sticky="ew", padx=2)
        ttk.Label(dialog, text="Actions for this step:").grid(row=7, column=0, sticky="w", padx=4, pady=(8,0))
        actions_listbox = tk.Listbox(dialog, height=4, width=40)
        actions_listbox.grid(row=8, column=0, columnspan=4, sticky="ew", padx=4)
        for a in actions:
            if isinstance(a, dict) and a.get('type') == 'autoclicker':
                actions_listbox.insert(tk.END, f"Autoclicker: {a['button']} {a['interval']}ms dur={a.get('duration')}")
            elif isinstance(a, tuple):
                actions_listbox.insert(tk.END, f"Stick: {a[0]} {a[1]} {a[2]}")
            else:
                actions_listbox.insert(tk.END, f"Button: {a}")
        def add_action():
            if type_var.get() == "Button":
                btn_display = btn_var.get()
                btn_code = None
                for group in MANUAL_CONTROLS:
                    for display, code in group["buttons"]:
                        if display == btn_display:
                            btn_code = code
                if btn_code is None:
                    self.log(f"Invalid button: {btn_display}", level="error")
                    return
                actions.append(btn_code)
                actions_listbox.insert(tk.END, f"Button: {btn_code}")
            elif type_var.get() == "Stick":
                stick = stick_var.get()
                direction = dir_var.get()
                try:
                    magnitude = float(mag_var.get())
                except Exception:
                    self.log("Invalid magnitude.", level="error")
                    return
                actions.append((stick, direction, magnitude))
                actions_listbox.insert(tk.END, f"Stick: {stick} {direction} {magnitude}")
            else:  # Autoclicker
                btn_display = btn_var.get()
                btn_code = None
                for group in MANUAL_CONTROLS:
                    for display, code in group["buttons"]:
                        if display == btn_display:
                            btn_code = code
                if btn_code is None:
                    self.log(f"Invalid button: {btn_display}", level="error")
                    return
                try:
                    interval = int(auto_interval_var.get())
                    if interval < 10:
                        self.log("Interval too low (min 10 ms).", level="warning")
                        return
                except Exception:
                    self.log("Invalid autoclicker interval.", level="error")
                    return
                duration = None
                if auto_duration_var.get().strip():
                    try:
                        duration = int(auto_duration_var.get())
                        if duration < 0:
                            raise ValueError
                    except Exception:
                        self.log("Invalid autoclicker duration.", level="error")
                        return
                actions.append({"type": "autoclicker", "button": btn_code, "interval": interval, "duration": duration})
                actions_listbox.insert(tk.END, f"Autoclicker: {btn_code} {interval}ms dur={duration}")
        def remove_action():
            sel = actions_listbox.curselection()
            if not sel:
                return
            idx = sel[0]
            actions.pop(idx)
            actions_listbox.delete(idx)
        add_btn = ttk.Button(dialog, text="+ Add Action", command=add_action)
        add_btn.grid(row=9, column=0, pady=4)
        remove_btn = ttk.Button(dialog, text="Remove Selected", command=remove_action)
        remove_btn.grid(row=9, column=1, pady=4)
        def update_fields(*_):
            if type_var.get() == "Button":
                btn_combo.config(state="readonly")
                stick_combo.config(state="disabled")
                dir_combo.config(state="disabled")
                mag_entry.config(state="disabled")
                auto_interval_entry.config(state="disabled")
                auto_duration_entry.config(state="disabled")
            elif type_var.get() == "Stick":
                btn_combo.config(state="disabled")
                stick_combo.config(state="readonly")
                dir_combo.config(state="readonly")
                mag_entry.config(state="normal")
                auto_interval_entry.config(state="disabled")
                auto_duration_entry.config(state="disabled")
            else:  # Autoclicker
                btn_combo.config(state="readonly")
                stick_combo.config(state="disabled")
                dir_combo.config(state="disabled")
                mag_entry.config(state="disabled")
                auto_interval_entry.config(state="normal")
                auto_duration_entry.config(state="normal")
        type_var.trace_add("write", update_fields)
        update_fields()
        def on_ok2():
            try:
                new_delay = int(delay_var.get())
                if new_delay < 0:
                    raise ValueError
            except Exception:
                self.log("Invalid delay.", level="error")
                return
            if not actions:
                self.log("No actions added for this step.", level="error")
                return
            comment2 = comment_var.get().strip() or None
            if simultaneous_mode_var.get() and len(actions) > 1:
                step = actions
            else:
                step = actions[0]
            if comment2 is not None:
                self.current_macro_steps[idx] = (step, new_delay, comment2)
            else:
                self.current_macro_steps[idx] = (step, new_delay)
            self.update_macro_steps_tree()
            dialog.destroy()
        ttk.Button(dialog, text="OK", command=on_ok2).grid(row=10, column=1, pady=8)
        ttk.Button(dialog, text="Cancel", command=dialog.destroy).grid(row=10, column=2, pady=8)
        dialog.wait_window()

    def update_eol_macro_steps_tree(self):
        self.eol_macro_steps_tree.delete(*self.eol_macro_steps_tree.get_children())
        val = self.eol_macro_var.get()
        if val == "None":
            return
        elif val == "Custom":
            steps = self.current_eol_macro_steps
        else:
            macro = self.macros.get(val)
            steps = macro.steps if macro else []
        for i, step_tuple in enumerate(steps):
            if len(step_tuple) == 3:
                code, delay, comment = step_tuple
            else:
                code, delay = step_tuple
                comment = ""
            if isinstance(code, dict) and code.get('type') == 'autoclicker':
                label = f"Autoclicker {code['button']} {code['interval']}ms"
                mag = code.get('duration', '-')
                self.eol_macro_steps_tree.insert("", "end", iid=str(i), values=("Autoclicker", label, mag, str(delay), comment))
            elif isinstance(code, tuple):
                stick, direction, magnitude = code
                self.eol_macro_steps_tree.insert("", "end", iid=str(i), values=("Stick", f"{stick} {direction}", f"{magnitude:.2f}", str(delay), comment))
            elif isinstance(code, list):
                label = "Simultaneous: ["
                parts = []
                for action in code:
                    if isinstance(action, dict) and action.get('type') == 'autoclicker':
                        parts.append(f"Autoclicker {action['button']} {action['interval']}ms")
                    elif isinstance(action, tuple):
                        stick, direction, magnitude = action
                        parts.append(f"Stick {stick} {direction} {magnitude:.2f}")
                    else:
                        parts.append(f"Button {action}")
                label += ", ".join(parts) + "]"
                self.eol_macro_steps_tree.insert("", "end", iid=str(i), values=("Simultaneous", label, "-", str(delay), comment))
            else:
                self.eol_macro_steps_tree.insert("", "end", iid=str(i), values=("Button", str(code), "-", str(delay), comment))

    def on_macro_select(self, event=None):
        sel = self.macro_listbox.curselection()
        if not sel:
            self.log("No macro selected to load.", level="warning")
            return
        idx = sel[0]
        name = self.macro_listbox.get(idx).replace(" [RUNNING]", "").strip()
        macro = self.macros.get(name)
        if not macro:
            self.log(f"Macro not found: {name}", level="error")
            return
        self.macro_name_var.set(macro.name)
        self.current_macro_steps = macro.steps.copy()
        # Set description in the ScrolledText widget
        self.macro_desc_text.delete("1.0", tk.END)
        self.macro_desc_text.insert(tk.END, getattr(macro, 'description', '') or '')
        self.update_macro_steps_tree()
        # Also load end-of-loop macro info
        if hasattr(macro, 'end_of_loop_macro_name') and macro.end_of_loop_macro_name:
            self.eol_macro_var.set(macro.end_of_loop_macro_name)
            self.current_eol_macro_steps = []
        elif hasattr(macro, 'end_of_loop_macro') and macro.end_of_loop_macro:
            self.eol_macro_var.set("Custom")
            self.current_eol_macro_steps = macro.end_of_loop_macro.copy()
        else:
            self.eol_macro_var.set("None")
            self.current_eol_macro_steps = []
        self.update_eol_macro_steps_tree()
        self.log(f"Loaded macro: {macro.name}", level="success")
        if name in self.running_macros:
            self.set_macro_status(f"Macro '{name}' is running.", color="green")
        else:
            self.set_macro_status(f"Macro '{name}' loaded.", color="black")

    def on_close(self):
        if self.worker:
            self.worker.disconnect()
        if self.autoclicker:
            self.autoclicker.stop()
        if self.current_macro_runner:
            self.current_macro_runner.stop()
        self.destroy()

    def add_host_dialog(self):
        dialog = tk.Toplevel(self)
        dialog.title("Add Host")
        dialog.grab_set()
        dialog.resizable(False, False)
        ttk.Label(dialog, text="Host IP:").grid(row=0, column=0, padx=4, pady=4, sticky="w")
        ip_var = tk.StringVar()
        ip_entry = ttk.Entry(dialog, textvariable=ip_var, width=20)
        ip_entry.grid(row=0, column=1, padx=4, pady=4)
        ttk.Label(dialog, text="Label (optional):").grid(row=1, column=0, padx=4, pady=4, sticky="w")
        label_var = tk.StringVar()
        label_entry = ttk.Entry(dialog, textvariable=label_var, width=20)
        label_entry.grid(row=1, column=1, padx=4, pady=4)
        def on_ok():
            ip = ip_var.get().strip()
            label = label_var.get().strip()
            if not ip:
                self.log("Host IP required.", level="warning")
                return
            # Use IP as key, allow duplicate labels but not duplicate IPs
            if ip in self.hosts:
                self.log("Host IP already exists.", level="warning")
                return
            self.hosts[ip] = {'host': ip, 'label': label}
            self._write_hosts()
            self._load_hosts()
            dialog.destroy()
            self.log(f"Added host: {label+' ' if label else ''}{ip}", level="success")
        ttk.Button(dialog, text="OK", command=on_ok).grid(row=2, column=0, pady=8)
        ttk.Button(dialog, text="Cancel", command=dialog.destroy).grid(row=2, column=1, pady=8)
        dialog.wait_window()

    def edit_host_dialog(self):
        idx = self.host_combo.current()
        if idx < 0:
            self.log("No host selected to edit.", level="warning")
            return
        host_keys = list(self.hosts.keys())
        key = host_keys[idx]
        entry = self.hosts[key]
        dialog = tk.Toplevel(self)
        dialog.title("Edit Host")
        dialog.grab_set()
        dialog.resizable(False, False)
        ttk.Label(dialog, text="Host IP:").grid(row=0, column=0, padx=4, pady=4, sticky="w")
        ip_var = tk.StringVar(value=entry['host'])
        ip_entry = ttk.Entry(dialog, textvariable=ip_var, width=20)
        ip_entry.grid(row=0, column=1, padx=4, pady=4)
        ttk.Label(dialog, text="Label (optional):").grid(row=1, column=0, padx=4, pady=4, sticky="w")
        label_var = tk.StringVar(value=entry.get('label', ''))
        label_entry = ttk.Entry(dialog, textvariable=label_var, width=20)
        label_entry.grid(row=1, column=1, padx=4, pady=4)
        def on_ok():
            new_ip = ip_var.get().strip()
            new_label = label_var.get().strip()
            if not new_ip:
                self.log("Host IP required.", level="warning")
                return
            if new_ip != key and new_ip in self.hosts:
                self.log("Host IP already exists.", level="warning")
                return
            # Remove old, add new
            del self.hosts[key]
            self.hosts[new_ip] = {'host': new_ip, 'label': new_label}
            self._write_hosts()
            self._load_hosts()
            dialog.destroy()
            self.log(f"Edited host: {new_label+' ' if new_label else ''}{new_ip}", level="success")
        ttk.Button(dialog, text="OK", command=on_ok).grid(row=2, column=0, pady=8)
        ttk.Button(dialog, text="Cancel", command=dialog.destroy).grid(row=2, column=1, pady=8)
        dialog.wait_window()

    def delete_host(self):
        idx = self.host_combo.current()
        if idx < 0:
            self.log("No host selected to delete.", level="warning")
            return
        host_keys = list(self.hosts.keys())
        key = host_keys[idx]
        entry = self.hosts[key]
        confirm = messagebox.askyesno("Delete Host", f"Delete host {entry.get('label', '')+' ' if entry.get('label') else ''}{entry['host']}?")
        if not confirm:
            return
        del self.hosts[key]
        self._write_hosts()
        self._load_hosts()
        # Update dropdown selection after deletion
        host_list = list(self.host_combo['values'])
        if host_list:
            self.host_combo.current(0)
            self.host_var.set(host_list[0])
        else:
            self.host_var.set("")
        self.log(f"Deleted host: {entry.get('label', '')+' ' if entry.get('label') else ''}{entry['host']}", level="success")

    def download_macros_from_github(self):
        """Download all .macro.json macros from the official GitHub Macros folder and merge into user's Macros folder."""
        from tkinter import messagebox
        GITHUB_API_URL = "https://api.github.com/repos/ItsDeidara/PSAuto.py/contents/Macros"
        if not messagebox.askyesno("Download Macros", "Macros with the same name will be replaced. Continue?"):
            return
        try:
            resp = requests.get(GITHUB_API_URL)
            resp.raise_for_status()
            files = resp.json()
        except Exception as e:
            self.log(f"Failed to fetch macro list: {e}", level="error")
            return
        macros_dir = resource_path('Macros')
        os.makedirs(macros_dir, exist_ok=True)
        count = 0
        for file in files:
            if file['name'].endswith('.macro.json'):
                try:
                    macro_resp = requests.get(file['download_url'])
                    macro_resp.raise_for_status()
                    with open(os.path.join(macros_dir, file['name']), 'wb') as f:
                        f.write(macro_resp.content)
                    count += 1
                except Exception as e:
                    self.log(f"Failed to download {file['name']}: {e}", level="error")
        self.log(f"Downloaded {count} macros from GitHub.", level="success")
        self.refresh_macro_list()
        # Show popup to user
        messagebox.showinfo(
            "Download Complete",
            f"Downloaded/updated {count} macros from GitHub.\nOnly macros with the same name were replaced; all others were left untouched."
        )

    def save_macro(self):
        """Save the current macro to disk and update the macro list."""
        name = self.macro_name_var.get().strip()
        if not name:
            self.log("Macro name required.", level="warning")
            return
        steps = self.current_macro_steps.copy()
        description = self.macro_desc_text.get("1.0", tk.END).strip()
        # End-of-loop macro
        eol_macro_name = self.eol_macro_var.get()
        if eol_macro_name == "None":
            eol_macro = []
            eol_macro_name_val = None
        elif eol_macro_name == "Custom":
            eol_macro = self.current_eol_macro_steps.copy()
            eol_macro_name_val = None
        else:
            eol_macro = []
            eol_macro_name_val = eol_macro_name
        macro = Macro(
            name,
            steps=steps,
            end_of_loop_macro=eol_macro,
            end_of_loop_macro_name=eol_macro_name_val,
            description=description
        )
        macros_dir = resource_path('Macros')
        os.makedirs(macros_dir, exist_ok=True)
        macro_path = os.path.join(macros_dir, f"{name}.macro.json")
        try:
            macro.save(macro_path)
            self.macros[name] = macro
            self.refresh_macro_list()
            self.log(f"Saved macro: {name}", level="success")
        except Exception as e:
            self.log(f"Failed to save macro: {e}", level="error")

    def import_macro(self):
        from tkinter import filedialog
        import shutil
        file_path = filedialog.askopenfilename(
            title="Import Macro",
            filetypes=[("Macro Files", "*.macro.json"), ("All Files", "*.")]
        )
        if not file_path:
            return
        # Auto-rename if needed
        import os
        base_dir = os.path.dirname(file_path)
        base_name = os.path.basename(file_path)
        if not base_name.endswith('.macro.json'):
            # Replace spaces with underscores for safety
            new_base = base_name.replace(' ', '_')
            if new_base.endswith('.json'):
                new_base = new_base[:-5] + '.macro.json'
            else:
                new_base = new_base + '.macro.json'
            new_path = os.path.join(base_dir, new_base)
            shutil.copy2(file_path, new_path)
            file_path = new_path
            self.log(f"Renamed imported macro to: {new_base}", level="info")
        try:
            macro = Macro.load(file_path)
            self.macros[macro.name] = macro
            self.refresh_macro_list()
            self.log(f"Imported macro: {macro.name}", level="success")
            # Always select and load the imported macro, even if the list was empty before
            for idx in range(self.macro_listbox.size()):
                if self.macro_listbox.get(idx) == macro.name:
                    self.macro_listbox.selection_clear(0, tk.END)
                    self.macro_listbox.selection_set(idx)
                    self.on_macro_select()
                    break
            else:
                # If not found, select the first macro if any
                if self.macro_listbox.size() > 0:
                    self.macro_listbox.selection_clear(0, tk.END)
                    self.macro_listbox.selection_set(0)
                    self.on_macro_select()
        except Exception as e:
            self.log(f"Failed to import macro: {e}", level="error")

    def export_macro(self):
        from tkinter import filedialog
        sel = self.macro_listbox.curselection()
        if not sel:
            self.log("No macro selected to export.", level="warning")
            return
        idx = sel[0]
        name = self.macro_listbox.get(idx).replace(" [RUNNING]", "").strip()
        macro = self.macros.get(name)
        if not macro:
            self.log(f"Macro not found: {name}", level="error")
            return
        file_path = filedialog.asksaveasfilename(
            title="Export Macro",
            defaultextension=".macro.json",
            filetypes=[("Macro Files", "*.macro.json"), ("All Files", "*.*")]
        )
        if not file_path:
            return
        try:
            macro.save(file_path)
            self.log(f"Exported macro: {name}", level="success")
        except Exception as e:
            self.log(f"Failed to export macro: {e}", level="error")

    def remove_macro_step(self):
        sel = self.macro_steps_tree.selection()
        if not sel:
            self.log("No macro step selected to remove.", level="warning")
            return
        idx = int(sel[0])
        del self.current_macro_steps[idx]
        self.update_macro_steps_tree()

    def move_macro_step_up(self):
        sel = self.macro_steps_tree.selection()
        if not sel:
            self.log("No macro step selected to move up.", level="warning")
            return
        idx = int(sel[0])
        if idx == 0:
            return
        self.current_macro_steps[idx-1], self.current_macro_steps[idx] = self.current_macro_steps[idx], self.current_macro_steps[idx-1]
        self.update_macro_steps_tree()
        self.macro_steps_tree.selection_set(str(idx-1))

    def move_macro_step_down(self):
        sel = self.macro_steps_tree.selection()
        if not sel:
            self.log("No macro step selected to move down.", level="warning")
            return
        idx = int(sel[0])
        if idx == len(self.current_macro_steps) - 1:
            return
        self.current_macro_steps[idx+1], self.current_macro_steps[idx] = self.current_macro_steps[idx], self.current_macro_steps[idx+1]
        self.update_macro_steps_tree()
        self.macro_steps_tree.selection_set(str(idx+1))

    def repeat_macro_step(self):
        sel = self.macro_steps_tree.selection()
        if not sel:
            self.log("No macro step selected to repeat.", level="warning")
            return
        idx = int(sel[0])
        step = self.current_macro_steps[idx]
        self.current_macro_steps.insert(idx+1, step)
        self.update_macro_steps_tree()
        self.macro_steps_tree.selection_set(str(idx+1))

    def refresh_macro_list(self):
        macros_dir = resource_path('Macros')
        os.makedirs(macros_dir, exist_ok=True)
        # Auto-rename .json files that do not end with .macro.json
        for path in glob.glob(os.path.join(macros_dir, '*.json')):
            if not path.endswith('.macro.json'):
                new_path = path[:-5] + '.macro.json'
                if not os.path.exists(new_path):
                    try:
                        os.rename(path, new_path)
                        self.log(f"Renamed {os.path.basename(path)} to {os.path.basename(new_path)} for macro detection.", level="info")
                    except Exception as e:
                        self.log(f"Failed to rename {os.path.basename(path)}: {e}", level="error")
        self.macros.clear()
        for path in glob.glob(os.path.join(macros_dir, '*.macro.json')):
            try:
                macro = Macro.load(path)
                self.macros[macro.name] = macro
            except Exception as e:
                self.log(f"Failed to load macro {os.path.basename(path)}: {e}", level="error")
        self.macro_listbox.delete(0, tk.END)
        for name in sorted(self.macros.keys()):
            self.macro_listbox.insert(tk.END, name)
        # Update end-of-loop macro choices
        eol_choices = ["None", "Custom"] + sorted(self.macros.keys())
        self.eol_macro_combo['values'] = eol_choices

    def run_selected_macros(self):
        sel = self.macro_listbox.curselection()
        if not sel:
            self.log("No macro(s) selected to run.", level="warning")
            return
        for idx in sel:
            name = self.macro_listbox.get(idx).replace(" [RUNNING]", "").strip()
            macro = self.macros.get(name)
            if not macro:
                self.log(f"Macro not found: {name}", level="error")
                continue
            if name in self.running_macros:
                self.set_macro_status(f"Macro '{name}' is already running.", color="orange")
                continue
            # Get loop count
            try:
                loop_count = int(self.macro_loop_count_var.get())
            except Exception:
                loop_count = 1
            if self.macro_infinite_var.get():
                loop_count = -1
            def loop_progress_callback(loop_num, total_loops, macro_name=name):
                if loop_count == -1:
                    self.set_macro_status(f"Macro '{macro_name}' is looping: Loop {loop_num} (infinite)", color="blue")
                else:
                    self.set_macro_status(f"Macro '{macro_name}' is looping: Loop {loop_num} of {total_loops}", color="blue")
            runner = MacroRunner(
                self.command_queue,
                macro,
                self.log,
                get_macro_by_name=lambda n: self.macros.get(n),
                refresh_callback=self.refresh_macro_list,
                loop_progress_callback=loop_progress_callback
            )
            self.running_macros[name] = runner
            runner.play(loop_count=loop_count)
            # Mark as running in the listbox
            self.macro_listbox.delete(idx)
            self.macro_listbox.insert(idx, name + " [RUNNING]")
            if loop_count == -1:
                self.set_macro_status(f"Macro '{name}' is looping infinitely.", color="blue")
            else:
                self.set_macro_status(f"Macro '{name}' is running ({loop_count} loops).", color="green")
        self.macro_listbox.selection_clear(0, tk.END)

    def stop_selected_macros(self):
        if not self.running_macros:
            self.log("No macros are currently running.", level="warning")
            return
        # Make a list to avoid changing dict size during iteration
        running_names = list(self.running_macros.keys())
        for name in running_names:
            runner = self.running_macros.get(name)
            if runner:
                runner.stop()
                del self.running_macros[name]
                # Remove [RUNNING] tag in the listbox
                for idx in range(self.macro_listbox.size()):
                    item_name = self.macro_listbox.get(idx).replace(" [RUNNING]", "").strip()
                    if item_name == name:
                        self.macro_listbox.delete(idx)
                        self.macro_listbox.insert(idx, name)
                        break
                self.set_macro_status(f"Macro '{name}' stopped.", color="red")
        self.macro_listbox.selection_clear(0, tk.END)

    def edit_eol_macro_dialog(self):
        # Dialog for editing end-of-loop macro steps (self.current_eol_macro_steps)
        dialog = tk.Toplevel(self)
        dialog.title("Edit End-of-Loop Macro Steps")
        dialog.grab_set()
        dialog.resizable(False, False)
        steps = self.current_eol_macro_steps
        tree = ttk.Treeview(dialog, columns=("Type", "Name/Dir", "Mag", "Delay", "Comment"), show="headings", height=8)
        for col in ("Type", "Name/Dir", "Mag", "Delay", "Comment"):
            tree.heading(col, text=col)
            tree.column(col, width=70 if col!="Name/Dir" and col!="Comment" else 120 if col=="Name/Dir" else 180)
        tree.grid(row=0, column=0, columnspan=5, padx=4, pady=4, sticky="nsew")
        def refresh_tree():
            tree.delete(*tree.get_children())
            for i, step_tuple in enumerate(steps):
                if len(step_tuple) == 3:
                    code, delay, comment = step_tuple
                else:
                    code, delay = step_tuple
                    comment = ""
                if isinstance(code, list):
                    label = "Simultaneous: ["
                    parts = []
                    for action in code:
                        if isinstance(action, dict) and action.get('type') == 'autoclicker':
                            parts.append(f"Autoclicker {action['button']} {action['interval']}ms")
                        elif isinstance(action, tuple):
                            stick, direction, magnitude = action
                            parts.append(f"Stick {stick} {direction} {magnitude:.2f}")
                        else:
                            parts.append(f"Button {action}")
                    label += ", ".join(parts) + "]"
                    tree.insert("", "end", iid=str(i), values=("Simultaneous", label, "-", str(delay), comment))
                elif isinstance(code, dict) and code.get('type') == 'autoclicker':
                    label = f"Autoclicker {code['button']} {code['interval']}ms"
                    mag = code.get('duration', '-')
                    tree.insert("", "end", iid=str(i), values=("Autoclicker", label, mag, str(delay), comment))
                elif isinstance(code, tuple):
                    stick, direction, magnitude = code
                    tree.insert("", "end", iid=str(i), values=("Stick", f"{stick} {direction}", f"{magnitude:.2f}", str(delay), comment))
                else:
                    tree.insert("", "end", iid=str(i), values=("Button", str(code), "-", str(delay), comment))
        refresh_tree()
        def add_step():
            self.add_macro_step_dialog()
            refresh_tree()
        def edit_step():
            sel = tree.selection()
            if not sel:
                self.log("No step selected to edit.", level="warning")
                return
            idx = int(sel[0])
            # Temporarily set selection in main tree for reuse
            self.macro_steps_tree.selection_set(str(idx))
            self.edit_macro_step()
            refresh_tree()
        def remove_step():
            sel = tree.selection()
            if not sel:
                self.log("No step selected to remove.", level="warning")
                return
            idx = int(sel[0])
            del steps[idx]
            refresh_tree()
        def move_up():
            sel = tree.selection()
            if not sel:
                return
            idx = int(sel[0])
            if idx == 0:
                return
            steps[idx-1], steps[idx] = steps[idx], steps[idx-1]
            refresh_tree()
            tree.selection_set(str(idx-1))
        def move_down():
            sel = tree.selection()
            if not sel:
                return
            idx = int(sel[0])
            if idx == len(steps) - 1:
                return
            steps[idx+1], steps[idx] = steps[idx], steps[idx+1]
            refresh_tree()
            tree.selection_set(str(idx+1))
        ttk.Button(dialog, text="Add Step", command=add_step).grid(row=1, column=0, pady=4)
        ttk.Button(dialog, text="Edit Step", command=edit_step).grid(row=1, column=1, pady=4)
        ttk.Button(dialog, text="Remove Step", command=remove_step).grid(row=1, column=2, pady=4)
        ttk.Button(dialog, text="Move Up", command=move_up).grid(row=1, column=3, pady=4)
        ttk.Button(dialog, text="Move Down", command=move_down).grid(row=1, column=4, pady=4)
        ttk.Button(dialog, text="OK", command=dialog.destroy).grid(row=2, column=2, pady=8)
        dialog.wait_window()
        self.update_eol_macro_steps_tree()

def launch_gui():
    app = PSRemotePlayGUI()
    app.mainloop()

if __name__ == "__main__":
    launch_gui() 