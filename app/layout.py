import cv2
import json
import os


LAYOUT_FILE = "data/layout.json"

GREEN = (0, 255, 0)
RED = (0, 0, 255)
WHITE = (245, 245, 245)
GRAY = (170, 170, 170)
BLACK = (8, 10, 9)
DARK = (18, 23, 20)


class LayoutDesigner:

    def __init__(self, width=960, height=540):

        self.width = width
        self.height = height

        self.zones = []

        self.current_points = []

        self.selected_zone = None

        self.zone_counter = 1

        self.drawing = False

    # --------------------------------------------------
    # START DRAWING
    # --------------------------------------------------

    def start_zone(self):

        self.current_points = []

        self.drawing = True

        self.selected_zone = None

    # --------------------------------------------------
    # ADD POINT
    # --------------------------------------------------

    def add_point(self, x, y):

        if not self.drawing:
            return

        if y < 70:
            return

        self.current_points.append(
            [int(x), int(y)]
        )

    # --------------------------------------------------
    # FINISH ZONE
    # --------------------------------------------------

    def finish_zone(
        self,
        name=None,
        zone_type="normal"
    ):

        if len(self.current_points) < 3:
            return False

        if name is None or not name.strip():

            name = f"Zone {self.zone_counter}"

        zone = {

            "id": self.zone_counter,

            "name": name,

            "type": zone_type,

            "points": self.current_points.copy(),

            "max_people": 0,

            "warning": 70,

            "critical": 90
        }

        self.zones.append(zone)

        self.zone_counter += 1

        self.current_points = []

        self.drawing = False

        return True

    # --------------------------------------------------
    # CANCEL CURRENT DRAWING
    # --------------------------------------------------

    def cancel_drawing(self):

        self.current_points = []

        self.drawing = False

    # --------------------------------------------------
    # DELETE ZONE
    # --------------------------------------------------

    def delete_zone(self, zone_index):

        if 0 <= zone_index < len(self.zones):

            self.zones.pop(zone_index)

            self.selected_zone = None

    # --------------------------------------------------
    # CLEAR ALL
    # --------------------------------------------------

    def clear(self):

        self.zones = []

        self.current_points = []

        self.selected_zone = None

        self.zone_counter = 1

        self.drawing = False

    # --------------------------------------------------
    # SELECT ZONE
    # --------------------------------------------------

    def select_zone(self, x, y):

        for index in range(
            len(self.zones) - 1,
            -1,
            -1
        ):

            zone = self.zones[index]

            points = zone["points"]

            if len(points) < 3:
                continue

            inside = cv2.pointPolygonTest(
                self._numpy_points(points),
                (x, y),
                False
            )

            if inside >= 0:

                self.selected_zone = index

                return index

        self.selected_zone = None

        return None

    # --------------------------------------------------
    # DRAW
    # --------------------------------------------------

    def draw(self, frame):

        # Draw existing zones

        for index, zone in enumerate(self.zones):

            points = self._numpy_points(
                zone["points"]
            )

            if index == self.selected_zone:

                color = RED

            else:

                color = GREEN

            cv2.polylines(
                frame,
                [points],
                True,
                color,
                2,
                cv2.LINE_AA
            )

            # Transparent fill

            overlay = frame.copy()

            cv2.fillPoly(
                overlay,
                [points],
                DARK
            )

            cv2.addWeighted(
                overlay,
                0.25,
                frame,
                0.75,
                0,
                frame
            )

            # Zone label

            x, y = zone["points"][0]

            label = zone["name"]

            cv2.putText(
                frame,
                label,
                (x + 5, y + 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                color,
                2,
                cv2.LINE_AA
            )

        # Draw current polygon

        if len(self.current_points) > 0:

            for point in self.current_points:

                cv2.circle(
                    frame,
                    tuple(point),
                    5,
                    GREEN,
                    -1
                )

            if len(self.current_points) > 1:

                for i in range(
                    len(self.current_points) - 1
                ):

                    p1 = tuple(
                        self.current_points[i]
                    )

                    p2 = tuple(
                        self.current_points[i + 1]
                    )

                    cv2.line(
                        frame,
                        p1,
                        p2,
                        GREEN,
                        2,
                        cv2.LINE_AA
                    )

        return frame

    # --------------------------------------------------
    # SAVE
    # --------------------------------------------------

    def save(self):

        os.makedirs(
            os.path.dirname(LAYOUT_FILE),
            exist_ok=True
        )

        data = {

            "width": self.width,

            "height": self.height,

            "zones": self.zones
        }

        with open(
            LAYOUT_FILE,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                data,
                file,
                indent=4
            )

        print("Layout saved.")

        return True

    # --------------------------------------------------
    # LOAD
    # --------------------------------------------------

    def load(self):

        if not os.path.exists(
            LAYOUT_FILE
        ):

            return False

        try:

            with open(
                LAYOUT_FILE,
                "r",
                encoding="utf-8"
            ) as file:

                data = json.load(file)

            self.width = data.get(
                "width",
                self.width
            )

            self.height = data.get(
                "height",
                self.height
            )

            self.zones = data.get(
                "zones",
                []
            )

            if self.zones:

                self.zone_counter = max(
                    zone.get("id", 0)
                    for zone in self.zones
                ) + 1

            else:

                self.zone_counter = 1

            print("Layout loaded.")

            return True

        except Exception as error:

            print(
                f"Could not load layout: {error}"
            )

            return False

    # --------------------------------------------------
    # NUMPY POINTS
    # --------------------------------------------------

    def _numpy_points(self, points):

        import numpy as np

        return np.array(
            points,
            dtype="int32"
        ).reshape((-1, 1, 2))