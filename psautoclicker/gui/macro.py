import threading
import time
import json
from .autoclicker import Autoclicker
from colorama import Fore

class Macro:
    def __init__(self, name, steps=None, end_of_loop_macro=None, end_of_loop_macro_name=None):
        self.name = name
        self.steps = steps or []  # List of (step, delay_ms)
        self.end_of_loop_macro = end_of_loop_macro or []  # List of (step, delay_ms)
        self.end_of_loop_macro_name = end_of_loop_macro_name  # Name of saved macro to use as end-of-loop macro

    def add_step(self, step, delay_ms):
        self.steps.append((step, delay_ms))

    def to_dict(self):
        return {
            "name": self.name,
            "steps": self.steps,
            "end_of_loop_macro": self.end_of_loop_macro,
            "end_of_loop_macro_name": self.end_of_loop_macro_name,
        }

    @staticmethod
    def from_dict(d):
        return Macro(
            d["name"],
            d["steps"],
            d.get("end_of_loop_macro", []),
            d.get("end_of_loop_macro_name"),
        )

    def save(self, path):
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f)

    @staticmethod
    def load(path):
        with open(path, 'r') as f:
            d = json.load(f)
        return Macro.from_dict(d)

class MacroRunner:
    def __init__(self, command_queue, macro, log_callback, get_macro_by_name=None, refresh_callback=None):
        self.command_queue = command_queue
        self.macro = macro
        self.log_callback = log_callback
        self._thread = None
        self._running = threading.Event()
        self._autoclickers = []
        self._loop_count = 1
        self.get_macro_by_name = get_macro_by_name  # function to get a Macro by name
        self.refresh_callback = refresh_callback

    def play(self, loop_count=1):
        if self._thread and self._thread.is_alive():
            self.log_callback("Macro already running.")
            return
        self._loop_count = loop_count
        self._running.set()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self.log_callback(f"Playing macro: {self.macro.name} (loops: {'infinite' if loop_count==-1 else loop_count})")

    def stop(self):
        self._running.clear()
        for ac in self._autoclickers:
            ac.stop()
        self._autoclickers.clear()
        if self._thread and threading.current_thread() != self._thread:
            self._thread.join(timeout=1)
        self.log_callback("Macro stopped.")

    def _run_steps(self, steps):
        for step, delay_ms in steps:
            if not self._running.is_set():
                break
            if isinstance(step, dict) and step.get('type') == 'autoclicker':
                ac = Autoclicker(
                    self.command_queue,
                    step['button'],
                    step['interval'],
                    self.log_callback,
                    duration_ms=step.get('duration'),
                    stop_event=self._running
                )
                self._autoclickers.append(ac)
                ac.start()
                self.log_callback(f"Started autoclicker in macro: {step['button']} every {step['interval']}ms")
            elif isinstance(step, tuple) and len(step) == 3:
                self.command_queue.put(step)
                self.log_callback(f"Macro step: Stick {step}")
            else:
                self.command_queue.put(step)
                self.log_callback(f"Macro step: Button {step}")
            time.sleep(delay_ms / 1000.0)

    def _run(self):
        try:
            loop_num = 0
            while self._running.is_set() and (self._loop_count == -1 or loop_num < self._loop_count):
                self.log_callback(f"Macro loop {loop_num+1}")
                self._run_steps(self.macro.steps)
                # End-of-loop macro
                end_steps = []
                if self.macro.end_of_loop_macro_name and self.get_macro_by_name:
                    macro_obj = self.get_macro_by_name(self.macro.end_of_loop_macro_name)
                    if macro_obj:
                        end_steps = macro_obj.steps
                        self.log_callback(f"Running end-of-loop macro: {macro_obj.name}")
                elif self.macro.end_of_loop_macro:
                    end_steps = self.macro.end_of_loop_macro
                    self.log_callback("Running custom end-of-loop macro")
                if end_steps:
                    self._run_steps(end_steps)
                # Colored debug message for loop completion
                print(Fore.CYAN + f"[DEBUG] Completed macro loop {loop_num+1}")
                self.log_callback(f"[DEBUG] Completed macro loop {loop_num+1}", level="info")
                loop_num += 1
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            self.log_callback(f"Macro error: {e}\n{tb}")
        self.stop()
        if self.refresh_callback:
            self.refresh_callback() 