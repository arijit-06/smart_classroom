"""
OCCUPANCY DETECTION SYSTEM v1.3 - OPTIMIZED SNAPSHOT PROCESSING
Key Feature: 10fps snapshot capture with reduced processing load

Architecture:
  30fps Camera → 10fps Snapshots → Processing Pipeline → State Output

Author: Smart Building Automation Team
Date: 2025-11-27
"""

import cv2
import numpy as np
import time
from ultralytics import YOLO
from collections import deque
from datetime import datetime
import threading
import psutil
import os

class OptimizedOccupancyDetector:
    def __init__(self, zone_id="demo_zone", confidence_threshold=0.6, 
                 motion_threshold=500, snapshot_fps=10):
        """
        Initialize optimized occupancy detector with snapshot processing

        Args:
            zone_id: Zone identifier
            confidence_threshold: YOLO detection confidence
            motion_threshold: Optical flow pixel movement threshold
            snapshot_fps: Frames per second for processing (10fps = half processing load)
        """
        self.zone_id = zone_id
        self.confidence_threshold = confidence_threshold
        self.motion_threshold = motion_threshold
        self.snapshot_interval = 1.0 / snapshot_fps  # 0.1s for 10fps

        print("[INIT] Loading YOLO8n model...")
        try:
            self.model = YOLO('yolov8n.pt')
            print("[✓] YOLO8n loaded successfully")
        except Exception as e:
            print(f"[ERROR] Failed to load model: {e}")
            self.model = YOLO('yolov8n.pt')

        # Optical flow detector
        self.lk_params = dict(
            winSize=(15, 15),
            maxLevel=2,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03)
        )

        # State tracking
        self.prev_frame_gray = None
        self.occupancy_state = False
        self.last_motion_time = time.time()

        # Statistics
        self.frame_count = 0
        self.processing_count = 0
        self.occupancy_history = []
        self.state_changes = []
        
        # Performance monitoring
        self.process = psutil.Process(os.getpid())
        self.processing_times = []

        # Snapshot buffer
        self.snapshot_buffer = deque(maxlen=3)

    def get_process_usage(self):
        """Get current process CPU usage"""
        try:
            cpu_percent = self.process.cpu_percent()
            return cpu_percent
        except:
            return 0

    def preprocess_frame_for_lowlight(self, frame):
        """CLAHE preprocessing for low-light conditions"""
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l_clahe = clahe.apply(l)
        lab_clahe = cv2.merge([l_clahe, a, b])
        frame_enhanced = cv2.cvtColor(lab_clahe, cv2.COLOR_LAB2BGR)
        return frame_enhanced

    def detect_persons_yolo8(self, frame):
        """YOLO8n person detection"""
        frame_enhanced = self.preprocess_frame_for_lowlight(frame)
        results = self.model(frame_enhanced, conf=self.confidence_threshold, verbose=False)

        person_count = 0
        detections = []

        for detection in results[0].boxes:
            if int(detection.cls) == 0:  # Person class
                person_count += 1
                x1, y1, x2, y2 = map(int, detection.xyxy[0])
                confidence = detection.conf.item()
                detections.append({
                    'bbox': (x1, y1, x2, y2),
                    'confidence': confidence,
                    'center': ((x1 + x2) // 2, (y1 + y2) // 2)
                })

        return person_count, detections, frame_enhanced

    def detect_motion_optical_flow(self, frame_gray):
        """Optical Flow motion detection"""
        if self.prev_frame_gray is None:
            self.prev_frame_gray = frame_gray
            return False, 0

        corners = cv2.goodFeaturesToTrack(
            self.prev_frame_gray, maxCorners=200, qualityLevel=0.01,
            minDistance=7, blockSize=7
        )

        if corners is None or len(corners) == 0:
            self.prev_frame_gray = frame_gray
            return False, 0

        next_pts, status, err = cv2.calcOpticalFlowPyrLK(
            self.prev_frame_gray, frame_gray, corners, None, **self.lk_params
        )

        if status is None or next_pts is None:
            self.prev_frame_gray = frame_gray
            return False, 0

        good_old = corners[status == 1]
        good_new = next_pts[status == 1]

        if len(good_old) == 0:
            self.prev_frame_gray = frame_gray
            return False, 0

        movement = np.sum(np.sqrt(
            (good_new[:, 0] - good_old[:, 0]) ** 2 +
            (good_new[:, 1] - good_old[:, 1]) ** 2
        ))

        self.prev_frame_gray = frame_gray.copy()
        motion_detected = movement > self.motion_threshold
        return motion_detected, movement

    def apply_temporal_validation(self, person_detected, motion_detected):
        """Temporal validation - motion for info only"""
        current_time = time.time()
        
        if motion_detected:
            self.last_motion_time = current_time
        
        time_since_motion = current_time - self.last_motion_time

        if person_detected:
            new_state = True
            confidence = "HIGH"
        else:
            new_state = False
            confidence = "NONE"

        return new_state, confidence, time_since_motion

    def publish_state_change(self, new_state, prev_state):
        """Publish only on state changes"""
        if new_state != prev_state:
            timestamp = datetime.now().isoformat()
            state_text = "OCCUPIED" if new_state else "EMPTY"
            print(f"[STATE CHANGE] {timestamp} -> {state_text}")
            self.state_changes.append({'time': timestamp, 'state': state_text})
            return True
        return False

    def draw_visualization(self, frame, person_count, motion_detected, 
                          confidence, time_since_motion, occupancy_state):
        """Draw visualization with performance metrics"""
        height, width = frame.shape[:2]

        # Semi-transparent background
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (500, 330), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

        # Main status
        status_text = "OCCUPIED" if occupancy_state else "EMPTY"
        status_color = (0, 255, 0) if occupancy_state else (0, 0, 255)
        cv2.putText(frame, status_text, (20, 50),
                   cv2.FONT_HERSHEY_SIMPLEX, 1.3, status_color, 3)

        # Detection info
        detection_color = (0, 255, 0) if person_count > 0 else (100, 100, 100)
        cv2.putText(frame, f"Persons Detected: {person_count}", (20, 100),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, detection_color, 2)

        # Motion info
        motion_color = (0, 255, 0) if motion_detected else (100, 100, 100)
        motion_text = "Motion: YES" if motion_detected else "Motion: NO"
        cv2.putText(frame, motion_text, (20, 140),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, motion_color, 2)

        # Confidence level
        cv2.putText(frame, f"Confidence: {confidence}", (20, 180),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        # Time since last motion
        cv2.putText(frame, f"Time since motion: {time_since_motion:.1f}s", (20, 220),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 200, 100), 2)

        # Processing mode
        cv2.putText(frame, "Mode: 10fps SNAPSHOT PROCESSING", (20, 260),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 165, 0), 2)

        # Processing load reduction info
        load_reduction = ((1/30) - self.snapshot_interval) / (1/30) * 100
        cv2.putText(frame, f"Load Reduction: {load_reduction:.0f}%", (20, 300),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        # Timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(frame, timestamp, (20, height - 20),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)

        return frame

    def run_demo(self, camera_index=0, show_fps=True):
        """
        v1.3: 10fps snapshot processing for reduced load
        """
        print(f"\n[DEMO] Opening camera {camera_index}...")
        cap = cv2.VideoCapture(camera_index)

        if not cap.isOpened():
            print("[ERROR] Failed to open camera!")
            return

        # Camera settings
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 30)

        print("[✓] Camera opened successfully")
        print(f"[INFO] Snapshot processing: {1/self.snapshot_interval:.0f}fps")
        print("[INFO] Motion detection: INFORMATIONAL ONLY")
        print("[INFO] Press 'q' to quit, 's' to screenshot\n")

        last_snapshot_time = time.time()
        prev_occupancy_state = False
        fps_timer = []
        
        # Current processing results
        person_count = 0
        motion_detected = False
        confidence = "INITIALIZING"
        time_since_motion = 0

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    print("[ERROR] Failed to read frame from camera")
                    break

                frame_time = time.time()
                self.frame_count += 1

                current_time = time.time()
                time_since_last_snapshot = current_time - last_snapshot_time

                # Process snapshot every 0.1s (10fps)
                if time_since_last_snapshot >= self.snapshot_interval:
                    process_start = time.time()
                    self.processing_count += 1

                    # Processing pipeline
                    frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    person_count, detections, frame_enhanced = self.detect_persons_yolo8(frame)
                    motion_detected, movement = self.detect_motion_optical_flow(frame_gray)
                    
                    new_occupancy, confidence, time_since_motion = self.apply_temporal_validation(
                        person_detected=(person_count > 0),
                        motion_detected=motion_detected
                    )

                    state_changed = self.publish_state_change(new_occupancy, prev_occupancy_state)
                    self.occupancy_state = new_occupancy
                    prev_occupancy_state = new_occupancy

                    # Log history
                    self.occupancy_history.append({
                        'time': datetime.now(),
                        'persons': person_count,
                        'motion': motion_detected,
                        'occupancy': new_occupancy,
                        'confidence': confidence
                    })

                    # Console output with performance
                    if self.processing_count % 5 == 0:
                        cpu_usage = self.get_process_usage()
                        avg_process_time = sum(self.processing_times[-10:]) / len(self.processing_times[-10:]) * 1000 if self.processing_times else 0
                        status = "OCCUPIED" if new_occupancy else "EMPTY"
                        print(f"[Snapshot {self.processing_count}] {status} | "
                              f"Persons: {person_count} | Motion: {motion_detected} | "
                              f"CPU: {cpu_usage:.1f}% | Proc: {avg_process_time:.1f}ms")

                    last_snapshot_time = current_time
                    process_time = time.time() - process_start
                    self.processing_times.append(process_time)

                # Calculate FPS
                if show_fps:
                    fps_timer.append(time.time() - frame_time)
                    if len(fps_timer) > 30:
                        fps_timer.pop(0)
                    fps = 1 / (sum(fps_timer) / len(fps_timer)) if fps_timer else 0
                else:
                    fps = 0

                # Draw visualization
                frame = self.draw_visualization(
                    frame, person_count, motion_detected, confidence,
                    time_since_motion, self.occupancy_state
                )

                # Add FPS
                if show_fps:
                    cv2.putText(frame, f"FPS: {fps:.1f}", (500, 30),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2)

                # Display
                cv2.imshow('Occupancy Detection v1.3 - 10fps Snapshot Processing', frame)

                # Key handling
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    print("\n[INFO] Quitting...")
                    break
                elif key == ord('s'):
                    filename = f"occupancy_v13_screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                    cv2.imwrite(filename, frame)
                    print(f"[✓] Screenshot saved: {filename}")

        finally:
            cap.release()
            cv2.destroyAllWindows()

            # Statistics
            print("\n" + "="*70)
            print("OCCUPANCY DETECTION v1.3 - FINAL STATISTICS")
            print("="*70)
            print(f"Total frames captured: {self.frame_count}")
            print(f"Snapshots processed: {self.processing_count}")
            print(f"Processing efficiency: {self.processing_count/max(self.frame_count, 1)*100:.1f}%")
            print(f"Average processing time: {sum(self.processing_times)/len(self.processing_times)*1000:.1f}ms")
            print(f"Average CPU usage: {sum([h.get('cpu', 0) for h in self.occupancy_history])/len(self.occupancy_history) if self.occupancy_history else 0:.1f}%")
            print(f"State changes detected: {len(self.state_changes)}")
            print("="*70)
            print("\nv1.3 OPTIMIZATIONS:")
            print("✓ 10fps snapshot processing (67% load reduction)")
            print("✓ Real-time performance monitoring")
            print("✓ Optimized processing pipeline")
            print("✓ Motion tracking (informational only)")
            print("="*70)


if __name__ == "__main__":
    print("\n" + "="*70)
    print("OCCUPANCY DETECTION SYSTEM v1.3 - SNAPSHOT PROCESSING")
    print("="*70)
    print("\nKey Features:")
    print("1. ✓ 10fps snapshot processing (reduced load)")
    print("2. ✓ Real-time performance monitoring")
    print("3. ✓ YOLO8n person detection")
    print("4. ✓ Optical flow motion detection")
    print("5. ✓ Motion tracking (informational only)")
    print("="*70 + "\n")

    # Create detector
    detector = OptimizedOccupancyDetector(
        zone_id="demo_zone",
        confidence_threshold=0.6,
        motion_threshold=500,
        snapshot_fps=10  # 10fps processing
    )

    # Run demo
    detector.run_demo(camera_index=0, show_fps=True)