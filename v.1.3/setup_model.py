#!/usr/bin/env python3
"""
Model setup script for Raspberry Pi deployment
Creates optimized model from v.1.2 weights
"""

import os
import shutil
from ultralytics import YOLO

def setup_model():
    """Setup and optimize model for Pi deployment"""
    
    # Check for model in v.1.2
    model_paths = [
        '../v.1.2/model.pt',
        '../v.1.2/yolov8n.pt',
        'yolov8n.pt'
    ]
    
    source_model = None
    for path in model_paths:
        if os.path.exists(path):
            source_model = path
            break
    
    if not source_model:
        print("ERROR: No model found. Please ensure yolov8n.pt exists.")
        return False
    
    print(f"Found model: {source_model}")
    
    try:
        # Load model
        model = YOLO(source_model)
        
        # Create optimized version for Pi (optional)
        print("Creating Pi-optimized model...")
        model.export(format='onnx', optimize=True, half=False, imgsz=320)
        
        # Copy original model as backup
        if not os.path.exists('model_original.pt'):
            shutil.copy2(source_model, 'model_original.pt')
            print("Original model copied to model_original.pt")
        
        print("Model setup complete!")
        return True
        
    except Exception as e:
        print(f"Model setup failed: {e}")
        return False

if __name__ == "__main__":
    setup_model()