# Occupancy Detection System v1.3 - Raspberry Pi 4B

Multi-camera occupancy detection system optimized for Raspberry Pi 4B with plug-and-play camera support.

## Features

- **Multi-camera support**: Add/remove cameras by editing `camera_ips.txt`
- **Pi-optimized**: CPU-only processing, thermal throttling, headless operation
- **MQTT publishing**: State changes published to configurable MQTT broker
- **Classroom automation**: GPIO relay control for lights/projectors/AC
- **Plug-and-play**: No model retraining required, uses existing weights
- **Lightweight**: Frame differencing motion detection, 320x240 processing resolution

## File Structure

```
v.1.3/
├── occupancy_detector_pi.py      # Main detector script
├── camera_ips.txt                # Camera configuration
├── config_pi.yaml                # System configuration  
├── requirements_pi.txt           # Python dependencies
├── setup_model.py                # Model setup script
├── start_pi_detector.sh          # Startup script
├── occupancy-detector.service    # Systemd service file
└── README_v1.3.md               # This file
```

## Quick Start

### 1. Install Dependencies

```bash
cd v.1.3
pip install -r requirements_pi.txt
```

### 2. Setup Model

```bash
python setup_model.py
```

### 3. Configure Cameras

Edit `camera_ips.txt` with your camera details:
```
room_501,rtsp://admin:password@192.168.1.101:554/stream
room_502,rtsp://admin:password@192.168.1.102:554/stream
```

### 4. Configure Settings

Edit `config_pi.yaml`:
```yaml
mqtt_broker: "192.168.1.50"
processing_interval_sec: 1.0
confidence_threshold: 0.6
```

### 5. Run

**Option A: Direct run**
```bash
python occupancy_detector_pi.py
```

**Option B: Using startup script**
```bash
./start_pi_detector.sh
```

**Option C: As system service**
```bash
# Copy service file
sudo cp occupancy-detector.service /etc/systemd/system/

# Enable and start service
sudo systemctl enable occupancy-detector.service
sudo systemctl start occupancy-detector.service

# Check status
sudo systemctl status occupancy-detector.service
```

## Configuration Files

### camera_ips.txt
- One camera per line: `room_id,rtsp_url`
- Lines starting with `#` are ignored
- Add/remove cameras without code changes

### config_pi.yaml
- `mqtt_broker`: MQTT broker IP address
- `processing_interval_sec`: Processing frequency (1.0 = 1fps)
- `confidence_threshold`: YOLO detection threshold (0.6 recommended)
- `min_motion_score`: Motion detection sensitivity
- `temp_threshold_celsius`: CPU temperature for throttling (75°C)
- `gpio_pin`: BCM pin number for relay control (18)
- `gpio_active_high`: Relay activation logic (true = HIGH turns ON)

## MQTT Output

Published to: `analytics/occupancy/<room_id>`

Example payload:
```json
{
  "zone_id": "room_501",
  "timestamp": "2025-11-28T10:30:45Z",
  "occupancy": true,
  "state": "OCCUPIED",
  "person_count": 2
}
```

## Model Weights

The system automatically uses the trained model from `../v.1.2/model.pt`. If not found, it falls back to `yolov8n.pt`.

**No retraining required** - the existing weights are reused.

## Pi-Specific Optimizations

- **Resolution**: Frames resized to 320x240 for faster processing
- **Processing rate**: Configurable interval (default 1fps) to manage CPU load
- **Thermal throttling**: Automatically reduces processing frequency if CPU > 75°C
- **Headless operation**: No GUI windows, suitable for SSH deployment
- **Shared model**: Single YOLO instance shared across all cameras
- **GPIO relay control**: Automatic classroom equipment control

## Classroom Integration

The system can control classroom equipment via GPIO relay:

### Wiring
- Connect relay module to BCM pin 18 (configurable)
- Relay controls lights, projector, AC, etc.
- Supports both active-high and active-low relays

### Behavior
- **OCCUPIED**: Relay turns ON (equipment activated)
- **EMPTY**: Relay turns OFF (equipment deactivated)
- **State changes only**: No constant switching
- **Safe shutdown**: Relay turns OFF when system stops

## Troubleshooting

### High CPU Usage
- Increase `processing_interval_sec` in config
- Reduce number of cameras
- Check CPU temperature: `cat /sys/class/thermal/thermal_zone0/temp`

### Camera Connection Issues
- Verify RTSP URLs are accessible
- Check network connectivity
- Review logs for specific error messages

### MQTT Issues
- Verify broker IP and port in config
- Check firewall settings
- Test MQTT connectivity with mosquitto tools

## Logs

The system logs to console with timestamps. Redirect to file if needed:
```bash
python occupancy_detector_pi.py > occupancy.log 2>&1
```

## Stopping the System

Press `Ctrl+C` to gracefully stop all camera processing and disconnect MQTT.