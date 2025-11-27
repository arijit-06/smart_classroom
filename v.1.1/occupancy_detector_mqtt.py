
"""
Occupancy Detection with MQTT Publishing
Advanced version for deployment on central server
Detects occupancy and publishes to MQTT broker
Supports multiple camera feeds

Author: Smart Building Automation Team
Date: 2025-12-27
"""

import cv2
import time
import json
import threading
from ultralytics import YOLO
from collections import deque
from datetime import datetime
import paho.mqtt.client as mqtt
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class OccupancyDetectorMQTT:
    def __init__(self, zone_id, camera_source, mqtt_broker, mqtt_port=1883, 
                 confidence_threshold=0.5, buffer_size=3):
        """
        Initialize occupancy detector with MQTT publishing

        Args:
            zone_id: Zone identifier (e.g., "room_501")
            camera_source: Camera source (0 for webcam, or RTSP URL)
            mqtt_broker: MQTT broker IP/hostname
            mqtt_port: MQTT broker port (default 1883)
            confidence_threshold: Confidence threshold for YOLO
            buffer_size: Occupancy buffer size for stability
        """
        self.zone_id = zone_id
        self.camera_source = camera_source
        self.confidence_threshold = confidence_threshold
        self.buffer_size = buffer_size
        self.occupancy_buffer = deque(maxlen=buffer_size)

        # Load model
        logger.info(f"[{self.zone_id}] Loading YOLO11n model...")
        self.model = YOLO('yolo11n.pt')
        logger.info(f"[{self.zone_id}] Model loaded successfully")

        # MQTT setup
        self.mqtt_client = mqtt.Client(client_id=f"detector_{zone_id}")
        self.mqtt_client.on_connect = self.on_mqtt_connect
        self.mqtt_client.on_disconnect = self.on_mqtt_disconnect
        self.mqtt_broker = mqtt_broker
        self.mqtt_port = mqtt_port

        # Statistics
        self.frame_count = 0
        self.occupancy_count = 0
        self.last_occupancy_state = None

    def on_mqtt_connect(self, client, userdata, flags, rc):
        """MQTT connection callback"""
        if rc == 0:
            logger.info(f"[{self.zone_id}] Connected to MQTT broker")
        else:
            logger.error(f"[{self.zone_id}] MQTT connection failed with code {rc}")

    def on_mqtt_disconnect(self, client, userdata, rc):
        """MQTT disconnection callback"""
        if rc != 0:
            logger.warning(f"[{self.zone_id}] Unexpected MQTT disconnection: {rc}")

    def connect_mqtt(self):
        """Connect to MQTT broker"""
        try:
            self.mqtt_client.connect(self.mqtt_broker, self.mqtt_port, keepalive=60)
            self.mqtt_client.loop_start()
            logger.info(f"[{self.zone_id}] MQTT connection initiated")
        except Exception as e:
            logger.error(f"[{self.zone_id}] Failed to connect to MQTT: {e}")

    def publish_occupancy(self, person_count, occupancy_detected):
        """
        Publish occupancy data to MQTT

        Topic: analytics/occupancy
        """
        payload = {
            'zone_id': self.zone_id,
            'timestamp': datetime.now().isoformat(),
            'occupancy': occupancy_detected,
            'person_count': person_count,
            'occupancy_text': 'occupied' if occupancy_detected else 'empty'
        }

        try:
            self.mqtt_client.publish(
                'analytics/occupancy',
                json.dumps(payload),
                qos=1
            )
            logger.debug(f"[{self.zone_id}] Published: {payload}")
        except Exception as e:
            logger.error(f"[{self.zone_id}] Failed to publish: {e}")

    def detect_persons(self, frame):
        """Run YOLO detection"""
        results = self.model(frame, conf=self.confidence_threshold, verbose=False)

        person_count = 0
        for detection in results[0].boxes:
            if int(detection.cls) == 0:  # Person class
                person_count += 1

        return person_count, results[0]

    def get_occupancy_status(self, person_count):
        """Get stable occupancy status"""
        occupancy_detected = person_count > 0
        self.occupancy_buffer.append(occupancy_detected)

        if len(self.occupancy_buffer) > 0:
            stable_occupancy = sum(self.occupancy_buffer) > len(self.occupancy_buffer) / 2
        else:
            stable_occupancy = occupancy_detected

        return stable_occupancy

    def process_stream(self):
        """Process camera stream and publish occupancy"""
        logger.info(f"[{self.zone_id}] Opening camera: {self.camera_source}")

        cap = cv2.VideoCapture(self.camera_source)
        if not cap.isOpened():
            logger.error(f"[{self.zone_id}] Failed to open camera")
            return

        # Set camera properties
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 30)

        logger.info(f"[{self.zone_id}] Camera opened successfully")

        last_process_time = time.time()
        process_interval = 0.1  # 0.1 seconds = 10 FPS processing

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    logger.warning(f"[{self.zone_id}] Failed to read frame")
                    break

                current_time = time.time()
                time_since_last = current_time - last_process_time

                # Process every 0.1 seconds
                if time_since_last >= process_interval:
                    inference_start = time.time()
                    person_count, results = self.detect_persons(frame)
                    occupancy_stable = self.get_occupancy_status(person_count)
                    inference_time = time.time() - inference_start

                    # Update statistics
                    self.frame_count += 1
                    if occupancy_stable:
                        self.occupancy_count += 1

                    # Publish to MQTT only if state changed
                    if occupancy_stable != self.last_occupancy_state:
                        self.publish_occupancy(person_count, occupancy_stable)
                        self.last_occupancy_state = occupancy_stable

                    # Log every 10 frames
                    if self.frame_count % 10 == 0:
                        status = "OCCUPIED" if occupancy_stable else "EMPTY"
                        logger.info(
                            f"[{self.zone_id}] Frame {self.frame_count}: {status} | "
                            f"Persons: {person_count} | Inference: {inference_time*1000:.1f}ms"
                        )

                    last_process_time = current_time

        except Exception as e:
            logger.error(f"[{self.zone_id}] Error processing stream: {e}")

        finally:
            cap.release()
            logger.info(f"[{self.zone_id}] Camera closed")

    def start(self):
        """Start processing in a background thread"""
        self.connect_mqtt()
        thread = threading.Thread(target=self.process_stream, daemon=True)
        thread.start()
        logger.info(f"[{self.zone_id}] Processing thread started")
        return thread


# Configuration
CONFIG = {
    'zones': [
        {'zone_id': 'room_501', 'camera_source': 0},  # Webcam
        # Add more zones here
        # {'zone_id': 'room_502', 'camera_source': 'rtsp://admin:pwd@192.168.1.102:554/stream'},
    ],
    'mqtt_broker': 'localhost',  # Your MQTT broker IP
    'mqtt_port': 1883,
    'confidence_threshold': 0.5,
}


if __name__ == "__main__":
    logger.info("="*60)
    logger.info("OCCUPANCY DETECTION - MQTT VERSION")
    logger.info("="*60)

    # Create detectors for each zone
    detectors = []
    threads = []

    for zone_config in CONFIG['zones']:
        detector = OccupancyDetectorMQTT(
            zone_id=zone_config['zone_id'],
            camera_source=zone_config['camera_source'],
            mqtt_broker=CONFIG['mqtt_broker'],
            mqtt_port=CONFIG['mqtt_port'],
            confidence_threshold=CONFIG['confidence_threshold']
        )
        detectors.append(detector)
        thread = detector.start()
        threads.append(thread)

    logger.info(f"Started {len(detectors)} occupancy detectors")
    logger.info("Press Ctrl+C to stop...")

    try:
        # Keep main thread alive
        for thread in threads:
            thread.join()
    except KeyboardInterrupt:
        logger.info("\nShutdown requested")
        logger.info("Stopping all detectors...")
        for detector in detectors:
            detector.mqtt_client.loop_stop()
            detector.mqtt_client.disconnect()
        logger.info("All detectors stopped")
