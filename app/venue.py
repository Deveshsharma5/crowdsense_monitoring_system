import json
import os


VENUE_FILE = "data/venue_config.json"


class VenueConfig:

    def __init__(
        self,
        name="Default Venue",
        shape="rectangle",
        length=20,
        width=10,
        diameter=0,
        capacity=100,
        warning_threshold=70,
        critical_threshold=90,
        grid_size=5,
        zones=None,
        special_areas=None,
        floorplan=None
    ):

        self.name = name
        self.shape = shape

        self.length = float(length)
        self.width = float(width)
        self.diameter = float(diameter)

        self.capacity = int(capacity)

        self.warning_threshold = float(
            warning_threshold
        )

        self.critical_threshold = float(
            critical_threshold
        )

        self.grid_size = float(grid_size)

        self.zones = zones or []

        self.special_areas = special_areas or []

        self.floorplan = floorplan


    # ========================================================
    # AREA
    # ========================================================

    def calculate_area(self):

        if self.shape == "circle":

            radius = self.diameter / 2

            return 3.141592653589793 * radius * radius

        return self.length * self.width


    # ========================================================
    # SAVE
    # ========================================================

    def save(self):

        os.makedirs(
            "data",
            exist_ok=True
        )

        data = {

            "name": self.name,

            "shape": self.shape,

            "length": self.length,

            "width": self.width,

            "diameter": self.diameter,

            "capacity": self.capacity,

            "warning_threshold":
                self.warning_threshold,

            "critical_threshold":
                self.critical_threshold,

            "grid_size": self.grid_size,

            "zones": self.zones,

            "special_areas":
                self.special_areas,

            "floorplan":
                self.floorplan
        }

        with open(
            VENUE_FILE,
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

    @classmethod
    def load(cls):

        if not os.path.exists(
            VENUE_FILE
        ):

            return None

        try:

            with open(
                VENUE_FILE,
                "r",
                encoding="utf-8"
            ) as file:

                data = json.load(file)

            return cls(

                name=data.get(
                    "name",
                    "Default Venue"
                ),

                shape=data.get(
                    "shape",
                    "rectangle"
                ),

                length=data.get(
                    "length",
                    20
                ),

                width=data.get(
                    "width",
                    10
                ),

                diameter=data.get(
                    "diameter",
                    0
                ),

                capacity=data.get(
                    "capacity",
                    100
                ),

                warning_threshold=data.get(
                    "warning_threshold",
                    70
                ),

                critical_threshold=data.get(
                    "critical_threshold",
                    90
                ),

                grid_size=data.get(
                    "grid_size",
                    5
                ),

                zones=data.get(
                    "zones",
                    []
                ),

                special_areas=data.get(
                    "special_areas",
                    []
                ),

                floorplan=data.get(
                    "floorplan",
                    None
                )
            )

        except Exception as error:

            print(
                f"Could not load venue: {error}"
            )

            return None