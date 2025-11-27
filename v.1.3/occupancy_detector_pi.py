#!/usr/bin/env python3
"""
OCCUPANCY DETECTION SYSTEM v1.3 - RASPBERRY PI 4B OPTIMIZED
Multi-camera, plug-and-play occupancy detection for Raspberry Pi 4B

Features:
- Multi-camera RTSP support via camera_ips.txt
- CPU-optimized processing (no GPU required)
- MQTT publishing on state changes only
- Temperature-aware throttling
- Headless operation

Author: Smart Building Automation Team
Date: 2025-11-28
"""

import cv2
import numpy as np
import time
import json
import threading
import logging
import yaml
import os
import signal
import sys
from datetime import datetime
from ultralytics import YOLO
import paho.mqtt.client as mqtt

# GPIO setup for classroom relay control
try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    print("[WARNING] RPi.GPIO not available. Relay control disabled.")
    GPIO_AVAILABLE = False

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(name)s] - %(levelname)s - %(message)s'
)

class RaspberryPiOccupancyDetector:
    def __init__(self, room_id, rtsp_url, config, shared_model):
        self.room_id = room_id
        self.rtsp_url = rtsp_url
        self.config = config
        self.model = shared_model
        self.logger = logging.getLogger(f"Room_{room_id}")
        
        # State tracking
        self.occupancy_state = False
        self.prev_occupancy_state = False
        self.last_motion_time = time.time()
        self.prev_frame_gray = None
        
        # Performance tracking
        self.frame_count = 0
        self.process_count = 0
        self.is_running = False
        
        # MQTT client (shared reference)
        self.mqtt_client = None
        
        # GPIO relay setup for classroom control
        self.gpio_pin = config.get('gpio_pin', 18)
        self.gpio_active_high = config.get('gpio_active_high', True)
        self.setup_gpio()
        
    def setup_gpio(self):
        """Setup GPIO pin for relay control"""
        if not GPIO_AVAILABLE:
            self.logger.warning("GPIO not available, relay control disabled")
            return
            
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.gpio_pin, GPIO.OUT)
            # Initialize to OFF state
            initial_level = GPIO.LOW if self.gpio_active_high else GPIO.HIGH
            GPIO.output(self.gpio_pin, initial_level)
            self.logger.info(f"GPIO pin {self.gpio_pin} initialized (active_high={self.gpio_active_high})")
        except Exception as e:
            self.logger.error(f"GPIO setup failed: {e}")
    
    def control_relay(self, occupancy_state):
        """Control classroom relay based on occupancy"""
        if not GPIO_AVAILABLE:
            return
            
        try:
            if occupancy_state:
                level = GPIO.HIGH if self.gpio_active_high else GPIO.LOW
                action = "ON"
            else:
                level = GPIO.LOW if self.gpio_active_high else GPIO.HIGH
                action = "OFF"
                
            GPIO.output(self.gpio_pin, level)
            self.logger.info(f"Classroom relay {action} (pin {self.gpio_pin} -> {'HIGH' if level==GPIO.HIGH else 'LOW'})")
        except Exception as e:
            self.logger.error(f"Relay control failed: {e}")
    
    def set_mqtt_client(self, mqtt_client):
        """Set shared MQTT client"""
        self.mqtt_client = mqtt_client
        
    def preprocess_frame(self, frame):
        """Pi-optimized preprocessing with CLAHE for low-light"""
        # Resize to Pi-friendly resolution
        frame = cv2.resize(frame, (320, 240))
        
        # CLAHE enhancement for low-light
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
        l_clahe = clahe.apply(l)
        lab_clahe = cv2.merge([l_clahe, a, b])
        frame_enhanced = cv2.cvtColor(lab_clahe, cv2.COLOR_LAB2BGR)
        
        return frame_enhanced
        
    def detect_persons(self, frame):
        """YOLO person detection using shared model"""
        results = self.model(
            frame,
            conf=self.config['confidence_threshold'],
            verbose=False
        )
        
        person_count = 0
        for detection in results[0].boxes:
            if int(detection.cls) == 0:  # Person class
                person_count += 1
                
        return person_count
        
    def detect_motion_simple(self, frame_gray):
        """Lightweight motion detection via frame differencing"""
        if self.prev_frame_gray is None:
            self.prev_frame_gray = frame_gray.copy()
            return False, 0
            
        # Simple frame difference
        diff = cv2.absdiff(self.prev_frame_gray, frame_gray)
        motion_score = np.sum(diff)
        
        self.prev_frame_gray = frame_gray.copy()
        
        motion_detected = motion_score > self.config['min_motion_score']
        return motion_detected, motion_score
        
    def apply_temporal_validation(self, person_detected, motion_detected):
        """State machine with motion requirement"""
        current_time = time.time()
        
        if motion_detected:
            self.last_motion_time = current_time
            
        time_since_motion = current_time - self.last_motion_time
        
        # Occupied if person detected AND recent motion
        if person_detected and time_since_motion < self.config['static_timeout_sec']:
            new_state = True
        else:
            new_state = False
            
        return new_state
        
    def publish_state_change(self, person_count):
        """Publish to MQTT only on state changes"""
        if self.occupancy_state != self.prev_occupancy_state:
            payload = {
                "zone_id": self.room_id,
                "timestamp": datetime.now().isoformat(),
                "occupancy": self.occupancy_state,
                "state": "OCCUPIED" if self.occupancy_state else "EMPTY",
                "person_count": person_count
            }
            
            topic = f"analytics/occupancy/{self.room_id}"
            
            try:
                if self.mqtt_client:
                    self.mqtt_client.publish(topic, json.dumps(payload), qos=1)
                    self.logger.info(f"Published: {payload['state']} (persons={person_count})")
            except Exception as e:
                self.logger.error(f"MQTT publish failed: {e}")
                
    def process_camera(self):
        """Main processing loop for this camera"""
        self.logger.info(f"Starting camera processing: {self.rtsp_url}")
        
        cap = cv2.VideoCapture(self.rtsp_url)
        if not cap.isOpened():
            self.logger.error(f"Failed to open camera: {self.rtsp_url}")
            return
            
        # Optimize capture settings for Pi
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 15)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        self.is_running = True
        last_process_time = time.time()
        
        try:
            while self.is_running:
                ret, frame = cap.read()
                if not ret:
                    self.logger.warning("Failed to read frame, retrying...")
                    time.sleep(1)
                    continue
                    
                self.frame_count += 1
                current_time = time.time()
                
                # Process at configured interval
                if current_time - last_process_time >= self.config['processing_interval_sec']:
                    process_start = time.time()
                    self.process_count += 1
                    
                    # Preprocessing
                    frame_processed = self.preprocess_frame(frame)
                    frame_gray = cv2.cvtColor(frame_processed, cv2.COLOR_BGR2GRAY)
                    
                    # Detection
                    person_count = self.detect_persons(frame_processed)
                    motion_detected, motion_score = self.detect_motion_simple(frame_gray)
                    
                    # State machine
                    new_occupancy = self.apply_temporal_validation(
                        person_detected=(person_count > 0),
                        motion_detected=motion_detected
                    )
                    
                    self.occupancy_state = new_occupancy
                    
                    # Publish on state change and control relay
                    if self.occupancy_state != self.prev_occupancy_state:
                        self.publish_state_change(person_count)
                        self.control_relay(new_occupancy)  # Control classroom relay
                    self.prev_occupancy_state = new_occupancy
                    
                    # Log every 10 processes
                    if self.process_count % 10 == 0:
                        process_time = (time.time() - process_start) * 1000
                        state_text = "OCCUPIED" if new_occupancy else "EMPTY"
                        self.logger.info(
                            f"[{self.process_count}] {state_text} | "
                            f"Persons: {person_count} | Motion: {motion_detected} | "
                            f"Process: {process_time:.0f}ms"
                        )
                    
                    last_process_time = current_time
                    
        except Exception as e:
            self.logger.error(f"Processing error: {e}")
        finally:
            cap.release()
            self.logger.info("Camera processing stopped")
            
    def start(self):
        """Start processing in background thread"""
        thread = threading.Thread(target=self.process_camera, daemon=True)
        thread.start()
        return thread
        
    def stop(self):
        """Stop processing and cleanup GPIO"""
        self.is_running = False
        
        # Turn off relay and cleanup GPIO
        if GPIO_AVAILABLE:
            try:
                off_level = GPIO.LOW if self.gpio_active_high else GPIO.HIGH
                GPIO.output(self.gpio_pin, off_level)
                self.logger.info(f"Relay turned OFF on shutdown")
            except Exception as e:
                self.logger.error(f"GPIO cleanup error: {e}")


class MultiCameraOccupancySystem:
    def __init__(self):
        self.logger = logging.getLogger("MultiCamera")
        self.config = {}
        self.cameras = []
        self.detectors = []
        self.threads = []
        self.mqtt_client = None
        self.shared_model = None
        
    def load_config(self):
        """Load configuration from config_pi.yaml"""
        try:
            with open('config_pi.yaml', 'r') as f:
                self.config = yaml.safe_load(f)
            self.logger.info("Configuration loaded successfully")
        except Exception as e:
            self.logger.error(f"Failed to load config: {e}")
            # Default config
            self.config = {
                'mqtt_broker': 'localhost',
                'mqtt_port': 1883,
                'processing_interval_sec': 1.0,
                'static_timeout_sec': 10,
                'confidence_threshold': 0.6,
                'min_motion_score': 300,
                'temp_threshold_celsius': 75
            }
            
    def load_cameras(self):
        """Load camera configuration from camera_ips.txt"""
        try:
            with open('camera_ips.txt', 'r') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                        
                    try:
                        room_id, rtsp_url = line.split(',', 1)
                        self.cameras.append((room_id.strip(), rtsp_url.strip()))
                    except ValueError:
                        self.logger.warning(f"Malformed line {line_num}: {line}")
                        
            self.logger.info(f"Loaded {len(self.cameras)} cameras")
            for room_id, rtsp_url in self.cameras:
                self.logger.info(f"  {room_id}: {rtsp_url}")
                
        except Exception as e:
            self.logger.error(f"Failed to load cameras: {e}")
            
    def load_model(self):
        """Load shared YOLO model from available sources"""
        model_paths = [
            '../v.1.2/model.pt',
            '../v.1.2/yolov8n.pt', 
            'model_original.pt',
            'yolov8n.pt'
        ]
        
        model_path = None
        for path in model_paths:
            if os.path.exists(path):
                model_path = path
                break
                
        if not model_path:
            self.logger.error("No model found. Run setup_model.py first.")
            sys.exit(1)
            
        try:
            self.shared_model = YOLO(model_path)
            self.logger.info(f"Model loaded: {model_path}")
        except Exception as e:
            self.logger.error(f"Failed to load model: {e}")
            sys.exit(1)
            
    def setup_mqtt(self):
        """Setup MQTT client"""
        try:
            self.mqtt_client = mqtt.Client(client_id="pi_occupancy_detector")
            self.mqtt_client.on_connect = self._on_mqtt_connect
            self.mqtt_client.on_disconnect = self._on_mqtt_disconnect
            
            self.mqtt_client.connect(
                self.config['mqtt_broker'],
                self.config['mqtt_port'],
                keepalive=60
            )
            self.mqtt_client.loop_start()
            self.logger.info("MQTT client initialized")
        except Exception as e:
            self.logger.error(f"MQTT setup failed: {e}")
            
    def _on_mqtt_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.logger.info("Connected to MQTT broker")
        else:
            self.logger.error(f"MQTT connection failed: {rc}")
            
    def _on_mqtt_disconnect(self, client, userdata, rc):
        if rc != 0:
            self.logger.warning(f"Unexpected MQTT disconnection: {rc}")
            
    def get_cpu_temperature(self):
        """Get CPU temperature for thermal throttling"""
        try:
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                temp = int(f.read().strip()) / 1000.0
                return temp
        except:
            return 0
            
    def check_thermal_throttling(self):
        """Adjust processing interval based on CPU temperature"""
        temp = self.get_cpu_temperature()
        if temp > self.config['temp_threshold_celsius']:
            # Increase interval to reduce load
            new_interval = self.config['processing_interval_sec'] * 1.5
            self.logger.warning(f"High CPU temp ({temp:.1f}°C), throttling to {new_interval:.1f}s")
            self.config['processing_interval_sec'] = new_interval
            
    def start_detectors(self):
        """Start detector for each camera"""
        for room_id, rtsp_url in self.cameras:
            detector = RaspberryPiOccupancyDetector(
                room_id, rtsp_url, self.config, self.shared_model
            )
            detector.set_mqtt_client(self.mqtt_client)
            
            thread = detector.start()
            
            self.detectors.append(detector)
            self.threads.append(thread)
            
        self.logger.info(f"Started {len(self.detectors)} detectors")
        
    def run(self):
        """Main run loop"""
        self.logger.info("=== RASPBERRY PI OCCUPANCY DETECTION v1.3 ===")
        
        # Load configuration
        self.load_config()
        self.load_cameras()
        
        if not self.cameras:
            self.logger.error("No cameras configured. Check camera_ips.txt")
            return
            
        # Initialize components
        self.load_model()
        self.setup_mqtt()
        
        # Start detectors
        self.start_detectors()
        
        self.logger.info("System running. Press Ctrl+C to stop...")
        
        # Monitor loop
        try:
            while True:
                time.sleep(30)  # Check every 30 seconds
                self.check_thermal_throttling()
                
        except KeyboardInterrupt:
            self.logger.info("Shutdown requested...")
            self.stop()
            
    def stop(self):
        """Stop all detectors and cleanup"""
        for detector in self.detectors:
            detector.stop()
            
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
        
        # Final GPIO cleanup
        if GPIO_AVAILABLE:
            try:
                GPIO.cleanup()
                self.logger.info("GPIO cleanup completed")
            except:
                pass
            
        self.logger.info("All detectors stopped")


def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully"""
    print("\nShutdown signal received...")
    sys.exit(0)


def main():
    """Main entry point"""
    signal.signal(signal.SIGINT, signal_handler)
    
    system = MultiCameraOccupancySystem()
    system.run()


if __name__ == "__main__":
    main()