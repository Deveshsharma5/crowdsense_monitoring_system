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


def _get_active_stream_status():
    with status_lock:
        active_src = str(status_data.get("camera_source", "0")).strip()
        people = int(status_data.get("total_people", 0) or 0)
        sys_state = str(status_data.get("system", "")).strip().upper()

    frame_ready = False
    if display_frame_provider is not None:
        try:
            frame_ready = display_frame_provider() is not None
        except Exception:
            frame_ready = False

    active_cam_id = None
    if camera_manager_reference is not None:
        active_cam_id = getattr(camera_manager_reference, "active_camera_id", None)

    return {
        "camera_source": active_src,
        "total_people": people,
        "is_active": (sys_state == "ACTIVE" or frame_ready),
        "active_camera_id": active_cam_id
    }


def set_camera_manager(camera_manager):

    global camera_manager_reference

    camera_manager_reference = camera_manager

    if camera_manager is not None and hasattr(
        camera_manager,
        "set_active_stream_status_provider"
    ):
        camera_manager.set_active_stream_status_provider(
            _get_active_stream_status
        )


camera_switch_callback = None


def set_camera_switch_callback(callback):

    global camera_switch_callback

    camera_switch_callback = callback


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
@app.route(
    "/api/state",
    methods=["GET"]
)
def api_state():
    with status_lock:
        return jsonify(dict(status_data))

@app.route(
    "/api/zones",
    methods=["GET"]
)
def api_zones():
    with status_lock:
        zones = status_data.get("zones", [])
        if not zones and _api_instance is not None and getattr(_api_instance, "zone_manager", None) is not None:
            zones = _api_instance.zone_manager.get_zones()
        elif not zones:
            try:
                from zones import PhysicalZoneManager
                from venue import VenueConfig
                _vc = VenueConfig.load()
                zm = PhysicalZoneManager(_vc)
                zones = zm.get_zones()
            except Exception:
                pass
        return jsonify(zones if zones is not None else [])



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

            if camera_switch_callback is not None:
                try:
                    camera_switch_callback(camera)
                except Exception as cb_err:
                    print(f"Camera switch callback error: {cb_err}")

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
    # MJPEG GENERATOR (with cached JPEG and active fallback)
    # --------------------------------------------------------

    def generate():
        last_cam_frame_bytes = None

        try:

            while True:

                frame_bytes = None

                # 1. Try camera_manager worker frame
                if camera_manager is not None:
                    try:
                        frame_bytes = camera_manager.get_stream_frame(
                            camera_id
                        )
                    except Exception:
                        frame_bytes = None

                # 2. If camera_manager didn't yield a frame, or if this camera
                # matches the active camera source, reuse the processed display frame.
                if frame_bytes is None:
                    cam_src = str(camera.get("source", "0")).strip()
                    with status_lock:
                        active_src = str(status_data.get("camera_source", "0")).strip()
                    active_cam_id = getattr(camera_manager, "active_camera_id", None) if camera_manager else None

                    is_active_cam = (
                        cam_src == active_src
                        or (cam_src.isdigit() and active_src.isdigit() and int(cam_src) == int(active_src))
                        or (active_cam_id and camera_id == str(active_cam_id))
                    )
                    if is_active_cam:
                        frame_bytes = get_encoded_display_frame()

                if frame_bytes is None:
                    time.sleep(0.03)
                    continue

                if frame_bytes is last_cam_frame_bytes:
                    time.sleep(0.012)
                    continue

                last_cam_frame_bytes = frame_bytes

                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    b"Cache-Control: no-cache\r\n"
                    b"Pragma: no-cache\r\n"
                    b"\r\n"
                    + frame_bytes
                    + b"\r\n"
                )

                time.sleep(0.01)

        except GeneratorExit:
            return

        except Exception as error:

            print(
                f"Camera stream error "
                f"{camera_id}: {error}"
            )
            time.sleep(0.05)

    return Response(
        generate(),
        mimetype=(
            "multipart/x-mixed-replace; "
            "boundary=frame"
        ),
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Accel-Buffering": "no"
        }
    )


# ============================================================
# CACHED PROCESSED FRAME ENCODER
# ============================================================

_cached_encoded_display_frame = None
_cached_frame_obj_id = None
_cached_encode_lock = threading.Lock()


def get_encoded_display_frame():

    global _cached_encoded_display_frame
    global _cached_frame_obj_id

    if display_frame_provider is None:
        return None

    try:
        frame = display_frame_provider()
    except Exception:
        return None

    if frame is None:
        return None

    with _cached_encode_lock:

        fid = id(frame)

        if (
            _cached_frame_obj_id == fid
            and _cached_encoded_display_frame is not None
        ):
            return _cached_encoded_display_frame

        try:
            success, encoded = cv2.imencode(
                ".jpg",
                frame,
                [
                    int(cv2.IMWRITE_JPEG_QUALITY),
                    75
                ]
            )

            if success:
                _cached_encoded_display_frame = encoded.tobytes()
                _cached_frame_obj_id = fid
                return _cached_encoded_display_frame

        except Exception as error:
            print(f"JPEG encode error: {error}")

        return None


# ============================================================
# DASHBOARD PROCESSED CAMERA STREAM
# ============================================================

@app.route(
    "/api/dashboard/stream",
    methods=["GET"]
)
def dashboard_stream():

    def generate():
        last_frame_bytes = None

        while True:

            try:

                frame_bytes = get_encoded_display_frame()

                if frame_bytes is None:
                    time.sleep(0.03)
                    continue

                if frame_bytes is last_frame_bytes:
                    time.sleep(0.012)
                    continue

                last_frame_bytes = frame_bytes

                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    b"Cache-Control: no-cache\r\n"
                    b"Pragma: no-cache\r\n"
                    b"\r\n"
                    + frame_bytes
                    + b"\r\n"
                )

                time.sleep(0.01)

            except GeneratorExit:
                return

            except Exception as error:

                print(
                    f"Dashboard stream error: {error}"
                )

                time.sleep(0.05)

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
# STATIC FILES
# ============================================================

@app.route(
    "/static/<path:filename>",
    methods=["GET"]
)
def static_file(filename):

    static_dir = os.path.join(
        APP_FOLDER,
        "static"
    )

    if not os.path.isdir(static_dir):
        return ("Static folder not found.", 404)

    return send_from_directory(
        static_dir,
        filename
    )


# ============================================================
# API REGISTRATION
# ============================================================

_api_registered = False


_api_instance = None

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
    report_exporter=None,
    zone_manager=None
):

    global _api_registered, _api_instance

    if venue_config is None and (_api_instance is None or _api_instance.venue_config is None):
        try:
            from venue import VenueConfig
            venue_config = VenueConfig.load()
        except Exception:
            pass

    if camera_manager is None and (_api_instance is None or _api_instance.camera_manager is None):
        try:
            from camera_manager import CameraManager
            camera_manager = CameraManager()
        except Exception:
            pass

    if alert_manager is None and (_api_instance is None or _api_instance.alert_manager is None):
        try:
            from alert_manager import AlertManager
            alert_manager = AlertManager()
        except Exception:
            pass

    if incident_manager is None and (_api_instance is None or _api_instance.incident_manager is None):
        try:
            from incident_manager import IncidentManager
            incident_manager = IncidentManager()
        except Exception:
            pass

    if session_manager is None and (_api_instance is None or _api_instance.session_manager is None):
        try:
            from session_manager import SessionManager
            session_manager = SessionManager()
        except Exception:
            pass

    if analytics_manager is None and (_api_instance is None or _api_instance.analytics_manager is None):
        try:
            from analytics_manager import AnalyticsManager
            analytics_manager = AnalyticsManager()
        except Exception:
            pass

    if report_manager is None and (_api_instance is None or _api_instance.report_manager is None):
        try:
            from report_manager import ReportManager
            report_manager = ReportManager()
        except Exception:
            pass

    if report_exporter is None and (_api_instance is None or _api_instance.report_exporter is None):
        try:
            from report_exporter import ReportExporter
            report_exporter = ReportExporter()
        except Exception:
            pass

    if camera_manager is not None:
        set_camera_manager(camera_manager)

    if _api_instance is not None:
        _api_instance.update_managers(
            camera_manager=camera_manager,
            alert_manager=alert_manager,
            incident_manager=incident_manager,
            snapshot_manager=snapshot_manager,
            session_manager=session_manager,
            analytics_manager=analytics_manager,
            graph_manager=graph_manager,
            venue_config=venue_config,
            calibration=calibration,
            camera_calibration_manager=camera_calibration_manager,
            report_manager=report_manager,
            report_exporter=report_exporter,
            zone_manager=zone_manager
        )
        return

    _api_instance = CrowdSenseAPI(
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
        camera_calibration_manager=camera_calibration_manager,
        report_manager=report_manager,
        report_exporter=report_exporter,
        zone_manager=zone_manager
    )

    _api_registered = True
    print("CrowdSense API registered.")


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
# Auto-register API endpoints so server routes are immediately ready
try:
    register_api()
except Exception as _e:
    print(f"Initial API auto-register deferred: {_e}")
