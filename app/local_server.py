from flask import Flask, jsonify, send_from_directory, Response
import threading
import os
import time
import cv2
from datetime import datetime

from api_endpoints import CrowdSenseAPI


# ============================================================
# APP
# ============================================================

app = Flask(__name__)

status_lock = threading.Lock()

APP_FOLDER = os.path.dirname(
    os.path.abspath(__file__)
)

# Project root = folder containing app/
PROJECT_FOLDER = os.path.dirname(
    APP_FOLDER
)


# ============================================================
# DATA FOLDERS
# ============================================================

DATA_FOLDER = os.path.join(
    PROJECT_FOLDER,
    "data"
)

GRAPH_FOLDER = os.path.join(
    DATA_FOLDER,
    "graphs"
)

SNAPSHOT_FOLDER = os.path.join(
    DATA_FOLDER,
    "snapshots"
)

REPORT_FOLDER = os.path.join(
    DATA_FOLDER,
    "reports"
)


# Make sure required folders exist
os.makedirs(DATA_FOLDER, exist_ok=True)
os.makedirs(GRAPH_FOLDER, exist_ok=True)
os.makedirs(SNAPSHOT_FOLDER, exist_ok=True)
os.makedirs(REPORT_FOLDER, exist_ok=True)


# ============================================================
# STATUS
# ============================================================

status_data = {
    "system": "READY",
    "venue": "Not configured",

    "total_people": 0,
    "capacity": 0,
    "occupancy": 0,

    "risk": "SAFE",

    "zones": [],

    "camera_source": "0",

    "test_multiplier": 1,

    "last_alert": None,

    "last_update": None
}


# ============================================================
# CAMERA MANAGER REFERENCE
# ============================================================

camera_manager_reference = None


# ============================================================
# CROWDSENSE PROCESSED FRAME PROVIDER
# ============================================================

display_frame_provider = None


def set_display_frame_provider(provider):

    global display_frame_provider

    display_frame_provider = provider


def set_camera_manager(camera_manager):

    global camera_manager_reference

    camera_manager_reference = camera_manager


# ============================================================
# STATUS UPDATE
# ============================================================

def update_status(
    venue=None,
    total_people=None,
    capacity=None,
    risk=None,
    zones=None,
    system=None,
    camera_source=None,
    test_multiplier=None,
    last_alert=None,
    last_update=None
):

    with status_lock:

        if venue is not None:
            status_data["venue"] = venue

        if total_people is not None:
            status_data["total_people"] = int(
                total_people
            )

        if capacity is not None:
            status_data["capacity"] = int(
                capacity
            )

        # ----------------------------------------------------
        # OCCUPANCY
        # ----------------------------------------------------

        if status_data["capacity"] > 0:

            status_data["occupancy"] = round(
                (
                    status_data["total_people"]
                    /
                    status_data["capacity"]
                ) * 100,
                1
            )

        else:

            status_data["occupancy"] = 0

        # ----------------------------------------------------
        # OTHER STATUS
        # ----------------------------------------------------

        if risk is not None:
            status_data["risk"] = risk

        if zones is not None:
            status_data["zones"] = zones

        if system is not None:
            status_data["system"] = system

        if camera_source is not None:
            status_data["camera_source"] = str(
                camera_source
            )

        if test_multiplier is not None:
            status_data["test_multiplier"] = int(
                test_multiplier
            )

        if last_alert is not None:
            status_data["last_alert"] = last_alert

        if last_update is not None:

            status_data["last_update"] = last_update

        else:

            status_data["last_update"] = (
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            )


# ============================================================
# STATUS API
# ============================================================

@app.route(
    "/api/status",
    methods=["GET"]
)
def api_status():

    with status_lock:

        return jsonify(
            dict(status_data)
        )


# ============================================================
# CAMERA SWITCH
# ============================================================

@app.route(
    "/api/cameras/<camera_id>/switch",
    methods=["POST"]
)
def switch_camera(camera_id):

    camera_manager = camera_manager_reference

    if camera_manager is None:

        return jsonify({
            "success": False,
            "error": "Camera manager is not available."
        }), 503

    camera_id = str(
        camera_id
    )

    try:

        result = camera_manager.switch_camera(
            camera_id
        )

        if result is None:

            return jsonify({
                "success": False,
                "error": "Camera switch failed."
            }), 500

        if not result.get(
            "success",
            False
        ):

            return jsonify(
                result
            ), 400

        camera = result.get(
            "camera"
        )

        # ----------------------------------------------------
        # Update global CrowdSense camera status
        # ----------------------------------------------------

        if isinstance(
            camera,
            dict
        ):

            update_status(
                camera_source=camera.get(
                    "source",
                    ""
                )
            )

        return jsonify(
            result
        )

    except Exception as error:

        print(
            f"Camera switch error "
            f"{camera_id}: {error}"
        )

        return jsonify({
            "success": False,
            "error": str(error)
        }), 500


# ============================================================
# STOP ACTIVE CAMERA
# ============================================================

@app.route(
    "/api/cameras/stop-active",
    methods=["POST"]
)
def stop_active_camera():

    camera_manager = camera_manager_reference

    if camera_manager is None:

        return jsonify({
            "success": False,
            "error": "Camera manager is not available."
        }), 503

    try:

        active_camera_id = (
            camera_manager.get_active_camera_id()
        )

        if active_camera_id is None:

            return jsonify({
                "success": True,
                "message": "No active camera."
            })

        result = camera_manager.stop_camera(
            active_camera_id
        )

        update_status(
            camera_source=""
        )

        return jsonify({
            "success": True,
            "camera": result
        })

    except Exception as error:

        print(
            f"Active camera stop error: {error}"
        )

        return jsonify({
            "success": False,
            "error": str(error)
        }), 500


# ============================================================
# CAMERA STREAM
# ============================================================

@app.route(
    "/api/cameras/<camera_id>/stream",
    methods=["GET"]
)
def camera_stream(camera_id):

    camera_manager = camera_manager_reference

    if camera_manager is None:

        return (
            "Camera manager is not available.",
            503
        )

    camera_id = str(
        camera_id
    )

    camera = camera_manager.get_camera(
        camera_id
    )

    if camera is None:

        return (
            "Camera not found.",
            404
        )

    # --------------------------------------------------------
    # IMPORTANT
    #
    # The browser is NOT allowed to open the camera source
    # directly.
    #
    # CrowdSense switches the CameraWorker here and the
    # browser only receives the processed MJPEG stream.
    # --------------------------------------------------------

    try:

        switch_result = (
            camera_manager.switch_camera(
                camera_id
            )
        )

        if not switch_result.get(
            "success",
            False
        ):

            return (
                switch_result.get(
                    "error",
                    "Could not start camera."
                ),
                400
            )

        switched_camera = (
            switch_result.get(
                "camera"
            )
        )

        if isinstance(
            switched_camera,
            dict
        ):

            update_status(
                camera_source=switched_camera.get(
                    "source",
                    ""
                )
            )

    except Exception as error:

        print(
            f"Camera stream switch error "
            f"{camera_id}: {error}"
        )

        return (
            f"Could not start camera: {error}",
            500
        )

    # --------------------------------------------------------
    # MJPEG GENERATOR
    # --------------------------------------------------------

    def generate():

        try:

            while True:

                frame = (
                    camera_manager.get_stream_frame(
                        camera_id
                    )
                )

                if frame is None:

                    time.sleep(0.05)
                    continue

                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    b"Cache-Control: no-cache\r\n"
                    b"Pragma: no-cache\r\n"
                    b"\r\n"
                    + frame
                    + b"\r\n"
                )

                time.sleep(0.03)

        except GeneratorExit:

            # Browser closed the stream.
            # The camera itself is NOT stopped here because
            # another CrowdSense page may still be using it.
            return

        except Exception as error:

            print(
                f"Camera stream error "
                f"{camera_id}: {error}"
            )

    return Response(
        generate(),
        mimetype=(
            "multipart/x-mixed-replace; "
            "boundary=frame"
        ),
        headers={
            "Cache-Control": "no-cache",
            "Pragma": "no-cache"
        }
    )


# ============================================================
# DASHBOARD PROCESSED CAMERA STREAM
# ============================================================

@app.route(
    "/api/dashboard/stream",
    methods=["GET"]
)
def dashboard_stream():

    def generate():

        while True:

            try:

                if display_frame_provider is None:

                    time.sleep(0.1)
                    continue

                frame = display_frame_provider()

                if frame is None:

                    time.sleep(0.05)
                    continue

                # Frame is already processed by main.py:
                # Camera → YOLO → Calibration → Zones → Risk

                success, encoded = cv2.imencode(
                    ".jpg",
                    frame,
                    [
                        int(cv2.IMWRITE_JPEG_QUALITY),
                        85
                    ]
                )

                if not success:

                    time.sleep(0.05)
                    continue

                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    b"Cache-Control: no-cache\r\n"
                    b"Pragma: no-cache\r\n"
                    b"\r\n"
                    + encoded.tobytes()
                    + b"\r\n"
                )

                time.sleep(0.03)

            except GeneratorExit:

                return

            except Exception as error:

                print(
                    f"Dashboard stream error: {error}"
                )

                time.sleep(0.1)

    return Response(
        generate(),
        mimetype=(
            "multipart/x-mixed-replace; "
            "boundary=frame"
        ),
        headers={
            "Cache-Control":
                "no-cache, no-store, must-revalidate",

            "Pragma":
                "no-cache",

            "Expires":
                "0"
        }
    )


# ============================================================
# HTML PAGE HELPER
# ============================================================

def page(filename):

    path = os.path.join(
        APP_FOLDER,
        filename
    )

    if os.path.exists(path):

        return send_from_directory(
            APP_FOLDER,
            filename
        )

    return (
        f"""
        <html>
        <body style="
            background:#111;
            color:white;
            font-family:Arial;
            padding:40px;
        ">
            <h2>CrowdSense</h2>
            <p>{filename} not found.</p>
        </body>
        </html>
        """,
        404
    )


# ============================================================
# MAIN PAGES
# ============================================================

@app.route("/")
def dashboard():

    return page(
        "dashboard.html"
    )


@app.route("/dashboard")
def dashboard_page():

    return page(
        "dashboard.html"
    )


@app.route("/cameras")
def cameras_page():

    return page(
        "cameras.html"
    )


@app.route("/venue")
def venue_page():

    return page(
        "venue.html"
    )


@app.route("/zones")
def zones_page():

    return page(
        "zones.html"
    )


@app.route("/alerts")
def alerts_page():

    return page(
        "alerts.html"
    )


@app.route("/analytics")
def analytics_page():

    return page(
        "analytics.html"
    )


@app.route("/session")
def session_page():

    return page(
        "session.html"
    )


@app.route("/admin")
def admin_page():

    return page(
        "admin.html"
    )


@app.route("/calibration")
def calibration_page():

    return page(
        "calibration.html"
    )


@app.route("/reports")
def reports_page():

    return page(
        "reports.html"
    )


# ============================================================
# GRAPH FILES
# ============================================================

@app.route(
    "/graphs/<path:filename>",
    methods=["GET"]
)
def graph_file(filename):

    if not os.path.isdir(
        GRAPH_FOLDER
    ):

        return (
            "Graph folder not found.",
            404
        )

    return send_from_directory(
        GRAPH_FOLDER,
        filename
    )


# ============================================================
# SNAPSHOT FILES
# ============================================================

@app.route(
    "/snapshots/<path:filename>",
    methods=["GET"]
)
def snapshot_file(filename):

    if not os.path.isdir(
        SNAPSHOT_FOLDER
    ):

        return (
            "Snapshot folder not found.",
            404
        )

    return send_from_directory(
        SNAPSHOT_FOLDER,
        filename
    )


# ============================================================
# REPORT FILES
# ============================================================

@app.route(
    "/reports/files/<path:filename>",
    methods=["GET"]
)
def report_file(filename):

    if not os.path.isdir(
        REPORT_FOLDER
    ):

        return (
            "Report folder not found.",
            404
        )

    file_path = os.path.join(
        REPORT_FOLDER,
        filename
    )

    if not os.path.isfile(
        file_path
    ):

        return (
            "Report file not found.",
            404
        )

    return send_from_directory(
        REPORT_FOLDER,
        filename,
        as_attachment=False
    )


# ============================================================
# DATA FILES
# ============================================================

@app.route(
    "/data/<path:filename>",
    methods=["GET"]
)
def data_file(filename):

    if not os.path.isdir(
        DATA_FOLDER
    ):

        return (
            "Data folder not found.",
            404
        )

    return send_from_directory(
        DATA_FOLDER,
        filename
    )


# ============================================================
# API REGISTRATION
# ============================================================

_api_registered = False


def register_api(
    camera_manager=None,
    alert_manager=None,
    incident_manager=None,
    snapshot_manager=None,
    session_manager=None,
    analytics_manager=None,
    graph_manager=None,
    venue_config=None,
    calibration=None,
    camera_calibration_manager=None,
    report_manager=None,
    report_exporter=None
):

    global _api_registered

    if _api_registered:
        return

    set_camera_manager(
        camera_manager
    )

    CrowdSenseAPI(
        app=app,

        camera_manager=camera_manager,

        alert_manager=alert_manager,

        incident_manager=incident_manager,

        snapshot_manager=snapshot_manager,

        session_manager=session_manager,

        analytics_manager=analytics_manager,

        graph_manager=graph_manager,

        venue_config=venue_config,

        calibration=calibration,

        camera_calibration_manager=(
            camera_calibration_manager
        ),

        report_manager=report_manager,

        report_exporter=report_exporter
    )

    _api_registered = True

    print(
        "CrowdSense API registered."
    )


# ============================================================
# SERVER
# ============================================================

def start_server(
    host="0.0.0.0",
    port=5000
):

    print()
    print("=" * 60)
    print("              CROWDSENSE LOCAL SERVER")
    print("=" * 60)
    print()

    print(
        f"Dashboard : http://localhost:{port}"
    )

    print(
        f"Network   : http://<PC-IP>:{port}"
    )

    print()

    print("Pages:")

    print(
        f"  Dashboard   http://localhost:{port}/"
    )

    print(
        f"  Cameras     http://localhost:{port}/cameras"
    )

    print(
        f"  Venue       http://localhost:{port}/venue"
    )

    print(
        f"  Zones       http://localhost:{port}/zones"
    )

    print(
        f"  Alerts      http://localhost:{port}/alerts"
    )

    print(
        f"  Analytics   http://localhost:{port}/analytics"
    )

    print(
        f"  Session     http://localhost:{port}/session"
    )

    print(
        f"  Reports     http://localhost:{port}/reports"
    )

    print(
        f"  Admin       http://localhost:{port}/admin"
    )

    print(
        f"  Calibration http://localhost:{port}/calibration"
    )

    print()

    print("API:")

    print(
        f"  Status      http://localhost:{port}/api/status"
    )

    print(
        f"  Health      http://localhost:{port}/api/health"
    )

    print(
        f"  Cameras     http://localhost:{port}/api/cameras"
    )

    print(
        f"  Alerts      http://localhost:{port}/api/alerts"
    )

    print(
        f"  Incidents   http://localhost:{port}/api/incidents"
    )

    print(
        f"  Analytics   http://localhost:{port}/api/analytics"
    )

    print(
        f"  Sessions    http://localhost:{port}/api/sessions"
    )

    print(
        f"  Reports     http://localhost:{port}/api/reports"
    )

    print(
        f"  Camera Stream http://localhost:{port}/api/cameras/<camera_id>/stream"
    )

    print(
        f"  Camera Switch http://localhost:{port}/api/cameras/<camera_id>/switch"
    )

    print(
        f"  Dashboard Stream http://localhost:{port}/api/dashboard/stream"
    )

    print(
        f"  Report Files http://localhost:{port}/reports/files/<filename>"
    )

    print()

    print("=" * 60)
    print()

    app.run(
        host=host,
        port=port,
        debug=False,
        use_reloader=False,
        threaded=True
    )