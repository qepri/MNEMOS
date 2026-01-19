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
PORT = 5200

# Fix path when running as compiled exe
if getattr(sys, 'frozen', False):
    # If the application is run as a bundle, the PyInstaller bootloader
    # extends the sys module by a flag frozen=True and sets the app 
    # path into variable _MEIPASS'.
    application_path = os.path.dirname(sys.executable)
    os.chdir(application_path)
else:
    application_path = os.path.dirname(os.path.abspath(__file__))

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def print_progress_bar(iteration, total, prefix='', suffix='', decimals=1, length=50, fill='█', printEnd="\r"):
    """
    Call in a loop to create terminal progress bar
    """
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filledLength = int(length * iteration // total)
    bar = fill * filledLength + '-' * (length - filledLength)
    print(f'\r{prefix} |{bar}| {percent}% {suffix}', end=printEnd)
    # Print New Line on Complete
    if iteration == total: 
        print()

def run_command(command, shell=True, stream_output=False):
    """Runs a command and returns (returncode, stdout, stderr)"""
    if stream_output:
        process = subprocess.Popen(
            command, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT, # Merge stderr into stdout for streaming
            shell=shell, 
            text=True
        )
        output_lines = []
        for line in process.stdout:
            print(line, end="") # Stream to console
            output_lines.append(line)
        
        process.wait()
        return process.returncode, "".join(output_lines), ""
    else:
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
    installer_path = os.path.join(os.getcwd(), PODMAN_INSTALLER_NAME)
    
    if not os.path.exists(installer_path):
        # Fetch the latest release from GitHub API
        try:
            import urllib.request
            import json
            
            print("Fetching latest Podman Desktop version info...")
            api_url = "https://api.github.com/repos/containers/podman-desktop/releases/latest"
            with urllib.request.urlopen(api_url) as response:
                release_data = json.loads(response.read().decode())
                
            # Find the Windows installer asset (usually ends with -setup-x64.exe)
            download_url = None
            for asset in release_data.get("assets", []):
                name = asset.get("name", "").lower()
                if "setup" in name and "x64" in name and name.endswith(".exe"):
                    download_url = asset.get("browser_download_url")
                    print(f"Found latest installer: {name}")
                    break
            
            if not download_url:
                raise Exception("Could not find a Windows installer asset in the latest release.")

            print(f"Downloading Podman Installer from {download_url}...")
            print("This may take a few minutes depending on your connection.")
        
            # Create a progress reporter
            def report(block_num, block_size, total_size):
                downloaded = block_num * block_size
                if downloaded > total_size: downloaded = total_size
                if total_size > 0:
                    print_progress_bar(downloaded, total_size, prefix='Progress:', suffix='Complete', length=40)
            
            urllib.request.urlretrieve(download_url, installer_path, report)
            print("\nDownload complete.")
        except Exception as e:
            messagebox.showerror("Download Error", f"Failed to download Podman installer:\n{e}\n\nPlease install Podman Desktop manually from https://podman-desktop.io")
            return False

    print("Installing Podman Desktop...")
    # /S for silent install, /allusers for system-wide
    # Note: Podman Desktop installer might need elevation, which we should have if we are admin
    # Stream output here too, though silent install might not say much
    code, out, err = run_command(f'"{installer_path}" /S /allusers', stream_output=True)
    if code != 0:
        messagebox.showerror("Error", f"Podman installation failed:\n{err}\n{out}")
        return False
    return True

def start_podman_machine():
    """Ensures the Podman machine is running."""
    print("Checking Podman machine...")
    code, out, err = run_command("podman machine list --format \"{{.Name}} {{.Running}}\"")
    
    # If no machine exists, init one
    if "podman-machine-default" not in out:
        print("Initializing Podman machine (this works best with decent internet)...")
        # Stream output so user sees the download progress of the Fedora image
        code, out, err = run_command("podman machine init", stream_output=True)
        if code != 0:
            messagebox.showerror("Error", f"Failed to init Podman machine:\n{out}")
            return False

    # Start if not running
    # We can just try to start it, if it's already running it will say so (or we can check status)
    print("Starting Podman machine (this may take a moment)...")
    code, out, err = run_command("podman machine start", stream_output=True)
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
    
    # Set HOST_PROJECT_PATH for volume mounting in sibling containers
    os.environ["HOST_PROJECT_PATH"] = os.getcwd()
    
    print(f"Running: {cmd}")
    # Stream output to show Docker steps like 'Pulling...', 'Building...'
    code, out, err = run_command(cmd, stream_output=True)
    
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
