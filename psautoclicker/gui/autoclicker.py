import threading
import time

class Autoclicker:
    def __init__(self, command_queue, button_code, interval_ms, log_callback, duration_ms=None, stop_event=None):
        self.command_queue = command_queue
        self.button_code = button_code
        self.interval = interval_ms / 1000.0
        self.duration = duration_ms / 1000.0 if duration_ms is not None else None
        self.log_callback = log_callback
        self._running = threading.Event()
        self._thread = None
        self._external_stop = stop_event

    def start(self):
        if self._thread and self._thread.is_alive():
            self.log_callback("Autoclicker already running.")
            return
        self._running.set()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self.log_callback(f"Autoclicker started for {self.button_code} every {self.interval*1000:.0f} ms.")

    def stop(self):
        self._running.clear()
        if self._thread:
            self._thread.join(timeout=1)
        self.log_callback("Autoclicker stopped.")

    def _run(self):
        try:
            start_time = time.time()
            while self._running.is_set():
                if self._external_stop and not self._external_stop.is_set():
                    break
                self.command_queue.put(self.button_code)
                time.sleep(self.interval)
                if self.duration is not None and (time.time() - start_time) >= self.duration:
                    break
        except Exception as e:
            self.log_callback(f"Autoclicker error: {e}")
        self._running.clear() 