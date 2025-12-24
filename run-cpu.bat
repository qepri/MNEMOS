@echo off
echo Starting MNEMOS in CPU Mode...
docker-compose -f docker-compose.yml -f docker-compose.cpu.yml up --build %*
pause
