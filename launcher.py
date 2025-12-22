import sys
import os
import subprocess
import ctypes
import time
import webbrowser
import threading
from tkinter import messagebox, Tk

# Configuration
APP_NAME = "MNEMOS Context Daemon"
PODMAN_INSTALLER_NAME = "podman-desktop-setup.exe" # We will expect this in the same dir
COMPOSE_FILE = "docker-compose.prod.yml" # Podman supports docker-compose.yml
PORT = 5000

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def run_command(command, shell=True):
    """Runs a command and returns (returncode, stdout, stderr)"""
    process = subprocess.Popen(
        command, 
        stdout=subprocess.PIPE, 
        stderr=subprocess.PIPE, 
        shell=shell, 
        text=True
    )
    stdout, stderr = process.communicate()
    return process.returncode, stdout, stderr

def check_wsl2():
    """Checks if WSL2 is enabled."""
    # Simple check: see if wsl.exe exists and can list distributions
    # A more robust check might involve checking Windows Features via PowerShell
    code, out, err = run_command("wsl --list --verbose")
    if code != 0:
        # It might be that WSL is not installed at all
        return False
    return True

def enable_wsl2_and_restart():
    """Enables WSL2 features and prompts for restart."""
    if not is_admin():
        messagebox.showerror("Permission Denied", "Administrator privileges are required to enable WSL2. Please run this installer as Administrator.")
        return False

    # Enable VirtualMachinePlatform and Microsoft-Windows-Subsystem-Linux
    commands = [
        "dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart",
        "dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart"
    ]

    for cmd in commands:
        code, out, err = run_command(cmd)
        if code != 0:
            messagebox.showerror("Error", f"Failed to enable Windows feature:\n{err}")
            return False

    # Prompt for restart
    root = Tk()
    root.withdraw() # Hide main window
    if messagebox.askyesno("Restart Required", "WSL2 has been enabled. A computer restart is required to complete the installation.\n\nDo you want to restart now?"):
        run_command("shutdown /r /t 0")
    
    return True

def check_podman():
    """Checks if Podman is installed."""
    code, out, err = run_command("podman --version")
    return code == 0

def install_podman():
    """Installs Podman Desktop silently."""
    installer_path = os.path.join(os.getcwd(), PODMAN_INSTALLER_NAME)
    if not os.path.exists(installer_path):
        # In a real scenario, we might download it here if missing
        messagebox.showerror("Error", f"Podman installer not found: {installer_path}")
        return False

    print("Installing Podman Desktop...")
    # /S for silent install, /allusers for system-wide
    code, out, err = run_command(f'"{installer_path}" /S /allusers')
    if code != 0:
        messagebox.showerror("Error", f"Podman installation failed:\n{err}")
        return False
    return True

def start_podman_machine():
    """Ensures the Podman machine is running."""
    print("Checking Podman machine...")
    code, out, err = run_command("podman machine list --format \"{{.Name}} {{.Running}}\"")
    
    # If no machine exists, init one
    if "podman-machine-default" not in out:
        print("Initializing Podman machine (this may take a while)...")
        code, out, err = run_command("podman machine init")
        if code != 0:
            messagebox.showerror("Error", f"Failed to init Podman machine:\n{err}")
            return False

    # Start if not running
    # We can just try to start it, if it's already running it will say so (or we can check status)
    print("Starting Podman machine...")
    code, out, err = run_command("podman machine start")
    # Ignore "already running" errors
    return True

def start_app():
    """Runs podman-compose up."""
    print("Starting Application...")
    # Use Popen to run in background/parallel so we can capture output
    # Note: 'podman-compose' might need to be installed or we use 'podman compose' if supported
    # Podman Desktop usually includes a compose extension or we use docker-compose aliased
    
    # Check if docker-compose or podman-compose is available
    compose_cmd = "docker-compose"
    code, _, _ = run_command("podman-compose --version")
    if code == 0:
        compose_cmd = "podman-compose"
    
    cmd = f"{compose_cmd} -f {COMPOSE_FILE} up -d"
    code, out, err = run_command(cmd)
    
    if code != 0:
        messagebox.showerror("Error", f"Failed to start application:\n{err}\n{out}")
        return False
    
    return True

def wait_for_app():
    """Polls the localhost port to see if app is ready."""
    import urllib.request
    url = f"http://localhost:{PORT}"
    print(f"Waiting for {url}...")
    
    max_retries = 30
    for i in range(max_retries):
        try:
            with urllib.request.urlopen(url) as response:
                if response.status == 200:
                    return True
        except:
            pass
        time.sleep(2)
        print(".", end="", flush=True)
    
    return False

def main():
    # 1. Check WSL2
    if not check_wsl2():
        print("WSL2 not detected.")
        if enable_wsl2_and_restart():
            sys.exit(0) # Restarting...
        else:
            print("WSL2 setup failed or cancelled.")
            sys.exit(1)

    # 2. Check Podman
    if not check_podman():
        print("Podman not detected.")
        if not install_podman():
            sys.exit(1)
            
    # 3. Start Podman Machine
    if not start_podman_machine():
        sys.exit(1)

    # 4. Start App
    if not start_app():
        sys.exit(1)

    # 5. Open Browser
    if wait_for_app():
        webbrowser.open(f"http://localhost:{PORT}")
        print("\nApp is running! Close this window to stop the app.")
    else:
        messagebox.showwarning("Timeout", "App started but didn't respond in time. It might still be loading.")

    # 6. Keep alive until user closes
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping app...")
        run_command("docker-compose down") # or podman-compose

if __name__ == "__main__":
    # Hide console if packaged (optional, but for now we keep it for logs)
    main()
