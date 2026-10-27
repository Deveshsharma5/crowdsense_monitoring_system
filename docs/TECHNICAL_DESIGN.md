# CrowdSense — Technical Design Document

This document provides a comprehensive technical specification of the **CrowdSense** real-time computer vision crowd safety platform, detailing the architectural patterns, component interactions, mathematical formulations, data pipelines, and operational deployment models implemented in the codebase.

---

## Table of Contents

1. [System Overview & Goals](#1-system-overview--goals)
2. [End-to-End System Architecture](#2-end-to-end-system-architecture)
3. [Component Breakdown & Responsibilities](#3-component-breakdown--responsibilities)
4. [Data Flow Pipeline](#4-data-flow-pipeline)
   - [Phase 1: Video Ingestion & Person Detection](#phase-1-video-ingestion--person-detection)
   - [Phase 2: Planar Homography Perspective Transformation](#phase-2-planar-homography-perspective-transformation)
   - [Phase 3: Spatial Zoning & Density Calculation](#phase-3-spatial-zoning--density-calculation)
   - [Phase 4: Risk Evaluation & Multi-Channel Alerting](#phase-4-risk-evaluation--multi-channel-alerting)
   - [Phase 5: Time-Series Logging & Analytics Engine](#phase-5-time-series-logging--analytics-engine)
   - [Phase 6: Compliance PDF Safety Reporting](#phase-6-compliance-pdf-safety-reporting)
5. [User Interface & REST API Architecture](#5-user-interface--rest-api-architecture)
6. [Deployment & Infrastructure Topology](#6-deployment--infrastructure-topology)
7. [Current Limitations & Future Roadmap](#7-current-limitations--future-roadmap)

---

## 1. System Overview & Goals

CrowdSense is an edge-native physical security and crowd monitoring platform developed to prevent dangerous overcrowding, localized bottlenecks, and crush/stampede disasters at large gathering venues (stadiums, transit hubs, concert halls, and public festivals).

### Primary Engineering Objectives
- **Sub-Second Edge Latency**: Process camera frames and evaluate risk at 15–30 FPS on standard edge hardware.
- **Metric Ground Truth**: Convert arbitrary camera vantage angles into true real-world coordinates ($X, Y$ in meters) via planar homography.
- **Micro-Zoning**: Subdivide complex venues into discrete physical spatial zones with independently configurable safety thresholds.
- **Fail-Safe Multi-Channel Dispatch**: Asynchronous emergency notification queue (Telegram Bot API, local audio buzzer, and visual UI alerts) with strict state deduplication and cooldown rate limiting.
- **Forensic Compliance & Auditing**: Automated frame snapshot recording during incident events and 15-section PDF safety audit generation.

---

## 2. End-to-End System Architecture

```mermaid
flowchart TD
    subgraph VideoIngestion [1. Video Ingestion Subsystem]
        A[Camera Stream / RTSP / Video] --> B[stream_capture.py\nVideoStreamCapture]
        B -->|Thread-Safe Latest Frame| C[camera_worker.py\nCameraWorker]
        C -->|YOLOv11 Inference| D[Bounding Box & Bottom-Center Foot Detection]
    end

    subgraph SpatialTransformation [2. Perspective & Zoning Subsystem]
        D -->|Pixel Coordinates u, v| E[calibration.py\nPlanar Homography Matrix H]
        E -->|Real-World Metric Coordinates X, Y| F[zones.py\nPhysicalZoneManager]
        F --> G[Dynamic Grid Zone Allocation\nArea, Capacity, People, Density, Occupancy]
    end

    subgraph SafetyAndAlerting [3. Risk Assessment & Dispatch Engine]
        G --> H[safety_manager.py\nSafetyManager]
        H -->|Risk State: SAFE / WARNING / CRITICAL| I[alert_manager.py\nAlertManager]
        H -->|Edge Trigger: Enter CRITICAL| J[telegram_service.py\nTelegramNotifier Daemon]
        H -->|Incident Snapshot Store| K[incident_manager.py\nIncidentManager]
    end

    subgraph AnalyticsAndReporting [4. Historical Analytics & Compliance]
        G --> L[data_logger.py\nCSV Time-Series Logger]
        L --> M[analytics_manager.py\nAnalytics Engine]
        M --> N[report_manager.py\nReport Aggregator]
        N --> O[report_exporter.py\n15-Section ReportLab PDF Exporter]
    end

    subgraph PresentationTier [5. Dual Presentation Tier]
        P[local_server.py\nFlask Application :5000] --> Q[api_endpoints.py\nCrowdSenseAPI (40+ Endpoints)]
        Q --> R[10-Page Web Dashboard\nHTML5 / Vanilla JS / CSS3]
        S[main.py\nOpenCV Desktop Interface] --> C
        S --> H
    end
```

---

## 3. Component Breakdown & Responsibilities

| Subsystem File | Core Classes | Primary Responsibilities |
| :--- | :--- | :--- |
| `app/stream_capture.py` | `VideoStreamCapture` | Dedicated daemon thread continuously capturing video frames into a single-slot buffer, eliminating TCP/RTSP packet buffering lag. |
| `app/camera_worker.py` | `CameraWorker` | Executes Ultralytics YOLOv11 person detection (`class 0`), extracts bottom-center centroid coordinates of each detected person, and overlays tracking indicators. |
| `app/calibration.py` | `CameraCalibration` | Calculates and persists the $3 \times 3$ perspective transformation matrix ($H$) from 4 user-selected image points to known real-world venue metric bounds. |
| `app/zones.py` | `PhysicalZoneManager` | Discretizes rectangular or circular venue spaces into metric grid cells. Tracks dynamic person count, computes physical density ($\text{people}/m^2$), and evaluates per-zone occupancy against custom thresholds. |
| `app/venue.py` | `VenueConfig` | Serializes and validates venue dimensions (length, width, diameter, shape), maximum rated capacities, and default warning/critical thresholds. |
| `app/safety_manager.py` | `SafetyManager` | Evaluates multi-zone risks into global venue states (`SAFE`, `WARNING`, `CRITICAL`), preventing spurious alert transitions. |
| `app/telegram_service.py` | `TelegramNotifier` | Thread-safe, asynchronous emergency messaging queue delivering structured Markdown incident notifications with configurable cooldown (e.g., 300s) and state-transition deduplication. |
| `app/alert_manager.py` | `AlertManager` | Manages active audio frequencies, alert cooldown timers, and transient UI notifications. |
| `app/incident_manager.py` | `IncidentManager` | Captures high-resolution camera snapshots upon CRITICAL threshold breaches and records structured incident logs. |
| `app/data_logger.py` | `DataLogger` | Writes non-blocking, append-only CSV time-series records (`timestamp`, `total_people`, `zone_id`, `zone_people`, `density`, `risk`). |
| `app/analytics_manager.py` | `AnalyticsManager` | Parses historical CSV telemetry to compute statistical aggregates: peak headcounts, average densities, zone distribution matrices, and risk frequency. |
| `app/report_manager.py` | `ReportManager` | Combines venue configuration, session metadata, incident histories, and analytics metrics into structured document payloads. |
| `app/report_exporter.py` | `ReportExporter` | Generates comprehensive 15-section PDF event safety reports with embedded Matplotlib trend charts and compliance scorecards using ReportLab. |
| `app/session_manager.py` | `SessionManager` | Manages lifecycle, timer, and duration states for official crowd monitoring operational sessions. |
| `app/local_server.py` | Flask App | Serves static assets, HTML5 management views, and streams live annotated MJPEG video over HTTP. |
| `app/api_endpoints.py` | `CrowdSenseAPI` | Exposes 40+ RESTful API endpoints covering venue configuration, per-zone threshold updates, calibration coordinates, alerts, and system health. |
| `app/main.py` | Desktop GUI | Standalone OpenCV runtime providing an interactive Heads-Up Display (HUD), live zone matrices, and keyboard shortcuts. |

---

## 4. Data Flow Pipeline

### Phase 1: Video Ingestion & Person Detection
1. The video source (webcam device ID, RTSP IP camera URI, or offline video file) is opened by `VideoStreamCapture`.
2. A dedicated capture thread reads incoming frames. Only the latest complete frame is retained, discarding stale frames to ensure zero processing latency.
3. `CameraWorker` receives the frame and passes it to the `ultralytics.YOLO` model (`yolo11n.pt`).
4. Detections are filtered for `class == 0` (person) with a confidence threshold $\ge 0.35$.
5. For each detected bounding box $[x_1, y_1, x_2, y_2]$, the grounding coordinate (bottom-center) is computed:
   $$u = \frac{x_1 + x_2}{2}, \quad v = y_2$$
   *Grounding coordinates represent where the person stands on the physical floor, eliminating perspective distortion caused by head height.*

### Phase 2: Planar Homography Perspective Transformation
1. During venue setup, an operator marks 4 reference corners on the camera feed corresponding to the four known physical corners of the venue floor:
   $$(0, 0), \quad (L, 0), \quad (L, W), \quad (0, W)$$
2. OpenCV's `cv2.getPerspectiveTransform` computes the $3 \times 3$ Homography matrix $H$:
   $$\begin{bmatrix} X' \\ Y' \\ Z' \end{bmatrix} = H \begin{bmatrix} u \\ v \\ 1 \end{bmatrix}$$
3. Ground metric floor coordinates are recovered by normalization:
   $$X = \frac{X'}{Z'}, \quad Y = \frac{Y'}{Z'}$$

### Phase 3: Spatial Zoning & Density Calculation
1. `PhysicalZoneManager` discretizes the venue dimensions ($L \times W$) into regular grid squares based on `grid_size` (default: 5.0m):
   $$\text{Cols} = \lceil L / \text{grid} \rceil, \quad \text{Rows} = \lceil W / \text{grid} \rceil$$
2. For each detected person $(X, Y)$, the system clamps coordinates to venue boundaries and resolves the corresponding grid cell:
   $$\text{Col} = \lfloor X / \text{grid} \rfloor, \quad \text{Row} = \lfloor Y / \text{grid} \rfloor \implies \text{Zone ID: } \text{chr}(65 + \text{Row}) + (\text{Col} + 1)$$
3. Each zone computes:
   - **Zone Area ($m^2$)**: $A_z = \text{width} \times \text{height}$
   - **Zone Capacity**: Proportional share of venue capacity:
     $$C_z = \text{Venue Capacity} \times \left( \frac{A_z}{\text{Venue Area}} \right)$$
   - **Physical Density**:
     $$D_z = \frac{\text{People in Zone}}{A_z} \quad (\text{people}/m^2)$$
   - **Occupancy Percentage**:
     $$\text{Occ}_z = \left( \frac{\text{People in Zone}}{C_z} \right) \times 100$$

### Phase 4: Risk Evaluation & Multi-Channel Alerting
1. The risk state of each zone is evaluated against its thresholds:
   - If $\text{People} < 2$: State is forced to `SAFE` (prevents false alarms on isolated individuals).
   - If $\text{Occ}_z \ge \text{Critical Threshold}$ (default 90%, or zone custom): State $\to$ `CRITICAL`.
   - Else if $\text{Occ}_z \ge \text{Warning Threshold}$ (default 70%, or zone custom): State $\to$ `WARNING`.
   - Else: State $\to$ `SAFE`.
2. **State Transition Logic**:
   - Only a state transition into `CRITICAL` triggers the emergency dispatch pipeline. Continuous presence in `CRITICAL` does not spam alerts.
   - If a zone recovers to `SAFE` and subsequently re-breaches `CRITICAL`, a new alert is generated.
3. **Telegram Emergency Bot**:
   - Runs in a background worker thread with a thread-safe `queue.Queue`.
   - Enforces a per-zone cooldown period (default: 300 seconds).
   - Sanitizes output so that the Telegram bot token is never exposed in logs or API responses.
4. **Incident Capture**:
   - When entering `CRITICAL`, `IncidentManager` saves a full-resolution JPEG frame snapshot to `data/snapshots/` and appends an incident entry to `data/incidents/incidents.json`.

### Phase 5: Time-Series Logging & Analytics Engine
1. Every second, `DataLogger` appends an entry for each active zone to `data/logs/crowd_log.csv`.
2. `AnalyticsManager` processes these historical logs on demand to derive:
   - Peak concurrent crowd count and timestamp of occurrence.
   - Global and per-zone peak and average densities ($\text{people}/m^2$).
   - Most crowded zone identifier and duration spent in `WARNING`/`CRITICAL` states.
   - Total incident counts and session duration statistics.

### Phase 6: Compliance PDF Safety Reporting
1. `ReportExporter` aggregates data from `ReportManager` into a formal 15-section PDF document.
2. Generates dynamic vector charts using `matplotlib` (rendered to memory buffers):
   - Real-time occupancy timeline chart with warning/critical threshold lines.
   - Per-zone density comparison bar charts.
3. Formats document tables, safety audit scorecards, and incident tables using `reportlab.platypus` flowables (`Paragraph`, `Table`, `Image`, `Spacer`).

---

## 5. User Interface & REST API Architecture

### Web Interface Views (10 Modules)
- `/dashboard`: Live MJPEG stream with detection bounding boxes, active zone telemetry cards, global risk badge, and quick action buttons.
- `/venue`: Venue dimension editor (length, width, diameter, capacity, base thresholds).
- `/zones`: Individual zone threshold overrides (custom Min warning and Max critical percentages).
- `/calibration`: Interactive canvas for 4-point perspective corner marking.
- `/cameras`: Multi-input camera manager (switch between webcam, IP RTSP streams, and local video files).
- `/alerts`: Live safety state transition audit log.
- `/incidents`: Review captured critical incident events and visual JPEG snapshots.
- `/analytics`: Time-series crowd density graphs and zone breakdown analytics.
- `/reports`: Interactive PDF report generation and download portal.
- `/session`: Monitoring session timer and incident dispatch history.

### REST API Endpoints Overview
- **Streaming**: `GET /video_feed`
- **System**: `GET /api/system/status`
- **Venue**: `GET /api/venue`, `POST /api/venue`
- **Zoning**: `GET /api/zones`, `GET /api/zones/<id>/thresholds`, `POST /api/zones/<id>/thresholds`
- **Calibration**: `GET /api/calibration`, `POST /api/calibration`
- **Alerts**: `GET /api/alerts`, `POST /api/alerts/clear`
- **Incidents**: `GET /api/incidents`, `GET /api/snapshots/<filename>`
- **Telegram**: `GET /api/telegram/status`, `POST /api/telegram/test`
- **Analytics**: `GET /api/analytics`
- **Reporting**: `POST /api/reports/generate`, `GET /api/reports/download/<filename>`

---

## 6. Deployment & Infrastructure Topology

### Hardware Prerequisites
- **Processor**: Intel Core i5 / AMD Ryzen 5 or higher (minimum 4 cores).
- **RAM**: 8 GB minimum (16 GB recommended for high-resolution video streams).
- **GPU (Optional)**: NVIDIA GPU with CUDA support for accelerated YOLOv11 inference (automatically falls back to CPU via PyTorch).
- **Camera**: Standard USB webcam, RTSP-capable IP camera (1080p @ 15–30 FPS recommended).

### Software Topology
```text
[ Physical Camera (RTSP / USB) ]
               │
               ▼
[ Edge Host / Local Workstation ]
  ├── Python 3.10+ Runtime
  │     ├── Ultralytics YOLOv11n (Inference Engine)
  │     ├── OpenCV (Stream & Perspective Transformation)
  │     ├── Flask (REST API & Web UI Server on Port 5000)
  │     └── ReportLab + Matplotlib (PDF Engine)
  ├── Local File Store
  │     ├── data/logs/crowd_log.csv (Time-Series)
  │     ├── data/snapshots/ (Incident Images)
  │     └── data/reports/ (Generated Audit PDFs)
  └── Outbound Network (HTTPS)
        └── api.telegram.org (Emergency Bot Dispatch)
```

---

## 7. Current Limitations & Future Roadmap

### Current Limitations
1. **Planar Homography Constraint**: Assumes a predominantly flat ground surface. Severe elevation changes (e.g., stadium bleachers or multi-tiered amphitheaters) require multi-plane homography.
2. **Extreme Occlusion**: Under ultra-dense crush conditions ($> 6\text{ people}/m^2$), individual full-body bounding boxes experience high occlusion; head-only detection models may offer higher recall in extreme densities.
3. **Single Active Detection Stream**: While multiple camera sources can be configured and switched in `/cameras`, the core YOLO inference loop processes one active primary feed at a time.

### Future Roadmap
- **Multi-Camera Fused Tracking**: Implement 3D spatial re-identification across overlapping camera fields of view to cover massive convention centers with continuous tracking.
- **Predictive Bottleneck AI**: Integrate recurrent/LSTM flow forecasting to predict choke point stampedes 3–5 minutes before critical thresholds are reached.
- **Direct Public Address (PA) Integration**: Connect automated SIP/VoIP or automated audio hardware trigger to broadcast localized evacuation instructions automatically upon critical alerts.
