#!/bin/bash

# Setup script for pgAdminTUI

echo "Setting up pgAdminTUI..."

# Check Python version
python_version=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
required_version="3.9"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then 
    echo "Error: Python $required_version or higher is required (found $python_version)"
    exit 1
fi

echo "✓ Python $python_version found"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip --quiet

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

echo ""
echo "✅ Setup complete!"
echo ""
echo "To get started:"
echo "1. Activate the virtual environment: source venv/bin/activate"
echo "2. Configure your database connection using one of these methods:"
echo "   a. Set DATABASE_URL: export DATABASE_URL='postgresql://user:pass@localhost:5432/dbname'"
echo "   b. Copy and edit databases.yaml: cp databases.yaml.example databases.yaml"
echo "3. Run the application: python -m src.main"
echo ""
echo "For help: python -m src.main --help"