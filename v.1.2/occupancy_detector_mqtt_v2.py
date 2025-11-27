
"""
OCCUPANCY DETECTION SYSTEM v2 - MQTT PRODUCTION VERSION
For deployment on central server with all critical fixes
Supports multiple camera feeds simultaneously

All Fixes Implemented:
✓ Fix #1: YOLO8n (stable)
✓ Fix #2: Optical Flow (eliminates false positives)
✓ Fix #3: CLAHE (low-light handling)
✓ Fix #4: Temporal validation (10-second rule)
✓ Fix #5: Reduced inference load
✓ Fix #6: State machine
✓ Fix #7: Smart MQTT publishing

Author: Smart Building Automation Team
Date: 2025-11-27
"""

import cv2
import numpy as np
import time
import json
import threading
import logging
from ultralytics import YOLO
from collections import deque
from datetime import datetime
import paho.mqtt.client as mqtt
import psutil
import os

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(name)s] - %(levelname)s - %(message)s'
)


class ProductionOccupancyDetector:
    """Production-ready occupancy detector with all fixes"""

    def __init__(self, zone_id, camera_source, mqtt_broker, mqtt_port=1883,
                 confidence_threshold=0.6, motion_threshold=500, 
                 static_timeout=10, processing_interval=0.2):
        """
        Initialize production occupancy detector

        Args:
            zone_id: Room identifier (e.g., "room_501")
            camera_source: RTSP URL or camera index
            mqtt_broker: MQTT broker hostname/IP
            mqtt_port: MQTT port
            confidence_threshold: YOLO confidence (0.6+ recommended)
            motion_threshold: Optical flow threshold (pixels)
            static_timeout: Seconds before auto-off (10s rule)
            processing_interval: Process every N seconds
        """
        self.zone_id = zone_id
        self.camera_source = camera_source
        self.logger = logging.getLogger(f"Zone_{zone_id}")

        self.confidence_threshold = confidence_threshold
        self.motion_threshold = motion_threshold
        self.static_timeout = static_timeout
        self.processing_interval = processing_interval

        # YOLO8n model (stable)
        self.logger.info("Loading YOLO8n model...")
        self.model = YOLO('yolov8n.pt')
        self.logger.info("YOLO8n loaded successfully")

        # Optical flow parameters
        self.lk_params = dict(
            winSize=(15, 15),
            maxLevel=2,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03)
        )

        # State tracking
        self.prev_frame_gray = None
        self.occupancy_state = False
        self.last_motion_time = time.time()
        self.prev_occupancy_state = False

        # MQTT
        self.mqtt_broker = mqtt_broker
        self.mqtt_port = mqtt_port
        self.mqtt_client = mqtt.Client(client_id=f"detector_{zone_id}")
        self.mqtt_client.on_connect = self._on_mqtt_connect
        self.mqtt_client.on_disconnect = self._on_mqtt_disconnect
        self.mqtt_client.on_message = self._on_mqtt_message

        # Statistics
        self.frame_count = 0
        self.process_count = 0
        self.state_changes = []
        self.is_running = False
        
        # Performance monitoring
        self.process = psutil.Process(os.getpid())
        self.processing_times = []

    def _on_mqtt_connect(self, client, userdata, flags, rc):
        """MQTT connection callback"""
        if rc == 0:
            self.logger.info(f"Connected to MQTT broker at {self.mqtt_broker}")
        else:
            self.logger.error(f"MQTT connection failed: code {rc}")

    def _on_mqtt_disconnect(self, client, userdata, rc):
        """MQTT disconnect callback"""
        if rc != 0:
            self.logger.warning(f"Unexpected MQTT disconnection: {rc}")

    def _on_mqtt_message(self, client, userdata, msg):
        """MQTT message callback (for future control commands)"""
        self.logger.debug(f"MQTT message received: {msg.topic} = {msg.payload}")

    def connect_mqtt(self):
        """Connect to MQTT broker"""
        try:
            self.mqtt_client.connect(
                self.mqtt_broker,
                self.mqtt_port,
                keepalive=60
            )
            self.mqtt_client.loop_start()
            self.logger.info(f"MQTT connection initiated")
        except Exception as e:
            self.logger.error(f"MQTT connection error: {e}")

    def get_process_usage(self):
        """Get current process CPU usage"""
        try:
            cpu_percent = self.process.cpu_percent()
            return cpu_percent
        except:
            return 0
    
    def publish_occupancy(self, person_count, motion_detected, confidence):
        """
        Publish occupancy data with performance metrics (only on state change)
        """
        payload = {
            'zone_id': self.zone_id,
            'timestamp': datetime.now().isoformat(),
            'occupancy': self.occupancy_state,
            'state': 'OCCUPIED' if self.occupancy_state else 'EMPTY',
            'person_count': person_count,
            'motion_detected': motion_detected,
            'confidence': confidence,
            'performance': {
                'process_cpu_usage': self.get_process_usage(),
                'avg_processing_time': sum(self.processing_times[-10:]) / len(self.processing_times[-10:]) * 1000 if self.processing_times else 0
            }
        }

        try:
            self.mqtt_client.publish(
                'analytics/occupancy',
                json.dumps(payload),
                qos=1
            )
            self.logger.info(
                f"Published: {payload['state']} (persons={person_count}, "
                f"motion={motion_detected})"
            )
        except Exception as e:
            self.logger.error(f"Failed to publish: {e}")

    def preprocess_for_lowlight(self, frame):
        """Fix #3: CLAHE preprocessing for low-light"""
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l_clahe = clahe.apply(l)
        lab_clahe = cv2.merge([l_clahe, a, b])
        return cv2.cvtColor(lab_clahe, cv2.COLOR_LAB2BGR)

    def detect_persons_yolo8(self, frame):
        """Fix #1: YOLO8n detection with high confidence"""
        frame_enhanced = self.preprocess_for_lowlight(frame)

        results = self.model(
            frame_enhanced,
            conf=self.confidence_threshold,
            verbose=False
        )

        person_count = 0
        for detection in results[0].boxes:
            if int(detection.cls) == 0:  # Person class
                person_count += 1

        return person_count

    def detect_motion_optical_flow(self, frame_gray):
        """Fix #2: Optical Flow for motion detection"""
        if self.prev_frame_gray is None:
            self.prev_frame_gray = frame_gray.copy()
            return False, 0

        corners = cv2.goodFeaturesToTrack(
            self.prev_frame_gray,
            maxCorners=200,
            qualityLevel=0.01,
            minDistance=7,
            blockSize=7
        )

        if corners is None or len(corners) == 0:
            self.prev_frame_gray = frame_gray.copy()
            return False, 0

        next_pts, status, err = cv2.calcOpticalFlowPyrLK(
            self.prev_frame_gray,
            frame_gray,
            corners,
            None,
            **self.lk_params
        )

        if status is None or next_pts is None:
            self.prev_frame_gray = frame_gray.copy()
            return False, 0

        good_old = corners[status == 1]
        good_new = next_pts[status == 1]

        if len(good_old) == 0:
            self.prev_frame_gray = frame_gray.copy()
            return False, 0

        movement = np.sum(np.sqrt(
            (good_new[:, 0, 0] - good_old[:, 0, 0]) ** 2 +
            (good_new[:, 0, 1] - good_old[:, 0, 1]) ** 2
        ))

        self.prev_frame_gray = frame_gray.copy()
        motion_detected = movement > self.motion_threshold

        return motion_detected, movement

    def apply_temporal_validation(self, person_detected, motion_detected):
        """Fix #4: Temporal validation with 10-second rule"""
        current_time = time.time()

        if motion_detected and person_detected:
            self.last_motion_time = current_time

        time_since_motion = current_time - self.last_motion_time

        if person_detected and motion_detected:
            new_state = True
            confidence = "HIGH"
        elif person_detected and time_since_motion < self.static_timeout:
            new_state = True
            confidence = f"MEDIUM"
        else:
            new_state = False
            confidence = "NONE"

        return new_state, confidence

    def process_stream(self):
        """Main processing loop"""
        self.logger.info(f"Opening camera: {self.camera_source}")
        cap = cv2.VideoCapture(self.camera_source)

        if not cap.isOpened():
            self.logger.error(f"Failed to open camera")
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 30)

        self.logger.info(f"Camera opened successfully")
        self.is_running = True

        last_process_time = time.time()

        try:
            while self.is_running:
                ret, frame = cap.read()
                if not ret:
                    self.logger.warning(f"Failed to read frame, reconnecting...")
                    cap = cv2.VideoCapture(self.camera_source)
                    continue

                self.frame_count += 1
                current_time = time.time()

                # Fix #5: Process every 200-500ms (not every frame)
                if current_time - last_process_time >= self.processing_interval:
                    process_start = time.time()
                    self.process_count += 1

                    # Processing pipeline
                    frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

                    person_count = self.detect_persons_yolo8(frame)
                    motion_detected, _ = self.detect_motion_optical_flow(frame_gray)
                    new_occupancy, confidence = self.apply_temporal_validation(
                        person_detected=(person_count > 0),
                        motion_detected=motion_detected
                    )

                    self.occupancy_state = new_occupancy

                    # Fix #7: Publish only on state change
                    if new_occupancy != self.prev_occupancy_state:
                        self.publish_occupancy(person_count, motion_detected, confidence)
                        self.state_changes.append({
                            'time': datetime.now().isoformat(),
                            'state': 'OCCUPIED' if new_occupancy else 'EMPTY'
                        })

                    self.prev_occupancy_state = new_occupancy

                    # Log every 5 processes with performance metrics
                    if self.process_count % 5 == 0:
                        cpu_usage = self.get_process_usage()
                        avg_process_time = sum(self.processing_times[-10:]) / len(self.processing_times[-10:]) * 1000 if self.processing_times else 0
                        state_text = "OCCUPIED" if new_occupancy else "EMPTY"
                        self.logger.debug(
                            f"Frame {self.frame_count}: {state_text} | "
                            f"Persons: {person_count} | Motion: {motion_detected} | "
                            f"CPU: {cpu_usage:.1f}% | Proc: {avg_process_time:.1f}ms"
                        )

                    last_process_time = current_time
                    process_time = time.time() - process_start
                    self.processing_times.append(process_time)

        except Exception as e:
            self.logger.error(f"Processing error: {e}")

        finally:
            cap.release()
            self.logger.info(f"Camera closed")

    def start(self):
        """Start processing in background thread"""
        self.connect_mqtt()
        thread = threading.Thread(target=self.process_stream, daemon=True)
        thread.start()
        self.logger.info(f"Processing thread started")
        return thread

    def stop(self):
        """Stop processing"""
        self.is_running = False
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
        self.logger.info(f"Detector stopped")


# Example configuration for multiple zones
CONFIG = {
    'zones': [
        {
            'zone_id': 'room_501',
            'camera_source': 0,  # Webcam for demo
            # Or use RTSP: 'rtsp://admin:password@192.168.1.101:554/stream'
        },
        # Add more zones
        # {
        #     'zone_id': 'room_502',
        #     'camera_source': 'rtsp://admin:password@192.168.1.102:554/stream',
        # },
    ],
    'mqtt_broker': 'localhost',  # Change to your MQTT broker IP
    'mqtt_port': 1883,
    'confidence_threshold': 0.6,
    'motion_threshold': 500,
    'static_timeout': 10,
    'processing_interval': 0.2,
}


if __name__ == "__main__":
    logger = logging.getLogger("Main")
    logger.info("="*70)
    logger.info("OCCUPANCY DETECTION SYSTEM v2 - MQTT PRODUCTION")
    logger.info("="*70)
    logger.info("Starting detectors for all zones...")

    detectors = []
    threads = []

    try:
        for zone_config in CONFIG['zones']:
            detector = ProductionOccupancyDetector(
                zone_id=zone_config['zone_id'],
                camera_source=zone_config['camera_source'],
                mqtt_broker=CONFIG['mqtt_broker'],
                mqtt_port=CONFIG['mqtt_port'],
                confidence_threshold=CONFIG['confidence_threshold'],
                motion_threshold=CONFIG['motion_threshold'],
                static_timeout=CONFIG['static_timeout'],
                processing_interval=CONFIG['processing_interval']
            )
            detectors.append(detector)
            thread = detector.start()
            threads.append(thread)

        logger.info(f"Started {len(detectors)} occupancy detectors")
        logger.info("All fixes implemented:")
        logger.info("✓ Fix #1: YOLO8n (stable)")
        logger.info("✓ Fix #2: Optical Flow (no false positives)")
        logger.info("✓ Fix #3: CLAHE (low-light)")
        logger.info("✓ Fix #4: 10-second rule")
        logger.info("✓ Fix #5: Reduced inference load")
        logger.info("✓ Fix #6: State machine")
        logger.info("✓ Fix #7: Smart MQTT publishing")
        logger.info("="*70)
        logger.info("Press Ctrl+C to stop...")

        # Keep running
        for thread in threads:
            thread.join()

    except KeyboardInterrupt:
        logger.info("\nShutdown requested...")
        for detector in detectors:
            detector.stop()
        logger.info("All detectors stopped")
