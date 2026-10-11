import threading
import time


# ============================================================
# MULTI CAMERA MANAGER
# ============================================================

class MultiCameraManager:

    def __init__(
        self,
        camera_manager=None
    ):

        self.camera_manager = camera_manager

        self.lock = threading.RLock()

        self.results = {}

        self.running = False

    # ========================================================
    # CAMERA MANAGER
    # ========================================================

    def set_camera_manager(
        self,
        camera_manager
    ):

        with self.lock:

            self.camera_manager = camera_manager

    # ========================================================
    # UPDATE
    # ========================================================

    def update(self):

        with self.lock:

            camera_manager = self.camera_manager

        if camera_manager is None:

            return {}

        try:

            camera_results = (
                camera_manager.get_all_results()
            )

        except Exception as error:

            print(
                f"Multi-camera update error: {error}"
            )

            camera_results = {}

        if not isinstance(
            camera_results,
            dict
        ):

            camera_results = {}

        current_time = time.time()

        new_results = {}

        for camera_id, result in camera_results.items():

            camera_id = str(camera_id)

            if result is None:
                continue

            if not isinstance(
                result,
                dict
            ):
                continue

            # ------------------------------------------------
            # PEOPLE
            # ------------------------------------------------

            try:

                people = int(
                    result.get(
                        "people",
                        0
                    ) or 0
                )

            except Exception:

                people = 0

            people = max(
                0,
                people
            )

            # ------------------------------------------------
            # DETECTIONS
            # ------------------------------------------------

            detections = result.get(
                "detections",
                []
            )

            if not isinstance(
                detections,
                list
            ):

                detections = []

            # ------------------------------------------------
            # BOXES
            #
            # CameraWorker uses "detections".
            # MultiCameraManager exposes both
            # detections and boxes.
            # ------------------------------------------------

            boxes = []

            for detection in detections:

                if not isinstance(
                    detection,
                    dict
                ):

                    continue

                box = detection.get(
                    "box"
                )

                if box is not None:

                    boxes.append(
                        box
                    )

            # ------------------------------------------------
            # TIMESTAMP
            # ------------------------------------------------

            timestamp = result.get(
                "timestamp"
            )

            if timestamp is None:

                timestamp = current_time

            # ------------------------------------------------
            # STATUS
            # ------------------------------------------------

            status = result.get(
                "status",
                "UNKNOWN"
            )

            # ------------------------------------------------
            # ERROR
            # ------------------------------------------------

            error = result.get(
                "error"
            )

            # ------------------------------------------------
            # STORE RESULT
            # ------------------------------------------------

            new_results[camera_id] = {

                "camera_id":
                    camera_id,

                "source":
                    result.get(
                        "source"
                    ),

                "people":
                    people,

                "detections":
                    detections,

                "boxes":
                    boxes,

                "frame":
                    result.get(
                        "frame"
                    ),

                "timestamp":
                    timestamp,

                "status":
                    status,

                "error":
                    error
            }

        # ----------------------------------------------------
        # SAVE RESULTS
        # ----------------------------------------------------

        with self.lock:

            self.results = new_results

            return self._copy_results()

    # ========================================================
    # GET RESULTS
    # ========================================================

    def get_results(self):

        with self.lock:

            return self._copy_results()

    # ========================================================
    # COPY RESULTS
    # ========================================================

    def _copy_results(self):

        copied = {}

        for camera_id, result in self.results.items():

            copied[camera_id] = dict(
                result
            )

            if isinstance(
                result.get("detections"),
                list
            ):

                copied[camera_id][
                    "detections"
                ] = [

                    dict(detection)

                    for detection in
                    result["detections"]

                    if isinstance(
                        detection,
                        dict
                    )
                ]

            if isinstance(
                result.get("boxes"),
                list
            ):

                copied[camera_id][
                    "boxes"
                ] = list(
                    result["boxes"]
                )

        return copied

    # ========================================================
    # GET CAMERA RESULT
    # ========================================================

    def get_camera_result(
        self,
        camera_id
    ):

        camera_id = str(
            camera_id
        )

        with self.lock:

            result = self.results.get(
                camera_id
            )

            if result is None:

                return None

            copied = dict(result)

            if isinstance(
                result.get("detections"),
                list
            ):

                copied["detections"] = [

                    dict(item)

                    for item in
                    result["detections"]

                    if isinstance(
                        item,
                        dict
                    )
                ]

            if isinstance(
                result.get("boxes"),
                list
            ):

                copied["boxes"] = list(
                    result["boxes"]
                )

            return copied

    # ========================================================
    # TOTAL PEOPLE
    # ========================================================

    def get_total_people(self):

        with self.lock:

            total = 0

            for result in self.results.values():

                try:

                    total += max(
                        0,
                        int(
                            result.get(
                                "people",
                                0
                            ) or 0
                        )
                    )

                except Exception:

                    pass

            return total

    # ========================================================
    # CAMERA COUNT
    # ========================================================

    def get_camera_count(self):

        with self.lock:

            return len(
                self.results
            )

    # ========================================================
    # ACTIVE CAMERAS
    # ========================================================

    def get_active_cameras(self):

        with self.lock:

            active = []

            for camera_id, result in self.results.items():

                status = str(
                    result.get(
                        "status",
                        ""
                    )
                ).upper()

                if status not in (
                    "ERROR",
                    "DISCONNECTED",
                    "OFFLINE",
                    "STOPPED",
                    "DISABLED"
                ):

                    active.append(
                        camera_id
                    )

            return active

    # ========================================================
    # CAMERA ERRORS
    # ========================================================

    def get_camera_errors(self):

        with self.lock:

            errors = {}

            for camera_id, result in self.results.items():

                error = result.get(
                    "error"
                )

                if error:

                    errors[
                        camera_id
                    ] = str(error)

            return errors

    # ========================================================
    # SUMMARY
    # ========================================================

    def get_summary(self):

        with self.lock:

            total_people = 0

            active_cameras = 0

            errors = 0

            for result in self.results.values():

                try:

                    total_people += max(
                        0,
                        int(
                            result.get(
                                "people",
                                0
                            ) or 0
                        )
                    )

                except Exception:

                    pass

                status = str(
                    result.get(
                        "status",
                        ""
                    )
                ).upper()

                if status not in (
                    "ERROR",
                    "DISCONNECTED",
                    "OFFLINE",
                    "STOPPED",
                    "DISABLED"
                ):

                    active_cameras += 1

                if result.get("error"):

                    errors += 1

            return {

                "camera_count":
                    len(self.results),

                "active_cameras":
                    active_cameras,

                "total_people":
                    total_people,

                "errors":
                    errors
            }

    # ========================================================
    # RESET
    # ========================================================

    def reset(self):

        with self.lock:

            self.results = {}

    # ========================================================
    # SHUTDOWN
    # ========================================================

    def shutdown(self):

        self.running = False

        self.reset()