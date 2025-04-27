import hashlib
import subprocess
import platform
import sys

def get_system_info():
    """Retrieve system identifiers based on the operating system."""
    os_name = platform.system()
    if os_name == "Windows":
        # Get disk serial number on Windows
        try:
            result = subprocess.check_output("wmic diskdrive get serialnumber", shell=True).decode()
            serial = result.split("\n")[1].strip()
            return serial
        except Exception as e:
            print(f"Error fetching disk serial: {e}")
            return "unknown-windows-id"
    elif os_name == "Darwin":  # macOS
        try:
            result = subprocess.check_output("system_profiler SPHardwareDataType | grep Serial", shell=True).decode()
            serial = result.split(":")[1].strip()
            return serial
        except Exception as e:
            print(f"Error fetching macOS serial: {e}")
            return "unknown-macos-id"
    else:  # Linux or other
        try:
            result = subprocess.check_output("cat /proc/cpuinfo | grep Serial", shell=True).decode()
            serial = result.split(":")[1].strip()
            return serial
        except Exception as e:
            print(f"Error fetching Linux serial: {e}")
            return "unknown-linux-id"

def generate_hwid():
    """Generate a hashed HWID from system identifiers."""
    system_info = get_system_info()
    # Combine system info with platform details for uniqueness
    unique_string = f"{system_info}-{platform.node()}-{platform.machine()}"
    # Hash the string using SHA-256
    hwid_hash = hashlib.sha256(unique_string.encode()).hexdigest()
    # Shorten the hash to 32 characters for usability
    return hwid_hash[:32]

def main():
    print("Generating your HWID...")
    hwid = generate_hwid()
    print(f"Your HWID is: {hwid}")
    print("Please copy this HWID and paste it into the Telegram bot when prompted.")
    print("Press Enter to exit...")
    input()

if __name__ == "__main__":
    main()