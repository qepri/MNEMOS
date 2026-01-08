@echo off
echo Starting MNEMOS in Default Mode (GPU Enabled)...
:: Launch a separate process to open the browser after a delay (e.g., 20 seconds) to allow the app to initialize
echo Launching browser launch timer (20s)...
start "" cmd /c "ping 127.0.0.1 -n 21 > nul && start http://localhost:5200"

:: Run docker-compose in the foreground to keep verbose logs in this terminal
docker-compose -f docker-compose.yml up --build %*
pause
