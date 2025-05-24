from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
import os
import json
import glob
import threading
import time
import uuid
from pyremoteplay import RPDevice
import queue
import shutil
from flask_socketio import SocketIO, emit, join_room
import sys
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)

# Always resolve paths relative to the project root (where main.py is)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAVED_IPS_PATH = os.path.join(PROJECT_ROOT, "saved_ips.json")
MACROS_DIR = os.path.join(PROJECT_ROOT, "Macros")

macro_jobs = {}
connected_device = {"ip": None, "status": "disconnected"}

rp_device = None
rp_command_queue = queue.Queue()
rp_session_thread = None

socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

manual_autoclicker_thread = None
manual_autoclicker_stop = threading.Event()

macro_stop_events = {}

# --- Device Management Endpoints ---
print(f"[DEBUG] SAVED_IPS_PATH resolved to: {SAVED_IPS_PATH}")

def ensure_saved_ips():
    # Always ensure saved_ips.json is a dict
    print(f"[DEBUG] ensure_saved_ips called. Path: {SAVED_IPS_PATH}")
    if not os.path.exists(SAVED_IPS_PATH):
        print("[DEBUG] saved_ips.json does not exist, creating new.")
        with open(SAVED_IPS_PATH, 'w') as f:
            json.dump({}, f)
    else:
        try:
            with open(SAVED_IPS_PATH, 'r') as f:
                data = json.load(f)
            print(f"[DEBUG] saved_ips.json loaded: {data}")
            if not isinstance(data, dict):
                print("[DEBUG] saved_ips.json is not a dict, resetting.")
                with open(SAVED_IPS_PATH, 'w') as f:
                    json.dump({}, f)
        except Exception as e:
            print(f"[DEBUG] Error reading saved_ips.json: {e}, resetting.")
            with open(SAVED_IPS_PATH, 'w') as f:
                json.dump({}, f)

def read_devices():
    ensure_saved_ips()
    with open(SAVED_IPS_PATH, 'r') as f:
        data = json.load(f)
        print(f"[DEBUG] read_devices loaded: {data}")
        return data

def write_devices(devices):
    print(f"[DEBUG] write_devices called with: {devices}")
    with open(SAVED_IPS_PATH, 'w') as f:
        json.dump(devices, f, indent=2)
    print(f"[DEBUG] write_devices wrote to {SAVED_IPS_PATH}")

@app.route("/api/devices", methods=["GET"])
def list_devices():
    devices = read_devices()
    # Return as a list of dicts with key, host, label
    return jsonify([
        {"key": k, "host": v["host"], "label": v.get("label", "")}
        for k, v in devices.items()
    ])

@app.route("/api/devices", methods=["POST"])
def add_device():
    data = request.json
    host = data.get("host")
    label = data.get("label", "")
    print(f"[DEBUG] add_device called with host={host}, label={label}")
    if not host:
        return jsonify({"error": "Host required"}), 400
    devices = read_devices()
    print(f"[DEBUG] Devices before add: {devices}")
    key = host
    devices[key] = {"host": host, "label": label}
    write_devices(devices)
    print(f"[DEBUG] Devices after add: {devices}")
    return jsonify({"status": "ok"})

@app.route("/api/devices/<key>", methods=["PUT"])
def edit_device(key):
    data = request.json
    host = data.get("host")
    label = data.get("label", "")
    print(f"[DEBUG] edit_device called with key={key}, host={host}, label={label}")
    devices = read_devices()
    print(f"[DEBUG] Devices before edit: {devices}")
    if key not in devices:
        return jsonify({"error": "Device not found"}), 404
    devices[key] = {"host": host, "label": label}
    write_devices(devices)
    print(f"[DEBUG] Devices after edit: {devices}")
    return jsonify({"status": "ok"})

@app.route("/api/devices/<key>", methods=["DELETE"])
def delete_device(key):
    print(f"[DEBUG] delete_device called with key={key}")
    devices = read_devices()
    print(f"[DEBUG] Devices before delete: {devices}")
    if key in devices:
        del devices[key]
        write_devices(devices)
        print(f"[DEBUG] Devices after delete: {devices}")
        return jsonify({"status": "ok"})
    print(f"[DEBUG] Device {key} not found for delete.")
    return jsonify({"error": "Device not found"}), 404

# --- Macro Management (Stub) ---
@app.route("/api/macros", methods=["GET"])
def list_macros():
    if not os.path.exists(MACROS_DIR):
        return jsonify([])
    macro_files = glob.glob(os.path.join(MACROS_DIR, "*.json"))
    macros = []
    for path in macro_files:
        try:
            with open(path, "r") as f:
                macro = json.load(f)
                macros.append(macro)
        except Exception:
            continue
    return jsonify(macros)

@app.route("/api/macros", methods=["POST"])
def add_macro():
    macro = request.json
    if not macro or not macro.get("name"):
        return jsonify({"error": "Macro must have a name"}), 400
    if not os.path.exists(MACROS_DIR):
        os.makedirs(MACROS_DIR)
    macro_path = os.path.join(MACROS_DIR, f"{macro['name']}.json")
    with open(macro_path, "w") as f:
        json.dump(macro, f, indent=2)
    return jsonify({"status": "ok"})

@app.route("/api/macros/<name>", methods=["DELETE"])
def delete_macro(name):
    macro_path = os.path.join(MACROS_DIR, f"{name}.json")
    if os.path.exists(macro_path):
        os.remove(macro_path)
        return jsonify({"status": "ok"})
    return jsonify({"error": "Macro not found"}), 404

@app.route("/api/macros/import", methods=["POST"])
def import_macro():
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    file = request.files['file']
    if not file.filename.endswith('.json'):
        return jsonify({"error": "Only .json files allowed"}), 400
    filename = secure_filename(file.filename)
    if not os.path.exists(MACROS_DIR):
        os.makedirs(MACROS_DIR)
    path = os.path.join(MACROS_DIR, filename)
    file.save(path)
    return jsonify({"status": "ok"})

@app.route("/api/macros/export/<name>", methods=["GET"])
def export_macro(name):
    filename = f"{name}.json"
    path = os.path.join(MACROS_DIR, filename)
    if not os.path.exists(path):
        return jsonify({"error": "Macro not found"}), 404
    return send_file(path, as_attachment=True)

# --- Automation Control (Stub) ---
@app.route("/api/connect", methods=["POST"])
def connect_device():
    global rp_device, rp_command_queue, rp_session_thread
    data = request.json
    ip = data.get("ip")
    if not ip:
        return jsonify({"error": "Device IP required"}), 400
    try:
        rp_device = RPDevice(ip)
        users = rp_device.get_users()
        if not users:
            return jsonify({"error": "No users found on device"}), 400
        user = users[0]
        rp_device.get_status()
        rp_device.create_session(user)
        connected_device["ip"] = ip
        connected_device["status"] = "connected"
        return jsonify({"status": "connected", "ip": ip})
    except Exception as e:
        connected_device["ip"] = None
        connected_device["status"] = "disconnected"
        return jsonify({"error": str(e)}), 500

@app.route("/api/disconnect", methods=["POST"])
def disconnect_device():
    global rp_device
    if rp_device:
        try:
            rp_device.disconnect()
        except Exception:
            pass
    rp_device = None
    connected_device["ip"] = None
    connected_device["status"] = "disconnected"
    return jsonify({"status": "disconnected"})

@app.route("/api/connection_status", methods=["GET"])
def connection_status():
    return jsonify(connected_device)

@app.route("/api/run_macro", methods=["POST"])
def run_macro():
    global rp_device, rp_command_queue
    data = request.json
    macro_name = data.get("name")
    loop_count = data.get("loop_count", 1)
    if not macro_name:
        return jsonify({"error": "Macro name required"}), 400
    if not rp_device or connected_device["status"] != "connected":
        return jsonify({"error": "Not connected to any device"}), 400
    macro_path = os.path.join(MACROS_DIR, f"{macro_name}.json")
    if not os.path.exists(macro_path):
        return jsonify({"error": "Macro not found"}), 404
    with open(macro_path, "r") as f:
        macro = json.load(f)
    end_steps = []
    if macro.get("end_of_loop_macro_name"):
        end_macro_path = os.path.join(MACROS_DIR, f"{macro['end_of_loop_macro_name']}.json")
        if os.path.exists(end_macro_path):
            with open(end_macro_path, "r") as ef:
                end_macro = json.load(ef)
                end_steps = end_macro.get("steps", [])
    elif macro.get("end_of_loop_macro"):
        end_steps = macro["end_of_loop_macro"]
    job_id = str(uuid.uuid4())
    macro_jobs[job_id] = {"status": "running", "log": []}
    macro_stop_events[job_id] = threading.Event()
    def log_callback(msg):
        macro_jobs[job_id]["log"].append(msg)
        socketio.emit("macro_log", {"job_id": job_id, "log": macro_jobs[job_id]["log"], "status": macro_jobs[job_id]["status"]}, room=job_id)
    def macro_thread():
        try:
            log_callback(f"Starting macro: {macro_name}")
            loop_num = 0
            while (loop_count == -1 or loop_num < loop_count) and not macro_stop_events[job_id].is_set():
                log_callback(f"Macro loop {loop_num+1}")
                try:
                    execute_macro_steps(macro.get("steps", []), log_callback, stop_event=macro_stop_events[job_id])
                except RuntimeError:
                    macro_jobs[job_id]["status"] = "error"
                    return
                if end_steps and not macro_stop_events[job_id].is_set():
                    log_callback("Running end-of-loop macro")
                    try:
                        execute_macro_steps(end_steps, log_callback, stop_event=macro_stop_events[job_id])
                    except RuntimeError:
                        macro_jobs[job_id]["status"] = "error"
                        return
                loop_num += 1
            if macro_stop_events[job_id].is_set():
                macro_jobs[job_id]["status"] = "stopped"
                log_callback("Macro stopped by user.")
            else:
                macro_jobs[job_id]["status"] = "finished"
                log_callback("Macro finished.")
        except Exception as e:
            macro_jobs[job_id]["status"] = "error"
            log_callback(f"Macro error: {e}")
        finally:
            macro_stop_events.pop(job_id, None)
    t = threading.Thread(target=macro_thread, daemon=True)
    t.start()
    return jsonify({"job_id": job_id, "status": "started"})

@app.route("/api/macro_status/<job_id>", methods=["GET"])
def macro_status(job_id):
    job = macro_jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job)

@app.route("/api/stop_macro", methods=["POST"])
def stop_macro():
    data = request.json
    job_id = data.get("job_id")
    if not job_id or job_id not in macro_stop_events:
        return jsonify({"error": "No running macro with that job_id"}), 400
    macro_stop_events[job_id].set()
    return jsonify({"status": "stopping"})

@app.route("/api/button", methods=["POST"])
def send_button():
    global rp_device
    data = request.json
    button = data.get("button")
    if not button:
        return jsonify({"error": "Button required"}), 400
    if not rp_device or connected_device["status"] != "connected":
        return jsonify({"error": "Not connected to any device"}), 400
    try:
        rp_device.controller.button(button)
        return jsonify({"status": "ok", "button": button})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/stick", methods=["POST"])
def send_stick():
    global rp_device
    data = request.json
    stick = data.get("stick")
    direction = data.get("direction")
    magnitude = data.get("magnitude", 1.0)
    if not stick or not direction:
        return jsonify({"error": "Stick and direction required"}), 400
    if not rp_device or connected_device["status"] != "connected":
        return jsonify({"error": "Not connected to any device"}), 400
    try:
        # pyremoteplay expects: stick_name ('left' or 'right'), point (x, y)
        stick_name = stick.replace("_STICK", "").lower()
        if direction == "UP":
            point = (0.0, -magnitude)
        elif direction == "DOWN":
            point = (0.0, magnitude)
        elif direction == "LEFT":
            point = (-magnitude, 0.0)
        elif direction == "RIGHT":
            point = (magnitude, 0.0)
        elif direction == "NEUTRAL":
            point = (0.0, 0.0)
        else:
            return jsonify({"error": "Unknown direction"}), 400
        rp_device.controller.stick(stick_name, point=point)
        rp_device.controller.update_sticks()
        return jsonify({"status": "ok", "stick": stick, "direction": direction, "magnitude": magnitude})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Root: Serve a minimal HTML dashboard ---
@app.route("/")
def dashboard():
    return send_from_directory(os.path.join(os.path.dirname(__file__), "static"), "index.html")

@app.before_request
def log_request_info():
    print(f"[DEBUG] {request.method} {request.path}")

@app.route("/static/<path:filename>")
def static_files(filename):
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    file_path = os.path.join(static_dir, filename)
    print(f"[DEBUG] Serving static file: {file_path}")
    if not os.path.exists(file_path):
        print(f"[ERROR] Static file not found: {file_path}")
    return send_from_directory(static_dir, filename)

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(PROJECT_ROOT, 'app_icon.ico', mimetype='image/vnd.microsoft.icon')

def background_maintenance():
    while True:
        # Ensure saved_ips.json exists and is a dict
        try:
            if not os.path.exists(SAVED_IPS_PATH):
                with open(SAVED_IPS_PATH, "w") as f:
                    json.dump({}, f)
            else:
                # Self-heal: if file is not a dict, reset to {}
                try:
                    with open(SAVED_IPS_PATH, 'r') as f:
                        data = json.load(f)
                    if not isinstance(data, dict):
                        with open(SAVED_IPS_PATH, 'w') as f:
                            json.dump({}, f)
                except Exception as e:
                    with open(SAVED_IPS_PATH, 'w') as f:
                        json.dump({}, f)
        except Exception as e:
            print(f"[Self-Heal] Error ensuring saved_ips.json: {e}")
        # Ensure Macros directory exists
        try:
            if not os.path.exists(MACROS_DIR):
                os.makedirs(MACROS_DIR)
        except Exception as e:
            print(f"[Self-Heal] Error ensuring Macros dir: {e}")
        # Self-heal: Rename .json files in Macros dir that are not .macro.json
        try:
            for fname in os.listdir(MACROS_DIR):
                if fname.endswith(".json") and not fname.endswith(".macro.json"):
                    old_path = os.path.join(MACROS_DIR, fname)
                    base = fname[:-5]  # remove .json
                    new_path = os.path.join(MACROS_DIR, f"{base}.macro.json")
                    # Avoid overwriting existing .macro.json
                    if not os.path.exists(new_path):
                        try:
                            os.rename(old_path, new_path)
                            print(f"[Self-Heal] Renamed {fname} -> {base}.macro.json")
                        except Exception as e:
                            print(f"[Self-Heal] Error renaming {fname}: {e}")
        except Exception as e:
            print(f"[Self-Heal] Error scanning Macros dir: {e}")
        time.sleep(10)

# Start background maintenance thread
threading.Thread(target=background_maintenance, daemon=True).start()

@socketio.on('join_job')
def on_join_job(data):
    job_id = data.get('job_id')
    join_room(job_id)
    # Send current log
    if job_id in macro_jobs:
        emit("macro_log", {"job_id": job_id, "log": macro_jobs[job_id]["log"], "status": macro_jobs[job_id]["status"]})

@app.route("/api/manual_autoclicker/start", methods=["POST"])
def start_manual_autoclicker():
    global manual_autoclicker_thread, manual_autoclicker_stop, rp_device
    data = request.json
    button = data.get("button")
    interval = int(data.get("interval", 100))
    duration = int(data.get("duration", 0))  # ms, 0 = infinite
    if not button:
        return jsonify({"error": "Button required"}), 400
    if not rp_device or connected_device["status"] != "connected":
        return jsonify({"error": "Not connected to any device"}), 400
    if manual_autoclicker_thread and manual_autoclicker_thread.is_alive():
        manual_autoclicker_stop.set()
        manual_autoclicker_thread.join(timeout=1)
    manual_autoclicker_stop.clear()
    def ac_thread():
        start_time = time.time()
        while not manual_autoclicker_stop.is_set():
            try:
                rp_device.controller.button(button)
            except Exception:
                break
            time.sleep(interval / 1000.0)
            if duration > 0 and (time.time() - start_time) * 1000 >= duration:
                break
        manual_autoclicker_stop.set()
    manual_autoclicker_thread = threading.Thread(target=ac_thread, daemon=True)
    manual_autoclicker_thread.start()
    return jsonify({"status": "started"})

@app.route("/api/manual_autoclicker/stop", methods=["POST"])
def stop_manual_autoclicker():
    global manual_autoclicker_thread, manual_autoclicker_stop
    manual_autoclicker_stop.set()
    if manual_autoclicker_thread:
        manual_autoclicker_thread.join(timeout=1)
    return jsonify({"status": "stopped"})

# --- Macro Step Execution Helper ---
def execute_macro_steps(steps, log_callback, stop_event=None):
    global rp_device, connected_device
    for step_tuple in steps:
        if stop_event and stop_event.is_set():
            log_callback("Macro stopped by user.")
            raise RuntimeError("Macro stopped by user")
        if len(step_tuple) == 3:
            step, delay_ms, comment = step_tuple
        else:
            step, delay_ms = step_tuple
            comment = None
        if not rp_device or connected_device["status"] != "connected":
            log_callback("Device disconnected. Stopping macro.")
            raise RuntimeError("Device disconnected")
        if isinstance(step, list) and len(step) >= 3 and step[0] == "REPEAT":
            repeat_count = step[1]
            nested_steps = step[2]
            log_callback(f"Repeat block: {repeat_count} times")
            for i in range(repeat_count):
                if stop_event and stop_event.is_set():
                    log_callback("Macro stopped by user.")
                    raise RuntimeError("Macro stopped by user")
                log_callback(f"Repeat iteration {i+1} of {repeat_count}")
                execute_macro_steps(nested_steps, log_callback, stop_event=stop_event)
            if comment:
                log_callback(f"Repeat comment: {comment}")
            time.sleep(delay_ms / 1000.0)
            continue
        actions = step if isinstance(step, list) else [step]
        autoclickers_started = []
        for action in actions:
            if isinstance(action, dict) and action.get('type') == 'autoclicker':
                def ac_thread(button, interval, duration, stop_event):
                    start_time = time.time()
                    while (duration is None or (time.time() - start_time) < duration) and rp_device and connected_device["status"] == "connected" and (not stop_event or not stop_event.is_set()):
                        try:
                            rp_device.controller.button(button)
                        except Exception as e:
                            log_callback(f"Autoclicker error: {e}")
                            break
                        time.sleep(interval / 1000.0)
                t = threading.Thread(target=ac_thread, args=(action['button'], action['interval'], action.get('duration', None), stop_event), daemon=True)
                t.start()
                autoclickers_started.append(action['button'])
            elif isinstance(action, (list, tuple)) and len(action) == 3:
                stick, direction, magnitude = action
                try:
                    stick_name = stick.replace("_STICK", "").lower()
                    if direction == "UP":
                        point = (0.0, -magnitude)
                    elif direction == "DOWN":
                        point = (0.0, magnitude)
                    elif direction == "LEFT":
                        point = (-magnitude, 0.0)
                    elif direction == "RIGHT":
                        point = (magnitude, 0.0)
                    elif direction == "NEUTRAL":
                        point = (0.0, 0.0)
                    else:
                        log_callback(f"Unknown stick direction: {direction}")
                        continue
                    rp_device.controller.stick(stick_name, point=point)
                    rp_device.controller.update_sticks()
                    log_callback(f"Macro step: Stick {action}")
                except Exception as e:
                    log_callback(f"Error sending stick: {e}")
            else:
                try:
                    rp_device.controller.button(action)
                    log_callback(f"Macro step: Button {action}")
                except Exception as e:
                    log_callback(f"Error sending button: {e}")
        if autoclickers_started:
            log_callback(f"Started autoclicker(s) in macro: {', '.join(map(str, autoclickers_started))}")
        if comment:
            log_callback(f"Step comment: {comment}")
        time.sleep(delay_ms / 1000.0) 