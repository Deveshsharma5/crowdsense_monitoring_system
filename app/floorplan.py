import os
import json
import cv2


FLOORPLAN_FILE = "data/floorplan.json"


class FloorPlan:

    def __init__(self):

        self.path = None
        self.image = None

        self.width = 0
        self.height = 0

        self.venue_length = 0.0
        self.venue_width = 0.0

    # ========================================================
    # LOAD FLOOR PLAN IMAGE
    # ========================================================

    def load_image(self, path):

        if not os.path.exists(path):

            print("Floor plan file not found.")

            return False

        image = cv2.imread(path)

        if image is None:

            print("Could not read floor plan.")

            return False

        self.path = path

        self.image = image

        self.height, self.width = image.shape[:2]

        return True

    # ========================================================
    # SET PHYSICAL DIMENSIONS
    # ========================================================

    def set_dimensions(
        self,
        length,
        width
    ):

        self.venue_length = float(length)

        self.venue_width = float(width)

    # ========================================================
    # FLOOR PLAN PIXEL → REAL WORLD
    # ========================================================

    def pixel_to_world(
        self,
        x,
        y
    ):

        if (
            self.width <= 0
            or
            self.height <= 0
        ):

            return None

        world_x = (
            x
            / self.width
            * self.venue_length
        )

        world_y = (
            y
            / self.height
            * self.venue_width
        )

        return (
            world_x,
            world_y
        )

    # ========================================================
    # REAL WORLD → FLOOR PLAN PIXEL
    # ========================================================

    def world_to_pixel(
        self,
        x,
        y
    ):

        if (
            self.venue_length <= 0
            or
            self.venue_width <= 0
        ):

            return None

        px = int(
            x
            / self.venue_length
            * self.width
        )

        py = int(
            y
            / self.venue_width
            * self.height
        )

        return (
            px,
            py
        )

    # ========================================================
    # SAVE
    # ========================================================

    def save(self):

        os.makedirs(
            "data",
            exist_ok=True
        )

        data = {

            "path": self.path,

            "width": self.width,

            "height": self.height,

            "venue_length":
                self.venue_length,

            "venue_width":
                self.venue_width
        }

        with open(
            FLOORPLAN_FILE,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                data,
                file,
                indent=4
            )

    # ========================================================
    # LOAD
    # ========================================================

    def load(self):

        if not os.path.exists(
            FLOORPLAN_FILE
        ):

            return False

        try:

            with open(
                FLOORPLAN_FILE,
                "r",
                encoding="utf-8"
            ) as file:

                data = json.load(file)

            path = data.get(
                "path"
            )

            if not path:

                return False

            if not self.load_image(
                path
            ):

                return False

            self.venue_length = float(
                data.get(
                    "venue_length",
                    0
                )
            )

            self.venue_width = float(
                data.get(
                    "venue_width",
                    0
                )
            )

            return True

        except Exception as error:

            print(
                f"Floor plan load error: {error}"
            )

            return False