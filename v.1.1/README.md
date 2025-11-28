# Occupancy Detection System v1.1

**Initial Release** - Basic occupancy detection with YOLO11 and MQTT integration.

## 🚀 Features

### Core Detection
- **YOLO11n model** for person detection
- **Basic occupancy logic** - person present = occupied
- **Webcam support** - USB camera integration
- **Real-time processing** - Live video analysis

### MQTT Integration
- **State publishing** - Occupancy status to MQTT broker
- **JSON payloads** - Structured data format
- **Configurable broker** - Custom MQTT server support

### Visualization
- **Live video display** - Real-time detection overlay
- **Person count** - Number of people detected
- **Status indicators** - Visual occupancy state
- **Bounding boxes** - Person detection visualization

## 📁 Files
- `occupancy_demo.py` - Basic demo implementation
- `occupancy_detector_mqtt.py` - MQTT-enabled version
- `requirements.txt` - Python dependencies
- `SETUP_INSTRUCTIONS.txt` - Installation guide
- `MQTT_INTEGRATION_GUIDE.txt` - MQTT setup
- `quick_start.sh` - Quick setup script

## ⚙️ Configuration
- **Model**: YOLO11n (yolo11n.pt)
- **Confidence**: 0.5 (default)
- **Processing**: Every frame (high CPU usage)
- **MQTT**: Basic state publishing

## 🎯 Use Cases
- **Proof of concept** - Initial occupancy detection
- **Development testing** - Algorithm validation
- **Basic automation** - Simple on/off control

## ⚠️ Known Issues
- **High false positives** - Detects static images/posters as people
- **No motion validation** - Static objects trigger occupancy
- **High CPU usage** - Processes every frame
- **Frame jitter** - Rapid state changes
- **Poor low-light performance** - Struggles in dim conditions

## 📊 Performance
- **Processing Rate**: 30 FPS (every frame)
- **CPU Usage**: High (100% processing)
- **Accuracy**: Moderate (false positives common)
- **Latency**: Low (immediate response)

---
*This is the foundation version that established the basic occupancy detection framework.*