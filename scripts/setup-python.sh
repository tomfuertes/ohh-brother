#!/bin/bash
# Setup Python environment for Ohh Brother

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PYTHON_DIR="$PROJECT_ROOT/python"
VENV_DIR="$PYTHON_DIR/venv"

echo "Setting up Python environment for Ohh Brother..."

# Check Python version
PYTHON_CMD=""
if command -v python3.11 &> /dev/null; then
    PYTHON_CMD="python3.11"
elif command -v python3.10 &> /dev/null; then
    PYTHON_CMD="python3.10"
elif command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    if [[ $(echo "$PYTHON_VERSION >= 3.9" | bc -l) -eq 1 ]]; then
        PYTHON_CMD="python3"
    fi
fi

if [ -z "$PYTHON_CMD" ]; then
    echo "Error: Python 3.9+ is required but not found."
    echo "Please install Python 3.9 or later."
    exit 1
fi

echo "Using $PYTHON_CMD ($(which $PYTHON_CMD))"

# Create virtual environment
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    $PYTHON_CMD -m venv "$VENV_DIR"
else
    echo "Virtual environment already exists"
fi

# Activate and install dependencies
echo "Installing dependencies..."
source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install -r "$PYTHON_DIR/requirements.txt"

echo ""
echo "Setup complete!"
echo ""
echo "To activate the environment manually:"
echo "   source $VENV_DIR/bin/activate"
echo ""
echo "To test the transcription:"
echo "   cd $PYTHON_DIR && python transcriber.py --test"
