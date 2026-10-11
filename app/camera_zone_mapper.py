import cv2
import numpy as np


class CameraZoneMapper:

    def __init__(
        self,
        calibration_manager=None,
        zone_manager=None
    ):

        self.calibration_manager = (
            calibration_manager
        )

        self.zone_manager = (
            zone_manager
        )

    # ========================================================
    # MANAGERS
    # ========================================================

    def set_calibration_manager(
        self,
        calibration_manager
    ):

        self.calibration_manager = (
            calibration_manager
        )

    def set_zone_manager(
        self,
        zone_manager
    ):

        self.zone_manager = (
            zone_manager
        )

    # ========================================================
    # CALIBRATION
    # ========================================================

    def get_calibration(
        self,
        camera_id
    ):

        if self.calibration_manager is None:
            return None

        return self.calibration_manager.get_calibration(
            camera_id
        )

    def is_calibrated(
        self,
        camera_id
    ):

        if self.calibration_manager is None:
            return False

        return self.calibration_manager.is_calibrated(
            camera_id
        )

    # ========================================================
    # GET CALIBRATION POINTS
    # ========================================================

    def _get_points(
        self,
        calibration
    ):

        if not calibration:
            return None

        matrix = calibration.get(
            "matrix"
        )

        if not isinstance(
            matrix,
            dict
        ):

            return None

        points = matrix.get(
            "points"
        )

        if not isinstance(
            points,
            list
        ):

            return None

        if len(points) < 4:
            return None

        converted = []

        for point in points[:4]:

            if not isinstance(
                point,
                dict
            ):

                return None

            if (
                "x" not in point
                or
                "y" not in point
            ):

                return None

            try:

                converted.append([
                    float(point["x"]),
                    float(point["y"])
                ])

            except Exception:

                return None

        return np.array(
            converted,
            dtype=np.float32
        )

    # ========================================================
    # ORDER POINTS
    # ========================================================

    def _order_points(
        self,
        points
    ):

        points = np.array(
            points,
            dtype=np.float32
        )

        if len(points) != 4:
            return None

        ordered = np.zeros(
            (4, 2),
            dtype=np.float32
        )

        sums = points.sum(
            axis=1
        )

        differences = np.diff(
            points,
            axis=1
        ).reshape(-1)

        # Top-left
        ordered[0] = points[
            np.argmin(sums)
        ]

        # Bottom-right
        ordered[2] = points[
            np.argmax(sums)
        ]

        # Top-right
        ordered[1] = points[
            np.argmin(differences)
        ]

        # Bottom-left
        ordered[3] = points[
            np.argmax(differences)
        ]

        return ordered

    # ========================================================
    # PIXEL → VENUE
    # ========================================================

    def pixel_to_venue(
        self,
        camera_id,
        x,
        y
    ):

        calibration = self.get_calibration(
            camera_id
        )

        if not calibration:
            return None

        points = self._get_points(
            calibration
        )

        if points is None:
            return None

        points = self._order_points(
            points
        )

        if points is None:
            return None

        try:

            venue_length = float(
                calibration.get(
                    "venue_length",
                    1
                )
            )

            venue_width = float(
                calibration.get(
                    "venue_width",
                    1
                )
            )

        except Exception:

            return None

        if (
            venue_length <= 0
            or
            venue_width <= 0
        ):

            return None

        # ----------------------------------------------------
        # Destination venue rectangle
        # ----------------------------------------------------

        destination = np.array([

            [0, 0],

            [venue_length, 0],

            [venue_length, venue_width],

            [0, venue_width]

        ], dtype=np.float32)

        # ----------------------------------------------------
        # Perspective transform
        # ----------------------------------------------------

        try:

            transform = cv2.getPerspectiveTransform(
                points,
                destination
            )

        except Exception:

            return None

        source_point = np.array([[
            [
                float(x),
                float(y)
            ]
        ]], dtype=np.float32)

        try:

            transformed = cv2.perspectiveTransform(
                source_point,
                transform
            )

        except Exception:

            return None

        venue_x = float(
            transformed[0][0][0]
        )

        venue_y = float(
            transformed[0][0][1]
        )

        return {

            "x": venue_x,

            "y": venue_y

        }

    # ========================================================
    # PERSON POINT
    # ========================================================

    def get_person_point(
        self,
        box
    ):

        if not box or len(box) < 4:

            return None

        try:

            x1, y1, x2, y2 = box[:4]

            return {

                "x":
                    (
                        float(x1)
                        +
                        float(x2)
                    ) / 2,

                "y":
                    float(y2)

            }

        except Exception:

            return None

    # ========================================================
    # PERSON → VENUE
    # ========================================================

    def person_to_venue(
        self,
        camera_id,
        box
    ):

        point = self.get_person_point(
            box
        )

        if point is None:
            return None

        return self.pixel_to_venue(
            camera_id,
            point["x"],
            point["y"]
        )

    # ========================================================
    # ZONE
    # ========================================================

    def get_zone_for_point(
        self,
        point
    ):

        if (
            self.zone_manager is None
            or
            point is None
        ):

            return None

        x = point.get("x")
        y = point.get("y")

        if x is None or y is None:
            return None

        # ----------------------------------------------------
        # Try supported zone-manager methods
        # ----------------------------------------------------

        for method_name in (

            "get_zone_at_point",

            "find_zone",

            "get_zone"

        ):

            method = getattr(
                self.zone_manager,
                method_name,
                None
            )

            if not callable(method):
                continue

            try:

                return method(
                    x,
                    y
                )

            except TypeError:

                try:

                    return method(
                        point
                    )

                except Exception:

                    pass

            except Exception:

                pass

        return None

    # ========================================================
    # MAP DETECTION
    # ========================================================

    def map_detection(
        self,
        camera_id,
        detection
    ):

        if not detection:
            return None

        box = detection.get(
            "box"
        )

        if box is None:

            box = detection.get(
                "bbox"
            )

        venue_point = self.person_to_venue(
            camera_id,
            box
        )

        zone = self.get_zone_for_point(
            venue_point
        )

        result = dict(
            detection
        )

        result["venue_point"] = (
            venue_point
        )

        result["zone"] = zone

        return result

    # ========================================================
    # MAP CAMERA RESULT
    # ========================================================

    def map_camera_result(
        self,
        camera_id,
        result
    ):

        if not result:
            return result

        mapped = dict(
            result
        )

        detections = result.get(
            "detections",
            []
        )

        if not isinstance(
            detections,
            list
        ):

            detections = []

        mapped_detections = []

        for detection in detections:

            mapped_detection = (
                self.map_detection(
                    camera_id,
                    detection
                )
            )

            if mapped_detection is not None:

                mapped_detections.append(
                    mapped_detection
                )

        mapped[
            "detections"
        ] = mapped_detections

        return mapped

    # ========================================================
    # MAP ALL CAMERAS
    # ========================================================

    def map_all_cameras(
        self,
        results
    ):

        if not results:
            return {}

        mapped = {}

        for camera_id, result in results.items():

            mapped[
                str(camera_id)
            ] = self.map_camera_result(
                camera_id,
                result
            )

        return mapped