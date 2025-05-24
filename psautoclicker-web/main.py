import sys
import subprocess
import pkg_resources
import os
import threading
import webbrowser
import time
import platform
from packaging.requirements import Requirement
from packaging.version import Version, InvalidVersion

REQUIREMENTS_PATH = os.path.join(os.path.dirname(__file__), 'requirements.txt')
AUTO_OPEN_BROWSER = True  # Set to False to disable auto-opening the web UI

def install_requirements():
    with open(REQUIREMENTS_PATH) as f:
        required = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    installed = {pkg.key: pkg.version for pkg in pkg_resources.working_set}
    missing = []
    for req_str in required:
        try:
            req = Requirement(req_str)
            key = req.name.lower()
            if key not in installed:
                missing.append(req_str)
            else:
                try:
                    if req.specifier and not req.specifier.contains(Version(installed[key]), prereleases=True):
                        missing.append(req_str)
                except InvalidVersion:
                    missing.append(req_str)
        except Exception:
            # fallback: if parsing fails, try to install
            missing.append(req_str)
    if missing:
        print(f"Installing missing packages: {missing}")
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', *missing])
        print("\nPackages installed. Restarting application...")
        time.sleep(1)
        try:
            if platform.system() == "Windows":
                subprocess.Popen([sys.executable] + sys.argv, shell=True)
                sys.exit(0)
            else:
                os.execv(sys.executable, [sys.executable] + sys.argv)
        except Exception as e:
            print(f"Automatic restart failed: {e}")
            print("Please restart the application manually.")
            sys.exit(0)

if __name__ == "__main__":
    try:
        # Only check requirements if not running as a PyInstaller bundle
        if not getattr(sys, 'frozen', False):
            install_requirements()
    except Exception as e:
        print(f"Error checking/installing requirements: {e}")
        input("Press Enter to exit...")
        sys.exit(1)
    from gui.webserver import app, socketio
    def run_server():
        socketio.run(app, host="0.0.0.0", port=8000, debug=False, use_reloader=False)
    if AUTO_OPEN_BROWSER:
        threading.Timer(1.0, lambda: webbrowser.open("http://localhost:8000/")).start()
    run_server() 