import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
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

SAVED_IPS_PATH = os.path.join(os.path.dirname(__file__), '..', 'saved_ips.json')

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
        x, y, cx, cy = self.widget.bbox("insert") if hasattr(self.widget, 'bbox') else (0,0,0,0)
        x = x + self.widget.winfo_rootx() + 25
        y = y + self.widget.winfo_rooty() + 20
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
        self._build_widgets()
        self._load_hosts()
        self.connected = False
        self.protocol("WM_DELETE_WINDOW", self.on_close)

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
        ttk.Label(host_frm, text="Select Host:").pack(side="left")
        self.host_var = tk.StringVar()
        self.host_combo = ttk.Combobox(host_frm, textvariable=self.host_var, state="readonly")
        self.host_combo.pack(side="left", fill="x", expand=True, padx=5)
        # Host CRUD buttons
        ttk.Button(host_frm, text="Add", command=self.add_host_dialog).pack(side="left", padx=2)
        ttk.Button(host_frm, text="Edit", command=self.edit_host_dialog).pack(side="left", padx=2)
        ttk.Button(host_frm, text="Delete", command=self.delete_host).pack(side="left", padx=2)
        self.connect_btn = ttk.Button(host_frm, text="Connect", command=self.on_connect)
        self.connect_btn.pack(side="left", padx=5)
        self.disconnect_btn = ttk.Button(host_frm, text="Disconnect", command=self.on_disconnect, state=tk.DISABLED)
        self.disconnect_btn.pack(side="left", padx=5)
        self.status_var = tk.StringVar(value="Disconnected")
        ttk.Label(frm, textvariable=self.status_var, foreground="blue").pack(anchor="w", pady=(2, 5))
        # Manual Controls (grouped)
        for group in MANUAL_CONTROLS:
            group_frm = ttk.LabelFrame(frm, text=group["label"])
            group_frm.pack(fill="x", pady=(8, 0), padx=2)
            for i, (display, code) in enumerate(group["buttons"]):
                btn = ttk.Button(group_frm, text=display, width=12, command=lambda c=code: self.send_button(c))
                btn.grid(row=0, column=i, padx=2, pady=2, sticky="ew")
            group_frm.grid_columnconfigure(tuple(range(len(group["buttons"]))), weight=1)
        # Autoclicker section (now in Controls tab)
        auto_frm = ttk.LabelFrame(frm, text="Autoclicker")
        auto_frm.pack(fill="x", pady=(10, 0), padx=2)
        ttk.Label(auto_frm, text="Button/Stick:").grid(row=0, column=0, sticky="w")
        btn_choices = [display for group in MANUAL_CONTROLS for display, _ in group["buttons"]]
        self.auto_btn_var = tk.StringVar(value="CROSS")
        self.auto_btn_combo = ttk.Combobox(auto_frm, textvariable=self.auto_btn_var, values=btn_choices, state="readonly", width=14)
        self.auto_btn_combo.grid(row=0, column=1, padx=2)
        ttk.Label(auto_frm, text="Interval (ms):").grid(row=0, column=2, sticky="w")
        self.auto_interval_var = tk.StringVar(value="100")
        self.auto_interval_entry = ttk.Entry(auto_frm, textvariable=self.auto_interval_var, width=6)
        self.auto_interval_entry.grid(row=0, column=3, padx=2)
        self.auto_start_btn = ttk.Button(auto_frm, text="Start", command=self.start_autoclicker)
        self.auto_start_btn.grid(row=0, column=4, padx=2)
        self.auto_stop_btn = ttk.Button(auto_frm, text="Stop", command=self.stop_autoclicker, state=tk.DISABLED)
        self.auto_stop_btn.grid(row=0, column=5, padx=2)
        # Log area (now in Controls tab)
        self.log_area = scrolledtext.ScrolledText(frm, height=8, state=tk.DISABLED)
        self.log_area.pack(fill="both", expand=True, padx=5, pady=10)

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
        ttk.Label(macro_list_frm, text="Saved Macros:").pack(anchor="w", padx=4, pady=(4, 0))
        self.macro_listbox = tk.Listbox(macro_list_frm, selectmode=tk.EXTENDED, height=12)
        self.macro_listbox.pack(fill="both", expand=True, padx=4, pady=2)
        macro_list_btns = ttk.Frame(macro_list_frm)
        macro_list_btns.pack(fill="x", padx=4, pady=2)
        ttk.Button(macro_list_btns, text="Load", command=self.on_macro_select).pack(side="left", padx=2)
        ttk.Button(macro_list_btns, text="Save", command=self.save_macro).pack(side="left", padx=2)
        ttk.Button(macro_list_btns, text="Import", command=self.import_macro).pack(side="left", padx=2)
        ttk.Button(macro_list_btns, text="Export", command=self.export_macro).pack(side="left", padx=2)
        ttk.Button(macro_list_btns, text="Run Selected", command=self.run_selected_macros).pack(side="left", padx=2)
        ttk.Button(macro_list_btns, text="Stop Selected", command=self.stop_selected_macros).pack(side="left", padx=2)
        # Optionally, auto-load on selection:
        self.macro_listbox.bind('<<ListboxSelect>>', self.on_macro_select)
        macro_pane.add(macro_list_frm, weight=1)
        # Macro Step Editor (right)
        macro_edit_frm = ttk.Frame(macro_pane)
        macro_edit_frm.pack(fill="both", expand=True)
        ttk.Label(macro_edit_frm, text="Macro Steps:").pack(anchor="w", padx=4, pady=(4, 0))
        self.macro_steps_tree = ttk.Treeview(macro_edit_frm, columns=("Type", "Name/Dir", "Mag", "Delay"), show="headings", selectmode="browse", height=10)
        self.macro_steps_tree.heading("Type", text="Type")
        self.macro_steps_tree.heading("Name/Dir", text="Name/Direction")
        self.macro_steps_tree.heading("Mag", text="Magnitude")
        self.macro_steps_tree.heading("Delay", text="Delay (ms)")
        self.macro_steps_tree.column("Type", width=70)
        self.macro_steps_tree.column("Name/Dir", width=120)
        self.macro_steps_tree.column("Mag", width=70)
        self.macro_steps_tree.column("Delay", width=80)
        self.macro_steps_tree.pack(fill="both", expand=True, padx=4, pady=2)
        # Loop count controls
        loop_frm = ttk.Frame(macro_edit_frm)
        loop_frm.pack(fill="x", padx=4, pady=2)
        ttk.Label(loop_frm, text="Loop Count:").pack(side="left")
        self.macro_loop_count_var = tk.StringVar(value="1")
        self.macro_infinite_var = tk.BooleanVar(value=False)
        loop_entry = ttk.Entry(loop_frm, textvariable=self.macro_loop_count_var, width=5)
        loop_entry.pack(side="left", padx=2)
        inf_check = ttk.Checkbutton(loop_frm, text="Infinite", variable=self.macro_infinite_var, command=lambda: self.macro_loop_count_var.set("-1") if self.macro_infinite_var.get() else self.macro_loop_count_var.set("1"))
        inf_check.pack(side="left", padx=2)
        # End-of-loop macro controls
        eol_frm = ttk.LabelFrame(macro_edit_frm, text="End-of-Loop Macro")
        eol_frm.pack(fill="x", padx=4, pady=4)
        ttk.Label(eol_frm, text="Use saved macro:").pack(side="left")
        self.eol_macro_var = tk.StringVar(value="None")
        eol_macro_choices = ["None", "Custom"] + sorted(self.macros.keys())
        self.eol_macro_combo = ttk.Combobox(eol_frm, textvariable=self.eol_macro_var, values=eol_macro_choices, state="readonly", width=16)
        self.eol_macro_combo.pack(side="left", padx=2)
        ttk.Button(eol_frm, text="Edit Custom", command=self.edit_eol_macro_dialog).pack(side="left", padx=2)
        self.eol_macro_steps_tree = ttk.Treeview(eol_frm, columns=("Type", "Name/Dir", "Mag", "Delay"), show="headings", height=4)
        for col in ("Type", "Name/Dir", "Mag", "Delay"):
            self.eol_macro_steps_tree.heading(col, text=col)
            self.eol_macro_steps_tree.column(col, width=70 if col!="Name/Dir" else 120)
        self.eol_macro_steps_tree.pack(fill="x", padx=2, pady=2)
        self.eol_macro_var.trace_add("write", lambda *_: self.update_eol_macro_steps_tree())
        macro_step_btns = ttk.Frame(macro_edit_frm)
        macro_step_btns.pack(fill="x", padx=4, pady=2)
        ttk.Button(macro_step_btns, text="Add Step", command=self.add_macro_step_dialog).pack(side="left", padx=2)
        ttk.Button(macro_step_btns, text="Edit Step", command=self.edit_macro_step).pack(side="left", padx=2)
        ttk.Button(macro_step_btns, text="Remove Step", command=self.remove_macro_step).pack(side="left", padx=2)
        ttk.Button(macro_step_btns, text="Move Up", command=self.move_macro_step_up).pack(side="left", padx=2)
        ttk.Button(macro_step_btns, text="Move Down", command=self.move_macro_step_down).pack(side="left", padx=2)
        ttk.Button(macro_step_btns, text="Repeat Step", command=self.repeat_macro_step).pack(side="left", padx=2)
        macro_edit_frm.grid_rowconfigure(1, weight=1)
        macro_edit_frm.grid_columnconfigure(0, weight=1)
        macro_pane.add(macro_edit_frm, weight=3)
        # Macro state
        self.refresh_macro_list()
        self.update_eol_macro_steps_tree()

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
        # Dialog for adding a macro step (button, stick, or autoclicker)
        dialog = tk.Toplevel(self)
        dialog.title("Add Macro Step")
        dialog.grab_set()
        dialog.resizable(False, False)
        ttk.Label(dialog, text="Type:").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        # Place radio buttons together
        type_var = tk.StringVar(value="Button")
        type_frame = ttk.Frame(dialog)
        type_frame.grid(row=0, column=1, columnspan=3, sticky="w")
        ttk.Radiobutton(type_frame, text="Button", variable=type_var, value="Button").pack(side="left", padx=2)
        ttk.Radiobutton(type_frame, text="Stick", variable=type_var, value="Stick").pack(side="left", padx=2)
        ttk.Radiobutton(type_frame, text="Autoclicker", variable=type_var, value="Autoclicker").pack(side="left", padx=2)
        # Button selection
        ttk.Label(dialog, text="Button:").grid(row=1, column=0, sticky="w", padx=4)
        btn_choices = [display for group in MANUAL_CONTROLS if group["label"] not in ("Left Stick", "Right Stick") for display, _ in group["buttons"]]
        btn_var = tk.StringVar(value=btn_choices[0])
        btn_combo = ttk.Combobox(dialog, textvariable=btn_var, values=btn_choices, state="readonly", width=14)
        btn_combo.grid(row=1, column=1, columnspan=2, sticky="ew", padx=2)
        # Stick selection
        ttk.Label(dialog, text="Stick:").grid(row=2, column=0, sticky="w", padx=4)
        stick_var = tk.StringVar(value="LEFT_STICK")
        stick_combo = ttk.Combobox(dialog, textvariable=stick_var, values=["LEFT_STICK", "RIGHT_STICK"], state="readonly", width=10)
        stick_combo.grid(row=2, column=1, sticky="ew", padx=2)
        dir_var = tk.StringVar(value="UP")
        dir_combo = ttk.Combobox(dialog, textvariable=dir_var, values=["UP", "DOWN", "LEFT", "RIGHT", "NEUTRAL"], state="readonly", width=10)
        dir_combo.grid(row=2, column=2, sticky="ew", padx=2)
        ttk.Label(dialog, text="Magnitude:").grid(row=3, column=0, sticky="w", padx=4)
        mag_var = tk.DoubleVar(value=1.0)
        mag_entry = ttk.Entry(dialog, textvariable=mag_var, width=6)
        mag_entry.grid(row=3, column=1, sticky="ew", padx=2)
        # Interval label with tooltip
        interval_label = ttk.Label(dialog, text="Interval (ms):")
        interval_label.grid(row=4, column=0, sticky="w", padx=4)
        ToolTip(interval_label, "Interval (ms): How often to press the button. Lower = faster. Minimum 10ms.")
        auto_interval_var = tk.StringVar(value="100")
        auto_interval_entry = ttk.Entry(dialog, textvariable=auto_interval_var, width=8)
        auto_interval_entry.grid(row=4, column=1, sticky="ew", padx=2)
        # Duration label with tooltip
        duration_label = ttk.Label(dialog, text="Duration (ms, blank=until macro stops):")
        duration_label.grid(row=4, column=2, sticky="w", padx=4)
        ToolTip(duration_label, "How long to run the autoclicker for this step (in milliseconds). Leave blank to run until the macro or autoclicker is stopped.")
        auto_duration_var = tk.StringVar(value="")
        auto_duration_entry = ttk.Entry(dialog, textvariable=auto_duration_var, width=10)
        auto_duration_entry.grid(row=4, column=3, sticky="ew", padx=2)
        # Delay and repeat
        delay_label = ttk.Label(dialog, text="Delay (ms):")
        delay_label.grid(row=5, column=0, sticky="w", padx=4)
        ToolTip(delay_label, "How long to wait after this step before the next step (in milliseconds).")
        delay_var = tk.StringVar(value="100")
        delay_entry = ttk.Entry(dialog, textvariable=delay_var, width=8)
        delay_entry.grid(row=5, column=1, sticky="ew", padx=2)
        ttk.Label(dialog, text="Repeat:").grid(row=5, column=2, sticky="w", padx=4)
        repeat_var = tk.StringVar(value="1")
        repeat_entry = ttk.Entry(dialog, textvariable=repeat_var, width=4)
        repeat_entry.grid(row=5, column=3, sticky="ew", padx=2)
        # Enable/disable fields based on type
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
        # OK/Cancel
        def on_ok():
            try:
                delay = int(delay_var.get())
                repeat = int(repeat_var.get())
                if delay < 0 or repeat < 1:
                    raise ValueError
            except Exception:
                self.log("Invalid delay or repeat count.", level="error")
                return
            steps = []
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
                for _ in range(repeat):
                    steps.append((btn_code, delay))
            elif type_var.get() == "Stick":
                stick = stick_var.get()
                direction = dir_var.get()
                try:
                    magnitude = float(mag_var.get())
                except Exception:
                    self.log("Invalid magnitude.", level="error")
                    return
                for _ in range(repeat):
                    steps.append(((stick, direction, magnitude), delay))
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
                for _ in range(repeat):
                    steps.append(({"type": "autoclicker", "button": btn_code, "interval": interval, "duration": duration}, delay))
            for step in steps:
                self.current_macro_steps.append(step)
            self.update_macro_steps_tree()
            dialog.destroy()
        ttk.Button(dialog, text="OK", command=on_ok).grid(row=6, column=1, pady=8)
        ttk.Button(dialog, text="Cancel", command=dialog.destroy).grid(row=6, column=2, pady=8)
        dialog.wait_window()

    def update_macro_steps_tree(self):
        self.macro_steps_tree.delete(*self.macro_steps_tree.get_children())
        for i, (code, delay) in enumerate(self.current_macro_steps):
            if isinstance(code, dict) and code.get('type') == 'autoclicker':
                label = f"Autoclicker {code['button']} {code['interval']}ms"
                mag = code.get('duration', '-')
                self.macro_steps_tree.insert("", "end", iid=str(i), values=("Autoclicker", label, mag, str(delay)))
            elif isinstance(code, tuple):
                stick, direction, magnitude = code
                self.macro_steps_tree.insert("", "end", iid=str(i), values=("Stick", f"{stick} {direction}", f"{magnitude:.2f}", str(delay)))
            else:
                self.macro_steps_tree.insert("", "end", iid=str(i), values=("Button", str(code), "-", str(delay)))

    def edit_macro_step(self):
        sel = self.macro_steps_tree.selection()
        if not sel:
            self.log("No macro step selected to edit.", level="warning")
            return
        idx = int(sel[0])
        code, delay = self.current_macro_steps[idx]
        # Pre-fill dialog with current values
        dialog = tk.Toplevel(self)
        dialog.title("Edit Macro Step")
        dialog.grab_set()
        dialog.resizable(False, False)
        # Determine type
        if isinstance(code, dict) and code.get('type') == 'autoclicker':
            type_val = "Autoclicker"
        elif isinstance(code, tuple):
            type_val = "Stick"
        else:
            type_val = "Button"
        type_var = tk.StringVar(value=type_val)
        ttk.Label(dialog, text="Type:").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        # Place radio buttons together
        type_frame = ttk.Frame(dialog)
        type_frame.grid(row=0, column=1, columnspan=3, sticky="w")
        ttk.Radiobutton(type_frame, text="Button", variable=type_var, value="Button").pack(side="left", padx=2)
        ttk.Radiobutton(type_frame, text="Stick", variable=type_var, value="Stick").pack(side="left", padx=2)
        ttk.Radiobutton(type_frame, text="Autoclicker", variable=type_var, value="Autoclicker").pack(side="left", padx=2)
        # Button selection
        btn_choices = [display for group in MANUAL_CONTROLS if group["label"] not in ("Left Stick", "Right Stick") for display, _ in group["buttons"]]
        btn_var = tk.StringVar(value="")
        stick_var = tk.StringVar(value="LEFT_STICK")
        dir_var = tk.StringVar(value="UP")
        mag_var = tk.DoubleVar(value=1.0)
        auto_interval_var = tk.StringVar(value="100")
        auto_duration_var = tk.StringVar(value="")
        if type_val == "Button" and not isinstance(code, tuple):
            for group in MANUAL_CONTROLS:
                for display, c in group["buttons"]:
                    if c == code:
                        btn_var.set(display)
        if type_val == "Stick" and isinstance(code, tuple):
            stick_var.set(code[0])
            dir_var.set(code[1])
            mag_var.set(code[2])
        if type_val == "Autoclicker" and isinstance(code, dict):
            for group in MANUAL_CONTROLS:
                for display, c in group["buttons"]:
                    if c == code.get("button"):
                        btn_var.set(display)
            auto_interval_var.set(str(code.get("interval", 100)))
            auto_duration_var.set(str(code.get("duration", "")) if code.get("duration") is not None else "")
        btn_combo = ttk.Combobox(dialog, textvariable=btn_var, values=btn_choices, state="readonly", width=14)
        btn_combo.grid(row=1, column=1, columnspan=2, sticky="ew", padx=2)
        stick_combo = ttk.Combobox(dialog, textvariable=stick_var, values=["LEFT_STICK", "RIGHT_STICK"], state="readonly", width=10)
        stick_combo.grid(row=2, column=1, sticky="ew", padx=2)
        dir_combo = ttk.Combobox(dialog, textvariable=dir_var, values=["UP", "DOWN", "LEFT", "RIGHT", "NEUTRAL"], state="readonly", width=10)
        dir_combo.grid(row=2, column=2, sticky="ew", padx=2)
        ttk.Label(dialog, text="Magnitude:").grid(row=3, column=0, sticky="w", padx=4)
        mag_entry = ttk.Entry(dialog, textvariable=mag_var, width=6)
        mag_entry.grid(row=3, column=1, sticky="ew", padx=2)
        # Interval label with tooltip
        interval_label = ttk.Label(dialog, text="Interval (ms):")
        interval_label.grid(row=4, column=0, sticky="w", padx=4)
        ToolTip(interval_label, "Interval (ms): How often to press the button. Lower = faster. Minimum 10ms.")
        auto_interval_entry = ttk.Entry(dialog, textvariable=auto_interval_var, width=8)
        auto_interval_entry.grid(row=4, column=1, sticky="ew", padx=2)
        # Duration label with tooltip
        duration_label = ttk.Label(dialog, text="Duration (ms, blank=until macro stops):")
        duration_label.grid(row=4, column=2, sticky="w", padx=4)
        ToolTip(duration_label, "How long to run the autoclicker for this step (in milliseconds). Leave blank to run until the macro or autoclicker is stopped.")
        auto_duration_entry = ttk.Entry(dialog, textvariable=auto_duration_var, width=10)
        auto_duration_entry.grid(row=4, column=3, sticky="ew", padx=2)
        # Delay and repeat
        delay_label = ttk.Label(dialog, text="Delay (ms):")
        delay_label.grid(row=5, column=0, sticky="w", padx=4)
        ToolTip(delay_label, "How long to wait after this step before the next step (in milliseconds).")
        delay_var = tk.StringVar(value=str(delay))
        delay_entry = ttk.Entry(dialog, textvariable=delay_var, width=8)
        delay_entry.grid(row=5, column=1, sticky="ew", padx=2)
        ttk.Label(dialog, text="Repeat:").grid(row=5, column=2, sticky="w", padx=4)
        repeat_var = tk.StringVar(value="1")
        repeat_entry = ttk.Entry(dialog, textvariable=repeat_var, width=4)
        repeat_entry.grid(row=5, column=3, sticky="ew", padx=2)
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
                new_delay = int(delay_var.get())
                if new_delay < 0:
                    raise ValueError
            except Exception:
                self.log("Invalid delay.", level="error")
                return
            if type_var.get() == "Button":
                btn_display = btn_var.get()
                btn_code = None
                for group in MANUAL_CONTROLS:
                    for display, c in group["buttons"]:
                        if display == btn_display:
                            btn_code = c
                if btn_code is None:
                    self.log(f"Invalid button: {btn_display}", level="error")
                    return
                self.current_macro_steps[idx] = (btn_code, new_delay)
            elif type_var.get() == "Stick":
                stick = stick_var.get()
                direction = dir_var.get()
                try:
                    magnitude = float(mag_var.get())
                except Exception:
                    self.log("Invalid magnitude.", level="error")
                    return
                self.current_macro_steps[idx] = ((stick, direction, magnitude), new_delay)
            else:  # Autoclicker
                btn_display = btn_var.get()
                btn_code = None
                for group in MANUAL_CONTROLS:
                    for display, c in group["buttons"]:
                        if display == btn_display:
                            btn_code = c
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
                self.current_macro_steps[idx] = ( {"type": "autoclicker", "button": btn_code, "interval": interval, "duration": duration}, new_delay )
            self.update_macro_steps_tree()
            dialog.destroy()
        ttk.Button(dialog, text="OK", command=on_ok).grid(row=6, column=1, pady=8)
        ttk.Button(dialog, text="Cancel", command=dialog.destroy).grid(row=6, column=2, pady=8)
        dialog.wait_window()

    def remove_macro_step(self):
        sel = self.macro_steps_tree.selection()
        if not sel:
            self.log("No macro step selected to remove.", level="warning")
            return
        idx = int(sel[0])
        self.current_macro_steps.pop(idx)
        self.update_macro_steps_tree()

    def move_macro_step_up(self):
        sel = self.macro_steps_tree.selection()
        if not sel:
            self.log("No macro step selected to move.", level="warning")
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
            self.log("No macro step selected to move.", level="warning")
            return
        idx = int(sel[0])
        if idx >= len(self.current_macro_steps)-1:
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

    def load_all_macros(self):
        # Ensure Macros/ folder exists
        macros_dir = os.path.join(os.path.dirname(__file__), '../../Macros')
        os.makedirs(macros_dir, exist_ok=True)
        self.macros.clear()
        for path in glob.glob(os.path.join(macros_dir, '*.macro.json')):
            try:
                macro = Macro.load(path)
                self.macros[macro.name] = macro
            except Exception as e:
                self.log(f"Error loading macro from {path}: {e}", level="error")

    def refresh_macro_list(self, select_macro=None):
        self.load_all_macros()
        self.macro_listbox.delete(0, tk.END)
        for name in sorted(self.macros.keys()):
            running = name in self.running_macros and self.running_macros[name]._thread and self.running_macros[name]._thread.is_alive()
            label = f"{name} {'[RUNNING]' if running else ''}"
            self.macro_listbox.insert(tk.END, label)
        # Update end-of-loop macro choices
        eol_choices = ["None", "Custom"] + sorted(self.macros.keys())
        self.eol_macro_combo["values"] = eol_choices
        self.update_eol_macro_steps_tree()
        # Auto-select and load macro if requested
        if select_macro and select_macro in self.macros:
            idx = list(sorted(self.macros.keys())).index(select_macro)
            self.macro_listbox.selection_clear(0, tk.END)
            self.macro_listbox.selection_set(idx)
            self.on_macro_select()

    def save_macro(self):
        name = self.macro_name_var.get().strip()
        if not name:
            self.log("Macro name required.", level="warning")
            return
        if not self.current_macro_steps:
            self.log("No steps to save.", level="warning")
            return
        macro = Macro(name, self.current_macro_steps)
        # Save end-of-loop macro info
        val = self.eol_macro_var.get()
        if val == "Custom":
            macro.end_of_loop_macro = self.current_eol_macro_steps.copy()
            macro.end_of_loop_macro_name = None
        elif val and val != "None":
            macro.end_of_loop_macro = []
            macro.end_of_loop_macro_name = val
        else:
            macro.end_of_loop_macro = []
            macro.end_of_loop_macro_name = None
        macros_dir = os.path.join(os.path.dirname(__file__), '../../Macros')
        os.makedirs(macros_dir, exist_ok=True)
        path = os.path.join(macros_dir, f"{name}.macro.json")
        try:
            macro.save(path)
            self.log(f"Macro saved to {path}", level="success")
            self.refresh_macro_list(select_macro=name)
        except Exception as e:
            self.log(f"Error saving macro: {e}", level="error")

    def import_macro(self):
        import tkinter.filedialog as fd
        paths = fd.askopenfilenames(filetypes=[("Macro Files", "*.macro.json")])
        if not paths:
            return
        imported = 0
        for path in paths:
            try:
                macro = Macro.load(path)
                macros_dir = os.path.join(os.path.dirname(__file__), '../../Macros')
                os.makedirs(macros_dir, exist_ok=True)
                dest = os.path.join(macros_dir, os.path.basename(path))
                macro.save(dest)
                self.macros[macro.name] = macro
                imported += 1
            except Exception as e:
                self.log(f"Error importing macro from {path}: {e}", level="error")
        self.refresh_macro_list()
        if imported:
            # Auto-select the last imported macro
            self.refresh_macro_list(select_macro=macro.name)
        self.log(f"Imported {imported} macro(s).", level="success")

    def delete_macro(self):
        sel = self.macro_listbox.curselection()
        if not sel:
            self.log("No macro selected to delete.", level="warning")
            return
        idx = sel[0]
        name = self.macro_listbox.get(idx).replace(" [RUNNING]", "").strip()
        macros_dir = os.path.join(os.path.dirname(__file__), '../../Macros')
        path = os.path.join(macros_dir, f"{name}.macro.json")
        try:
            if os.path.exists(path):
                os.remove(path)
                self.log(f"Deleted macro: {name}", level="success")
            else:
                self.log(f"Macro file not found: {path}", level="warning")
        except Exception as e:
            self.log(f"Error deleting macro: {e}", level="error")
        self.refresh_macro_list()

    def export_macro(self):
        import tkinter.filedialog as fd
        sel = self.macro_listbox.curselection()
        if not sel:
            self.log("No macro selected to export.", level="warning")
            return
        for idx in sel:
            name = self.macro_listbox.get(idx)
            macro = self.macros.get(name)
            if not macro:
                self.log(f"Macro not found: {name}", level="error")
                continue
            path = fd.asksaveasfilename(defaultextension=".macro.json", initialfile=f"{name}.macro.json", filetypes=[("Macro Files", "*.macro.json")])
            if not path:
                continue
            try:
                macro.save(path)
                self.log(f"Exported macro: {name} to {path}", level="success")
            except Exception as e:
                self.log(f"Error exporting macro {name}: {e}", level="error")

    def run_selected_macros(self):
        sel = self.macro_listbox.curselection()
        if not sel:
            self.log("No macro selected to run.", level="warning")
            return
        # Get loop count from GUI
        try:
            loop_count = int(self.macro_loop_count_var.get())
        except Exception:
            loop_count = 1
        for idx in sel:
            name = self.macro_listbox.get(idx).replace(" [RUNNING]", "").strip()
            macro = self.macros.get(name)
            if not macro:
                self.log(f"Macro not found: {name}", level="error")
                continue
            if name in self.running_macros and self.running_macros[name]._thread and self.running_macros[name]._thread.is_alive():
                self.log(f"Macro already running: {name}", level="warning")
                continue
            # Pass a refresh callback to MacroRunner
            runner = MacroRunner(self.command_queue, macro, self.log, refresh_callback=self.refresh_macro_list)
            self.running_macros[name] = runner
            runner.play(loop_count=loop_count)
            self.log(f"Started macro: {name}", level="success")
        self.refresh_macro_list()

    def stop_selected_macros(self):
        sel = self.macro_listbox.curselection()
        if not sel:
            self.log("No macro selected to stop.", level="warning")
            return
        for idx in sel:
            name = self.macro_listbox.get(idx).replace(" [RUNNING]", "").strip()
            runner = self.running_macros.get(name)
            if runner:
                runner.stop()
                self.log(f"Stopped macro: {name}", level="success")
        self.refresh_macro_list()

    def edit_eol_macro_dialog(self):
        # Dialog for editing custom end-of-loop macro steps
        dialog = tk.Toplevel(self)
        dialog.title("Edit End-of-Loop Macro")
        dialog.grab_set()
        dialog.resizable(False, False)
        steps = self.current_eol_macro_steps.copy()
        tree = ttk.Treeview(dialog, columns=("Type", "Name/Dir", "Mag", "Delay"), show="headings", height=8)
        for col in ("Type", "Name/Dir", "Mag", "Delay"):
            tree.heading(col, text=col)
            tree.column(col, width=70 if col!="Name/Dir" else 120)
        tree.pack(fill="both", expand=True, padx=4, pady=4)
        def update_tree():
            tree.delete(*tree.get_children())
            for i, (code, delay) in enumerate(steps):
                if isinstance(code, dict) and code.get('type') == 'autoclicker':
                    label = f"Autoclicker {code['button']} {code['interval']}ms"
                    mag = code.get('duration', '-')
                    tree.insert("", "end", iid=str(i), values=("Autoclicker", label, mag, str(delay)))
                elif isinstance(code, tuple):
                    stick, direction, magnitude = code
                    tree.insert("", "end", iid=str(i), values=("Stick", f"{stick} {direction}", f"{magnitude:.2f}", str(delay)))
                else:
                    tree.insert("", "end", iid=str(i), values=("Button", str(code), "-", str(delay)))
        update_tree()
        def add_step():
            self.add_macro_step_dialog()
            steps.extend(self.current_macro_steps[len(steps):])
            update_tree()
        def remove_step():
            sel = tree.selection()
            if not sel:
                return
            idx = int(sel[0])
            steps.pop(idx)
            update_tree()
        ttk.Button(dialog, text="Add Step", command=add_step).pack(side="left", padx=2, pady=2)
        ttk.Button(dialog, text="Remove Step", command=remove_step).pack(side="left", padx=2, pady=2)
        def on_ok():
            self.current_eol_macro_steps = steps.copy()
            self.update_eol_macro_steps_tree()
            dialog.destroy()
        ttk.Button(dialog, text="OK", command=on_ok).pack(side="right", padx=4, pady=4)
        ttk.Button(dialog, text="Cancel", command=dialog.destroy).pack(side="right", padx=4, pady=4)
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
        for i, (code, delay) in enumerate(steps):
            if isinstance(code, dict) and code.get('type') == 'autoclicker':
                label = f"Autoclicker {code['button']} {code['interval']}ms"
                mag = code.get('duration', '-')
                self.eol_macro_steps_tree.insert("", "end", iid=str(i), values=("Autoclicker", label, mag, str(delay)))
            elif isinstance(code, tuple):
                stick, direction, magnitude = code
                self.eol_macro_steps_tree.insert("", "end", iid=str(i), values=("Stick", f"{stick} {direction}", f"{magnitude:.2f}", str(delay)))
            else:
                self.eol_macro_steps_tree.insert("", "end", iid=str(i), values=("Button", str(code), "-", str(delay)))

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

def launch_gui():
    app = PSRemotePlayGUI()
    app.mainloop()

if __name__ == "__main__":
    launch_gui() 