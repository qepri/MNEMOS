# Mnemos Windows Installer

This document explains the Windows installer system for Mnemos, which packages the entire application stack (PostgreSQL, pgvector, Flask, Celery, Redis, Ollama, Angular) as a one-click executable.

## Overview

The installer uses **Podman** instead of Docker Desktop to provide a free, open-source container runtime. While you develop with Docker, end users will run with Podman.

### Key Technologies

- **NSIS**: Creates the Windows .exe installer
- **Podman**: Container runtime (replaces Docker Desktop for end users)
- **WSL2**: Linux backend for Podman on Windows
- **PowerShell**: Automation scripts for installation and setup

## Quick Start - Building the Installer

### Prerequisites

1. Install [NSIS](https://nsis.sourceforge.io/Download) (v3.0+)
2. Have Docker running (for your dev environment)

### Build Command

```powershell
# Simple build (small installer, downloads images during install)
.\installer\build-installer.ps1

# Full build (bundles all images, ~3-5GB installer)
.\installer\build-installer.ps1 -BundleImages
```

Output: `dist\Mnemos-Setup.exe`

## File Structure

```
installer/
├── build-installer.ps1          # Build automation script
├── install.ps1                  # PowerShell installation logic
├── mnemos-installer.nsi         # NSIS installer definition
└── BUILD.md                     # Detailed build documentation

docker-compose.podman.yml        # Podman-compatible compose file
README.INSTALLER.md             # This file
```

## How It Works

### Installation Flow

1. **User runs Mnemos-Setup.exe**
2. **Installer checks system requirements:**
   - Windows 10/11 (version 2004+)
   - Administrator privileges
3. **Installs WSL2** if not present
4. **Downloads and installs Podman**
5. **Creates Podman Machine** (WSL2-based VM)
6. **Copies application files**
7. **Creates startup scripts** and shortcuts
8. **(Optional) Pre-downloads container images**

### Runtime Flow

1. **User clicks "Mnemos" desktop shortcut**
2. **start-mnemos.bat runs:**
   - Starts Podman Machine (if stopped)
   - Runs `podman-compose up`
3. **Services start:**
   - PostgreSQL + pgvector
   - Redis
   - Flask backend
   - Celery worker
   - Ollama (LLM server)
   - Angular frontend
4. **Browser opens to http://localhost:5200**

## Docker vs Podman Differences

The application is developed with Docker but distributed with Podman. Here are the key differences handled by the installer:

| Aspect | Docker (Dev) | Podman (Production) |
|--------|--------------|---------------------|
| Compose command | `docker-compose` | `podman-compose` |
| GPU syntax | `deploy.resources.reservations.devices` | `devices: [nvidia.com/gpu=all]` |
| Socket path | `/var/run/docker.sock` | `/run/podman/podman.sock` |
| Backend | Docker Desktop (Hyper-V) | Podman Machine (WSL2) |
| Security | Daemon (root) | Rootless by default |

The [docker-compose.podman.yml](docker-compose.podman.yml) file adapts your Docker setup for Podman.

## GPU Support

For NVIDIA GPU support, end users need:

1. **NVIDIA drivers** (latest)
2. **WSL2** with NVIDIA support
3. **NVIDIA Container Toolkit** in WSL2

The installer checks for GPU and provides guidance, but doesn't automatically install NVIDIA tools (due to complexity and licensing).

### GPU Setup for End Users

```bash
# Inside WSL2 Ubuntu
wsl

# Add NVIDIA package repository
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

# Install
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit

# Configure Podman
sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml
```

## Testing the Installer

### Minimal Test

1. Create a VM with Windows 10/11 (clean install)
2. Install NVIDIA drivers if testing GPU
3. Run `Mnemos-Setup.exe`
4. Follow installation wizard
5. Verify desktop shortcut appears
6. Click shortcut and wait for services to start
7. Open browser to http://localhost:5200
8. Test core features

### Comprehensive Test

See [installer/BUILD.md](installer/BUILD.md) for detailed testing procedures.

## Configuration

### Environment Variables

The installer creates a `.env` file at installation. End users can edit:

```
C:\Program Files\Mnemos\.env
```

Key settings:
- `EMBEDDING_DEVICE=cuda` (or `cpu` for non-GPU)
- `OLLAMA_NUM_CTX=2048` (context window)
- Database credentials (if changed)

### Resource Allocation

Podman Machine defaults:
- **CPUs**: 4
- **Memory**: 8GB
- **Disk**: 100GB

To adjust, users can recreate the machine:

```powershell
podman machine stop mnemos-machine
podman machine rm mnemos-machine
podman machine init mnemos-machine --cpus 6 --memory 16384 --disk-size 200
podman machine start mnemos-machine
```

## Troubleshooting

### Common Issues

**Issue: "WSL2 installation requires a restart"**
- Expected on first install
- User must restart Windows
- Installer will resume after restart

**Issue: "Podman machine failed to start"**
```powershell
# Check WSL2
wsl --status

# Restart machine
podman machine stop mnemos-machine
podman machine start mnemos-machine
```

**Issue: "Containers won't start"**
```powershell
# Check Podman
cd "C:\Program Files\Mnemos"
podman-compose -f docker-compose.podman.yml ps

# View logs
podman-compose -f docker-compose.podman.yml logs
```

**Issue: "No GPU detected but I have NVIDIA"**
- Install latest NVIDIA drivers
- Follow GPU setup steps above
- Restart Podman Machine after setup

### Log Locations

- **Installation logs**: `%TEMP%\nsis-install.log`
- **Podman logs**: `podman logs <container-name>`
- **Application logs**: `C:\Program Files\Mnemos\uploads\logs\`

## Distribution

### Signing the Installer (Recommended)

For production distribution, code sign the executable:

```powershell
# With a code signing certificate
signtool sign /f certificate.pfx /p password /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 dist\Mnemos-Setup.exe
```

### Release Checklist

- [ ] Test on clean Windows 10 VM
- [ ] Test on clean Windows 11 VM
- [ ] Test with NVIDIA GPU
- [ ] Test without GPU
- [ ] Verify all shortcuts work
- [ ] Test update/uninstall process
- [ ] Generate SHA256 checksum
- [ ] Sign executable
- [ ] Create release notes
- [ ] Upload to distribution platform

### Size Optimization

Two distribution strategies:

**1. Minimal Installer (~100MB)**
- No bundled images
- Fast download
- Slower first launch (pulls images)
- **Recommended** for most users

**2. Full Installer (~4GB)**
- All images bundled
- Slow download
- Fast first launch
- Good for offline installs or slow internet

Build minimal:
```powershell
.\installer\build-installer.ps1
```

Build full:
```powershell
.\installer\build-installer.ps1 -BundleImages
```

## Maintenance

### Updating the Installer

When you update the application:

1. Test with Docker (your dev environment)
2. Update version in `mnemos-installer.nsi`
3. Rebuild installer
4. Test on clean Windows install
5. Distribute new version

### Compatibility Testing

Test matrix:
- Windows 10 (21H2, 22H2)
- Windows 11 (all versions)
- With/without GPU
- Various RAM configurations (8GB, 16GB, 32GB)

## Development Workflow

Your workflow stays the same:

```powershell
# Develop with Docker as usual
docker-compose up

# When ready to build installer
.\installer\build-installer.ps1

# Test installer in VM
```

The installer automatically converts your Docker setup to Podman.

## License Considerations

- **Podman**: Apache License 2.0 (free, open source)
- **Docker Desktop**: Commercial license required for some use cases
- **Your Application**: Your license

Using Podman avoids Docker Desktop licensing issues for commercial distribution.

## Support & Contributing

For issues with the installer:
1. Check [BUILD.md](installer/BUILD.md) troubleshooting section
2. Review logs (`%TEMP%\nsis-install.log`)
3. Open GitHub issue with:
   - Windows version
   - Installation logs
   - Error messages
   - Steps to reproduce

## Advanced Topics

### Custom Branding

Edit `installer/mnemos-installer.nsi`:
- Change icons: `!define MUI_ICON "path\to\icon.ico"`
- Modify welcome text
- Add license agreement
- Customize finish page

### Silent Installation

For enterprise deployment:

```cmd
Mnemos-Setup.exe /S /D=C:\CustomPath
```

### Portable Installation

To create a portable version that doesn't require admin:
- Use Podman without WSL2 integration
- Store data in portable directory
- Requires more complex setup (not covered by default installer)

## Next Steps

1. **Build your first installer**: `.\installer\build-installer.ps1`
2. **Test in VM**: Set up a clean Windows VM
3. **Read detailed docs**: [installer/BUILD.md](installer/BUILD.md)
4. **Plan distribution**: GitHub Releases, website, etc.

---

For detailed build instructions, see [installer/BUILD.md](installer/BUILD.md)
