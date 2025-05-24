import sys
import subprocess
import pkg_resources
import os

REQUIREMENTS_PATH = os.path.join(os.path.dirname(__file__), '..', 'requirements.txt')

def install_requirements():
    with open(REQUIREMENTS_PATH) as f:
        required = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    installed = {pkg.key for pkg in pkg_resources.working_set}
    missing = [pkg for pkg in required if pkg.split('==')[0].lower() not in installed]
    if missing:
        print(f"Installing missing packages: {missing}")
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', *missing])
        print("\nPackages installed. Please restart the application.")
        input("Press Enter to exit...")
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
    from gui.app import launch_gui
    launch_gui() 