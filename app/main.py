import cv2
import numpy as np
import os
import time
import json
import threading
from datetime import datetime

from ultralytics import YOLO

from venue import VenueConfig
from zones import PhysicalZoneManager
from calibration import CameraCalibration
from floorplan import FloorPlan

from data_logger import CrowdLogger
from graph_manager import CrowdGraphManager
from alert_manager import AlertManager
from snapshot_manager import SnapshotManager
from system_state import SystemState

# NEW BACKEND MANAGERS
from camera_manager import CameraManager
from incident_manager import IncidentManager
from session_manager import SessionManager
from analytics_manager import AnalyticsManager

# NEW CROWDSENSE BACKEND MANAGERS
from camera_calibration_manager import CameraCalibrationManager
from multi_camera_manager import MultiCameraManager
from camera_zone_mapper import CameraZoneMapper
from safety_manager import SafetyManager
from report_manager import ReportManager
from report_exporter import ReportExporter

from local_server import (
    start_server,
    update_status,
    register_api,
    set_display_frame_provider
)


# ============================================================
# WINDOWS BEEP
# ============================================================

try:
    import winsound
except ImportError:
    winsound = None


# ============================================================
# CLIPBOARD
# ============================================================

try:
    import pyperclip
except ImportError:
    pyperclip = None


# ============================================================
# CROWDSENSE
# ============================================================

WINDOW_NAME = "CrowdSense"

CAMERA_WIDTH = 960
CAMERA_HEIGHT = 540

HEADER_HEIGHT = 105

MODEL_PATH = "yolo11n.pt"

DEFAULT_CAMERA_SOURCE = "0"

DEFAULT_TEST_MULTIPLIER = 1

GRAPH_UPDATE_SECONDS = 60

LOG_UPDATE_SECONDS = 5

ALARM_COOLDOWN_SECONDS = 8


# ============================================================
# COLORS
# ============================================================

BLACK = (8, 8, 10)
DARK = (18, 18, 22)
FIELD_DARK = (32, 32, 38)

GREEN = (35, 215, 75)
RED = (35, 35, 220)
YELLOW = (0, 165, 255)
WHITE = (255, 255, 255)
GRAY = (180, 183, 190)
DARK_GRAY = (95, 98, 108)

FONT = cv2.FONT_HERSHEY_SIMPLEX


# ============================================================
# MODES
# ============================================================

MODE_SETUP = "setup"
MODE_MONITOR = "monitor"
MODE_ADMIN = "admin"
MODE_CALIBRATION = "calibration"

current_mode = MODE_SETUP


# ============================================================
# GLOBAL COMPONENTS
# ============================================================

venue = VenueConfig.load()

if venue is None:

    venue = VenueConfig(
        name="Default Venue",
        shape="rectangle",
        length=20,
        width=10,
        diameter=0,
        capacity=100,
        warning_threshold=70,
        critical_threshold=90,
        grid_size=5,
        zones=[],
        special_areas=[],
        floorplan=None
    )

    venue.save()


zone_manager = PhysicalZoneManager(
    venue
)

calibration = CameraCalibration()

floorplan = FloorPlan()

logger = CrowdLogger()

graph_manager = CrowdGraphManager()

alert_manager = AlertManager(
    cooldown_seconds=ALARM_COOLDOWN_SECONDS
)

snapshot_manager = SnapshotManager(
    cooldown_seconds=ALARM_COOLDOWN_SECONDS
)

system_state = SystemState()


# ============================================================
# NEW BACKEND MANAGERS
# ============================================================

camera_manager = CameraManager()

incident_manager = IncidentManager()

session_manager = SessionManager()

analytics_manager = AnalyticsManager(
    alert_manager=alert_manager,
    incident_manager=incident_manager,
    session_manager=session_manager
)

# ============================================================
# ADDITIONAL CROWDSENSE MANAGERS
# ============================================================

camera_calibration_manager = CameraCalibrationManager()

multi_camera_manager = MultiCameraManager(
    camera_manager=camera_manager
)

camera_zone_mapper = CameraZoneMapper(
    calibration_manager=camera_calibration_manager,
    zone_manager=zone_manager
)

safety_manager = SafetyManager(
    alert_manager=alert_manager,
    incident_manager=incident_manager,
    snapshot_manager=snapshot_manager
)

report_manager = ReportManager(
    analytics_manager=analytics_manager,
    alert_manager=alert_manager,
    incident_manager=incident_manager,
    session_manager=session_manager,
    venue_config=venue
)

report_exporter = ReportExporter(
    report_manager=report_manager,
    graph_manager=graph_manager
)


# ============================================================
# CAMERA / AI
# ============================================================

cap = None

model = None

camera_source = DEFAULT_CAMERA_SOURCE

SAVED_CAMERAS_FILE = "data/saved_cameras.json"


def load_saved_cameras():

    os.makedirs("data", exist_ok=True)

    if not os.path.exists(SAVED_CAMERAS_FILE):
        return []

    try:

        with open(
            SAVED_CAMERAS_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(file)

        if isinstance(data, list):
            return data

    except Exception as error:

        print(
            f"Saved camera load error: {error}"
        )

    return []


def save_saved_cameras(cameras):

    os.makedirs("data", exist_ok=True)

    try:

        with open(
            SAVED_CAMERAS_FILE,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                cameras,
                file,
                indent=4
            )

        return True

    except Exception as error:

        print(
            f"Saved camera save error: {error}"
        )

        return False


saved_cameras = load_saved_cameras()


# ============================================================
# LIVE FRAME
# ============================================================

latest_display_frame = None


# ============================================================
# GRID
# ============================================================

grid_mode = True


# ============================================================
# ADMIN
# ============================================================

active_field = None

shape_dropdown_open = False

admin_fields = {}


# ============================================================
# RECTANGLES
# ============================================================

admin_button_rect = None
save_start_button_rect = None
save_button_rect = None
cancel_button_rect = None
shape_rect = None
field_rects = {}
floorplan_button_rect = None
calibration_button_rect = None
test_alert_button_rect = None

# Saved camera buttons
save_camera_button_rect = None
saved_camera_select_rects = []
saved_camera_delete_rects = []


# ============================================================
# FLOOR PLAN
# ============================================================

floorplan_message = "NO FLOOR PLAN"

pending_floorplan_path = None

if venue.floorplan:

    try:

        if floorplan.load_image(
            venue.floorplan
        ):

            floorplan.set_dimensions(
                venue.length,
                venue.width
            )

            floorplan_message = "FLOOR PLAN LOADED"

    except Exception:
        pass


# ============================================================
# CALIBRATION
# ============================================================

calibration_points = []

calibration_message = (
    "CLICK 4 POINTS: TL → TR → BR → BL"
)


# ============================================================
# TIMERS
# ============================================================

last_log_time = 0
last_graph_time = 0
last_alarm_time = 0


# ============================================================
# SESSION STATE
# ============================================================

session_started = False

last_session_risk = "SAFE"


# ============================================================
# ALARM STATE
# ============================================================

alarm_active = False


# ============================================================
# TEXT
# ============================================================

def text(
    frame,
    value,
    position,
    size=0.4,
    color=WHITE,
    thickness=1
):

    cv2.putText(
        frame,
        str(value),
        position,
        FONT,
        size,
        color,
        thickness,
        cv2.LINE_AA
    )


# ============================================================
# PANEL
# ============================================================

def panel(
    frame,
    x1,
    y1,
    x2,
    y2,
    color=DARK,
    border=None,
    thickness=1
):

    cv2.rectangle(
        frame,
        (x1, y1),
        (x2, y2),
        color,
        -1
    )

    if border is not None:

        cv2.rectangle(
            frame,
            (x1, y1),
            (x2, y2),
            border,
            thickness
        )


# ============================================================
# BUTTON
# ============================================================

def button(
    frame,
    label,
    rect,
    color=GREEN,
    font_scale=0.36
):

    x1, y1, x2, y2 = rect

    cv2.rectangle(
        frame,
        (x1, y1),
        (x2, y2),
        FIELD_DARK,
        -1
    )

    cv2.rectangle(
        frame,
        (x1, y1),
        (x2, y2),
        color,
        2,
        cv2.LINE_AA
    )

    corner = 6

    cv2.line(
        frame,
        (x1, y1),
        (x1 + corner, y1),
        WHITE,
        1,
        cv2.LINE_AA
    )

    cv2.line(
        frame,
        (x1, y1),
        (x1, y1 + corner),
        WHITE,
        1,
        cv2.LINE_AA
    )

    size = cv2.getTextSize(
        label,
        FONT,
        font_scale,
        2
    )[0]

    tx = x1 + (
        (x2 - x1 - size[0]) // 2
    )

    ty = y1 + (
        (y2 - y1 + size[1]) // 2
    )

    text(
        frame,
        label,
        (tx, ty),
        font_scale,
        color,
        2
    )


# ============================================================
# ADMIN FIELDS
# ============================================================

def load_admin_fields():

    return {

        "name": str(
            getattr(
                venue,
                "name",
                "Default Venue"
            )
        ),

        "shape": str(
            getattr(
                venue,
                "shape",
                "rectangle"
            )
        ),

        "length": str(
            getattr(
                venue,
                "length",
                20
            )
        ),

        "width": str(
            getattr(
                venue,
                "width",
                10
            )
        ),

        "diameter": str(
            getattr(
                venue,
                "diameter",
                0
            )
        ),

        "capacity": str(
            getattr(
                venue,
                "capacity",
                100
            )
        ),

        "warning": str(
            getattr(
                venue,
                "warning_threshold",
                70
            )
        ),

        "critical": str(
            getattr(
                venue,
                "critical_threshold",
                90
            )
        ),

        "grid": str(
            getattr(
                venue,
                "grid_size",
                5
            )
        ),

        "camera_name": "",

        "camera": camera_source,

        "test_multiplier": str(
            DEFAULT_TEST_MULTIPLIER
        )
    }


admin_fields = load_admin_fields()


# ============================================================
# CAMERA SOURCE
# ============================================================

def get_camera_source():

    value = admin_fields.get(
        "camera",
        DEFAULT_CAMERA_SOURCE
    )

    # Convert anything to text first
    value = str(value).strip()

    if not value:
        value = DEFAULT_CAMERA_SOURCE

    # Laptop/webcam source such as 0, 1, 2
    if value.isdigit():
        return int(value)

    # IP camera / phone camera URL
    return value


# ============================================================
# SAVED CAMERA MANAGEMENT
# ============================================================

def save_current_camera():

    global saved_cameras
    global camera_source

    # IMPORTANT:
    # Convert to string BEFORE using .strip()
    name = str(
        admin_fields.get("camera_name", "")
    ).strip()

    source = str(
        admin_fields.get("camera", "")
    ).strip()

    if not name:

        print("Camera name is required.")

        return False

    if not source:

        print("Camera source is required.")

        return False

    # --------------------------------------------------------
    # If camera name already exists, update it
    # --------------------------------------------------------

    for camera in saved_cameras:

        if str(camera.get("name", "")).strip() == name:

            camera["source"] = source

            # Keep the currently selected source correct
            camera_source = get_camera_source()

            print(
                f"Camera updated: {name} -> {source}"
            )

            return save_saved_cameras(
                saved_cameras
            )

    # --------------------------------------------------------
    # Otherwise create a new saved camera
    # --------------------------------------------------------

    saved_cameras.append({
        "name": name,
        "source": source
    })

    # Keep current camera source synchronized
    camera_source = get_camera_source()

    print(
        f"Camera saved: {name} -> {source}"
    )

    return save_saved_cameras(
        saved_cameras
    )


def select_saved_camera(index):

    global camera_source

    try:

        index = int(index)

        camera = saved_cameras[index]

        admin_fields["camera_name"] = (
            camera.get("name", "")
        )

        admin_fields["camera"] = (
            camera.get("source", "")
        )

        camera_source = get_camera_source()

        print(
            f"Selected camera: "
            f"{camera.get('name')}"
        )

        print(
            f"Source: "
            f"{camera.get('source')}"
        )

        return True

    except Exception as error:

        print(
            f"Camera selection error: {error}"
        )

        return False


def delete_saved_camera(index):

    global saved_cameras

    try:

        index = int(index)

        camera = saved_cameras.pop(index)

        save_saved_cameras(
            saved_cameras
        )

        print(
            f"Deleted camera: "
            f"{camera.get('name')}"
        )

        return True

    except Exception as error:

        print(
            f"Camera delete error: {error}"
        )

        return False


# ============================================================
# TEST MULTIPLIER
# ============================================================

def get_test_multiplier():

    try:

        multiplier = int(
            float(
                admin_fields.get(
                    "test_multiplier",
                    "1"
                )
            )
        )

        return max(
            1,
            multiplier
        )

    except Exception:

        return 1


# ============================================================
# START SESSION
# ============================================================

def start_crowdsense_session():

    global session_started

    if session_started:
        return

    try:

        session = session_manager.start_session(
            venue_name=venue.name,
            cameras=[
                {
                    "camera_id": "CAMERA1",
                    "source": str(camera_source),
                    "enabled": True
                }
            ],
            capacity=venue.capacity
        )

        if session is not None:

            session_started = True

            print(
                f"Session active: "
                f"{session.get('session_id')}"
            )

    except Exception as error:

        print(
            f"Session start error: {error}"
        )


# ============================================================
# END SESSION
# ============================================================

def end_crowdsense_session():

    global session_started

    if not session_started:
        return

    try:

        completed = (
            session_manager.end_session()
        )

        if completed:

            print(
                f"Session completed: "
                f"{completed.get('session_id')}"
            )

    except Exception as error:

        print(
            f"Session end error: {error}"
        )

    session_started = False


# ============================================================
# OPEN CAMERA
# ============================================================

def start_camera():

    global cap
    global model
    global current_mode
    global camera_source

    camera_source = get_camera_source()

    # Release previously opened camera
    if cap is not None:

        try:
            cap.release()
        except Exception:
            pass

        cap = None

    print()
    print("================================")
    print("STARTING CROWDSENSE")
    print("================================")

    print(
        f"Camera source: {camera_source}"
    )

    # --------------------------------------------------------
    # CAMERA
    # --------------------------------------------------------

    # Use DirectShow for Windows laptop/webcam cameras.
    # Keep the normal backend for IP/phone camera URLs.

    if isinstance(camera_source, int):

        cap = cv2.VideoCapture(
            camera_source,
            cv2.CAP_DSHOW
        )

    else:

        cap = cv2.VideoCapture(
            camera_source
        )

    if not cap.isOpened():

        print()
        print(
            "ERROR: Camera could not be opened."
        )

        cap.release()

        cap = None

        return False

    cap.set(
        cv2.CAP_PROP_FRAME_WIDTH,
        CAMERA_WIDTH
    )

    cap.set(
        cv2.CAP_PROP_FRAME_HEIGHT,
        CAMERA_HEIGHT
    )

    # --------------------------------------------------------
    # AI
    # --------------------------------------------------------

    if model is None:

        print()
        print(
            "Loading CrowdSense AI..."
        )

        try:

            model = YOLO(
                MODEL_PATH
            )

        except Exception as error:

            print(
                f"ERROR loading YOLO: {error}"
            )

            cap.release()

            cap = None

            return False

        print(
            "AI model loaded."
        )

    # --------------------------------------------------------
    # CALIBRATION
    #
    # Do NOT replace the calibration object here.
    # The web API keeps a reference to this object.
    # --------------------------------------------------------

    calibration.reset()

    loaded = calibration.load()

    if loaded:

        if (
            abs(
                calibration.venue_length
                -
                venue.length
            ) > 0.001

            or

            abs(
                calibration.venue_width
                -
                venue.width
            ) > 0.001
        ):

            print(
                "Calibration does not match venue."
            )

            calibration.reset()

            calibration.set_venue_dimensions(
                venue.length,
                venue.width
            )

        else:

            print(
                "Existing calibration loaded."
            )

    else:

        calibration.set_venue_dimensions(
            venue.length,
            venue.width
        )

        print(
            "Camera is not calibrated."
        )

    # --------------------------------------------------------
    # REGISTER CURRENT COMPONENTS WITH API
    # --------------------------------------------------------

    try:

        register_api(
            camera_manager=camera_manager,
            alert_manager=alert_manager,
            incident_manager=incident_manager,
            snapshot_manager=snapshot_manager,
            session_manager=session_manager,
            analytics_manager=analytics_manager,
            graph_manager=graph_manager,
            venue_config=venue,
            calibration=calibration,
            camera_calibration_manager=camera_calibration_manager,
            report_manager=report_manager,
            report_exporter=report_exporter
        )

    except Exception as error:

        print(
            f"API registration error: {error}"
        )

    # --------------------------------------------------------
    # SESSION
    # --------------------------------------------------------

    start_crowdsense_session()

    # --------------------------------------------------------
    # STATE
    # --------------------------------------------------------

    system_state.update(
        system="ACTIVE",
        venue=venue.name,
        total_people=0,
        capacity=venue.capacity,
        camera_source=str(camera_source),
        test_multiplier=get_test_multiplier()
    )

    current_mode = MODE_MONITOR

    print()
    print(
        "CrowdSense monitoring started."
    )

    print("A = Admin")
    print("C = Calibration")
    print("G = Grid")
    print("Q = Quit")
    print()

    return True


# ============================================================
# SAVE ADMIN SETTINGS
# ============================================================

def save_admin_settings(
    start_after_save=False
):

    global venue
    global current_mode
    global active_field
    global shape_dropdown_open
    global zone_manager
    global calibration
    global admin_fields
    global pending_floorplan_path

    try:

        name = (
            admin_fields["name"]
            .strip()
        )

        if not name:
            name = "Default Venue"

        shape = (
            admin_fields["shape"]
            .strip()
            .lower()
        )

        if shape not in (
            "rectangle",
            "circle"
        ):

            raise ValueError(
                "Shape must be rectangle or circle."
            )

        if shape == "rectangle":

            length = float(
                admin_fields["length"]
            )

            width = float(
                admin_fields["width"]
            )

            if length <= 0 or width <= 0:

                raise ValueError(
                    "Dimensions must be greater than 0."
                )

            new_length = length
            new_width = width
            new_diameter = 0

        else:

            diameter = float(
                admin_fields["diameter"]
            )

            if diameter <= 0:

                raise ValueError(
                    "Diameter must be greater than 0."
                )

            new_length = diameter
            new_width = diameter
            new_diameter = diameter

        capacity = int(
            float(
                admin_fields["capacity"]
            )
        )

        if capacity <= 0:

            raise ValueError(
                "Capacity must be greater than 0."
            )

        warning = float(
            admin_fields["warning"]
        )

        critical = float(
            admin_fields["critical"]
        )

        if warning <= 0 or critical <= 0:

            raise ValueError(
                "Thresholds must be greater than 0."
            )

        if warning >= critical:

            raise ValueError(
                "Warning must be lower than critical."
            )

        grid_size = float(
            admin_fields["grid"]
        )

        if grid_size <= 0:

            raise ValueError(
                "Grid size must be greater than 0."
            )

        test_multiplier = get_test_multiplier()

        camera_value = str(
            admin_fields.get(
                "camera",
                "0"
            )
        ).strip()

        if not camera_value:
            camera_value = "0"

        dimensions_changed = (

            abs(
                venue.length -
                new_length
            ) > 0.001

            or

            abs(
                venue.width -
                new_width
            ) > 0.001

            or

            venue.shape != shape
        )

        venue.name = name
        venue.shape = shape
        venue.length = new_length
        venue.width = new_width
        venue.diameter = new_diameter
        venue.capacity = capacity
        venue.warning_threshold = warning
        venue.critical_threshold = critical
        venue.grid_size = grid_size

        if pending_floorplan_path:

            venue.floorplan = (
                pending_floorplan_path
            )

        venue.save()

        zone_manager = PhysicalZoneManager(
            venue
        )

        if dimensions_changed:

            calibration.reset()

            calibration.set_venue_dimensions(
                venue.length,
                venue.width
            )

        system_state.update(
            venue=venue.name,
            capacity=venue.capacity,
            camera_source=camera_value,
            test_multiplier=test_multiplier
        )

        # ----------------------------------------------------
        # Update web API's venue reference
        # ----------------------------------------------------

        try:

            register_api(
                camera_manager=camera_manager,
                alert_manager=alert_manager,
                incident_manager=incident_manager,
                snapshot_manager=snapshot_manager,
                session_manager=session_manager,
                analytics_manager=analytics_manager,
                graph_manager=graph_manager,
                venue_config=venue,
                calibration=calibration,
                camera_calibration_manager=camera_calibration_manager,
                report_manager=report_manager,
                report_exporter=report_exporter
            )

        except Exception as error:

            print(
                f"API update error: {error}"
            )

        active_field = None
        shape_dropdown_open = False

        if start_after_save:

            current_mode = MODE_SETUP

            if not start_camera():

                current_mode = MODE_SETUP

                return False

        else:

            current_mode = MODE_MONITOR

        print()
        print(
            "================================"
        )

        print(
            "VENUE CONFIGURATION SAVED"
        )

        print(
            f"Venue: {venue.name}"
        )

        print(
            f"Shape: {venue.shape}"
        )

        print(
            f"Area: "
            f"{venue.calculate_area():.2f} m²"
        )

        print(
            f"Capacity: {venue.capacity}"
        )

        print(
            f"Grid: {venue.grid_size:.2f} m"
        )

        print(
            f"Zones: {len(zone_manager.zones)}"
        )

        print(
            f"Test multiplier: {test_multiplier}x"
        )

        print(
            f"Camera: {camera_value}"
        )

        print(
            "================================"
        )

        return True

    except Exception as error:

        print()
        print(
            f"Admin error: {error}"
        )

        return False


# ============================================================
# BEEP
# ============================================================

def crowd_alarm():

    global last_alarm_time

    now = time.time()

    if (
        now - last_alarm_time
        <
        ALARM_COOLDOWN_SECONDS
    ):

        return

    last_alarm_time = now

    if winsound is None:
        return

    def beep_thread():

        try:

            for _ in range(3):

                winsound.Beep(
                    1200,
                    250
                )

                time.sleep(0.1)

        except Exception:
            pass

    threading.Thread(
        target=beep_thread,
        daemon=True
    ).start()


# ============================================================
# TEST ALERT
# ============================================================

def trigger_test_alert():

    global latest_display_frame

    print()
    print("================================")
    print("CROWDSENSE TEST ALERT")
    print("================================")

    alert = alert_manager.create_alert(
        zone_id="TEST",
        risk="CRITICAL",
        people=venue.capacity + 1,
        density=1.0,
        special_type="TEST"
    )

    if alert:

        if latest_display_frame is not None:

            snapshot_manager.capture(
                latest_display_frame,
                "TEST",
                "CRITICAL"
            )

        crowd_alarm()

        system_state.update(
            last_alert=alert
        )

    print(
        "TEST ALERT COMPLETE"
    )

    print("================================")


# ============================================================
# OPEN ADMIN
# ============================================================

def open_admin():

    global current_mode
    global active_field
    global shape_dropdown_open
    global admin_fields

    admin_fields = load_admin_fields()

    active_field = None
    shape_dropdown_open = False

    current_mode = MODE_ADMIN


# ============================================================
# OPEN CALIBRATION
# ============================================================

def open_calibration():

    global current_mode
    global calibration_points
    global calibration_message

    if cap is None:
        return

    current_mode = MODE_CALIBRATION

    calibration_points = []

    calibration.reset()

    calibration.set_venue_dimensions(
        venue.length,
        venue.width
    )

    calibration_message = (
        "CLICK 4 POINTS: TL → TR → BR → BL"
    )


# ============================================================
# SAVE CALIBRATION
# ============================================================

def save_calibration():

    global calibration_message

    if len(calibration_points) != 4:

        calibration_message = (
            "EXACTLY 4 POINTS REQUIRED"
        )

        return

    if calibration.calculate():

        calibration.save()

        calibration_message = (
            "CALIBRATION SAVED"
        )

        print(
            "Camera calibration saved."
        )

    else:

        calibration_message = (
            "CALIBRATION FAILED"
        )


# ============================================================
# IMPORT FLOOR PLAN
# ============================================================

def import_floorplan():

    global floorplan_message
    global pending_floorplan_path

    try:

        from tkinter import (
            Tk,
            filedialog
        )

        root = Tk()

        root.withdraw()

        root.attributes(
            "-topmost",
            True
        )

        path = filedialog.askopenfilename(

            title="Select Venue Floor Plan",

            filetypes=[
                (
                    "Image files",
                    "*.png *.jpg *.jpeg *.bmp"
                ),
                (
                    "All files",
                    "*.*"
                )
            ]
        )

        root.destroy()

        if not path:

            floorplan_message = (
                "FLOOR PLAN SELECTION CANCELLED"
            )

            return

        if floorplan.load_image(path):

            floorplan.set_dimensions(
                venue.length,
                venue.width
            )

            pending_floorplan_path = path

            floorplan_message = (
                "FLOOR PLAN SELECTED"
            )

            print(
                f"Floor plan: {path}"
            )

        else:

            floorplan_message = (
                "COULD NOT LOAD FLOOR PLAN"
            )

    except Exception as error:

        floorplan_message = (
            "FLOOR PLAN ERROR"
        )

        print(
            f"Floor plan error: {error}"
        )


# ============================================================
# CALIBRATION CLICK
# ============================================================

def handle_calibration_click(x, y):

    global calibration_points
    global calibration_message

    if y < 70:
        return

    if len(calibration_points) >= 4:
        return

    calibration_points.append(
        (x, y)
    )

    calibration.add_point(
        x,
        y
    )

    names = [
        "TOP-LEFT",
        "TOP-RIGHT",
        "BOTTOM-RIGHT",
        "BOTTOM-LEFT"
    ]

    if len(calibration_points) < 4:

        calibration_message = (
            f"CLICK {names[len(calibration_points)]}"
        )

    else:

        calibration_message = (
            "4 POINTS SELECTED — PRESS S"
        )


# ============================================================
# MOUSE CALLBACK
# ============================================================

def mouse_callback(
    event,
    x,
    y,
    flags,
    param
):

    global current_mode
    global active_field
    global shape_dropdown_open
    global admin_fields

    if event != cv2.EVENT_LBUTTONDOWN:
        return

    # ========================================================
    # SETUP
    # ========================================================

    if current_mode == MODE_SETUP:

        if save_start_button_rect:

            x1, y1, x2, y2 = save_start_button_rect

            if (
                x1 <= x <= x2
                and
                y1 <= y <= y2
            ):

                save_admin_settings(
                    start_after_save=True
                )

                return

        if floorplan_button_rect:

            x1, y1, x2, y2 = floorplan_button_rect

            if (
                x1 <= x <= x2
                and
                y1 <= y <= y2
            ):

                import_floorplan()

                return

        if shape_dropdown_open:

            if shape_rect:

                x1, y1, x2, y2 = shape_rect

                top = y2

                if (
                    x1 <= x <= x2
                    and
                    top <= y <= top + 70
                ):

                    if y < top + 35:

                        admin_fields["shape"] = "rectangle"

                    else:

                        admin_fields["shape"] = "circle"

                    shape_dropdown_open = False

                    return

            shape_dropdown_open = False

        if shape_rect:

            x1, y1, x2, y2 = shape_rect

            if (
                x1 <= x <= x2
                and
                y1 <= y <= y2
            ):

                shape_dropdown_open = (
                    not shape_dropdown_open
                )

                active_field = None

                return

        for name, rect in field_rects.items():

            x1, y1, x2, y2 = rect

            if (
                x1 <= x <= x2
                and
                y1 <= y <= y2
            ):

                active_field = name

                shape_dropdown_open = False

                return

        return

    # ========================================================
    # CALIBRATION
    # ========================================================

    if current_mode == MODE_CALIBRATION:

        handle_calibration_click(
            x,
            y
        )

        return

    # ========================================================
    # ADMIN
    # ========================================================

    if current_mode == MODE_ADMIN:

        # ====================================================
        # SAVE CAMERA
        # ====================================================

        if save_camera_button_rect:

            x1, y1, x2, y2 = save_camera_button_rect

            if (
                x1 <= x <= x2
                and
                y1 <= y <= y2
            ):

                if save_current_camera():

                    print(
                        "Camera saved successfully."
                    )

                return

        # ====================================================
        # SELECT SAVED CAMERA
        # ====================================================

        for index, rect in saved_camera_select_rects:

            x1, y1, x2, y2 = rect

            if (
                x1 <= x <= x2
                and
                y1 <= y <= y2
            ):

                if select_saved_camera(index):

                    print(
                        "Saved camera selected."
                    )

                return

        # ====================================================
        # DELETE SAVED CAMERA
        # ====================================================

        for index, rect in saved_camera_delete_rects:

            x1, y1, x2, y2 = rect

            if (
                x1 <= x <= x2
                and
                y1 <= y <= y2
            ):

                if delete_saved_camera(index):

                    print(
                        "Saved camera deleted."
                    )

                return

        if test_alert_button_rect:

            x1, y1, x2, y2 = test_alert_button_rect

            if (
                x1 <= x <= x2
                and
                y1 <= y <= y2
            ):

                trigger_test_alert()

                return

        if calibration_button_rect:

            x1, y1, x2, y2 = calibration_button_rect

            if (
                x1 <= x <= x2
                and
                y1 <= y <= y2
            ):

                open_calibration()

                return

        if floorplan_button_rect:

            x1, y1, x2, y2 = floorplan_button_rect

            if (
                x1 <= x <= x2
                and
                y1 <= y <= y2
            ):

                import_floorplan()

                return

        if save_button_rect:

            x1, y1, x2, y2 = save_button_rect

            if (
                x1 <= x <= x2
                and
                y1 <= y <= y2
            ):

                save_admin_settings()

                return

        if cancel_button_rect:

            x1, y1, x2, y2 = cancel_button_rect

            if (
                x1 <= x <= x2
                and
                y1 <= y <= y2
            ):

                current_mode = MODE_MONITOR

                active_field = None

                shape_dropdown_open = False

                return

        if shape_dropdown_open:

            if shape_rect:

                x1, y1, x2, y2 = shape_rect

                top = y2

                if (
                    x1 <= x <= x2
                    and
                    top <= y <= top + 70
                ):

                    if y < top + 35:

                        admin_fields["shape"] = "rectangle"

                    else:

                        admin_fields["shape"] = "circle"

                    shape_dropdown_open = False

                    return

            shape_dropdown_open = False

        if shape_rect:

            x1, y1, x2, y2 = shape_rect

            if (
                x1 <= x <= x2
                and
                y1 <= y <= y2
            ):

                shape_dropdown_open = (
                    not shape_dropdown_open
                )

                active_field = None

                return

        for name, rect in field_rects.items():

            x1, y1, x2, y2 = rect

            if (
                x1 <= x <= x2
                and
                y1 <= y <= y2
            ):

                active_field = name

                shape_dropdown_open = False

                return

        return

    # ========================================================
    # MONITOR
    # ========================================================

    if current_mode == MODE_MONITOR:

        if admin_button_rect:

            x1, y1, x2, y2 = admin_button_rect

            if (
                x1 <= x <= x2
                and
                y1 <= y <= y2
            ):

                open_admin()


# ============================================================
# FIELD DRAWER
# ============================================================

def draw_input_field(
    frame,
    name,
    label,
    value,
    rect
):

    field_rects[name] = rect

    x1, y1, x2, y2 = rect

    text(
        frame,
        label,
        (x1, y1 - 8),
        0.34,
        WHITE,
        2
    )

    cv2.rectangle(
        frame,
        (x1, y1),
        (x2, y2),
        FIELD_DARK,
        -1
    )

    border = (
        RED
        if active_field == name
        else GREEN
    )

    cv2.rectangle(
        frame,
        (x1, y1),
        (x2, y2),
        border,
        2
    )

    display_value = str(value)

    if len(display_value) > 35:

        display_value = (
            display_value[:32]
            + "..."
        )

    text(
        frame,
        display_value,
        (x1 + 9, y1 + 23),
        0.32,
        WHITE,
        2
    )


# ============================================================
# SETUP SCREEN
# ============================================================

def draw_setup_screen(frame):

    global field_rects
    global shape_rect
    global save_start_button_rect
    global floorplan_button_rect

    frame[:] = BLACK

    field_rects = {}

    cv2.rectangle(
        frame,
        (0, 0),
        (CAMERA_WIDTH, 72),
        BLACK,
        -1
    )

    cv2.line(
        frame,
        (0, 70),
        (CAMERA_WIDTH, 70),
        GREEN,
        2
    )

    text(
        frame,
        "CROWDSENSE",
        (25, 31),
        0.68,
        GREEN,
        3
    )

    text(
        frame,
        "VENUE SETUP  /  SYSTEM INITIALIZATION",
        (27, 55),
        0.30,
        GRAY,
        2
    )

    draw_input_field(
        frame,
        "name",
        "VENUE NAME",
        admin_fields["name"],
        (30, 95, 300, 130)
    )

    text(
        frame,
        "VENUE SHAPE",
        (30, 157),
        0.28,
        GRAY,
        2
    )

    shape_rect = (
        30,
        164,
        300,
        194
    )

    cv2.rectangle(
        frame,
        (30, 164),
        (300, 194),
        FIELD_DARK,
        -1
    )

    cv2.rectangle(
        frame,
        (30, 164),
        (300, 194),
        GREEN,
        2
    )

    text(
        frame,
        admin_fields["shape"].upper(),
        (40, 185),
        0.34,
        WHITE,
        2
    )

    if admin_fields["shape"] == "rectangle":

        draw_input_field(
            frame,
            "length",
            "LENGTH (m)",
            admin_fields["length"],
            (30, 225, 160, 260)
        )

        draw_input_field(
            frame,
            "width",
            "WIDTH (m)",
            admin_fields["width"],
            (175, 225, 300, 260)
        )

        y = 295

    else:

        draw_input_field(
            frame,
            "diameter",
            "DIAMETER (m)",
            admin_fields["diameter"],
            (30, 225, 300, 260)
        )

        y = 295

    draw_input_field(
        frame,
        "capacity",
        "MAX CAPACITY",
        admin_fields["capacity"],
        (30, y, 160, y + 35)
    )

    draw_input_field(
        frame,
        "grid",
        "GRID (m)",
        admin_fields["grid"],
        (175, y, 300, y + 35)
    )

    draw_input_field(
        frame,
        "warning",
        "WARNING %",
        admin_fields["warning"],
        (30, y + 65, 160, y + 100)
    )

    draw_input_field(
        frame,
        "critical",
        "CRITICAL %",
        admin_fields["critical"],
        (175, y + 65, 300, y + 100)
    )

    panel(
        frame,
        340,
        95,
        925,
        385,
        DARK,
        GREEN,
        2
    )

    text(
        frame,
        "CAMERA SOURCE",
        (365, 114),
        0.34,
        GREEN,
        2
    )

    draw_input_field(
        frame,
        "camera",
        "0 = LAPTOP CAMERA / URL = PHONE CAMERA",
        admin_fields["camera"],
        (365, 150, 900, 188)
    )

    draw_input_field(
        frame,
        "test_multiplier",
        "TEST MULTIPLIER  /  1 PERSON = Nx PEOPLE",
        admin_fields["test_multiplier"],
        (365, 220, 610, 258)
    )

    text(
        frame,
        "TEST MODE",
        (635, 244),
        0.30,
        YELLOW,
        2
    )

    text(
        frame,
        "Set to 5 for testing:",
        (365, 275),
        0.30,
        WHITE,
        1
    )

    text(
        frame,
        "1 detected person → 5 counted people",
        (365, 300),
        0.32,
        YELLOW,
        2
    )

    floorplan_button_rect = (
        365,
        330,
        610,
        370
    )

    button(
        frame,
        "IMPORT FLOOR PLAN",
        floorplan_button_rect,
        GREEN,
        0.34
    )

    plan_status = (
        "LOADED"
        if (
            floorplan.path
            or
            pending_floorplan_path
        )
        else
        "NOT LOADED"
    )

    plan_color = (
        GREEN
        if plan_status == "LOADED"
        else GRAY
    )

    text(
        frame,
        f"FLOOR PLAN: {plan_status}",
        (630, 355),
        0.30,
        plan_color,
        2
    )

    save_start_button_rect = (
        340,
        410,
        925,
        475
    )

    button(
        frame,
        "SAVE & START CROWDSENSE",
        save_start_button_rect,
        GREEN,
        0.52
    )

    text(
        frame,
        "CLICK FIELD → TYPE → ENTER",
        (30, 520),
        0.27,
        GRAY,
        2
    )

    text(
        frame,
        "ESC = EXIT",
        (830, 520),
        0.27,
        GRAY,
        2
    )

    if shape_dropdown_open:

        x1, y1, x2, y2 = shape_rect

        cv2.rectangle(
            frame,
            (x1, y2),
            (x2, y2 + 70),
            BLACK,
            -1
        )

        cv2.rectangle(
            frame,
            (x1, y2),
            (x2, y2 + 70),
            GREEN,
            2
        )

        text(
            frame,
            "RECTANGLE",
            (x1 + 10, y2 + 25),
            0.32,
            WHITE,
            2
        )

        text(
            frame,
            "CIRCLE",
            (x1 + 10, y2 + 58),
            0.32,
            WHITE,
            2
        )


# ============================================================
# ADMIN SCREEN
# ============================================================

def draw_admin_screen(frame):

    global field_rects
    global shape_rect
    global save_button_rect
    global cancel_button_rect
    global calibration_button_rect
    global floorplan_button_rect
    global test_alert_button_rect

    global save_camera_button_rect
    global saved_camera_select_rects
    global saved_camera_delete_rects

    frame[:] = DARK

    field_rects = {}

    saved_camera_select_rects = []
    saved_camera_delete_rects = []

    # ========================================================
    # HEADER
    # ========================================================

    cv2.rectangle(
        frame,
        (0, 0),
        (CAMERA_WIDTH, 70),
        BLACK,
        -1
    )

    cv2.line(
        frame,
        (0, 68),
        (CAMERA_WIDTH, 68),
        GREEN,
        2
    )

    text(
        frame,
        "CROWDSENSE",
        (25, 30),
        0.62,
        GREEN,
        3
    )

    text(
        frame,
        "ADMIN CONTROL",
        (27, 54),
        0.32,
        WHITE,
        2
    )

    # ========================================================
    # VENUE SETTINGS
    # ========================================================

    draw_input_field(
        frame,
        "name",
        "VENUE",
        admin_fields["name"],
        (25, 95, 300, 130)
    )

    text(
        frame,
        "SHAPE",
        (25, 157),
        0.28,
        GRAY,
        2
    )

    shape_rect = (
        25,
        164,
        300,
        194
    )

    cv2.rectangle(
        frame,
        (25, 164),
        (300, 194),
        FIELD_DARK,
        -1
    )

    cv2.rectangle(
        frame,
        (25, 164),
        (300, 194),
        GREEN,
        2
    )

    text(
        frame,
        admin_fields["shape"].upper(),
        (35, 185),
        0.34,
        WHITE,
        2
    )

    if admin_fields["shape"] == "rectangle":

        draw_input_field(
            frame,
            "length",
            "LENGTH (m)",
            admin_fields["length"],
            (25, 225, 155, 260)
        )

        draw_input_field(
            frame,
            "width",
            "WIDTH (m)",
            admin_fields["width"],
            (170, 225, 300, 260)
        )

        y = 295

    else:

        draw_input_field(
            frame,
            "diameter",
            "DIAMETER (m)",
            admin_fields["diameter"],
            (25, 225, 300, 260)
        )

        y = 295

    draw_input_field(
        frame,
        "capacity",
        "CAPACITY",
        admin_fields["capacity"],
        (25, y, 155, y + 35)
    )

    draw_input_field(
        frame,
        "grid",
        "GRID (m)",
        admin_fields["grid"],
        (170, y, 300, y + 35)
    )

    draw_input_field(
        frame,
        "warning",
        "WARNING %",
        admin_fields["warning"],
        (25, y + 65, 155, y + 100)
    )

    draw_input_field(
        frame,
        "critical",
        "CRITICAL %",
        admin_fields["critical"],
        (170, y + 65, 300, y + 100)
    )

    # ========================================================
    # CAMERA MANAGEMENT PANEL
    # ========================================================

    panel(
        frame,
        335,
        90,
        935,
        483,
        BLACK,
        DARK_GRAY,
        1
    )

    text(
        frame,
        "CAMERA MANAGEMENT",
        (360, 111),
        0.34,
        GREEN,
        2
    )

    # ========================================================
    # CAMERA NAME
    # ========================================================

    draw_input_field(
        frame,
        "camera_name",
        "CAMERA NAME",
        admin_fields["camera_name"],
        (360, 145, 600, 183)
    )

    # ========================================================
    # CAMERA SOURCE
    # ========================================================

    draw_input_field(
        frame,
        "camera",
        "CAMERA SOURCE",
        admin_fields["camera"],
        (610, 145, 910, 183)
    )

    # ========================================================
    # SAVE CAMERA
    # ========================================================

    save_camera_button_rect = (
        360,
        195,
        570,
        235
    )

    button(
        frame,
        "SAVE CAMERA",
        save_camera_button_rect,
        GREEN,
        0.34
    )

    text(
        frame,
        "Saved permanently",
        (590, 220),
        0.28,
        GRAY,
        2
    )

    # ========================================================
    # SAVED CAMERAS
    # ========================================================

    text(
        frame,
        "SAVED CAMERAS",
        (360, 265),
        0.32,
        WHITE,
        2
    )

    cv2.line(
        frame,
        (360, 273),
        (910, 273),
        DARK_GRAY,
        1
    )

    max_visible = 4

    visible_cameras = saved_cameras[
        :max_visible
    ]

    if not visible_cameras:

        text(
            frame,
            "NO SAVED CAMERAS",
            (360, 300),
            0.30,
            GRAY,
            2
        )

    else:

        for index, camera in enumerate(
            visible_cameras
        ):

            row_y = (
                285 +
                index * 38
            )

            camera_name = camera.get(
                "name",
                f"Camera {index + 1}"
            )

            camera_source_value = camera.get(
                "source",
                ""
            )

            # ------------------------------------------------
            # NAME
            # ------------------------------------------------

            text(
                frame,
                f"{index + 1}. {camera_name}",
                (360, row_y + 18),
                0.28,
                WHITE,
                2
            )

            # ------------------------------------------------
            # SOURCE
            # ------------------------------------------------

            source_display = str(
                camera_source_value
            )

            if len(source_display) > 22:

                source_display = (
                    source_display[:19]
                    + "..."
                )

            text(
                frame,
                source_display,
                (510, row_y + 18),
                0.26,
                GRAY,
                2
            )

            # ------------------------------------------------
            # SELECT BUTTON
            # ------------------------------------------------

            select_rect = (
                735,
                row_y - 5,
                815,
                row_y + 27
            )

            saved_camera_select_rects.append(
                (
                    index,
                    select_rect
                )
            )

            button(
                frame,
                "SELECT",
                select_rect,
                GREEN,
                0.27
            )

            # ------------------------------------------------
            # DELETE BUTTON
            # ------------------------------------------------

            delete_rect = (
                825,
                row_y - 5,
                905,
                row_y + 27
            )

            saved_camera_delete_rects.append(
                (
                    index,
                    delete_rect
                )
            )

            button(
                frame,
                "DELETE",
                delete_rect,
                RED,
                0.27
            )

    # ========================================================
    # TEST MULTIPLIER
    # ========================================================

    draw_input_field(
        frame,
        "test_multiplier",
        "TEST MULTIPLIER",
        admin_fields["test_multiplier"],
        (360, 440, 570, 473)
    )

    text(
        frame,
        "1 detected = "
        f"{get_test_multiplier()} counted",
        (590, 463),
        0.28,
        YELLOW,
        2
    )

    # ========================================================
    # CAMERA TOOLS
    # ========================================================

    calibration_button_rect = (
        360,
        493,
        520,
        533
    )

    button(
        frame,
        "CALIBRATE",
        calibration_button_rect,
        GREEN,
        0.31
    )

    floorplan_button_rect = (
        530,
        493,
        665,
        533
    )

    button(
        frame,
        "FLOOR PLAN",
        floorplan_button_rect,
        GREEN,
        0.31
    )

    test_alert_button_rect = (
        675,
        493,
        745,
        533
    )

    button(
        frame,
        "TEST",
        test_alert_button_rect,
        RED,
        0.31
    )

    # ========================================================
    # STATUS
    # ========================================================

    calibration_status = (
        "CALIBRATED"
        if calibration.matrix is not None
        else "NOT CALIBRATED"
    )

    calibration_color = (
        GREEN
        if calibration.matrix is not None
        else RED
    )

    text(
        frame,
        f"CAMERA: {calibration_status}",
        (755, 375),
        0.28,
        calibration_color,
        2
    )

    text(
        frame,
        f"ZONES: {len(zone_manager.zones)}",
        (755, 400),
        0.28,
        WHITE,
        2
    )

    text(
        frame,
        "S = SAVE & START",
        (755, 430),
        0.26,
        GRAY,
        2
    )

    text(
        frame,
        "ESC = BACK",
        (755, 455),
        0.26,
        GRAY,
        2
    )

    # ========================================================
    # SAVE / CANCEL
    # ========================================================

    save_button_rect = (
        25,
        493,
        150,
        533
    )

    cancel_button_rect = (
        165,
        493,
        290,
        533
    )

    button(
        frame,
        "SAVE",
        save_button_rect,
        GREEN,
        0.36
    )

    button(
        frame,
        "CANCEL",
        cancel_button_rect,
        RED,
        0.36
    )

    # ========================================================
    # SHAPE DROPDOWN
    # ========================================================

    if shape_dropdown_open:

        x1, y1, x2, y2 = shape_rect

        cv2.rectangle(
            frame,
            (x1, y2),
            (x2, y2 + 70),
            BLACK,
            -1
        )

        cv2.rectangle(
            frame,
            (x1, y2),
            (x2, y2 + 70),
            GREEN,
            2
        )

        text(
            frame,
            "RECTANGLE",
            (x1 + 10, y2 + 25),
            0.32,
            WHITE,
            2
        )

        text(
            frame,
            "CIRCLE",
            (x1 + 10, y2 + 58),
            0.32,
            WHITE,
            2
        )


# ============================================================
# CALIBRATION SCREEN
# ============================================================

def draw_calibration_screen(frame):

    cv2.rectangle(
        frame,
        (0, 0),
        (CAMERA_WIDTH, 70),
        BLACK,
        -1
    )

    cv2.line(
        frame,
        (0, 68),
        (CAMERA_WIDTH, 68),
        GREEN,
        2
    )

    text(
        frame,
        "CROWDSENSE",
        (20, 30),
        0.58,
        GREEN,
        2
    )

    text(
        frame,
        "CAMERA CALIBRATION",
        (20, 53),
        0.32,
        WHITE,
        2
    )

    names = [
        "TL",
        "TR",
        "BR",
        "BL"
    ]

    for i, point in enumerate(
        calibration_points
    ):

        x, y = point

        cv2.circle(
            frame,
            (x, y),
            7,
            RED,
            -1
        )

        text(
            frame,
            names[i],
            (x + 10, y - 10),
            0.35,
            RED,
            2
        )

    panel(
        frame,
        15,
        CAMERA_HEIGHT - 75,
        CAMERA_WIDTH - 15,
        CAMERA_HEIGHT - 15,
        BLACK,
        GREEN,
        1
    )

    text(
        frame,
        calibration_message,
        (30, CAMERA_HEIGHT - 45),
        0.34,
        WHITE,
        2
    )

    text(
        frame,
        "S SAVE   R RESET   ESC BACK",
        (650, CAMERA_HEIGHT - 22),
        0.27,
        GRAY,
        2
    )


# ============================================================
# WORLD TO CAMERA
# ============================================================

def world_to_pixel(
    world_x,
    world_y
):

    if calibration.matrix is None:
        return None

    try:

        inverse = np.linalg.inv(
            calibration.matrix
        )

    except Exception:

        return None

    point = np.float32(
        [
            [
                [
                    float(world_x),
                    float(world_y)
                ]
            ]
        ]
    )

    result = cv2.perspectiveTransform(
        point,
        inverse
    )

    return (
        int(result[0][0][0]),
        int(result[0][0][1])
    )


# ============================================================
# GRID
# ============================================================

def draw_physical_grid(frame):

    if not grid_mode:
        return

    if calibration.matrix is None:

        text(
            frame,
            "GRID: CALIBRATION REQUIRED",
            (20, 135),
            0.34,
            RED,
            2
        )

        return

    for zone in zone_manager.zones:

        x1 = zone["x"]
        y1 = zone["y"]

        x2 = x1 + zone["width"]
        y2 = y1 + zone["height"]

        points = [

            world_to_pixel(
                x1,
                y1
            ),

            world_to_pixel(
                x2,
                y1
            ),

            world_to_pixel(
                x2,
                y2
            ),

            world_to_pixel(
                x1,
                y2
            )

        ]

        if any(
            point is None
            for point in points
        ):

            continue

        risk = zone["risk"]

        if risk == "CRITICAL":

            color = RED

        elif risk == "WARNING":

            color = YELLOW

        else:

            color = GREEN

        polygon = np.array(
            points,
            dtype=np.int32
        )

        cv2.polylines(
            frame,
            [polygon],
            True,
            color,
            2,
            cv2.LINE_AA
        )

        center_x = int(
            sum(
                point[0]
                for point in points
            ) / 4
        )

        center_y = int(
            sum(
                point[1]
                for point in points
            ) / 4
        )

        zone_people = zone.get(
            "people",
            0
        )

        text(
            frame,
            f"{zone['id']}  {zone_people}",
            (
                center_x - 20,
                center_y
            ),
            0.28,
            color,
            2
        )


# ============================================================
# MONITOR HEADER
# ============================================================

def draw_monitor_header(
    frame,
    total_people,
    overall_status
):

    if overall_status == "SAFE":

        status_color = GREEN

    elif overall_status == "WARNING":

        status_color = YELLOW

    else:

        status_color = RED

    cv2.rectangle(
        frame,
        (0, 0),
        (
            CAMERA_WIDTH,
            HEADER_HEIGHT
        ),
        BLACK,
        -1
    )

    cv2.line(
        frame,
        (
            0,
            HEADER_HEIGHT - 1
        ),
        (
            CAMERA_WIDTH,
            HEADER_HEIGHT - 1
        ),
        status_color,
        2
    )

    text(
        frame,
        "CROWDSENSE",
        (20, 31),
        0.62,
        GREEN,
        3
    )

    text(
        frame,
        venue.name,
        (22, 54),
        0.32,
        GRAY,
        2
    )

    text(
        frame,
        "PEOPLE",
        (22, 86),
        0.28,
        GRAY,
        2
    )

    text(
        frame,
        total_people,
        (95, 88),
        0.45,
        WHITE,
        2
    )

    text(
        frame,
        f"/ {venue.capacity}",
        (145, 88),
        0.32,
        GRAY,
        2
    )

    multiplier = get_test_multiplier()

    if multiplier > 1:

        text(
            frame,
            f"TEST {multiplier}x",
            (220, 87),
            0.30,
            YELLOW,
            2
        )

    cv2.rectangle(
        frame,
        (
            CAMERA_WIDTH - 225,
            10
        ),
        (
            CAMERA_WIDTH - 20,
            48
        ),
        BLACK,
        -1
    )

    cv2.rectangle(
        frame,
        (
            CAMERA_WIDTH - 225,
            10
        ),
        (
            CAMERA_WIDTH - 20,
            48
        ),
        status_color,
        2
    )

    text(
        frame,
        f"●  {overall_status}",
        (
            CAMERA_WIDTH - 208,
            37
        ),
        0.42,
        status_color,
        2
    )

    occupancy = 0

    if venue.capacity > 0:

        occupancy = (
            total_people /
            venue.capacity
        ) * 100

    text(
        frame,
        f"OCCUPANCY  {occupancy:.0f}%",
        (
            CAMERA_WIDTH - 220,
            75
        ),
        0.30,
        WHITE,
        1
    )

    calibration_status = (
        "CALIBRATED"
        if calibration.matrix is not None
        else "UNCALIBRATED"
    )

    calibration_color = (
        GREEN
        if calibration.matrix is not None
        else RED
    )

    text(
        frame,
        calibration_status,
        (
            CAMERA_WIDTH - 118,
            98
        ),
        0.27,
        calibration_color,
        2
    )


# ============================================================
# MONITOR CONTROLS
# ============================================================

def draw_monitor_controls(frame):

    global admin_button_rect

    admin_button_rect = (
        20,
        112,
        120,
        140
    )

    button(
        frame,
        "ADMIN",
        admin_button_rect,
        GREEN,
        0.31
    )

    text(
        frame,
        "G",
        (140, 132),
        0.29,
        GREEN,
        2
    )

    text(
        frame,
        "GRID",
        (153, 132),
        0.29,
        GRAY,
        2
    )

    text(
        frame,
        "C",
        (205, 132),
        0.29,
        GREEN,
        2
    )

    text(
        frame,
        "CALIBRATE",
        (218, 132),
        0.29,
        GRAY,
        2
    )

    text(
        frame,
        "Q",
        (CAMERA_WIDTH - 45, 132),
        0.29,
        RED,
        2
    )


# ============================================================
# LOG DATA + SESSION
# ============================================================

def process_logging(
    total_people,
    overall_status="SAFE"
):

    global last_log_time
    global last_graph_time
    global last_session_risk

    now = time.time()

    # --------------------------------------------------------
    # LOG EVERY 5 SECONDS
    # --------------------------------------------------------

    if (
        now - last_log_time
        >= LOG_UPDATE_SECONDS
    ):

        logger.log(
            total_people,
            zone_manager.zones
        )

        # ----------------------------------------------------
        # SESSION UPDATE
        #
        # Only update every logging interval so the JSON
        # session file is not rewritten every video frame.
        # ----------------------------------------------------

        if session_started:

            warning_event = (
                overall_status == "WARNING"
                and
                last_session_risk != "WARNING"
            )

            critical_event = (
                overall_status == "CRITICAL"
                and
                last_session_risk != "CRITICAL"
            )

            try:

                session_manager.update_session(
                    total_people=total_people,
                    capacity=venue.capacity,
                    warning=warning_event,
                    critical=critical_event
                )

            except Exception as error:

                print(
                    f"Session update error: {error}"
                )

            last_session_risk = (
                overall_status
            )

        last_log_time = now

    # --------------------------------------------------------
    # GRAPH UPDATE
    # --------------------------------------------------------

    if (
        now - last_graph_time
        >= GRAPH_UPDATE_SECONDS
    ):

        last_graph_time = now

        def generate_graphs():

            try:

                graph_manager.generate_all()

            except Exception as error:

                print(
                    f"Graph update error: {error}"
                )

        threading.Thread(
            target=generate_graphs,
            daemon=True
        ).start()


# ============================================================
# PROCESS ALERTS
# ============================================================

def process_alerts(
    frame,
    total_people,
    overall_status
):

    global alarm_active

    # ========================================================
    # CREATE ZONE ALERTS
    # ========================================================

    alerts = (
        alert_manager
        .process_zones(
            zone_manager.zones
        )
        or []
    )

    # ========================================================
    # CAPACITY ALERT
    # ========================================================

    if total_people > venue.capacity:

        capacity_alert = (
            alert_manager.create_alert(
                zone_id="VENUE",
                risk="CRITICAL",
                people=total_people,
                density=0.0,
                special_type="CAPACITY"
            )
        )

        if capacity_alert:

            alerts.append(
                capacity_alert
            )

    # ========================================================
    # ALARM
    # ========================================================

    if (
        overall_status == "CRITICAL"
        or
        total_people > venue.capacity
    ):

        crowd_alarm()

        alarm_active = True

    else:

        alarm_active = False

    # ========================================================
    # SNAPSHOT + INCIDENT
    #
    # ALERT
    #   ↓
    # SNAPSHOT
    #   ↓
    # INCIDENT WITH EXACT SNAPSHOT PATH
    # ========================================================

    if alerts:

        for alert in alerts:

            if not isinstance(
                alert,
                dict
            ):
                continue

            # ------------------------------------------------
            # CAPTURE SNAPSHOT FOR THIS ALERT
            # ------------------------------------------------

            snapshot_path = (
                snapshot_manager.capture(
                    frame=frame,

                    zone_id=alert.get(
                        "zone_id",
                        "UNKNOWN"
                    ),

                    risk=alert.get(
                        "risk",
                        "UNKNOWN"
                    ),

                    camera_id=alert.get(
                        "camera_id"
                    ),

                    alert_id=alert.get(
                        "alert_id"
                    )
                )
            )

            # ------------------------------------------------
            # CREATE INCIDENT WITH SNAPSHOT PATH
            # ------------------------------------------------

            incident = (
                incident_manager.create_incident(
                    alert=alert,
                    snapshot_path=snapshot_path
                )
            )

            # ------------------------------------------------
            # LOG RESULT
            # ------------------------------------------------

            if incident:

                if snapshot_path:

                    print(
                        f"INCIDENT {incident['incident_id']} "
                        f"linked to snapshot: "
                        f"{snapshot_path}"
                    )

                else:

                    print(
                        f"INCIDENT {incident['incident_id']} "
                        f"created without snapshot."
                    )

        # ----------------------------------------------------
        # UPDATE SYSTEM STATE
        # ----------------------------------------------------

        system_state.update(
            last_alert=alerts[-1]
        )

    return alerts


# ============================================================
# START LOCAL SERVER
# ============================================================

def launch_local_server():

    try:

        # ----------------------------------------------------
        # REGISTER ALL BACKEND MANAGERS
        # ----------------------------------------------------

        register_api(
            camera_manager=camera_manager,
            alert_manager=alert_manager,
            incident_manager=incident_manager,
            snapshot_manager=snapshot_manager,
            session_manager=session_manager,
            analytics_manager=analytics_manager,
            graph_manager=graph_manager,
            venue_config=venue,
            calibration=calibration,
            camera_calibration_manager=camera_calibration_manager,
            report_manager=report_manager,
            report_exporter=report_exporter
        )

        # ----------------------------------------------------
        # CONNECT PROCESSED FRAME TO WEB DASHBOARD
        # ----------------------------------------------------

        set_display_frame_provider(
            lambda: latest_display_frame
        )

        # ----------------------------------------------------
        # START FLASK
        # ----------------------------------------------------

        threading.Thread(
            target=start_server,
            kwargs={
                "host": "0.0.0.0",
                "port": 5000
            },
            daemon=True
        ).start()

        print(
            "Local Wi-Fi dashboard started."
        )

    except Exception as error:

        print(
            f"Local server error: {error}"
        )


# ============================================================
# WINDOW
# ============================================================

cv2.namedWindow(
    WINDOW_NAME,
    cv2.WINDOW_NORMAL
)

cv2.resizeWindow(
    WINDOW_NAME,
    CAMERA_WIDTH,
    CAMERA_HEIGHT
)

cv2.setMouseCallback(
    WINDOW_NAME,
    mouse_callback
)


# ============================================================
# START SERVER
# ============================================================

launch_local_server()


# ============================================================
# STARTUP
# ============================================================

print()
print("============================================")
print("              CROWDSENSE")
print("============================================")
print()
print("VENUE SETUP MODE")
print("Camera has NOT started.")
print()
print("Configure the venue and press")
print("SAVE & START CROWDSENSE.")
print()
print("Local dashboard:")
print("http://127.0.0.1:5000")
print()
print("============================================")
print()


# ============================================================
# MAIN LOOP
# ============================================================

while True:

    # ========================================================
    # SETUP
    # ========================================================

    if current_mode == MODE_SETUP:

        setup_frame = np.zeros(
            (
                CAMERA_HEIGHT,
                CAMERA_WIDTH,
                3
            ),
            dtype=np.uint8
        )

        draw_setup_screen(
            setup_frame
        )

        cv2.imshow(
            WINDOW_NAME,
            setup_frame
        )

        key = cv2.waitKeyEx(20)

        key_ascii = key & 0xFF

        if key_ascii == 27:

            break

        if key_ascii in (
            ord("s"),
            ord("S")
        ):

            if active_field is not None:

                active_field = None

            else:

                save_admin_settings(
                    start_after_save=True
                )

            continue

        if active_field is not None:

            if key_ascii in (
                8,
                127
            ):

                admin_fields[active_field] = (
                    str(admin_fields[active_field])[:-1]
                )

            elif key_ascii == 22:

                if pyperclip is not None:

                    try:

                        pasted = pyperclip.paste()

                        pasted = "".join(
                            ch for ch in pasted
                            if 32 <= ord(ch) <= 126
                        )

                        admin_fields[
                            active_field
                        ] += pasted

                    except Exception:
                        pass

            elif key_ascii in (
                10,
                13
            ):

                active_field = None

            elif (
                32 <= key_ascii <= 126
            ):

                admin_fields[
                    active_field
                ] += chr(
                    key_ascii
                )

        continue

    # ========================================================
    # ADMIN
    # ========================================================

    if current_mode == MODE_ADMIN:

        admin_frame = np.zeros(
            (
                CAMERA_HEIGHT,
                CAMERA_WIDTH,
                3
            ),
            dtype=np.uint8
        )

        draw_admin_screen(
            admin_frame
        )

        cv2.imshow(
            WINDOW_NAME,
            admin_frame
        )

        key = cv2.waitKeyEx(20)

        key_ascii = key & 0xFF

        if key_ascii == 27:

            current_mode = MODE_MONITOR

            active_field = None

            shape_dropdown_open = False

            continue

        if key_ascii in (
            ord("s"),
            ord("S")
        ):

            if active_field is not None:

                active_field = None

            else:

                save_admin_settings(
                    start_after_save=True
                )

            continue

        if key_ascii in (
            ord("c"),
            ord("C")
        ):

            if active_field is None:

                open_calibration()

            continue

        if key_ascii in (
            ord("t"),
            ord("T")
        ):

            trigger_test_alert()

            continue

        if active_field is not None:

            if key_ascii in (
                8,
                127
            ):

                admin_fields[active_field] = (
                    str(admin_fields[active_field])[:-1]
                )

            elif key_ascii == 22:

                if pyperclip is not None:

                    try:

                        pasted = pyperclip.paste()

                        pasted = "".join(
                            ch for ch in pasted
                            if 32 <= ord(ch) <= 126
                        )

                        admin_fields[
                            active_field
                        ] += pasted

                    except Exception:
                        pass

            elif key_ascii in (
                10,
                13
            ):

                active_field = None

            elif (
                32 <= key_ascii <= 126
            ):

                admin_fields[
                    active_field
                ] += chr(
                    key_ascii
                )

        continue

    # ========================================================
    # CALIBRATION
    # ========================================================

    if current_mode == MODE_CALIBRATION:

        if cap is None:

            current_mode = MODE_ADMIN

            continue

        success, frame = cap.read()

        if not success:

            print(
                "Camera frame unavailable."
            )

            current_mode = MODE_ADMIN

            continue

        frame = cv2.resize(
            frame,
            (
                CAMERA_WIDTH,
                CAMERA_HEIGHT
            ),
            interpolation=cv2.INTER_AREA
        )

        draw_calibration_screen(
            frame
        )

        cv2.imshow(
            WINDOW_NAME,
            frame
        )

        key = cv2.waitKeyEx(20)

        key_ascii = key & 0xFF

        if key_ascii == 27:

            current_mode = MODE_ADMIN

            continue

        if key_ascii in (
            ord("r"),
            ord("R")
        ):

            calibration_points = []

            calibration.reset()

            calibration.set_venue_dimensions(
                venue.length,
                venue.width
            )

            calibration_message = (
                "CLICK 4 POINTS: TL → TR → BR → BL"
            )

            continue

        if key_ascii in (
            ord("s"),
            ord("S")
        ):

            save_calibration()

            continue

        continue

    # ========================================================
    # MONITOR
    # ========================================================

    if current_mode == MODE_MONITOR:

        if cap is None:

            current_mode = MODE_SETUP

            continue

        success, frame = cap.read()

        if not success:

            print(
                "ERROR: Camera frame unavailable."
            )

            break

        frame = cv2.resize(
            frame,
            (
                CAMERA_WIDTH,
                CAMERA_HEIGHT
            ),
            interpolation=cv2.INTER_AREA
        )

        # ====================================================
        # YOLO
        # ====================================================

        results = model.track(
            frame,
            persist=True,
            classes=[0],
            verbose=False
        )

        tracked_people = []

        if (
            results
            and
            results[0].boxes is not None
        ):

            boxes = results[0].boxes

            for i, box in enumerate(boxes):

                x1, y1, x2, y2 = map(
                    int,
                    box.xyxy[0]
                    .cpu()
                    .tolist()
                )

                if boxes.id is not None:

                    track_id = int(
                        boxes.id[i].item()
                    )

                else:

                    track_id = i + 1

                # ------------------------------------------------
                # Bottom-center of person
                # ------------------------------------------------

                foot_x = int(
                    (x1 + x2) / 2
                )

                foot_y = int(
                    y2
                )

                world_position = None

                if calibration.matrix is not None:

                    world_position = (
                        calibration
                        .pixel_to_world(
                            foot_x,
                            foot_y
                        )
                    )

                tracked_people.append({

                    "id": track_id,

                    "box": (
                        x1,
                        y1,
                        x2,
                        y2
                    ),

                    "foot": (
                        foot_x,
                        foot_y
                    ),

                    "world": world_position

                })

        # ====================================================
        # TEST MULTIPLIER
        # ====================================================

        test_multiplier = get_test_multiplier()

        # ====================================================
        # RESET ZONES
        # ====================================================

        zone_manager.reset_counts()

        # ====================================================
        # ASSIGN PEOPLE TO ZONES
        # ====================================================

        assigned_people = 0

        for person in tracked_people:

            world = person["world"]

            if world is None:

                print(
                    f"[ZONE MISS] "
                    f"Person #{person['id']} "
                    f"has no world position."
                )

                continue

            world_x, world_y = world

            zone = zone_manager.add_person(
                world_x,
                world_y,
                multiplier=test_multiplier
            )

            if zone is not None:

                assigned_people += 1

                print(
                    f"[ZONE] "
                    f"Person #{person['id']} "
                    f"World=("
                    f"{world_x:.2f}, "
                    f"{world_y:.2f}"
                    f") -> "
                    f"{zone['id']}"
                )

            else:

                print(
                    f"[ZONE MISS] "
                    f"Person #{person['id']} "
                    f"World=("
                    f"{world_x:.2f}, "
                    f"{world_y:.2f}"
                    f")"
                )

        # ====================================================
        # TOTAL PEOPLE
        # ====================================================

        total_people = (
            len(tracked_people)
            *
            test_multiplier
        )

        # ====================================================
        # OVERALL RISK
        # ====================================================

        overall_status = "SAFE"

        # Venue capacity

        if total_people > venue.capacity:

            overall_status = "CRITICAL"

        # Zone risk

        else:

            for zone in zone_manager.zones:

                if zone["risk"] == "CRITICAL":

                    overall_status = "CRITICAL"

                    break

                if (
                    zone["risk"] == "WARNING"
                    and
                    overall_status == "SAFE"
                ):

                    overall_status = "WARNING"

        # Venue occupancy

        if venue.capacity > 0:

            occupancy = (
                total_people /
                venue.capacity
            ) * 100

            if (
                occupancy >=
                venue.critical_threshold
            ):

                overall_status = "CRITICAL"

            elif (
                occupancy >=
                venue.warning_threshold
                and
                overall_status == "SAFE"
            ):

                overall_status = "WARNING"

        # ====================================================
        # DRAW GRID
        # ====================================================

        draw_physical_grid(
            frame
        )

        # ====================================================
        # PERSON BOXES
        # ====================================================

        for person in tracked_people:

            x1, y1, x2, y2 = (
                person["box"]
            )

            cv2.rectangle(
                frame,
                (x1, y1),
                (x2, y2),
                GREEN,
                2,
                cv2.LINE_AA
            )

            text(
                frame,
                f"#{person['id']}",
                (
                    x1,
                    max(
                        HEADER_HEIGHT + 20,
                        y1 - 8
                    )
                ),
                0.38,
                WHITE,
                2
            )

            if person["world"] is not None:

                wx, wy = (
                    person["world"]
                )

                text(
                    frame,
                    f"{wx:.1f}m,{wy:.1f}m",
                    (
                        x1,
                        min(
                            CAMERA_HEIGHT - 10,
                            y2 + 15
                        )
                    ),
                    0.23,
                    GRAY,
                    1
                )

        # ====================================================
        # HEADER
        # ====================================================

        draw_monitor_header(
            frame,
            total_people,
            overall_status
        )

        # ====================================================
        # CONTROLS
        # ====================================================

        draw_monitor_controls(
            frame
        )

        # ====================================================
        # ASSIGNMENT DEBUG
        # ====================================================

        debug_color = (
            GREEN
            if assigned_people ==
            len(tracked_people)
            else YELLOW
        )

        text(
            frame,
            f"ZONES {assigned_people}/{len(tracked_people)}",
            (20, 165),
            0.28,
            debug_color,
            2
        )

        # ====================================================
        # ALERT
        # ====================================================

        alerts = process_alerts(
            frame,
            total_people,
            overall_status
        )

        # ====================================================
        # ALERT BANNER
        # ====================================================

        if overall_status == "CRITICAL":

            cv2.rectangle(
                frame,
                (300, 112),
                (660, 148),
                RED,
                -1
            )

            text(
                frame,
                "CRITICAL CROWD CONDITION",
                (330, 137),
                0.38,
                WHITE,
                2
            )

        elif overall_status == "WARNING":

            cv2.rectangle(
                frame,
                (360, 112),
                (600, 148),
                YELLOW,
                -1
            )

            text(
                frame,
                "CROWD WARNING",
                (395, 137),
                0.38,
                BLACK,
                2
            )

        # ====================================================
        # LOGGING + SESSION
        # ====================================================

        process_logging(
            total_people,
            overall_status
        )

        # ====================================================
        # SYSTEM STATE
        # ====================================================

        system_state.update(

            system="ACTIVE",

            venue=venue.name,

            total_people=total_people,

            capacity=venue.capacity,

            risk=overall_status,

            zones=zone_manager.zones,

            camera_source=str(
                camera_source
            ),

            test_multiplier=test_multiplier,

            last_update=(
                datetime.now()
                .strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            )
        )

        # ====================================================
        # LOCAL WEB DASHBOARD
        # ====================================================

        try:

            update_status(

                venue=venue.name,

                total_people=total_people,

                capacity=venue.capacity,

                risk=overall_status,

                zones=zone_manager.zones,

                system="ACTIVE",

                camera_source=str(
                    camera_source
                ),

                test_multiplier=test_multiplier,

                last_alert=(
                    alerts[-1]
                    if alerts
                    else None
                )
            )

        except Exception as error:

            print(
                f"Dashboard update error: {error}"
            )

        # ====================================================
        # SAVE FRAME
        # ====================================================

        latest_display_frame = (
            frame.copy()
        )

        # ====================================================
        # DISPLAY
        # ====================================================

        cv2.imshow(
            WINDOW_NAME,
            frame
        )

        # ====================================================
        # KEYBOARD
        # ====================================================

        key = cv2.waitKeyEx(1)

        key_ascii = key & 0xFF

        if key_ascii in (
            ord("a"),
            ord("A")
        ):

            open_admin()

        elif key_ascii in (
            ord("c"),
            ord("C")
        ):

            open_calibration()

        elif key_ascii in (
            ord("g"),
            ord("G")
        ):

            grid_mode = not grid_mode

            print(
                "Grid Mode:",
                "ON"
                if grid_mode
                else "OFF"
            )

        elif key_ascii in (
            ord("q"),
            ord("Q")
        ):

            break


# ============================================================
# CLEANUP
# ============================================================

# ------------------------------------------------------------
# End active session first
# ------------------------------------------------------------

end_crowdsense_session()

# ------------------------------------------------------------
# Update system state
# ------------------------------------------------------------

system_state.update(
    system="STOPPED"
)

try:

    update_status(
        system="STOPPED"
    )

except Exception:
    pass

# ------------------------------------------------------------
# Release camera
# ------------------------------------------------------------

if cap is not None:

    cap.release()

# ------------------------------------------------------------
# Close OpenCV
# ------------------------------------------------------------

cv2.destroyAllWindows()

print()
print("================================")
print("CROWDSENSE STOPPED")
print("================================")
