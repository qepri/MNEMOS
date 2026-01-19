import os
import sys
import shutil
import subprocess
import tkinter as tk
from tkinter import messagebox
from pathlib import Path

APP_NAME = "Mnemos"
EXE_NAME = "Mnemos.exe"

def create_shortcut(target_path, shortcut_path, working_dir):
    """Creates a Windows shortcut using PowerShell to avoid pywin32 dependency."""
    ps_cmd = (
        f'$s=(New-Object -COM WScript.Shell).CreateShortcut("{shortcut_path}");'
        f'$s.TargetPath="{target_path}";'
        f'$s.WorkingDirectory="{working_dir}";'
        f'$s.Save()'
    )
    subprocess.run(["powershell", "-Command", ps_cmd], check=True)

def install():
    # 1. Setup Paths
    install_dir = Path(os.environ["LOCALAPPDATA"]) / APP_NAME
    desktop_dir = Path(os.path.join(os.environ["USERPROFILE"], "Desktop"))
    
    # Files to copy (these must be bundled via PyInstaller --add-data)
    # The source is sys._MEIPASS because we are running inside a onefile exe
    source_dir = getattr(sys, '_MEIPASS', os.path.abspath("."))
    
    print(f"Installing to {install_dir}...")
    
    try:
        # 2. Cleanup existing
        if install_dir.exists():
            shutil.rmtree(install_dir)
        install_dir.mkdir(parents=True)
        
        # 3. Copy Files
        # We expect a '_internal_app' folder inside the temporary directory containing all our files
        # Or we act simple: We bundle specific folders/files.
        # Let's assume the build script dumps everything into the root of _MEIPASS/bundled
        
        bundled_root = Path(source_dir) / "bundled"
        if not bundled_root.exists():
            # Fallback for testing: copy from current dir if not in exe
            bundled_root = Path("RAG_App_Dist") 
        
        if not bundled_root.exists():
             raise FileNotFoundError(f"Could not find bundled files at {bundled_root}")

        shutil.copytree(bundled_root, install_dir, dirs_exist_ok=True)
        
        # Ensure 'ollama_models' exists (we excluded it from bundle to save space)
        (install_dir / "ollama_models").mkdir(exist_ok=True)
        
        # 4. Create Shortcut
        exe_path = install_dir / EXE_NAME
        shortcut_path = desktop_dir / f"{APP_NAME}.lnk"
        
        if not exe_path.exists():
             raise FileNotFoundError(f"Could not find {EXE_NAME} in installation")
             
        create_shortcut(str(exe_path), str(shortcut_path), str(install_dir))
        
        messagebox.showinfo("Success", f"{APP_NAME} installed successfully!\nA shortcut has been created on your desktop.")
        
        # 5. Launch
        subprocess.Popen([str(exe_path)], cwd=str(install_dir))
        
    except Exception as e:
        messagebox.showerror("Installation Failed", f"Error: {e}")
        # Keep console open if it crashed
        input("Press Enter to exit...")

if __name__ == "__main__":
    # Simple TK setup to hide main window
    root = tk.Tk()
    root.withdraw()
    install()
