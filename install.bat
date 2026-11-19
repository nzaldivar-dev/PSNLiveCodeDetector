@echo off
setlocal
cd /d "%~dp0"
echo Creating virtual environment...
py -3.14 -m venv .venv
if errorlevel 1 (
  echo Python 3.14 was not found. Install Python 3.12 x64 and enable Add to PATH.
  pause
  exit /b 1
)
call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
echo.
echo Installation complete. For NVIDIA GPU acceleration, install a compatible CUDA-enabled
echo PyTorch/CTranslate2 setup for your NVIDIA driver. Whisper automatically falls back to CPU.
pause
