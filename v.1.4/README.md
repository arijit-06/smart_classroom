# Occupancy Detection System v1.4

**Edge Optimized** - Simplified deployment with configurable FPS, 2-minute timer, and CCTV integration.

## 🆕 What's New from v1.3

### Simplified Edge Deployment
- **Configurable FPS** - User selectable 10/5/1 FPS snapshot processing
- **2-minute auto-off timer** - Automatic equipment shutdown after 120 seconds
- **Removed motion detection** - Simplified person-only logic
- **CCTV camera support** - Direct IP camera integration via RTSP/HTTP
- **Inference time tracking** - Real-time performance monitoring

### Streamlined Operation
- **No CPU/GPU stats** - Removed system-wide monitoring
- **User input prompts** - Interactive FPS selection at startup
- **Enhanced camera support** - Multiple IP camera protocols
- **Simplified configuration** - Focused on essential settings

### Performance Focus
- **Inference timing** - YOLO processing time in milliseconds
- **Snapshot-based processing** - Configurable frame rate
- **Memory optimization** - Reduced overhead
- **Edge-friendly** - Minimal resource requirements

## 🚀 Features

### Configurable Processing
- **User-selectable FPS** - Choose 10/5/1 FPS at startup
- **Snapshot processing** - Only process frames at selected rate
- **Performance scaling** - Higher FPS = better accuracy, more CPU usage
- **Real-time adjustment** - Change FPS without code modification

### Smart Timer Logic
- **2-minute countdown** - Starts when no person detected
- **Auto-reset timer** - Resets when person appears during countdown
- **Immediate activation** - Lights ON instantly when person detected
- **Configurable timeout** - 120 seconds default, adjustable in config

### CCTV Integration
- **RTSP support** - Direct IP camera connection
- **HTTP cameras** - Web-based camera streams
- **Authentication** - Username/password support
- **Multiple brands** - Hikvision, Dahua, generic IP cameras
- **USB fallback** - Local camera support via index

### Simplified Detection
- **Person-only logic** - No motion validation required
- **YOLO8n inference** - Proven model performance
- **Confidence thresholding** - Configurable detection sensitivity
- **Processing resolution** - 320x240 for speed

## 📁 Files
- `occupancy_detector_edge.py` - Main edge detector
- `cameras_edge.txt` - CCTV camera configuration
- `config_edge.yaml` - Edge-specific settings
- `requirements_edge.txt` - Minimal dependencies
- `start_edge.sh` - Startup script
- `README_v1.4.md` - Detailed documentation

## ⚙️ Configuration

### Camera Setup (`cameras_edge.txt`)
```
classroom_101,rtsp://admin:password@192.168.1.101:554/stream
classroom_102,http://192.168.1.102/video.cgi
office_201,0
```

### System Settings (`config_edge.yaml`)
```yaml
snapshot_fps: 5                    # Overridden by user input
confidence_threshold: 0.6
auto_off_timeout: 120             # 2 minutes
gpio_pin: 18
gpio_active_high: true
```

## 🎯 Improvements from v1.3

### Simplified Operation
- **Removed motion detection** - Eliminated complex optical flow
- **User-friendly startup** - Interactive FPS selection
- **Focused configuration** - Only essential settings
- **Streamlined logging** - Inference time focus

### Enhanced Camera Support
- **CCTV integration** - Direct IP camera support
- **Multiple protocols** - RTSP, HTTP, USB
- **Brand compatibility** - Works with major camera manufacturers
- **Authentication support** - Secure camera connections

### Performance Optimization
- **Configurable FPS** - Balance accuracy vs performance
- **Inference timing** - Real-time performance monitoring
- **Memory efficiency** - Reduced overhead
- **Edge deployment** - Minimal resource requirements

### Timer Enhancement
- **2-minute rule** - Classroom-appropriate timeout
- **Smart reset** - Timer resets on person detection
- **Countdown display** - Shows remaining time
- **Configurable duration** - Adjustable timeout

## 📊 Performance Comparison

| Metric | v1.3 | v1.4 | Change |
|--------|------|------|--------|
| Motion Detection | Optical Flow | None | Simplified |
| FPS Selection | Fixed 1fps | User selectable 10/5/1 | Configurable |
| Timer Logic | None | 2-minute auto-off | Enhanced |
| Camera Support | RTSP only | RTSP/HTTP/USB | Expanded |
| Performance Monitoring | CPU/GPU stats | Inference time only | Focused |
| User Interaction | None | FPS prompt | Interactive |

## 🎯 Use Cases
- **Classroom automation** - 2-minute timer perfect for classrooms
- **CCTV integration** - Leverage existing camera infrastructure
- **Edge deployment** - Minimal resource requirements
- **Performance tuning** - Configurable FPS for different scenarios
- **Simple automation** - Straightforward on/off control

### FPS Selection Guide
- **10 FPS**: High accuracy, real-time response, higher CPU usage
- **5 FPS**: Balanced performance (recommended for most cases)
- **1 FPS**: Minimal CPU usage, slower response, energy efficient

### Typical Deployment
```
Startup: "Enter snapshot FPS (10/5/1): 5"
System: "Using 5 FPS snapshot processing"
Operation: Person detected → Lights ON → 2min timer → Lights OFF
```

## 🔧 CCTV Camera Examples

### Hikvision
```
rtsp://admin:password@192.168.1.100:554/Streaming/Channels/101
```

### Dahua
```
rtsp://admin:password@192.168.1.101:554/cam/realmonitor?channel=1&subtype=0
```

### Generic IP Camera
```
rtsp://username:password@ip:554/stream
http://ip/video.cgi
```

## 📈 Performance Monitoring
```
[Snapshot 10] OCCUPIED | Persons: 2 | Inference: 45.2ms | Auto-off in: 120s
[Snapshot 20] EMPTY | Persons: 0 | Inference: 42.1ms | Auto-off in: 95s
STATE CHANGE: EMPTY | Persons: 0 | Inference: 41.8ms
```

## ✅ Key Changes from v1.3
- ✅ **Configurable FPS** - User selectable processing rate
- ✅ **2-minute timer** - Automatic equipment shutdown
- ✅ **Simplified logic** - Removed motion detection complexity
- ✅ **CCTV support** - Direct IP camera integration
- ✅ **Inference timing** - Performance-focused monitoring
- ✅ **Interactive startup** - User-friendly configuration
- ❌ **Motion detection** - Removed for simplicity
- ❌ **System stats** - Removed CPU/GPU monitoring

## 🎯 Best For
- **Simple deployments** - Straightforward occupancy detection
- **CCTV integration** - Leverage existing camera infrastructure
- **Performance tuning** - Configurable processing rates
- **Classroom automation** - 2-minute timer ideal for classrooms
- **Edge computing** - Minimal resource requirements

---
*This version focuses on simplicity and edge deployment with configurable performance and enhanced camera support.*