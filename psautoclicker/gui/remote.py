import threading
import asyncio
from pyremoteplay import RPDevice
import queue

class SessionWorker(threading.Thread):
    def __init__(self, host, command_queue, log_callback, on_connected, on_disconnected):
        super().__init__(daemon=True)
        self.host = host
        self.command_queue = command_queue
        self.log_callback = log_callback
        self.on_connected = on_connected
        self.on_disconnected = on_disconnected
        self._disconnect_event = threading.Event()
        self.loop = None
        self.device = None

    def run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._main())

    def disconnect(self):
        self._disconnect_event.set()
        if self.device:
            self.loop.call_soon_threadsafe(self.device.disconnect)

    async def _main(self):
        try:
            self.device = RPDevice(self.host)
            user = await self._get_user(self.device)
            if not user:
                self.log_callback("No user found on device.")
                self.on_disconnected()
                return
            if not self.device.is_on:
                self.device.wakeup(user)
                self.log_callback("Waking up device...")
                if not await self.device.async_wait_for_wakeup():
                    self.log_callback("Timed out waiting for device to wakeup")
                    self.on_disconnected()
                    return
            self.device.create_session(user)
            if not await self.device.connect():
                self.log_callback("Failed to start Session")
                self.on_disconnected()
                return
            self.log_callback("Session connected. Waiting for session to be ready...")
            await self.device.async_wait_for_session()
            self.on_connected()
            self.log_callback("Session ready. Processing button commands...")
            while self.device.connected and not self._disconnect_event.is_set():
                try:
                    cmd = self.command_queue.get(timeout=0.1)
                    if isinstance(cmd, tuple) and len(cmd) == 3:
                        stick, direction, magnitude = cmd
                        await self.device.controller.async_stick(stick, direction, magnitude)
                        self.log_callback(f"Sent stick: {stick} {direction} {magnitude}")
                    else:
                        await self.device.controller.async_button(cmd)
                        self.log_callback(f"Sent button: {cmd}")
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    if isinstance(e, queue.Empty):
                        await asyncio.sleep(0.05)
                        continue
                    self.log_callback(f"Error sending input: {e}")
            self.device.disconnect()
            self.log_callback("Session disconnected.")
        except Exception as e:
            self.log_callback(f"Session error: {e}")
        finally:
            self.on_disconnected()

    async def _get_user(self, device):
        if not await device.async_get_status():
            return None
        users = device.get_users()
        if not users:
            return None
        return users[0] 