import asyncio
import argparse
import json
import os
from pyremoteplay import RPDevice

SAVED_IPS_PATH = os.path.join(os.path.dirname(__file__), 'psautoclicker', 'saved_ips.json')

def load_saved_ips():
    if not os.path.exists(SAVED_IPS_PATH):
        return {}
    with open(SAVED_IPS_PATH, 'r') as f:
        return json.load(f)

def select_host(saved_ips):
    if not saved_ips:
        print("No saved hosts found in saved_ips.json.")
        return None
    if len(saved_ips) == 1:
        return list(saved_ips.values())[0]['host']
    print("Available hosts:")
    for idx, (name, entry) in enumerate(saved_ips.items(), 1):
        print(f"  {idx}. {name} ({entry['host']})")
    while True:
        try:
            sel = int(input("Select host by number: "))
            if 1 <= sel <= len(saved_ips):
                return list(saved_ips.values())[sel-1]['host']
        except Exception:
            pass
        print("Invalid selection.")

async def task(device):
    """Task to run. This presses D-Pad buttons repeatedly."""
    buttons = ("LEFT", "RIGHT", "UP", "DOWN")
    await device.async_wait_for_session()
    print("Session ready. Sending D-Pad input...")
    while device.connected:
        for button in buttons:
            try:
                await device.controller.async_button(button)
                print(f"Sent: {button}")
            except Exception as e:
                print(f"Error sending {button}: {e}")
            await asyncio.sleep(1)
    print("Device disconnected")

async def get_user(device):
    if not await device.async_get_status():
        print("Could not get device status")
        return None
    users = device.get_users()
    if not users:
        print("No Users")
        return None
    return users[0]

async def runner(host):
    device = RPDevice(host)
    user = await get_user(device)
    if not user:
        return
    if not device.is_on:
        device.wakeup(user)
        if not await device.async_wait_for_wakeup():
            print("Timed out waiting for device to wakeup")
            return
    device.create_session(user)
    if not await device.connect():
        print("Failed to start Session")
        return
    asyncio.create_task(task(device))
    while device.connected:
        try:
            await asyncio.sleep(0)
        except KeyboardInterrupt:
            device.disconnect()
            break

def main():
    parser = argparse.ArgumentParser(description="Minimal pyremoteplay async CLI.")
    parser.add_argument("--host", type=str, help="IP address of Remote Play host")
    parser.add_argument("--list-hosts", action="store_true", help="List available hosts from saved_ips.json and exit")
    args = parser.parse_args()
    saved_ips = load_saved_ips()
    if args.list_hosts:
        if not saved_ips:
            print("No saved hosts found.")
        else:
            print("Available hosts:")
            for name, entry in saved_ips.items():
                print(f"  {name}: {entry['host']}")
        return
    host = args.host
    if not host:
        host = select_host(saved_ips)
    if not host:
        print("No host selected. Exiting.")
        return
    loop = asyncio.get_event_loop()
    loop.run_until_complete(runner(host))

if __name__ == "__main__":
    main() 