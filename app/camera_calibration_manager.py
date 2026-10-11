import json
import os
import threading


# ============================================================
# CAMERA CALIBRATION MANAGER
# ============================================================

CALIBRATION_FOLDER = "data"
CALIBRATION_FILE = os.path.join(
    CALIBRATION_FOLDER,
    "camera_calibrations.json"
)


class CameraCalibrationManager:

    def __init__(self):

        self.lock = threading.Lock()

        self.calibrations = {}

        os.makedirs(
            CALIBRATION_FOLDER,
            exist_ok=True
        )

        self.load()

    # ========================================================
    # LOAD
    # ========================================================

    def load(self):

        if not os.path.exists(
            CALIBRATION_FILE
        ):

            self.calibrations = {}

            return

        try:

            with open(
                CALIBRATION_FILE,
                "r",
                encoding="utf-8"
            ) as file:

                data = json.load(file)

            if isinstance(data, dict):

                self.calibrations = data

            else:

                self.calibrations = {}

        except Exception as error:

            print(
                f"Camera calibration load error: "
                f"{error}"
            )

            self.calibrations = {}

    # ========================================================
    # SAVE
    # ========================================================

    def save(self):

        os.makedirs(
            CALIBRATION_FOLDER,
            exist_ok=True
        )

        try:

            with open(
                CALIBRATION_FILE,
                "w",
                encoding="utf-8"
            ) as file:

                json.dump(
                    self.calibrations,
                    file,
                    indent=4
                )

            return True

        except Exception as error:

            print(
                f"Camera calibration save error: "
                f"{error}"
            )

            return False

    # ========================================================
    # SET CALIBRATION
    # ========================================================

    def set_calibration(
        self,
        camera_id,
        matrix,
        venue_length,
        venue_width
    ):

        camera_id = str(
            camera_id
        )

        if matrix is None:

            return False

        try:

            matrix_data = matrix.tolist()

        except Exception:

            matrix_data = matrix

        with self.lock:

            self.calibrations[
                camera_id
            ] = {

                "camera_id":
                    camera_id,

                "matrix":
                    matrix_data,

                "venue_length":
                    float(venue_length),

                "venue_width":
                    float(venue_width),

                "calibrated":
                    True
            }

            return self.save()

    # ========================================================
    # GET CALIBRATION
    # ========================================================

    def get_calibration(
        self,
        camera_id
    ):

        camera_id = str(
            camera_id
        )

        with self.lock:

            calibration = (
                self.calibrations.get(
                    camera_id
                )
            )

            if calibration is None:

                return None

            return dict(
                calibration
            )

    # ========================================================
    # CHECK CALIBRATED
    # ========================================================

    def is_calibrated(
        self,
        camera_id
    ):

        calibration = (
            self.get_calibration(
                camera_id
            )
        )

        if calibration is None:

            return False

        return bool(
            calibration.get(
                "calibrated",
                False
            )
        )

    # ========================================================
    # REMOVE
    # ========================================================

    def remove_calibration(
        self,
        camera_id
    ):

        camera_id = str(
            camera_id
        )

        with self.lock:

            if camera_id not in self.calibrations:

                return False

            del self.calibrations[
                camera_id
            ]

            return self.save()

    # ========================================================
    # GET ALL
    # ========================================================

    def get_all(self):

        with self.lock:

            return {
                camera_id: dict(
                    calibration
                )

                for camera_id, calibration
                in self.calibrations.items()
            }

    # ========================================================
    # FILE
    # ========================================================

    def get_file(self):

        return CALIBRATION_FILE