import json
import os
import threading
import cv2
from datetime import datetime

from camera_worker import CameraWorker


# ============================================================
# CAMERA MANAGER
# ============================================================

CAMERA_FOLDER = "data"

CAMERA_FILE = os.path.join(
    CAMERA_FOLDER,
    "camera_config.json"
)


class CameraManager:

    def __init__(
        self,
        model_path="yolo11n.pt",
        width=960,
        height=540
    ):

        self.model_path = model_path
        self.width = width
        self.height = height

        self.lock = threading.RLock()

        self.cameras = []
        self.workers = {}

        # ----------------------------------------------------
        # Currently active web camera
        # ----------------------------------------------------

        self.active_camera_id = None

        os.makedirs(
            CAMERA_FOLDER,
            exist_ok=True
        )

        self.load()

    # ========================================================
    # LOAD
    # ========================================================

    def load(self):

        if not os.path.exists(CAMERA_FILE):

            self.cameras = []
            return

        try:

            with open(
                CAMERA_FILE,
                "r",
                encoding="utf-8"
            ) as file:

                data = json.load(file)

            if isinstance(data, dict):

                cameras = data.get(
                    "cameras",
                    []
                )

            elif isinstance(data, list):

                cameras = data

            else:

                cameras = []

            if not isinstance(cameras, list):

                cameras = []

            self.cameras = []

            for camera in cameras:

                if not isinstance(camera, dict):
                    continue

                self.cameras.append(
                    self._normalise_camera(camera)
                )

        except Exception as error:

            print(
                f"Camera config load error: {error}"
            )

            self.cameras = []

    # ========================================================
    # SAVE
    # ========================================================

    def save(self):

        os.makedirs(
            CAMERA_FOLDER,
            exist_ok=True
        )

        try:

            with open(
                CAMERA_FILE,
                "w",
                encoding="utf-8"
            ) as file:

                json.dump(
                    {
                        "cameras": self.cameras
                    },
                    file,
                    indent=4
                )

            return True

        except Exception as error:

            print(
                f"Camera config save error: {error}"
            )

            return False

    # ========================================================
    # NORMALISE CAMERA
    # ========================================================

    def _normalise_camera(
        self,
        camera
    ):

        camera = dict(camera)

        camera_id = str(
            camera.get(
                "camera_id",
                camera.get(
                    "id",
                    ""
                )
            )
        ).strip()

        if not camera_id:

            camera_id = (
                self._next_camera_id()
            )

        name = str(
            camera.get(
                "name",
                camera_id
            )
        ).strip()

        source = str(
            camera.get(
                "source",
                camera.get(
                    "url",
                    "0"
                )
            )
        ).strip()

        enabled = camera.get(
            "enabled",
            True
        )

        if isinstance(
            enabled,
            str
        ):

            enabled = (
                enabled.lower()
                in (
                    "true",
                    "1",
                    "yes",
                    "on"
                )
            )

        return {

            "camera_id":
                camera_id,

            "name":
                name,

            "source":
                source,

            "enabled":
                bool(enabled),

            "status":
                camera.get(
                    "status",
                    "DISCONNECTED"
                ),

            "people":
                int(
                    camera.get(
                        "people",
                        0
                    ) or 0
                ),

            "last_check":
                camera.get(
                    "last_check"
                ),

            "error":
                camera.get(
                    "error"
                )
        }

    # ========================================================
    # NEXT CAMERA ID
    # ========================================================

    def _next_camera_id(self):

        existing = {

            str(
                camera.get(
                    "camera_id",
                    ""
                )
            )

            for camera in self.cameras

        }

        number = 1

        while (
            f"CAM{number}"
            in existing
        ):

            number += 1

        return f"CAM{number}"

    # ========================================================
    # ADD CAMERA
    # ========================================================

    def add_camera(
        self,
        name,
        source,
        enabled=True,
        camera_id=None
    ):

        name = str(
            name
        ).strip()

        source = str(
            source
        ).strip()

        if not name:

            raise ValueError(
                "Camera name is required."
            )

        if not source:

            raise ValueError(
                "Camera source is required."
            )

        with self.lock:

            if camera_id:

                camera_id = str(
                    camera_id
                ).strip()

            else:

                camera_id = (
                    self._next_camera_id()
                )

            for camera in self.cameras:

                if str(
                    camera.get(
                        "camera_id"
                    )
                ) == camera_id:

                    raise ValueError(
                        f"Camera {camera_id} "
                        f"already exists."
                    )

            camera = {

                "camera_id":
                    camera_id,

                "name":
                    name,

                "source":
                    source,

                "enabled":
                    bool(enabled),

                "status":
                    "DISCONNECTED",

                "people":
                    0,

                "last_check":
                    None,

                "error":
                    None
            }

            self.cameras.append(
                camera
            )

            self.save()

            return dict(
                camera
            )

    # ========================================================
    # UPDATE CAMERA
    # ========================================================

    def update_camera(
        self,
        camera_id,
        name=None,
        source=None,
        enabled=None,
        **kwargs
    ):

        camera_id = str(
            camera_id
        )

        with self.lock:

            camera = self._find_camera(
                camera_id
            )

            if camera is None:
                return None

            was_running = (
                camera_id
                in self.workers
            )

        if was_running:

            self.stop_camera(
                camera_id
            )

        with self.lock:

            camera = self._find_camera(
                camera_id
            )

            if camera is None:
                return None

            if name is not None:

                name = str(
                    name
                ).strip()

                if name:

                    camera["name"] = (
                        name
                    )

            if source is not None:

                source = str(
                    source
                ).strip()

                if source:

                    camera["source"] = (
                        source
                    )

            if enabled is not None:

                if isinstance(
                    enabled,
                    str
                ):

                    enabled = (
                        enabled.lower()
                        in (
                            "true",
                            "1",
                            "yes",
                            "on"
                        )
                    )

                camera["enabled"] = (
                    bool(enabled)
                )

            camera["status"] = (
                "DISCONNECTED"
            )

            camera["people"] = 0

            camera["error"] = None

            self.save()

            result = dict(
                camera
            )

        if (
            was_running
            and
            result["enabled"]
        ):

            self.start_camera(
                camera_id
            )

            current = self.get_camera(
                camera_id
            )

            if current is not None:

                return current

        return result

    # ========================================================
    # REMOVE CAMERA
    # ========================================================

    def remove_camera(
        self,
        camera_id
    ):

        camera_id = str(
            camera_id
        )

        self.stop_camera(
            camera_id
        )

        with self.lock:

            original_count = len(
                self.cameras
            )

            self.cameras = [

                camera

                for camera in self.cameras

                if str(
                    camera.get(
                        "camera_id"
                    )
                ) != camera_id

            ]

            removed = (
                len(self.cameras)
                < original_count
            )

            if removed:

                self.save()

            return removed

    # ========================================================
    # FIND CAMERA
    # ========================================================

    def _find_camera(
        self,
        camera_id
    ):

        camera_id = str(
            camera_id
        )

        for camera in self.cameras:

            if str(
                camera.get(
                    "camera_id"
                )
            ) == camera_id:

                return camera

        return None

    # ========================================================
    # GET CAMERA
    # ========================================================

    def get_camera(
        self,
        camera_id
    ):

        camera_id = str(
            camera_id
        )

        with self.lock:

            camera = self._find_camera(
                camera_id
            )

            if camera is None:
                return None

            result = dict(
                camera
            )

            worker = self.workers.get(
                camera_id
            )

        if worker is not None:

            try:

                status = (
                    worker.get_status()
                )

                if isinstance(
                    status,
                    dict
                ):

                    result.update(
                        status
                    )

            except Exception as error:

                result["error"] = (
                    str(error)
                )

        return result

    # ========================================================
    # LIST CAMERAS
    # ========================================================

    def list_cameras(self):

        with self.lock:

            cameras = [

                dict(camera)

                for camera in self.cameras

            ]

            workers = dict(
                self.workers
            )

        results = []

        for camera in cameras:

            result = dict(
                camera
            )

            camera_id = str(
                camera.get(
                    "camera_id"
                )
            )

            worker = workers.get(
                camera_id
            )

            if worker is not None:

                try:

                    status = (
                        worker.get_status()
                    )

                    if isinstance(
                        status,
                        dict
                    ):

                        result.update(
                            status
                        )

                except Exception as error:

                    result["error"] = (
                        str(error)
                    )

            results.append(
                result
            )

        return results

    # ========================================================
    # GET CAMERAS ALIAS
    # ========================================================

    def get_cameras(self):

        return self.list_cameras()

    # ========================================================
    # START CAMERA
    # ========================================================

    def start_camera(
        self,
        camera_id
    ):

        camera_id = str(
            camera_id
        )

        with self.lock:

            camera = self._find_camera(
                camera_id
            )

            if camera is None:
                return None

            if not camera.get(
                "enabled",
                True
            ):

                camera["status"] = (
                    "DISABLED"
                )

                self.save()

                return dict(
                    camera
                )

            existing = self.workers.get(
                camera_id
            )

            if (
                existing is not None
                and
                existing.is_running()
            ):

                return dict(
                    camera
                )

            try:

                worker = CameraWorker(

                    camera_id=
                        camera_id,

                    source=
                        camera[
                            "source"
                        ],

                    model_path=
                        self.model_path,

                    width=
                        self.width,

                    height=
                        self.height

                )

                self.workers[
                    camera_id
                ] = worker

                worker.start()

                camera["status"] = (
                    "CONNECTING"
                )

                camera["error"] = None

                self.save()

                return dict(
                    camera
                )

            except Exception as error:

                self.workers.pop(
                    camera_id,
                    None
                )

                camera["status"] = (
                    "ERROR"
                )

                camera["error"] = (
                    str(error)
                )

                self.save()

                print(
                    f"Camera start error "
                    f"{camera_id}: {error}"
                )

                return dict(
                    camera
                )

    # ========================================================
    # SWITCH CAMERA
    # ========================================================

    def switch_camera(
        self,
        camera_id
    ):

        camera_id = str(
            camera_id
        )

        # ----------------------------------------------------
        # Validate requested camera
        # ----------------------------------------------------

        with self.lock:

            camera = self._find_camera(
                camera_id
            )

            if camera is None:

                return {

                    "success":
                        False,

                    "error":
                        "Camera not found."

                }

            if not camera.get(
                "enabled",
                True
            ):

                return {

                    "success":
                        False,

                    "error":
                        "Camera is disabled."

                }

            previous_camera_id = (
                self.active_camera_id
            )

        # ----------------------------------------------------
        # Already active
        # ----------------------------------------------------

        if (
            previous_camera_id
            and
            str(previous_camera_id)
            == camera_id
        ):

            result = self.get_camera(
                camera_id
            )

            return {

                "success":
                    result is not None,

                "camera":
                    result,

                "camera_id":
                    camera_id

            }

        # ----------------------------------------------------
        # Stop previous active camera
        # ----------------------------------------------------

        if previous_camera_id:

            print(
                f"Switching camera: "
                f"{previous_camera_id} -> "
                f"{camera_id}"
            )

            self.stop_camera(
                previous_camera_id
            )

        # ----------------------------------------------------
        # Start requested camera
        # ----------------------------------------------------

        result = self.start_camera(
            camera_id
        )

        if result is None:

            return {

                "success":
                    False,

                "error":
                    "Could not start camera.",

                "camera_id":
                    camera_id

            }

        # ----------------------------------------------------
        # Store active camera
        # ----------------------------------------------------

        with self.lock:

            self.active_camera_id = (
                camera_id
            )

        return {

            "success":
                True,

            "camera":
                self.get_camera(
                    camera_id
                ),

            "camera_id":
                camera_id

        }

    # ========================================================
    # STOP CAMERA
    # ========================================================

    def stop_camera(
        self,
        camera_id
    ):

        camera_id = str(
            camera_id
        )

        with self.lock:

            worker = self.workers.pop(
                camera_id,
                None
            )

        if worker is not None:

            try:

                worker.stop()

            except Exception as error:

                print(
                    f"Camera stop error "
                    f"{camera_id}: {error}"
                )

        with self.lock:

            camera = self._find_camera(
                camera_id
            )

            if camera is not None:

                camera["status"] = (
                    "STOPPED"
                )

                camera["people"] = 0

                self.save()

            if (
                self.active_camera_id
                and
                str(
                    self.active_camera_id
                )
                == camera_id
            ):

                self.active_camera_id = None

            if camera is not None:

                return dict(
                    camera
                )

        return None

    # ========================================================
    # START ENABLED CAMERAS
    # ========================================================

    def start_enabled_cameras(self):

        with self.lock:

            camera_ids = [

                str(
                    camera.get(
                        "camera_id"
                    )
                )

                for camera in self.cameras

                if camera.get(
                    "enabled",
                    True
                )

            ]

        results = []

        for camera_id in camera_ids:

            result = (
                self.start_camera(
                    camera_id
                )
            )

            if result is not None:

                results.append(
                    result
                )

        return results

    # ========================================================
    # STOP ALL CAMERAS
    # ========================================================

    def stop_all_cameras(self):

        with self.lock:

            camera_ids = [

                str(
                    camera.get(
                        "camera_id"
                    )
                )

                for camera in self.cameras

            ]

        for camera_id in camera_ids:

            self.stop_camera(
                camera_id
            )

        with self.lock:

            self.active_camera_id = None

    # ========================================================
    # GET WORKER
    # ========================================================

    def get_worker(
        self,
        camera_id
    ):

        with self.lock:

            return self.workers.get(
                str(camera_id)
            )

    # ========================================================
    # GET LIVE RESULT
    # ========================================================

    def get_camera_result(
        self,
        camera_id
    ):

        worker = self.get_worker(
            camera_id
        )

        if worker is None:
            return None

        try:

            return worker.get_result()

        except Exception as error:

            print(
                f"Camera result error "
                f"{camera_id}: {error}"
            )

            return None

    # ========================================================
    # GET ALL LIVE RESULTS
    # ========================================================

    def get_all_results(self):

        with self.lock:

            workers = dict(
                self.workers
            )

        results = {}

        for camera_id, worker in workers.items():

            try:

                result = worker.get_result()

                if result is not None:

                    results[
                        str(camera_id)
                    ] = result

            except Exception as error:

                print(
                    f"Camera result error "
                    f"{camera_id}: {error}"
                )

        return results

    # ========================================================
    # GET STREAM FRAME
    # ========================================================

    def get_stream_frame(
        self,
        camera_id
    ):

        result = self.get_camera_result(
            camera_id
        )

        if not isinstance(
            result,
            dict
        ):

            return None

        frame = result.get(
            "frame"
        )

        if frame is None:
            return None

        try:

            success, encoded = (
                cv2.imencode(
                    ".jpg",
                    frame,
                    [
                        int(
                            cv2.IMWRITE_JPEG_QUALITY
                        ),
                        85
                    ]
                )
            )

            if not success:
                return None

            return encoded.tobytes()

        except Exception as error:

            print(
                f"Stream frame error "
                f"{camera_id}: {error}"
            )

            return None

    # ========================================================
    # CHECK ONE CAMERA
    # ========================================================

    def check_camera(
        self,
        camera_id
    ):

        camera_id = str(
            camera_id
        )

        # ----------------------------------------------------
        # IMPORTANT:
        # If CameraWorker is already running this camera,
        # do NOT open the physical camera a second time.
        # Use the existing worker instead.
        # ----------------------------------------------------

        worker = self.get_worker(
            camera_id
        )

        if worker is not None:

            try:

                result = worker.get_result()

                with self.lock:

                    camera = self._find_camera(
                        camera_id
                    )

                    if camera is None:
                        return None

                    camera["last_check"] = (
                        datetime.now().strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )
                    )

                    if isinstance(
                        result,
                        dict
                    ):

                        worker_status = str(
                            result.get(
                                "status",
                                ""
                            )
                        ).upper()

                        error = result.get(
                            "error"
                        )

                        frame = result.get(
                            "frame"
                        )

                        if (
                            frame is not None
                            and
                            worker_status not in (
                                "ERROR",
                                "DISCONNECTED",
                                "STOPPED"
                            )
                        ):

                            camera["status"] = (
                                "CONNECTED"
                            )

                            camera["error"] = (
                                None
                            )

                        elif worker_status:

                            camera["status"] = (
                                worker_status
                            )

                            camera["error"] = (
                                error
                            )

                        else:

                            camera["status"] = (
                                "DISCONNECTED"
                            )

                            camera["error"] = (
                                error
                                or
                                "Camera worker is running "
                                "but no frame is available."
                            )

                    else:

                        camera["status"] = (
                            "DISCONNECTED"
                        )

                        camera["error"] = (
                            "Camera worker is running "
                            "but no result is available."
                        )

                    self.save()

                    return dict(
                        camera
                    )

            except Exception as error:

                with self.lock:

                    camera = self._find_camera(
                        camera_id
                    )

                    if camera is None:
                        return None

                    camera["status"] = (
                        "ERROR"
                    )

                    camera["error"] = (
                        str(error)
                    )

                    camera["last_check"] = (
                        datetime.now().strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )
                    )

                    self.save()

                    return dict(
                        camera
                    )

        # ----------------------------------------------------
        # Worker is NOT running.
        #
        # Only now is it safe to perform a
        # standalone OpenCV connection test.
        # ----------------------------------------------------

        with self.lock:

            camera = self._find_camera(
                camera_id
            )

            if camera is None:
                return None

            source = camera[
                "source"
            ]

        capture = None

        try:

            if str(source).isdigit():

                source_value = int(
                    source
                )

            else:

                source_value = source

            capture = cv2.VideoCapture(
                source_value
            )

            if not capture.isOpened():

                status = {

                    "status":
                        "DISCONNECTED",

                    "error":
                        "Could not open camera."

                }

            else:

                success, frame = (
                    capture.read()
                )

                if success:

                    status = {

                        "status":
                            "CONNECTED",

                        "error":
                            None

                    }

                else:

                    status = {

                        "status":
                            "DISCONNECTED",

                        "error":
                            "Camera opened but "
                            "no frame received."

                    }

        except Exception as error:

            status = {

                "status":
                    "ERROR",

                "error":
                    str(error)

            }

        finally:

            if capture is not None:

                try:

                    capture.release()

                except Exception:
                    pass

        with self.lock:

            camera = self._find_camera(
                camera_id
            )

            if camera is None:
                return None

            camera["status"] = (
                status["status"]
            )

            camera["error"] = (
                status["error"]
            )

            camera["last_check"] = (
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            )

            self.save()

            result = dict(
                camera
            )

            result.update(
                status
            )

            return result

    # ========================================================
    # CHECK ALL CAMERAS
    # ========================================================

    def check_all_cameras(self):

        with self.lock:

            camera_ids = [

                str(
                    camera.get(
                        "camera_id"
                    )
                )

                for camera in self.cameras

            ]

        results = []

        for camera_id in camera_ids:

            result = (
                self.check_camera(
                    camera_id
                )
            )

            if result is not None:

                results.append(
                    result
                )

        return results

    # ========================================================
    # ENABLE / DISABLE
    # ========================================================

    def set_enabled(
        self,
        camera_id,
        enabled
    ):

        camera_id = str(
            camera_id
        )

        if isinstance(
            enabled,
            str
        ):

            enabled = (
                enabled.lower()
                in (
                    "true",
                    "1",
                    "yes",
                    "on"
                )
            )

        enabled = bool(
            enabled
        )

        with self.lock:

            camera = self._find_camera(
                camera_id
            )

            if camera is None:
                return None

            camera["enabled"] = (
                enabled
            )

            self.save()

        if not enabled:

            self.stop_camera(
                camera_id
            )

        return self.get_camera(
            camera_id
        )

    # ========================================================
    # ENABLE
    # ========================================================

    def enable_camera(
        self,
        camera_id
    ):

        result = self.set_enabled(
            camera_id,
            True
        )

        if result is not None:

            self.start_camera(
                camera_id
            )

        return self.get_camera(
            camera_id
        )

    # ========================================================
    # DISABLE
    # ========================================================

    def disable_camera(
        self,
        camera_id
    ):

        return self.set_enabled(
            camera_id,
            False
        )

    # ========================================================
    # ACTIVE CAMERA
    # ========================================================

    def get_active_camera_id(self):

        with self.lock:

            return self.active_camera_id

    # ========================================================
    # FILE
    # ========================================================

    def get_camera_file(self):

        return CAMERA_FILE

    # ========================================================
    # SHUTDOWN
    # ========================================================

    def shutdown(self):

        self.stop_all_cameras()