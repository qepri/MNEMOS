import os
import subprocess
import shutil
import sys

def install_requirements():
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

def build_exe():
    print("Building launcher.exe...")
    # --onefile: Bundle everything into one exe
    # --name: Name of the exe
    # --uac-admin: Request admin permissions (needed for WSL setup)
    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--onefile",
        "--console", # Keep console for now to see logs, switch to --windowed for final
        "--name", "RAG_App_Installer",
        "--uac-admin", 
        "launcher.py"
    ]
    subprocess.check_call(cmd)

def create_dist_folder():
    dist_dir = "RAG_App_Dist"
    if os.path.exists(dist_dir):
        shutil.rmtree(dist_dir)
    os.makedirs(dist_dir)

    # Copy Exe
    shutil.copy(os.path.join("dist", "RAG_App_Installer.exe"), dist_dir)
    
    # Copy Config & App Code
    # In a real 'one-file' install, we might want to bundle these INSIDE the exe 
    # or have the exe extract them. For now, we'll keep them side-by-side.
    items_to_copy = [
        "app",
        "config",
        "docker-compose.yml",
        "docker-compose.prod.yml",
        ".env.example",
        "requirements.txt",
        "Dockerfile"
    ]
    
    for item in items_to_copy:
        src = item
        dst = os.path.join(dist_dir, item)
        if os.path.isdir(src):
            shutil.copytree(src, dst)
        elif os.path.exists(src):
            shutil.copy(src, dst)
            
    print(f"Build complete! Output in {dist_dir}")

if __name__ == "__main__":
    try:
        install_requirements()
        build_exe()
        create_dist_folder()
    except Exception as e:
        print(f"Build failed: {e}")
