# CrowdSense

**Real-time AI-powered crowd monitoring and safety management system.**

CrowdSense uses YOLOv11 object detection to count people from live camera feeds, maps them to physical venue zones via perspective calibration, and provides real-time density and occupancy analytics through both a native desktop interface and a web dashboard.

---

## Features

- **Real-Time People Detection** — YOLOv11 nano model for fast, accurate person counting
- **Zone-Based Monitoring** — Physical grid system with per-zone density and risk levels (SAFE / WARNING / CRITICAL)
- **Multi-Camera Support** — Add, switch, and manage multiple camera sources (webcam, IP cameras, RTSP streams)
- **Perspective Calibration** — 4-point camera-to-world coordinate mapping for accurate spatial analysis
- **Web Dashboard** — 10-page Flask-powered dashboard with live MJPEG streaming
- **Native Desktop UI** — OpenCV-based interface with keyboard shortcuts
- **Automated Alerts** — Configurable warning/critical thresholds with cooldown management
- **Incident Tracking** — Automatic incident logging and snapshot capture
- **Session Management** — Start/stop monitoring sessions with full lifecycle tracking
- **PDF Reports** — Professional report generation with charts and analytics
- **Venue Configuration** — Rectangle and circle venue shapes with customizable grid sizes
- **Floor Plan Support** — Upload and overlay floor plans for spatial context

---

## Tech Stack

| Component | Technology |
|---|---|
| AI / Detection | YOLOv11 (Ultralytics), PyTorch |
| Computer Vision | OpenCV |
| Web Server | Flask |
| Charting | Matplotlib |
| PDF Reports | ReportLab |
| Frontend | HTML5, CSS3, Vanilla JS |

---

## Project Structure

```
crowdsense/
├── app/                        # Application source code
│   ├── main.py                 # Main application loop
│   ├── camera_worker.py        # Threaded camera + YOLO pipeline
│   ├── local_server.py         # Flask web server
│   ├── api_endpoints.py        # REST API endpoints
│   ├── venue.py                # Venue configuration model
│   ├── zones.py                # Physical zone management
│   ├── calibration.py          # Perspective transform
│   ├── camera_manager.py       # Camera CRUD operations
│   ├── alert_manager.py        # Alert system
│   ├── incident_manager.py     # Incident tracking
│   ├── safety_manager.py       # Safety orchestration
│   ├── analytics_manager.py    # Analytics engine
│   ├── session_manager.py      # Session lifecycle
│   ├── report_manager.py       # Report data aggregation
│   ├── report_exporter.py      # PDF generation
│   ├── graph_manager.py        # Chart generation
│   ├── snapshot_manager.py     # Incident snapshots
│   ├── dashboard.html          # Web dashboard pages
│   ├── cameras.html
│   ├── venue.html
│   ├── zones.html
│   ├── alerts.html
│   ├── analytics.html
│   ├── session.html
│   ├── admin.html
│   ├── calibration.html
│   └── reports.html
├── requirements.txt            # Python dependencies
└── README.md
```

---

## Setup

### Prerequisites

- Python 3.10+
- Webcam or IP camera (optional — works with video files too)

### Installation

```bash
# Clone the repository
git clone https://github.com/Deveshsharma5/crowdsense.git
cd crowdsense

# Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac

# Install dependencies
pip install -r requirements.txt
```

### Download YOLO Model

Download `yolo11n.pt` from [Ultralytics](https://docs.ultralytics.com/models/yolo11/) and place it in the project root.

---

## Usage

```bash
# Run CrowdSense
python app/main.py
```

### Desktop Interface (OpenCV Window)

| Key | Action |
|---|---|
| `A` | Open Admin / Setup panel |
| `C` | Open Calibration mode |
| `G` | Toggle grid overlay |
| `Q` | Quit |

### Web Dashboard

Once running, open your browser to:

```
http://localhost:5050
```

Available pages: Dashboard, Cameras, Venue, Zones, Alerts, Analytics, Sessions, Admin, Calibration, Reports.

---

## How It Works

1. **Camera Capture** — `CameraWorker` grabs frames in a background thread
2. **Person Detection** — YOLOv11 identifies people with bounding boxes and tracking IDs
3. **Perspective Transform** — 4-point calibration maps pixel coordinates to real-world positions
4. **Zone Assignment** — Each person is assigned to a physical zone in the venue grid
5. **Density Calculation** — Per-zone people count ÷ zone area = density
6. **Risk Assessment** — Zone occupancy compared against warning/critical thresholds
7. **Alert Generation** — Automated alerts with cooldown when thresholds are exceeded
8. **Data Logging** — All events logged to CSV files for analytics

---

## Configuration

- **Venue Setup** — Configure via Admin panel or web dashboard (`/venue`)
- **Camera Sources** — Add webcam (0, 1, 2) or IP camera URLs
- **Thresholds** — Set warning (default 70%) and critical (default 90%) occupancy levels
- **Grid Size** — Adjust zone grid resolution (default 5m)
- **Calibration** — Click 4 points (TL → TR → BR → BL) to map camera perspective

---

## Author

**Devesh Sharma**

---
