# CrowdSense — Sample Data & Benchmark Guide

This directory provides non-sensitive sample configurations, synthetic time-series telemetry, and instructions for safely evaluating the CrowdSense platform offline without requiring a live physical deployment.

---

## Directory Contents

| File | Type | Description |
| :--- | :--- | :--- |
| `sample_venue_config.json` | JSON | A realistic 30m × 15m exhibition hall venue configuration including custom bottleneck thresholds and special entrance/exit coordinates. |
| `sample_camera_calibration.json` | JSON | A sample 4-point planar homography calibration matrix mapping a 1280×720 camera stream to 2D real-world floor coordinates. |
| `sample_crowd_log.csv` | CSV | Synthetic time-series log illustrating multi-zone crowd flow across `SAFE`, `WARNING`, and `CRITICAL` state transitions. |

---

## 1. Using the Sample Configurations

### Loading Sample Venue Configuration
To evaluate the analytics and zoning engine with the provided sample venue:
```bash
# Copy sample configuration into active data path
mkdir -p data
cp sample_data/sample_venue_config.json data/venue_config.json
```
Once copied, start the web interface (`python app/local_server.py`) and navigate to `http://localhost:5000/venue` to view the 30m × 15m grid layout and custom zone thresholds.

### Loading Sample Calibration Matrix
To test homography coordinate projection without performing manual 4-point clicks:
```bash
cp sample_data/sample_camera_calibration.json data/camera_calibration.json
```

### Loading Sample Time-Series Telemetry
To test historical density analytics, peak calculations, and PDF safety report generation:
```bash
mkdir -p data/logs
cp sample_data/sample_crowd_log.csv data/logs/crowd_log.csv
```
Once copied, navigate to `http://localhost:5000/reports` or run `python tests/test_zone_thresholds.py` to compile an instant 15-section PDF safety audit based on this dataset.

---

## 2. Recommended Public Benchmark Video Datasets

For testing live video ingestion and YOLO person detection without capturing private footage, we recommend the following openly licensed public research datasets:

1. **PETS 2009 Benchmark (Performance Evaluation of Tracking and Surveillance)**:
   - **Focus**: Crowd counting, density estimation, and flow analysis in public concourses.
   - **Source**: [PETS 2009 Benchmark Dataset](https://homepages.inf.ed.ac.uk/rbf/PETS2009/)
   - **Recommended Sequence**: `S1.L1` (Crowd Flow) or `S2.L1` (Crowd Density).
   - **Usage**: Download the image sequence / AVI video and specify its file path when adding a camera in `http://localhost:5000/cameras`.

2. **Town Centre Dataset (Oxford Active Vision Group)**:
   - **Focus**: Street-level pedestrian monitoring from an elevated CCTV angle.
   - **Source**: [Oxford Town Centre Dataset](https://www.robots.ox.ac.uk/~lav/Research/Projects/2009bbenfold_headpose/project.html)
   - **Resolution**: 1920×1080 (HD), ideal for testing 4-point homography calibration and grid zoning.

3. **MOTChallenge (Multiple Object Tracking)**:
   - **Focus**: Dense pedestrian tracking in indoor/outdoor shopping and transit hubs.
   - **Source**: [MOTChallenge.net](https://motchallenge.net/) (MOT16 / MOT20 sequences).

---

## 3. Privacy, Ethics & Data Governance

CrowdSense is strictly designed under a **Privacy-by-Design** architecture:

- **No Facial Recognition**: The system detects and tracks bounding box centroids only (`class 0: person` in COCO). No facial features, biometrics, or demographic data are ever extracted or processed.
- **Edge Inference**: Inference and coordinate homography run entirely locally on-premise. No raw video frames are uploaded to any third-party cloud.
- **Synthetic Test Policy**: This repository contains zero private facial images or identifiable surveillance data. All sample logs provided in this folder are completely synthetic and mathematically generated.
- **Compliance**: The data processing model complies with GDPR / CCPA guidelines for anonymous aggregate crowd counting.

