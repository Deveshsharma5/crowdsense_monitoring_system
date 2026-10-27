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

    set_display_frame_provider,

    set_camera_switch_callback

)



requested_camera_switch = None





def on_web_camera_switch(camera):

    global requested_camera_switch

    requested_camera_switch = camera







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



ADMIN_WIDTH = 1320

ADMIN_HEIGHT = 800



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



BLACK = (20, 13, 10)       # #0a0d14 Main background

DARK = (38, 25, 19)        # #131926 Card background

ELEVATED = (48, 32, 24)    # #182030 Elevated panels

FIELD_DARK = (34, 20, 14)  # #0e1422 Input fields



GREEN = (129, 185, 16)     # #10b981 Primary accent (Emerald)

RED = (68, 68, 239)        # #ef4444 Critical

YELLOW = (11, 158, 245)    # #f59e0b Warning

PURPLE = (247, 85, 168)    # #a855f7 Surge

WHITE = (249, 245, 241)    # #f1f5f9 Primary text

GRAY = (184, 163, 148)     # #94a3b8 Secondary text

DARK_GRAY = (59, 41, 30)   # #1e293b Panel borders



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

reset_calibration_button_rect = None

clear_cameras_button_rect = None

reset_venue_button_rect = None

pending_confirmation = None

confirm_yes_rect = None

confirm_no_rect = None





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



    from stream_capture import LowLatencyVideoCapture

    cap = LowLatencyVideoCapture(

        camera_source,

        width=CAMERA_WIDTH,

        height=CAMERA_HEIGHT

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

            report_exporter=report_exporter,

            zone_manager=zone_manager

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



            # Show a "Starting..." loading frame immediately so the window feels
            # responsive before the blocking camera/YOLO init.
            _loading = np.zeros((CAMERA_HEIGHT, CAMERA_WIDTH, 3), dtype=np.uint8)
            text(_loading, "STARTING CROWDSENSE...", (CAMERA_WIDTH // 2 - 175, CAMERA_HEIGHT // 2 - 20), 0.70, GREEN, 2)
            text(_loading, "Loading camera and AI model. Please wait...", (CAMERA_WIDTH // 2 - 230, CAMERA_HEIGHT // 2 + 20), 0.40, (175, 190, 205), 1)
            try:
                cv2.imshow(WINDOW_NAME, _loading)
                cv2.waitKey(1)
            except Exception:
                pass

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



            for _ in range(2):



                winsound.Beep(

                    1000,

                    150

                )



                time.sleep(0.08)



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



        # ----------------------------------------------------

        # CONFIRMATION MODAL CLICKS

        # ----------------------------------------------------

        global pending_confirmation

        global saved_cameras



        if pending_confirmation:

            if confirm_yes_rect:

                x1, y1, x2, y2 = confirm_yes_rect

                if x1 <= x <= x2 and y1 <= y <= y2:

                    action = pending_confirmation.get("action")

                    if action == "delete_camera":

                        idx = pending_confirmation.get("index")

                        if idx is not None:

                            delete_saved_camera(idx)

                    elif action == "reset_calibration":

                        calibration.reset()

                        calibration.save()

                        print("Calibration reset confirmed.")

                    elif action == "clear_cameras":

                        saved_cameras.clear()

                        save_saved_cameras([])

                        print("Cleared all camera presets.")

                    elif action == "reset_venue":

                        admin_fields["name"] = "Default Venue"

                        admin_fields["shape"] = "rectangle"

                        admin_fields["length"] = "10.0"

                        admin_fields["width"] = "10.0"

                        admin_fields["capacity"] = "100"

                        admin_fields["warning"] = "70"

                        admin_fields["critical"] = "90"

                        admin_fields["grid"] = "5.0"

                        print("Reset venue settings to default.")

                    pending_confirmation = None

                    return



            if confirm_no_rect:

                x1, y1, x2, y2 = confirm_no_rect

                if x1 <= x <= x2 and y1 <= y <= y2:

                    pending_confirmation = None

                    return



            # Block other clicks while modal is open

            return



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

        # DELETE SAVED CAMERA (WITH CONFIRMATION)

        # ====================================================



        for index, rect in saved_camera_delete_rects:



            x1, y1, x2, y2 = rect



            if (

                x1 <= x <= x2

                and

                y1 <= y <= y2

            ):

                cam_name = saved_cameras[index].get("name", f"Camera {index + 1}") if index < len(saved_cameras) else "Camera"

                pending_confirmation = {

                    "action": "delete_camera",

                    "index": index,

                    "label": f"Delete '{cam_name}' preset?"

                }

                return



        # ====================================================

        # DANGER ZONE ACTIONS (WITH CONFIRMATION)

        # ====================================================

        if reset_calibration_button_rect:

            x1, y1, x2, y2 = reset_calibration_button_rect

            if x1 <= x <= x2 and y1 <= y <= y2:

                pending_confirmation = {

                    "action": "reset_calibration",

                    "label": "Reset all camera calibration mapping?"

                }

                return



        if clear_cameras_button_rect:

            x1, y1, x2, y2 = clear_cameras_button_rect

            if x1 <= x <= x2 and y1 <= y <= y2:

                pending_confirmation = {

                    "action": "clear_cameras",

                    "label": "Clear all saved camera presets?"

                }

                return



        if reset_venue_button_rect:

            x1, y1, x2, y2 = reset_venue_button_rect

            if x1 <= x <= x2 and y1 <= y <= y2:

                pending_confirmation = {

                    "action": "reset_venue",

                    "label": "Reset venue configuration to defaults?"

                }

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

                    top <= y <= top + 90

                ):



                    if y < top + 45:



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

        0.40,

        (215, 225, 235),

        1

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

        0.42,

        WHITE,

        1

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

        0.34,

        GRAY,

        1

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

        0.38,

        (175, 190, 205),

        1

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

        0.40,

        WHITE,

        1

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

        0.40,

        GREEN,

        1

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

        0.36,

        YELLOW,

        1

    )



    text(

        frame,

        "Set to 5 for testing:",

        (365, 275),

        0.34,

        (215, 225, 235),

        1

    )



    text(

        frame,

        "1 detected person → 5 counted people",

        (365, 300),

        0.36,

        YELLOW,

        1

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

        0.36,

        plan_color,

        1

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

        0.34,

        (175, 190, 205),

        1

    )



    text(

        frame,

        "ESC = EXIT",

        (830, 520),

        0.34,

        (175, 190, 205),

        1

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

            0.40,

            WHITE,

            1

        )



        text(

            frame,

            "CIRCLE",

            (x1 + 10, y2 + 58),

            0.40,

            WHITE,

            1

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
    global reset_calibration_button_rect
    global clear_cameras_button_rect
    global reset_venue_button_rect
    global confirm_yes_rect
    global confirm_no_rect
    global pending_confirmation

    # High-contrast color palette for maximum legibility on dark background
    frame[:] = BLACK

    field_rects = {}
    saved_camera_select_rects = []
    saved_camera_delete_rects = []

    W = ADMIN_WIDTH    # 1320
    H = ADMIN_HEIGHT   # 800

    # High-contrast text colors
    TEXT_WHITE = (252, 252, 252)
    TEXT_LABEL = (215, 225, 235)      # Crisp light silver (never faint)
    TEXT_MUTED = (175, 190, 205)      # Soft slate for hints (100% visible)
    BORDER_DIM = (65, 50, 40)         # Panel borders

    # Helper: dedicated admin input field drawer with sharp high-contrast text
    def draw_admin_field(name, label, value, rect):
        field_rects[name] = rect
        x1, y1, x2, y2 = rect

        # Crisp label above input box (scale 0.44, light silver, thickness 1, anti-aliased)
        cv2.putText(frame, str(label), (x1, y1 - 8), FONT, 0.44, TEXT_LABEL, 1, cv2.LINE_AA)

        # Field background box
        cv2.rectangle(frame, (x1, y1), (x2, y2), FIELD_DARK, -1)

        # Highlight border: RED when focused, GREEN when idle
        border_col = RED if active_field == name else GREEN
        cv2.rectangle(frame, (x1, y1), (x2, y2), border_col, 2, cv2.LINE_AA)

        # Value text inside box: scale 0.48, bright white, centered vertically
        display_val = str(value)
        if len(display_val) > 32:
            display_val = display_val[:29] + "..."
        cv2.putText(frame, display_val, (x1 + 12, y1 + 25), FONT, 0.48, TEXT_WHITE, 1, cv2.LINE_AA)

    # --------------------------------------------------------
    # TOP HEADER BAR
    # --------------------------------------------------------
    cv2.rectangle(frame, (0, 0), (W, 62), ELEVATED, -1)
    cv2.line(frame, (0, 62), (W, 62), BORDER_DIM, 1)
    cv2.rectangle(frame, (0, 0), (8, 62), GREEN, -1)

    text(frame, "CROWDSENSE", (24, 42), 0.72, GREEN, 2)
    text(frame, "|  ADMIN CONTROL CENTER", (240, 42), 0.52, TEXT_WHITE, 2)
    text(frame, "S = Save & Run  |  ESC = Back  |  C = Calibrate  |  T = Test Alert", (720, 41), 0.44, TEXT_MUTED, 1)

    # Column Layout
    LX1, LX2 = 18, 644
    RX1, RX2 = 660, 1302
    PAD = 18

    # ========================================================
    # 1. SYSTEM OVERVIEW (Left top)
    # ========================================================
    P1Y1, P1Y2 = 76, 224
    panel(frame, LX1, P1Y1, LX2, P1Y2, DARK, BORDER_DIM, 1)
    text(frame, "1. SYSTEM OVERVIEW", (LX1 + PAD, 108), 0.50, GREEN, 2)

    sys_status = "ACTIVE" if cap is not None and cap.isOpened() else "READY"
    calib_status = "CALIBRATED" if calibration.matrix is not None else "NOT CALIBRATED"
    calib_color = GREEN if calibration.matrix is not None else YELLOW

    src_text = str(admin_fields.get("camera", "0"))
    if len(src_text) > 22:
        src_text = src_text[:19] + "..."
    cap_text = f"{venue.capacity} max ({len(zone_manager.zones)} zones)"

    # Metric Row 1
    text(frame, "SYSTEM STATUS:", (LX1 + PAD, 148), 0.42, TEXT_LABEL, 1)
    text(frame, sys_status, (LX1 + PAD + 145, 148), 0.46, GREEN if sys_status == "ACTIVE" else TEXT_WHITE, 2)
    text(frame, "ACTIVE SOURCE:", (330, 148), 0.42, TEXT_LABEL, 1)
    text(frame, src_text, (475, 148), 0.44, TEXT_WHITE, 1)

    # Metric Row 2
    text(frame, "CALIBRATION:", (LX1 + PAD, 182), 0.42, TEXT_LABEL, 1)
    text(frame, calib_status, (LX1 + PAD + 145, 182), 0.44, calib_color, 2)
    text(frame, "CAPACITY:", (330, 182), 0.42, TEXT_LABEL, 1)
    text(frame, cap_text, (475, 182), 0.44, TEXT_WHITE, 1)

    # Footnote
    text(frame, "Live telemetry from backend pipeline. Updates on save.", (LX1 + PAD, 212), 0.38, TEXT_MUTED, 1)

    # ========================================================
    # 2. VENUE CONFIGURATION (Left, below overview)
    # ========================================================
    P2Y1, P2Y2 = 236, 708
    panel(frame, LX1, P2Y1, LX2, P2Y2, DARK, BORDER_DIM, 1)
    text(frame, "2. VENUE CONFIGURATION", (LX1 + PAD, 268), 0.50, GREEN, 2)

    # Venue Name
    draw_admin_field("name", "VENUE NAME", admin_fields["name"], (LX1 + PAD, 308, LX2 - PAD, 346))

    # Venue Shape
    text(frame, "VENUE SHAPE", (LX1 + PAD, 372), 0.44, TEXT_LABEL, 1)
    shape_rect = (LX1 + PAD, 380, LX2 - PAD, 418)
    sx1, sy1, sx2, sy2 = shape_rect
    cv2.rectangle(frame, (sx1, sy1), (sx2, sy2), FIELD_DARK, -1)
    cv2.rectangle(frame, (sx1, sy1), (sx2, sy2), BORDER_DIM, 1)
    text(frame, admin_fields["shape"].upper() + "   v", (sx1 + 14, 405), 0.48, TEXT_WHITE, 2)

    # Dimensions
    half_w = (LX2 - PAD - (LX1 + PAD) - 16) // 2
    if admin_fields["shape"] == "rectangle":
        draw_admin_field("length", "LENGTH (m)", admin_fields["length"], (LX1 + PAD, 452, LX1 + PAD + half_w, 490))
        draw_admin_field("width", "WIDTH (m)", admin_fields["width"], (LX2 - PAD - half_w, 452, LX2 - PAD, 490))
    else:
        draw_admin_field("diameter", "DIAMETER (m)", admin_fields["diameter"], (LX1 + PAD, 452, LX2 - PAD, 490))

    # Capacity and Grid
    draw_admin_field("capacity", "CAPACITY (MAX PEOPLE)", admin_fields["capacity"], (LX1 + PAD, 524, LX1 + PAD + half_w, 562))
    draw_admin_field("grid", "ZONE GRID SIZE (m)", admin_fields["grid"], (LX2 - PAD - half_w, 524, LX2 - PAD, 562))

    # Thresholds
    draw_admin_field("warning", "WARNING THRESHOLD (%)", admin_fields["warning"], (LX1 + PAD, 596, LX1 + PAD + half_w, 634))
    draw_admin_field("critical", "CRITICAL THRESHOLD (%)", admin_fields["critical"], (LX2 - PAD - half_w, 596, LX2 - PAD, 634))

    # Footnotes
    if admin_fields["shape"] == "rectangle":
        l_val = admin_fields.get("length", "0")
        w_val = admin_fields.get("width", "0")
        dim_info = f"Footprint: {l_val}m x {w_val}m (Rectangular Arena)"
    else:
        d_val = admin_fields.get("diameter", "0")
        dim_info = f"Diameter: {d_val}m (Circular Arena)"
    text(frame, dim_info, (LX1 + PAD, 668), 0.40, TEXT_LABEL, 1)
    text(frame, "Click any field to edit. Press Enter to confirm.", (LX1 + PAD, 694), 0.38, TEXT_MUTED, 1)

    # ========================================================
    # 3. CAMERA MANAGEMENT (Right top)
    # ========================================================
    P3Y1, P3Y2 = 76, 360
    panel(frame, RX1, P3Y1, RX2, P3Y2, DARK, BORDER_DIM, 1)
    text(frame, "3. CAMERA MANAGEMENT", (RX1 + PAD, 108), 0.50, GREEN, 2)

    cname_w = 210
    cbtn_w = 84
    csrc_w = (RX2 - PAD) - (RX1 + PAD + cname_w + 14) - (cbtn_w + 14)

    draw_admin_field("camera_name", "CAMERA NAME", admin_fields["camera_name"], (RX1 + PAD, 148, RX1 + PAD + cname_w, 186))
    draw_admin_field("camera", "SOURCE (0, 1, or URL)", admin_fields["camera"], (RX1 + PAD + cname_w + 14, 148, RX1 + PAD + cname_w + 14 + csrc_w, 186))
    save_camera_button_rect = (RX2 - PAD - cbtn_w, 148, RX2 - PAD, 186)
    button(frame, "SAVE", save_camera_button_rect, GREEN, 0.44)

    cv2.line(frame, (RX1 + PAD, 202), (RX2 - PAD, 202), BORDER_DIM, 1)
    text(frame, "SAVED CAMERA PRESETS", (RX1 + PAD, 226), 0.42, TEXT_LABEL, 1)

    max_visible = 3
    visible_cameras = saved_cameras[:max_visible]
    if not visible_cameras:
        text(frame, "No saved camera presets. Enter name & source above and click SAVE.", (RX1 + PAD, 260), 0.40, TEXT_MUTED, 1)
    else:
        for idx, cam in enumerate(visible_cameras):
            ry = 244 + idx * 38
            cn = cam.get("name", f"Cam {idx + 1}")
            cs = str(cam.get("source", ""))
            if len(cs) > 28:
                cs = cs[:25] + "..."

            text(frame, f"{idx + 1}. {cn}", (RX1 + PAD, ry + 22), 0.44, TEXT_WHITE, 2)
            text(frame, cs, (RX1 + PAD + 200, ry + 22), 0.42, TEXT_LABEL, 1)

            sel_r = (RX2 - PAD - 170, ry + 2, RX2 - PAD - 90, ry + 32)
            saved_camera_select_rects.append((idx, sel_r))
            button(frame, "SELECT", sel_r, GREEN, 0.38)

            del_r = (RX2 - PAD - 80, ry + 2, RX2 - PAD, ry + 32)
            saved_camera_delete_rects.append((idx, del_r))
            button(frame, "DELETE", del_r, RED, 0.38)

    # ========================================================
    # 4. MONITORING CONTROLS (Right middle)
    # ========================================================
    P4Y1, P4Y2 = 372, 548
    panel(frame, RX1, P4Y1, RX2, P4Y2, DARK, BORDER_DIM, 1)
    text(frame, "4. MONITORING CONTROLS", (RX1 + PAD, 404), 0.50, GREEN, 2)

    draw_admin_field("test_multiplier", "TEST MULTIPLIER", admin_fields["test_multiplier"], (RX1 + PAD, 442, RX1 + PAD + 190, 480))
    text(frame, f"(1 detected person = {get_test_multiplier()} counted)", (RX1 + PAD + 208, 466), 0.42, YELLOW, 1)

    bw3 = (RX2 - PAD - (RX1 + PAD) - 28) // 3
    b1_x1 = RX1 + PAD
    b2_x1 = b1_x1 + bw3 + 14
    b3_x1 = b2_x1 + bw3 + 14

    calibration_button_rect = (b1_x1, 494, b1_x1 + bw3, 536)
    floorplan_button_rect = (b2_x1, 494, b2_x1 + bw3, 536)
    test_alert_button_rect = (b3_x1, 494, RX2 - PAD, 536)

    button(frame, "CALIBRATE (C)", calibration_button_rect, GREEN, 0.44)
    button(frame, "FLOOR PLAN", floorplan_button_rect, GREEN, 0.44)
    button(frame, "TEST ALERT", test_alert_button_rect, RED, 0.44)

    # ========================================================
    # 5. DANGER ZONE (Right bottom)
    # ========================================================
    P5Y1, P5Y2 = 560, 708
    panel(frame, RX1, P5Y1, RX2, P5Y2, DARK, (45, 45, 80), 1)
    text(frame, "5. DANGER ZONE", (RX1 + PAD, 592), 0.50, RED, 2)

    reset_calibration_button_rect = (b1_x1, 612, b1_x1 + bw3, 654)
    clear_cameras_button_rect = (b2_x1, 612, b2_x1 + bw3, 654)
    reset_venue_button_rect = (b3_x1, 612, RX2 - PAD, 654)

    button(frame, "RESET CALIB", reset_calibration_button_rect, RED, 0.44)
    button(frame, "CLEAR PRESETS", clear_cameras_button_rect, RED, 0.44)
    button(frame, "RESET VENUE", reset_venue_button_rect, RED, 0.44)

    text(frame, "Destructive actions require confirmation dialog.", (RX1 + PAD, 690), 0.38, TEXT_MUTED, 1)

    # ========================================================
    # BOTTOM ACTION BAR
    # ========================================================
    cv2.line(frame, (0, 718), (W, 718), BORDER_DIM, 1)
    save_button_rect = (LX1, 726, LX1 + 242, 782)
    cancel_button_rect = (LX1 + 258, 726, LX1 + 438, 782)

    button(frame, "SAVE & APPLY (S)", save_button_rect, GREEN, 0.48)
    button(frame, "CANCEL (ESC)", cancel_button_rect, (120, 120, 130), 0.48)
    text(frame, "All settings persist immediately upon Save. Press 'S' to Save & Run. Press 'ESC' to exit.", (LX1 + 458, 758), 0.40, TEXT_LABEL, 1)

    # ========================================================
    # SHAPE DROPDOWN (if open)
    # ========================================================
    if shape_dropdown_open:
        x1, y1, x2, y2 = shape_rect
        cv2.rectangle(frame, (x1, y2), (x2, y2 + 90), ELEVATED, -1)
        cv2.rectangle(frame, (x1, y2), (x2, y2 + 90), GREEN, 2)
        cv2.line(frame, (x1, y2 + 45), (x2, y2 + 45), BORDER_DIM, 1)
        text(frame, "RECTANGLE", (x1 + 16, y2 + 30), 0.46, TEXT_WHITE, 2)
        text(frame, "CIRCLE", (x1 + 16, y2 + 75), 0.46, TEXT_WHITE, 2)

    # ========================================================
    # DESTRUCTIVE CONFIRMATION MODAL (if active)
    # ========================================================
    if pending_confirmation:
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (W, H), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.72, frame, 0.28, 0, frame)

        dlg_x1, dlg_y1, dlg_x2, dlg_y2 = 380, 260, 940, 500
        cv2.rectangle(frame, (dlg_x1, dlg_y1), (dlg_x2, dlg_y2), ELEVATED, -1)
        cv2.rectangle(frame, (dlg_x1, dlg_y1), (dlg_x2, dlg_y2), RED, 2)

        text(frame, "CONFIRM DESTRUCTIVE ACTION", (dlg_x1 + 32, dlg_y1 + 52), 0.54, RED, 2)
        p_msg = pending_confirmation.get("label", "Are you sure you want to proceed?")
        text(frame, p_msg, (dlg_x1 + 32, dlg_y1 + 104), 0.44, TEXT_WHITE, 1)

        confirm_yes_rect = (dlg_x1 + 32, dlg_y1 + 150, dlg_x1 + 250, dlg_y1 + 200)
        confirm_no_rect = (dlg_x1 + 280, dlg_y1 + 150, dlg_x1 + 498, dlg_y1 + 200)

        button(frame, "YES, PROCEED", confirm_yes_rect, RED, 0.44)
        button(frame, "CANCEL", confirm_no_rect, (120, 120, 130), 0.44)



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

        0.36,

        GRAY,

        1

    )



    text(

        frame,

        "PEOPLE",

        (22, 86),

        0.34,

        GRAY,

        1

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

        0.36,

        GRAY,

        1

    )



    multiplier = get_test_multiplier()



    if multiplier > 1:



        text(

            frame,

            f"TEST {multiplier}x",

            (220, 87),

            0.34,

            YELLOW,

            1

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

        0.34,

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

        0.33,

        calibration_color,

        1

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

        0.36

    )



    text(

        frame,

        "G",

        (140, 132),

        0.35,

        GREEN,

        2

    )



    text(

        frame,

        "GRID",

        (153, 132),

        0.35,

        GRAY,

        2

    )



    text(

        frame,

        "C",

        (205, 132),

        0.35,

        GREEN,

        2

    )



    text(

        frame,

        "CALIBRATE",

        (218, 132),

        0.35,

        GRAY,

        2

    )



    text(

        frame,

        "Q",

        (CAMERA_WIDTH - 45, 132),

        0.35,

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



        set_camera_switch_callback(

            on_web_camera_switch

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





# ------------------------------------------------------------
# STARTUP PROGRESS LOADING BAR
# ------------------------------------------------------------
def _show_initial_startup_progress():
    try:
        W = CAMERA_WIDTH
        H = CAMERA_HEIGHT
        _sframe = np.zeros((H, W, 3), dtype=np.uint8)
        _steps = [
            (18, "STARTING CROWDSENSE...", "Loading system configuration"),
            (42, "STARTING CROWDSENSE...", "Initializing YOLO detection engine"),
            (68, "STARTING CROWDSENSE...", "Configuring physical venue & zones"),
            (88, "STARTING CROWDSENSE...", "Launching local telemetry services"),
            (100, "CROWDSENSE READY", "Opening Admin Setup Interface..."),
        ]
        for _pct, _t1, _t2 in _steps:
            _sframe[:] = BLACK
            text(_sframe, "CROWDSENSE", (W // 2 - 130, H // 2 - 60), 0.85, GREEN, 2)
            text(_sframe, _t1, (W // 2 - 160, H // 2 - 15), 0.55, (252, 252, 252), 2)
            text(_sframe, _t2, (W // 2 - 190, H // 2 + 18), 0.38, (175, 190, 205), 1)
            _bw = 420
            _bh = 14
            _bx1 = (W - _bw) // 2
            _by1 = H // 2 + 45
            _bx2 = _bx1 + _bw
            _by2 = _by1 + _bh
            cv2.rectangle(_sframe, (_bx1, _by1), (_bx2, _by2), (25, 32, 45), -1)
            cv2.rectangle(_sframe, (_bx1, _by1), (_bx2, _by2), (65, 80, 100), 1)
            _fill = int(_bw * (_pct / 100.0))
            if _fill > 0:
                cv2.rectangle(_sframe, (_bx1, _by1), (_bx1 + _fill, _by2), GREEN, -1)
            text(_sframe, f"{_pct}%", (_bx2 + 12, _by1 + 12), 0.40, GREEN, 1)
            cv2.imshow(WINDOW_NAME, _sframe)
            cv2.waitKey(100)
    except Exception:
        pass

_show_initial_startup_progress()

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

                ADMIN_HEIGHT,

                ADMIN_WIDTH,

                3

            ),

            dtype=np.uint8

        )



        draw_admin_screen(

            admin_frame

        )



        cv2.resizeWindow(WINDOW_NAME, ADMIN_WIDTH, ADMIN_HEIGHT)

        cv2.imshow(

            WINDOW_NAME,

            admin_frame

        )



        key = cv2.waitKeyEx(20)



        key_ascii = key & 0xFF



        if key_ascii == 27:
            current_mode = MODE_MONITOR
            cv2.resizeWindow(WINDOW_NAME, CAMERA_WIDTH, CAMERA_HEIGHT)
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
        cv2.resizeWindow(WINDOW_NAME, CAMERA_WIDTH, CAMERA_HEIGHT)




        # ----------------------------------------------------

        # WEB CAMERA SWITCH SYNC

        # ----------------------------------------------------

        if requested_camera_switch is not None:

            sw_camera = requested_camera_switch

            requested_camera_switch = None

            try:

                new_src = sw_camera.get("source")

                new_name = sw_camera.get("name", "Camera")

                if new_src is not None:

                    admin_fields["camera"] = str(new_src)

                    admin_fields["camera_name"] = str(new_name)

                    print(f"[SWITCH] Switching active camera to: {new_name} ({new_src})")

                    start_camera()

                    continue

            except Exception as sw_err:

                print(f"[SWITCH ERROR] {sw_err}")



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

