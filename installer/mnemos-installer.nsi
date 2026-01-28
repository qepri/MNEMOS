; Mnemos NSIS Installer Script
; Creates a Windows .exe installer that bundles Podman and the application

;--------------------------------
; Includes

!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "WinVer.nsh"

;--------------------------------
; General Configuration

; Name and file
Name "Mnemos"
OutFile "..\dist\Mnemos-Setup.exe"
Unicode True

; Default installation directory
InstallDir "$PROGRAMFILES64\Mnemos"

; Registry key to check for directory (for uninstall)
InstallDirRegKey HKLM "Software\Mnemos" "Install_Dir"

; Request application privileges
RequestExecutionLevel admin

; Compression
SetCompressor /SOLID lzma

;--------------------------------
; Version Information

VIProductVersion "1.0.0.0"
VIAddVersionKey "ProductName" "Mnemos"
VIAddVersionKey "CompanyName" "Mnemos Team"
VIAddVersionKey "FileDescription" "Mnemos AI Knowledge Management System"
VIAddVersionKey "FileVersion" "1.0.0"
VIAddVersionKey "ProductVersion" "1.0.0"
VIAddVersionKey "LegalCopyright" "Copyright (C) 2025"

;--------------------------------
; Interface Settings

!define MUI_ABORTWARNING
!define MUI_ICON "${NSISDIR}\Contrib\Graphics\Icons\modern-install.ico"
!define MUI_UNICON "${NSISDIR}\Contrib\Graphics\Icons\modern-uninstall.ico"

;--------------------------------
; Pages

!insertmacro MUI_PAGE_LICENSE "..\LICENSE"
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

;--------------------------------
; Languages

!insertmacro MUI_LANGUAGE "English"

;--------------------------------
; Version Checks

Function .onInit
  ; Check Windows version (requires Windows 10 or later for WSL2)
  ${IfNot} ${AtLeastWin10}
    MessageBox MB_OK|MB_ICONSTOP "Mnemos requires Windows 10 or later (for WSL2 support)."
    Abort
  ${EndIf}

  ; Check if running as admin
  UserInfo::GetAccountType
  Pop $0
  ${If} $0 != "admin"
    MessageBox MB_OK|MB_ICONSTOP "Administrator privileges required!"
    Abort
  ${EndIf}
FunctionEnd

;--------------------------------
; Installer Sections

Section "Mnemos Core" SecCore
  SectionIn RO  ; Read-only - always installed

  SetOutPath "$INSTDIR"

  ; Copy application files (excluding large model files and dev artifacts)
  File /r /x "node_modules" /x ".git" /x "__pycache__" /x "*.pyc" /x "dist" /x "installer" /x "*.gguf" /x "ollama_models" /x ".venv" /x "venv" /x "*.tar" /x "docker-compose.podman.yml" /x "docker-compose.podman.test.yml" "..\*.*"

  ; Copy the podman compose file from installer directory
  SetOutPath "$INSTDIR"
  File "docker-compose.podman.yml"

  ; Write the installation path into the registry
  WriteRegStr HKLM "Software\Mnemos" "Install_Dir" "$INSTDIR"

  ; Write the uninstall keys
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Mnemos" "DisplayName" "Mnemos"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Mnemos" "UninstallString" '"$INSTDIR\uninstall.exe"'
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Mnemos" "DisplayIcon" "$INSTDIR\icon.ico"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Mnemos" "DisplayVersion" "1.0.0"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Mnemos" "Publisher" "Mnemos Team"
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Mnemos" "NoModify" 1
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Mnemos" "NoRepair" 1

  ; Create uninstaller
  WriteUninstaller "$INSTDIR\uninstall.exe"

SectionEnd

Section "Podman Runtime" SecPodman
  SectionIn RO  ; Read-only - always installed
  DetailPrint "Installing Podman and dependencies..."

  ; Run PowerShell installation script
  nsExec::ExecToLog 'powershell.exe -ExecutionPolicy Bypass -File "$INSTDIR\installer\install.ps1" -InstallDir "$INSTDIR"'
  Pop $0

  ${If} $0 != 0
    MessageBox MB_OK|MB_ICONEXCLAMATION "Podman installation encountered issues. Error code: $0$\n$\nYou may need to manually install Podman from https://podman.io"
  ${EndIf}

SectionEnd

Section "Desktop Shortcuts" SecShortcuts
  SectionIn RO  ; Read-only - always installed
  ; Create shortcuts
  CreateDirectory "$SMPROGRAMS\Mnemos"
  CreateShortcut "$SMPROGRAMS\Mnemos\Start Mnemos.lnk" "$INSTDIR\start-mnemos.bat" "" "$INSTDIR\icon.ico"
  CreateShortcut "$SMPROGRAMS\Mnemos\Stop Mnemos.lnk" "$INSTDIR\stop-mnemos.bat" "" "$INSTDIR\icon.ico"
  CreateShortcut "$SMPROGRAMS\Mnemos\Uninstall.lnk" "$INSTDIR\uninstall.exe"

  CreateShortcut "$DESKTOP\Mnemos.lnk" "$INSTDIR\start-mnemos.bat" "" "$INSTDIR\icon.ico"

SectionEnd

Section "Pre-pull Docker Images" SecImages
  SectionIn RO  ; Read-only - always installed
  DetailPrint "Pre-downloading container images (this may take a while)..."

  ; Start podman machine if not running
  nsExec::ExecToLog 'podman machine start mnemos-machine'

  ; Pull images
  nsExec::ExecToLog 'podman pull pgvector/pgvector:pg16'
  nsExec::ExecToLog 'podman pull redis:7-alpine'
  nsExec::ExecToLog 'podman pull ollama/ollama:latest'
  nsExec::ExecToLog 'podman pull adminer'

  DetailPrint "Container images downloaded."

SectionEnd

;--------------------------------
; Section Descriptions

!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
  !insertmacro MUI_DESCRIPTION_TEXT ${SecCore} "Core Mnemos application files (required)"
  !insertmacro MUI_DESCRIPTION_TEXT ${SecPodman} "Installs Podman container runtime and WSL2 dependencies"
  !insertmacro MUI_DESCRIPTION_TEXT ${SecShortcuts} "Creates desktop and start menu shortcuts"
  !insertmacro MUI_DESCRIPTION_TEXT ${SecImages} "Pre-downloads container images to speed up first launch (recommended, ~2GB download)"
!insertmacro MUI_FUNCTION_DESCRIPTION_END

;--------------------------------
; Uninstaller Section

Section "Uninstall"

  ; Stop services
  nsExec::ExecToLog 'podman-compose -f "$INSTDIR\docker-compose.podman.yml" down'

  ; Remove registry keys
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Mnemos"
  DeleteRegKey HKLM "Software\Mnemos"

  ; Remove files and directories
  RMDir /r "$INSTDIR"

  ; Remove shortcuts
  Delete "$DESKTOP\Mnemos.lnk"
  RMDir /r "$SMPROGRAMS\Mnemos"

  ; Optional: Ask if user wants to remove Podman
  MessageBox MB_YESNO "Do you want to remove Podman as well?$\n$\n(Choose 'No' if you use Podman for other applications)" IDYES RemovePodman IDNO SkipPodman

  RemovePodman:
    DetailPrint "Removing Podman..."
    nsExec::ExecToLog 'podman machine stop mnemos-machine'
    nsExec::ExecToLog 'podman machine rm mnemos-machine'
    ; Note: Full Podman uninstall would require running the Podman uninstaller

  SkipPodman:

SectionEnd
