#!/usr/bin/env bash
# Exit on error
set -e

# Upgrade build tools
echo "Upgrading pip, setuptools, and wheel..."
pip install --upgrade pip setuptools wheel

# Install dependencies
echo "Installing dependencies from requirements.txt..."
pip install -r requirements.txt

# Verify installation of key packages (optional, but helpful)
echo "Verifying installation..."
python -c "import rapidfuzz; print('rapidfuzz installed:', rapidfuzz.__version__)"
python -c "import orjson; print('orjson installed:', orjson.__version__)"
