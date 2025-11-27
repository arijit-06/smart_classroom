#!/bin/bash
# Raspberry Pi Occupancy Detector Startup Script

echo "=== Raspberry Pi Occupancy Detection v1.3 ==="
echo "Starting multi-camera occupancy detection system..."

# Check if we're in the right directory
if [ ! -f "occupancy_detector_pi.py" ]; then
    echo "ERROR: Please run this script from the v.1.3 directory"
    exit 1
fi

# Check if model setup is needed
if [ ! -f "model_original.pt" ] && [ ! -f "../v.1.2/yolov8n.pt" ]; then
    echo "Setting up model..."
    python setup_model.py
fi

# Check configuration files
if [ ! -f "camera_ips.txt" ]; then
    echo "ERROR: camera_ips.txt not found. Please configure your cameras first."
    exit 1
fi

if [ ! -f "config_pi.yaml" ]; then
    echo "ERROR: config_pi.yaml not found. Please configure the system first."
    exit 1
fi

# Start the detector
echo "Starting occupancy detector..."
python occupancy_detector_pi.py