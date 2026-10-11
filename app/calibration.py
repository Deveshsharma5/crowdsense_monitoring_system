import cv2
import numpy as np
import json
import os


CALIBRATION_FILE = (
    "data/camera_calibration.json"
)


class CameraCalibration:

    def __init__(self):

        self.image_points = []

        self.matrix = None

        self.venue_length = 0.0

        self.venue_width = 0.0


    # ========================================================
    # SET VENUE
    # ========================================================

    def set_venue_dimensions(
        self,
        length,
        width
    ):

        self.venue_length = float(
            length
        )

        self.venue_width = float(
            width
        )


    # ========================================================
    # RESET
    # ========================================================

    def reset(self):

        self.image_points = []

        self.matrix = None


    # ========================================================
    # ADD CAMERA POINT
    # ========================================================

    def add_point(
        self,
        x,
        y
    ):

        if len(
            self.image_points
        ) >= 4:

            return False


        self.image_points.append(
            [
                float(x),
                float(y)
            ]
        )

        return True


    # ========================================================
    # CALCULATE
    # ========================================================

    def calculate(self):

        if len(
            self.image_points
        ) != 4:

            print(
                "Exactly 4 camera points are required."
            )

            return False


        if (
            self.venue_length <= 0
            or
            self.venue_width <= 0
        ):

            print(
                "Invalid venue dimensions."
            )

            return False


        source = np.float32([

            self.image_points[0],

            self.image_points[1],

            self.image_points[2],

            self.image_points[3]
        ])


        destination = np.float32([

            [0, 0],

            [self.venue_length, 0],

            [
                self.venue_length,
                self.venue_width
            ],

            [0, self.venue_width]
        ])


        self.matrix = (
            cv2.getPerspectiveTransform(
                source,
                destination
            )
        )


        return True


    # ========================================================
    # CAMERA → WORLD
    # ========================================================

    def pixel_to_world(
        self,
        x,
        y
    ):

        if self.matrix is None:

            return None


        point = np.float32([

            [
                [
                    float(x),
                    float(y)
                ]
            ]

        ])


        result = (
            cv2.perspectiveTransform(
                point,
                self.matrix
            )
        )


        world_x = float(
            result[0][0][0]
        )

        world_y = float(
            result[0][0][1]
        )


        return (
            world_x,
            world_y
        )


    # ========================================================
    # SAVE
    # ========================================================

    def save(self):

        if self.matrix is None:

            print(
                "No calibration available."
            )

            return False


        os.makedirs(
            "data",
            exist_ok=True
        )


        data = {

            "venue_length":
                self.venue_length,

            "venue_width":
                self.venue_width,

            "image_points":
                self.image_points,

            "matrix":
                self.matrix.tolist()
        }


        with open(
            CALIBRATION_FILE,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                data,
                file,
                indent=4
            )


        return True


    # ========================================================
    # LOAD
    # ========================================================

    def load(self):

        if not os.path.exists(
            CALIBRATION_FILE
        ):

            return False


        try:

            with open(
                CALIBRATION_FILE,
                "r",
                encoding="utf-8"
            ) as file:

                data = json.load(file)


            self.venue_length = float(
                data["venue_length"]
            )

            self.venue_width = float(
                data["venue_width"]
            )

            self.image_points = (
                data["image_points"]
            )

            self.matrix = np.array(
                data["matrix"],
                dtype=np.float32
            )


            return True


        except Exception as error:

            print(
                f"Calibration load error: {error}"
            )

            return False