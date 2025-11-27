
"""
Occupancy Detection Demo - Real-time Human Detection
Uses YOLO11n for person detection on webcam feed
Processes one frame every 0.1 seconds
Output: "occupancy detected" or "no occupancy detected"

Author: Smart Building Automation Team
Date: 2025-12-27
"""

import cv2
import time
from ultralytics import YOLO
from collections import deque
from datetime import datetime

class OccupancyDetector:
    def __init__(self, confidence_threshold=0.5, buffer_size=3):
        """
        Initialize occupancy detector

        Args:
            confidence_threshold: Minimum confidence for person detection (0-1)
            buffer_size: Number of frames to buffer for stable occupancy detection
        """
        print("[INIT] Loading YOLO11n model...")
        try:
            self.model = YOLO('yolo11n.pt')  # Nano model - fast on CPU
            print("[✓] Model loaded successfully")
        except Exception as e:
            print(f"[ERROR] Failed to load model: {e}")
            print("[INFO] Attempting to download model...")
            self.model = YOLO('yolo11n.pt')

        self.confidence_threshold = confidence_threshold
        self.buffer_size = buffer_size
        self.occupancy_buffer = deque(maxlen=buffer_size)

        # Statistics
        self.frame_count = 0
        self.detection_count = 0
        self.start_time = time.time()
        self.frame_times = []

    def detect_persons(self, frame):
        """
        Run YOLO detection on frame
        Returns: number of persons detected, results object
        """
        results = self.model(frame, conf=self.confidence_threshold, verbose=False)

        # Count persons (class 0 in COCO dataset)
        person_count = 0
        for detection in results[0].boxes:
            if int(detection.cls) == 0:  # Person class
                person_count += 1

        return person_count, results[0]

    def get_occupancy_status(self, person_count):
        """
        Determine occupancy status with buffering for stability
        """
        occupancy_detected = person_count > 0
        self.occupancy_buffer.append(occupancy_detected)

        # Use majority voting from buffer
        if len(self.occupancy_buffer) > 0:
            stable_occupancy = sum(self.occupancy_buffer) > len(self.occupancy_buffer) / 2
        else:
            stable_occupancy = occupancy_detected

        return stable_occupancy

    def draw_info(self, frame, person_count, occupancy, fps, inference_time):
        """
        Draw detection info on frame
        """
        height, width = frame.shape[:2]

        # Background for text
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (400, 200), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

        # Main status
        status_text = "🟢 OCCUPANCY DETECTED" if occupancy else "🔴 NO OCCUPANCY"
        status_color = (0, 255, 0) if occupancy else (0, 0, 255)

        cv2.putText(frame, status_text, (20, 50),
                   cv2.FONT_HERSHEY_SIMPLEX, 1.2, status_color, 3)

        # Details
        cv2.putText(frame, f"Persons: {person_count}", (20, 100),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        cv2.putText(frame, f"FPS: {fps:.1f}", (20, 140),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        cv2.putText(frame, f"Inference: {inference_time*1000:.1f}ms", (20, 180),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        # Timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(frame, timestamp, (20, height - 20),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)

        return frame

    def run_demo(self, camera_index=0, show_boxes=True):
        """
        Run live demo on webcam

        Args:
            camera_index: Webcam index (0 for default)
            show_boxes: Whether to draw bounding boxes around detected persons
        """
        print(f"\n[DEMO] Opening camera {camera_index}...")
        cap = cv2.VideoCapture(camera_index)

        if not cap.isOpened():
            print("[ERROR] Failed to open camera!")
            return

        # Set camera resolution for faster processing
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 30)

        print("[✓] Camera opened successfully")
        print("[INFO] Press 'q' to quit, 's' to take screenshot")
        print("[INFO] Processing at ~0.1 second intervals...\n")

        last_process_time = time.time()
        process_interval = 0.1  # Process every 0.1 seconds

        occupancy_history = []

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    print("[ERROR] Failed to read frame from camera")
                    break

                current_time = time.time()
                time_since_last = current_time - last_process_time

                # Process frame every 0.1 seconds
                if time_since_last >= process_interval:
                    inference_start = time.time()
                    person_count, results = self.detect_persons(frame)
                    occupancy_stable = self.get_occupancy_status(person_count)
                    inference_time = time.time() - inference_start

                    # Statistics
                    self.frame_count += 1
                    if person_count > 0:
                        self.detection_count += 1

                    occupancy_history.append({
                        'time': datetime.now(),
                        'persons': person_count,
                        'occupancy': occupancy_stable,
                        'inference_time': inference_time
                    })

                    # Console output every 10 frames
                    if self.frame_count % 10 == 0:
                        status = "✓ OCCUPIED" if occupancy_stable else "✗ EMPTY"
                        print(f"[Frame {self.frame_count}] {status} | "
                              f"Persons: {person_count} | "
                              f"Inference: {inference_time*1000:.1f}ms")

                    last_process_time = current_time

                    # Draw bounding boxes
                    if show_boxes and len(results.boxes) > 0:
                        for detection in results.boxes:
                            if int(detection.cls) == 0:  # Person class
                                x1, y1, x2, y2 = map(int, detection.xyxy[0])
                                confidence = detection.conf.item()

                                # Green box for detected persons
                                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                                cv2.putText(frame, f"{confidence:.2f}", (x1, y1-10),
                                          cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

                # Calculate FPS
                if self.frame_times:
                    avg_time = sum(self.frame_times[-30:]) / len(self.frame_times[-30:])
                    fps = 1 / avg_time if avg_time > 0 else 0
                else:
                    fps = 0

                self.frame_times.append(time.time() - current_time)

                # Get latest occupancy and inference time
                if occupancy_history:
                    latest = occupancy_history[-1]
                    occupancy = latest['occupancy']
                    inference_time = latest['inference_time']
                else:
                    occupancy = False
                    inference_time = 0

                # Draw info on frame
                frame = self.draw_info(frame, person_count, occupancy, fps, inference_time)

                # Display frame
                cv2.imshow('Occupancy Detection Demo', frame)

                # Handle key presses
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    print("\n[INFO] Quitting...")
                    break
                elif key == ord('s'):
                    filename = f"occupancy_screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                    cv2.imwrite(filename, frame)
                    print(f"[✓] Screenshot saved: {filename}")

        finally:
            # Cleanup
            cap.release()
            cv2.destroyAllWindows()

            # Print statistics
            print("\n" + "="*60)
            print("OCCUPANCY DETECTION DEMO - STATISTICS")
            print("="*60)
            print(f"Total frames processed: {self.frame_count}")
            print(f"Frames with occupancy: {self.detection_count}")
            print(f"Occupancy rate: {self.detection_count/max(self.frame_count, 1)*100:.1f}%")
            print(f"Runtime: {time.time() - self.start_time:.1f} seconds")
            if self.frame_times:
                print(f"Average inference time: {sum(self.frame_times)/len(self.frame_times)*1000:.1f}ms")
                print(f"Max inference time: {max(self.frame_times)*1000:.1f}ms")
            print("="*60)


if __name__ == "__main__":
    print("\n" + "="*60)
    print("SMART BUILDING OCCUPANCY DETECTION DEMO")
    print("Real-time Human Detection using YOLO11")
    print("="*60)
    print("\nSetup Instructions:")
    print("1. Ensure your webcam is connected")
    print("2. Press 'q' to quit the demo")
    print("3. Press 's' to take a screenshot")
    print("="*60 + "\n")

    # Create detector instance
    detector = OccupancyDetector(
        confidence_threshold=0.5,  # Adjust for sensitivity
        buffer_size=3              # Stability buffer
    )

    # Run demo
    detector.run_demo(camera_index=0, show_boxes=True)
