#!/bin/bash
# Quick start script for occupancy demo

echo "========================================="
echo "Occupancy Detection Demo - Quick Start"
echo "========================================="

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.8+"
    exit 1
fi

echo "✓ Python found"

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

echo "✓ Dependencies installed"

# Run demo
echo ""
echo "Starting demo..."
echo "Press 'q' to quit"
echo ""
python occupancy_demo.py
