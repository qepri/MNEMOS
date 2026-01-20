@echo off
echo Starting MNEMOS in CPU Mode...
docker volume create ollama_models >nul 2>&1
docker-compose -f docker-compose.yml -f docker-compose.cpu.yml up --build %*
pause
