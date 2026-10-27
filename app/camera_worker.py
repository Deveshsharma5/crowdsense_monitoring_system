import cv2
import threading
import time
from datetime import datetime

from ultralytics import YOLO


# ============================================================
# CAMERA WORKER
# ============================================================

class CameraWorker:

    def __init__(
        self,
        camera_id,
        source,
        model_path="yolo11n.pt",
        width=960,
        height=540,
        confidence=0.25,
        reconnect_seconds=3
    ):

        self.camera_id = str(camera_id)

        self.source = self._convert_source(
            source
        )

        self.model_path = model_path

        self.width = width
        self.height = height

        self.confidence = confidence

        self.reconnect_seconds = (
            reconnect_seconds
        )

        # ----------------------------------------------------
        # Thread control
        # ----------------------------------------------------

        self.running = False
        self.thread = None

        self.lock = threading.Lock()

        # ----------------------------------------------------
        # Camera
        # ----------------------------------------------------

        self.cap = None

        # ----------------------------------------------------
        # AI
        # ----------------------------------------------------

        self.model = None

        # ----------------------------------------------------
        # Latest result
        # ----------------------------------------------------

        self.latest_result = {

            "camera_id":
                self.camera_id,

            "source":
                str(self.source),

            "status":
                "STOPPED",

            "people":
                0,

            "detections":
                [],

            "frame":
                None,

            "timestamp":
                None,

            "error":
                None
        }

        self.last_error = None

        self.last_frame_time = None

        self.last_reconnect_time = 0


    # ========================================================
    # SOURCE CONVERSION
    # ========================================================

    def _convert_source(
        self,
        source
    ):

        if isinstance(
            source,
            int
        ):

            return source

        source = str(
            source
        ).strip()

        if source.isdigit():

            return int(
                source
            )

        return source


    # ========================================================
    # LOAD MODEL
    # ========================================================

    def _load_model(self):

        if self.model is not None:

            return True

        try:

            print(
                f"[{self.camera_id}] "
                f"Loading YOLO model..."
            )

            self.model = YOLO(
                self.model_path
            )

            print(
                f"[{self.camera_id}] "
                f"YOLO model loaded."
            )

            return True

        except Exception as error:

            self.last_error = str(
                error
            )

            print(
                f"[{self.camera_id}] "
                f"YOLO load error: {error}"
            )

            return False


    # ========================================================
    # OPEN CAMERA
    # ========================================================

    def _open_camera(self):

        try:

            if self.cap is not None:

                try:

                    self.cap.release()

                except Exception:
                    pass

                self.cap = None

            print(
                f"[{self.camera_id}] "
                f"Opening camera: {self.source}"
            )

            # ------------------------------------------------
            # Open the camera
            # ------------------------------------------------

            from stream_capture import LowLatencyVideoCapture

            self.cap = LowLatencyVideoCapture(
                self.source,
                width=self.width,
                height=self.height
            )

            if not self.cap.isOpened():

                print(
                    f"[{self.camera_id}] "
                    f"Camera could not be opened."
                )

                try:

                    self.cap.release()

                except Exception:
                    pass

                self.cap = None

                return False

            # ------------------------------------------------
            # Resolution & Buffering
            # ------------------------------------------------

            self.cap.set(
                cv2.CAP_PROP_FRAME_WIDTH,
                self.width
            )

            self.cap.set(
                cv2.CAP_PROP_FRAME_HEIGHT,
                self.height
            )

            try:
                self.cap.set(
                    cv2.CAP_PROP_BUFFERSIZE,
                    1
                )
            except Exception:
                pass

            self.last_error = None

            print(
                f"[{self.camera_id}] "
                f"Camera connected."
            )

            return True

        except Exception as error:

            self.last_error = str(
                error
            )

            print(
                f"[{self.camera_id}] "
                f"Camera open error: {error}"
            )

            self.cap = None

            return False


    # ========================================================
    # PROCESS FRAME
    # ========================================================

    def _process_frame(
        self,
        frame
    ):

        detections = []

        people_count = 0

        try:

            if self.model is None:

                if not self._load_model():

                    return (
                        frame,
                        detections,
                        people_count
                    )

            results = self.model.track(

                frame,

                persist=True,

                classes=[0],

                conf=self.confidence,

                verbose=False
            )

            if (
                results
                and
                results[0].boxes is not None
            ):

                boxes = results[0].boxes

                people_count = len(
                    boxes
                )

                for index, box in enumerate(
                    boxes
                ):

                    x1, y1, x2, y2 = map(
                        int,
                        box.xyxy[0]
                        .cpu()
                        .tolist()
                    )

                    # ----------------------------------------
                    # Track ID
                    # ----------------------------------------

                    if boxes.id is not None:

                        track_id = int(
                            boxes.id[
                                index
                            ].item()
                        )

                    else:

                        track_id = (
                            index + 1
                        )

                    # ----------------------------------------
                    # Bottom center / foot point
                    # ----------------------------------------

                    foot_x = int(
                        (x1 + x2) / 2
                    )

                    foot_y = int(
                        y2
                    )

                    # ----------------------------------------
                    # Confidence
                    # ----------------------------------------

                    try:

                        confidence = float(
                            box.conf[
                                0
                            ].item()
                        )

                    except Exception:

                        confidence = 0.0

                    detections.append({

                        "id":
                            track_id,

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

                        "confidence":
                            round(
                                confidence,
                                4
                            )
                    })

            for item in detections:
                bx1, by1, bx2, by2 = item["box"]
                tid = item["id"]
                conf = item.get("confidence", 0)
                cv2.rectangle(
                    frame,
                    (bx1, by1),
                    (bx2, by2),
                    (129, 185, 16),
                    2,
                    cv2.LINE_AA
                )
                cv2.putText(
                    frame,
                    f"#{tid} ({int(conf * 100)}%)",
                    (bx1, max(20, by1 - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.42,
                    (255, 255, 255),
                    1,
                    cv2.LINE_AA
                )

            return (
                frame,
                detections,
                people_count
            )

        except Exception as error:

            self.last_error = str(
                error
            )

            print(
                f"[{self.camera_id}] "
                f"Inference error: {error}"
            )

            # ------------------------------------------------
            # IMPORTANT:
            # Even if YOLO fails, return the camera frame.
            # The stream should continue working.
            # ------------------------------------------------

            return (
                frame,
                detections,
                people_count
            )


    # ========================================================
    # UPDATE LIVE FRAME
    # ========================================================

    def _update_live_frame(
        self,
        frame,
        status="CONNECTED",
        error=None
    ):

        timestamp = (
            datetime.now()
            .strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        )

        with self.lock:

            current = dict(
                self.latest_result
            )

            current["camera_id"] = (
                self.camera_id
            )

            current["source"] = (
                str(self.source)
            )

            current["status"] = (
                status
            )

            current["frame"] = (
                frame.copy()
                if frame is not None
                else None
            )

            current["timestamp"] = (
                timestamp
            )

            current["error"] = (
                error
            )

            self.latest_result = current


    # ========================================================
    # WORKER LOOP
    # ========================================================

    def _worker_loop(self):

        print(
            f"[{self.camera_id}] "
            f"Worker started."
        )

        # ----------------------------------------------------
        # YOLO loading is attempted here.
        #
        # If it fails, we still allow the camera stream
        # to operate. Detection will simply remain empty.
        # ----------------------------------------------------

        model_loaded = self._load_model()

        if not model_loaded:

            self._set_status(
                "CONNECTED",
                error=self.last_error
            )

        while self.running:

            # ------------------------------------------------
            # CAMERA CONNECTION
            # ------------------------------------------------

            if self.cap is None:

                now = time.time()

                if (
                    now -
                    self.last_reconnect_time
                    <
                    self.reconnect_seconds
                ):

                    time.sleep(
                        0.1
                    )

                    continue

                self.last_reconnect_time = (
                    now
                )

                if not self._open_camera():

                    self._set_status(
                        "DISCONNECTED",
                        error=self.last_error
                    )

                    time.sleep(
                        0.5
                    )

                    continue

            # ------------------------------------------------
            # READ FRAME
            # ------------------------------------------------

            success, frame = (
                self.cap.read()
            )

            if not success:

                self.last_error = (
                    "Camera frame unavailable"
                )

                self._set_status(
                    "DISCONNECTED",
                    error=self.last_error
                )

                try:

                    self.cap.release()

                except Exception:
                    pass

                self.cap = None

                time.sleep(
                    0.2
                )

                continue

            # ------------------------------------------------
            # RESIZE
            # ------------------------------------------------

            try:

                frame = cv2.resize(
                    frame,
                    (
                        self.width,
                        self.height
                    ),
                    interpolation=cv2.INTER_AREA
                )

            except Exception as error:

                self.last_error = str(
                    error
                )

                continue

            # ------------------------------------------------
            # IMPORTANT:
            #
            # Save the raw camera frame BEFORE YOLO inference.
            #
            # This means the browser can receive the camera
            # stream even if YOLO takes time to process.
            # ------------------------------------------------

            self.last_frame_time = (
                time.time()
            )

            self._update_live_frame(
                frame,
                status="CONNECTED",
                error=None
            )

            # ------------------------------------------------
            # AI PROCESSING
            # ------------------------------------------------

            (
                processed_frame,
                detections,
                people_count
            ) = self._process_frame(
                frame
            )

            # ------------------------------------------------
            # TIMESTAMP
            # ------------------------------------------------

            timestamp = (
                datetime.now()
                .strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            )

            # ------------------------------------------------
            # SAVE PROCESSED RESULT
            # ------------------------------------------------

            with self.lock:

                self.latest_result = {

                    "camera_id":
                        self.camera_id,

                    "source":
                        str(self.source),

                    "status":
                        "CONNECTED",

                    "people":
                        people_count,

                    "detections":
                        detections,

                    "frame":
                        processed_frame.copy(),

                    "timestamp":
                        timestamp,

                    "error":
                        None
                }

        # ----------------------------------------------------
        # WORKER STOPPED
        # ----------------------------------------------------

        self._release_camera()

        self._set_status(
            "STOPPED"
        )

        print(
            f"[{self.camera_id}] "
            f"Worker stopped."
        )


    # ========================================================
    # START
    # ========================================================

    def start(self):

        if self.running:

            return True

        self.running = True

        self.thread = threading.Thread(

            target=self._worker_loop,

            name=(
                f"CrowdSense-{self.camera_id}"
            ),

            daemon=True
        )

        self.thread.start()

        return True


    # ========================================================
    # STOP
    # ========================================================

    def stop(self):

        self.running = False

        if (
            self.thread is not None
            and
            self.thread.is_alive()
        ):

            self.thread.join(
                timeout=3
            )

        self.thread = None

        self._release_camera()

        self._set_status(
            "STOPPED"
        )


    # ========================================================
    # RELEASE CAMERA
    # ========================================================

    def _release_camera(self):

        if self.cap is not None:

            try:

                self.cap.release()

            except Exception:
                pass

            self.cap = None


    # ========================================================
    # UPDATE STATUS
    # ========================================================

    def _set_status(
        self,
        status,
        error=None
    ):

        with self.lock:

            current = dict(
                self.latest_result
            )

            current["status"] = (
                status
            )

            current["error"] = (
                error
            )

            self.latest_result = (
                current
            )


    # ========================================================
    # GET RESULT
    # ========================================================

    def get_result(self):

        with self.lock:

            result = dict(
                self.latest_result
            )

            if result.get(
                "detections"
            ):

                result["detections"] = [

                    dict(item)

                    for item in
                    result["detections"]

                ]

            if result.get(
                "frame"
            ) is not None:

                result["frame"] = (
                    result["frame"].copy()
                )

            return result


    # ========================================================
    # GET STATUS
    # ========================================================

    def get_status(self):

        with self.lock:

            return {

                "camera_id":
                    self.camera_id,

                "source":
                    str(self.source),

                "status":
                    self.latest_result.get(
                        "status",
                        "STOPPED"
                    ),

                "people":
                    self.latest_result.get(
                        "people",
                        0
                    ),

                "timestamp":
                    self.latest_result.get(
                        "timestamp"
                    ),

                "error":
                    self.latest_result.get(
                        "error"
                    )
            }


    # ========================================================
    # IS RUNNING
    # ========================================================

    def is_running(self):

        return (
            self.running
            and
            self.thread is not None
            and
            self.thread.is_alive()
        )