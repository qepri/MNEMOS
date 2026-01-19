import os
import subprocess
import shutil
import sys
from pathlib import Path

def install_utils():
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

def build_launcher():
    print(">>> Building Stage 1: Mnemos.exe (Launcher)...")
    # This is the inner exe that runs the app
    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--onefile",
        "--console", 
        "--name", "Mnemos",
        "--uac-admin", 
        "launcher.py"
    ]
    subprocess.check_call(cmd)

def build_installer():
    print(">>> Building Stage 2: Setup_Mnemos.exe (Installer)...")
    
    # 1. Prepare Content Directory
    # We will put everything into a 'bundled' folder that PyInstaller will include
    dist_dir = Path("dist") / "bundled"
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    dist_dir.mkdir(parents=True)

    # Copy Launcher
    shutil.copy(Path("dist") / "Mnemos.exe", dist_dir / "Mnemos.exe")

    # Copy App Configs & Code
    # Note: We copy files *into* 'bundled' so they are extracted into 'bundled' folder inside _MEIPASS
    files_to_copy = [
        "docker-compose.yml",
        "docker-compose.prod.yml",
        ".env.example",
        "requirements.txt",
        "Dockerfile",
        "entrypoint.sh"
    ]
    
    dirs_to_copy = [
        "app",
        "config",
        "migrations",
        "frontend_spa"
    ]

    for item in files_to_copy:
        if os.path.exists(item):
            shutil.copy(item, dist_dir / item)
    
    for item in dirs_to_copy:
        if os.path.exists(item):
            tgt = dist_dir / item
            # Ignore node_modules to keep installer size check reasonable
            # and ignore local virtual environments if any
            shutil.copytree(item, tgt, dirs_exist_ok=True, ignore=shutil.ignore_patterns("node_modules", ".git", "__pycache__", "venv", ".angular"))

    # 2. Build the Installer Exe
    # We use --add-data to include the 'bundled' folder
    # Format: source;dest (Windows)
    add_data = f"dist/bundled;bundled"
    
    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--onefile",
        "--console", # Keep console for install logs
        "--name", "Setup_Mnemos",
        "--uac-admin",
        "--add-data", add_data,
        "install_script.py"
    ]
    subprocess.check_call(cmd)
    
    print(f"\n[SUCCESS] Installer created: {os.path.abspath('dist/Setup_Mnemos.exe')}")
    print("Share this file with your users.")

if __name__ == "__main__":
    try:
        install_utils()
        build_launcher()
        build_installer()
    except Exception as e:
        print(f"Build failed: {e}")
