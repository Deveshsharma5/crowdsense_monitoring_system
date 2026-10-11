import math


class PhysicalZoneManager:

    def __init__(self, venue):
        self.venue = venue
        self.zones = []
        self.generate_grid()

    # =========================================================
    # GENERATE GRID
    # =========================================================

    def generate_grid(self):

        self.zones = []

        grid = float(self.venue.grid_size)

        if grid <= 0:
            grid = 5.0

        if self.venue.shape == "rectangle":

            columns = math.ceil(
                self.venue.length / grid
            )

            rows = math.ceil(
                self.venue.width / grid
            )

            for row in range(rows):

                for column in range(columns):

                    x = column * grid
                    y = row * grid

                    cell_width = min(
                        grid,
                        self.venue.length - x
                    )

                    cell_height = min(
                        grid,
                        self.venue.width - y
                    )

                    if cell_width <= 0 or cell_height <= 0:
                        continue

                    zone = {
                        "id": f"{chr(65 + row)}{column + 1}",
                        "row": row,
                        "column": column,

                        "x": x,
                        "y": y,

                        "width": cell_width,
                        "height": cell_height,

                        "area": cell_width * cell_height,

                        "people": 0,
                        "density": 0.0,

                        "risk": "SAFE",

                        "special_type": None,

                        "zone_capacity": 0.0,
                        "occupancy": 0.0
                    }

                    self.zones.append(zone)

        elif self.venue.shape == "circle":

            self._generate_circle_grid()

        self.apply_special_areas()

        self.update_zone_capacities()

    # =========================================================
    # CIRCLE GRID
    # =========================================================

    def _generate_circle_grid(self):

        grid = float(self.venue.grid_size)

        if grid <= 0:
            grid = 5.0

        radius = float(
            self.venue.diameter
        ) / 2.0

        diameter = float(
            self.venue.diameter
        )

        columns = math.ceil(
            diameter / grid
        )

        rows = columns

        for row in range(rows):

            for column in range(columns):

                x = column * grid
                y = row * grid

                cell_width = min(
                    grid,
                    diameter - x
                )

                cell_height = min(
                    grid,
                    diameter - y
                )

                if cell_width <= 0 or cell_height <= 0:
                    continue

                center_x = (
                    x +
                    cell_width / 2.0
                )

                center_y = (
                    y +
                    cell_height / 2.0
                )

                circle_center_x = radius
                circle_center_y = radius

                distance = math.sqrt(
                    (
                        center_x -
                        circle_center_x
                    ) ** 2
                    +
                    (
                        center_y -
                        circle_center_y
                    ) ** 2
                )

                # Only create cells whose center
                # is inside the circular venue.

                if distance > radius:
                    continue

                zone = {
                    "id": f"C{row + 1}_{column + 1}",
                    "row": row,
                    "column": column,

                    "x": x,
                    "y": y,

                    "width": cell_width,
                    "height": cell_height,

                    "area": (
                        cell_width *
                        cell_height
                    ),

                    "people": 0,
                    "density": 0.0,

                    "risk": "SAFE",

                    "special_type": None,

                    "zone_capacity": 0.0,
                    "occupancy": 0.0
                }

                self.zones.append(zone)

    # =========================================================
    # VENUE BOUNDARY
    # =========================================================

    def point_inside_venue(
        self,
        world_x,
        world_y
    ):

        try:

            x = float(world_x)
            y = float(world_y)

        except Exception:

            return False

        # -----------------------------------------------------
        # RECTANGLE
        # -----------------------------------------------------

        if self.venue.shape == "rectangle":

            return (
                0.0 <= x <= self.venue.length
                and
                0.0 <= y <= self.venue.width
            )

        # -----------------------------------------------------
        # CIRCLE
        # -----------------------------------------------------

        if self.venue.shape == "circle":

            radius = (
                float(self.venue.diameter)
                / 2.0
            )

            center_x = radius
            center_y = radius

            distance = math.sqrt(
                (
                    x -
                    center_x
                ) ** 2
                +
                (
                    y -
                    center_y
                ) ** 2
            )

            return distance <= radius

        return False

    # =========================================================
    # CLAMP POINT TO VENUE
    # =========================================================

    def clamp_to_venue(
        self,
        world_x,
        world_y
    ):

        try:

            x = float(world_x)
            y = float(world_y)

        except Exception:

            return None

        # -----------------------------------------------------
        # RECTANGLE
        # -----------------------------------------------------

        if self.venue.shape == "rectangle":

            x = max(
                0.0,
                min(
                    x,
                    float(self.venue.length)
                )
            )

            y = max(
                0.0,
                min(
                    y,
                    float(self.venue.width)
                )
            )

            return x, y

        # -----------------------------------------------------
        # CIRCLE
        # -----------------------------------------------------

        if self.venue.shape == "circle":

            radius = (
                float(self.venue.diameter)
                / 2.0
            )

            center_x = radius
            center_y = radius

            dx = x - center_x
            dy = y - center_y

            distance = math.sqrt(
                dx * dx +
                dy * dy
            )

            if distance <= radius:
                return x, y

            if distance == 0:
                return center_x, center_y

            scale = radius / distance

            return (
                center_x + dx * scale,
                center_y + dy * scale
            )

        return None

    # =========================================================
    # CALCULATE LOCAL ZONE CAPACITY
    # =========================================================

    def update_zone_capacities(self):

        venue_area = float(
            self.venue.calculate_area()
        )

        if venue_area <= 0:

            for zone in self.zones:

                zone["zone_capacity"] = 1.0

            return

        venue_capacity = max(
            1,
            int(self.venue.capacity)
        )

        for zone in self.zones:

            proportional_capacity = (
                venue_capacity
                *
                zone["area"]
                /
                venue_area
            )

            # Keep the physical proportional value.
            #
            # Do NOT force every zone to 3 people.
            # That was causing:
            #
            # Venue capacity = 5
            # 8 zones × 3 = 24
            #
            # which is inconsistent.

            zone["zone_capacity"] = round(
                max(
                    0.1,
                    proportional_capacity
                ),
                2
            )

    # =========================================================
    # SPECIAL AREAS
    # =========================================================

    def apply_special_areas(self):

        for zone in self.zones:

            zone["special_type"] = None

            zone_x1 = zone["x"]
            zone_y1 = zone["y"]

            zone_x2 = (
                zone_x1 +
                zone["width"]
            )

            zone_y2 = (
                zone_y1 +
                zone["height"]
            )

            for special in self.venue.special_areas:

                sx1 = float(
                    special.get(
                        "x",
                        0
                    )
                )

                sy1 = float(
                    special.get(
                        "y",
                        0
                    )
                )

                sx2 = (
                    sx1 +
                    float(
                        special.get(
                            "width",
                            0
                        )
                    )
                )

                sy2 = (
                    sy1 +
                    float(
                        special.get(
                            "height",
                            0
                        )
                    )
                )

                overlap = (
                    zone_x1 < sx2
                    and
                    zone_x2 > sx1
                    and
                    zone_y1 < sy2
                    and
                    zone_y2 > sy1
                )

                if overlap:

                    zone["special_type"] = (
                        special.get(
                            "type",
                            "normal"
                        )
                    )

    # =========================================================
    # FIND EXACT ZONE
    # =========================================================

    def find_zone(
        self,
        world_x,
        world_y
    ):

        try:

            x = float(world_x)
            y = float(world_y)

        except Exception:

            return None

        # -----------------------------------------------------
        # First make sure the point is inside the actual venue.
        # -----------------------------------------------------

        if not self.point_inside_venue(
            x,
            y
        ):

            return None

        # -----------------------------------------------------
        # Find the zone.
        #
        # Use < for the normal right/bottom edges so a point
        # exactly on a boundary does not accidentally belong
        # to two zones.
        # -----------------------------------------------------

        for index, zone in enumerate(
            self.zones
        ):

            x1 = zone["x"]
            y1 = zone["y"]

            x2 = (
                x1 +
                zone["width"]
            )

            y2 = (
                y1 +
                zone["height"]
            )

            is_last_column = (
                index ==
                len(self.zones) - 1
            )

            inside_x = (
                x >= x1
                and
                (
                    x < x2
                    or
                    abs(x - x2) < 0.000001
                )
            )

            inside_y = (
                y >= y1
                and
                (
                    y < y2
                    or
                    abs(y - y2) < 0.000001
                )
            )

            if inside_x and inside_y:

                return zone

        return None

    # =========================================================
    # FIND NEAREST ZONE
    # =========================================================

    def find_nearest_zone(
        self,
        world_x,
        world_y
    ):

        if not self.zones:
            return None

        try:

            x = float(world_x)
            y = float(world_y)

        except Exception:

            return None

        nearest_zone = None
        nearest_distance = float("inf")

        for zone in self.zones:

            center_x = (
                zone["x"] +
                zone["width"] / 2.0
            )

            center_y = (
                zone["y"] +
                zone["height"] / 2.0
            )

            distance = math.sqrt(
                (
                    x -
                    center_x
                ) ** 2
                +
                (
                    y -
                    center_y
                ) ** 2
            )

            if distance < nearest_distance:

                nearest_distance = distance

                nearest_zone = zone

        return nearest_zone

    # =========================================================
    # ROBUST ZONE LOOKUP
    # =========================================================

    def resolve_zone(
        self,
        world_x,
        world_y
    ):

        # -----------------------------------------------------
        # Exact assignment first.
        # -----------------------------------------------------

        zone = self.find_zone(
            world_x,
            world_y
        )

        if zone is not None:

            return zone

        # -----------------------------------------------------
        # If calibration puts the point just outside the
        # configured venue, clamp it back inside.
        #
        # This handles small calibration errors around the
        # boundary without completely ignoring the detection.
        # -----------------------------------------------------

        clamped = self.clamp_to_venue(
            world_x,
            world_y
        )

        if clamped is None:

            return None

        clamped_x, clamped_y = clamped

        zone = self.find_zone(
            clamped_x,
            clamped_y
        )

        if zone is not None:

            return zone

        # -----------------------------------------------------
        # Final fallback:
        # choose the physically nearest zone.
        #
        # This prevents a small calibration mismatch from
        # causing the detected person to disappear from all
        # zone counts.
        # -----------------------------------------------------

        return self.find_nearest_zone(
            clamped_x,
            clamped_y
        )

    # =========================================================
    # RESET COUNTS
    # =========================================================

    def reset_counts(self):

        for zone in self.zones:

            zone["people"] = 0

            zone["density"] = 0.0

            zone["risk"] = "SAFE"

            zone["occupancy"] = 0.0

    # =========================================================
    # ADD PERSON
    # =========================================================

    def add_person(
        self,
        world_x,
        world_y,
        multiplier=1
    ):

        zone = self.resolve_zone(
            world_x,
            world_y
        )

        if zone is None:

            return None

        try:

            person_count = max(
                1,
                int(multiplier)
            )

        except Exception:

            person_count = 1

        zone["people"] += person_count

        # -----------------------------------------------------
        # DENSITY
        # -----------------------------------------------------

        if zone["area"] > 0:

            zone["density"] = (
                zone["people"]
                /
                zone["area"]
            )

        else:

            zone["density"] = 0.0

        # -----------------------------------------------------
        # OCCUPANCY
        # -----------------------------------------------------

        zone_capacity = max(
            0.1,
            float(
                zone.get(
                    "zone_capacity",
                    1.0
                )
            )
        )

        zone["occupancy"] = round(
            (
                zone["people"]
                /
                zone_capacity
            ) * 100,
            1
        )

        # -----------------------------------------------------
        # RISK
        # -----------------------------------------------------

        zone["risk"] = self.calculate_risk(
            zone
        )

        return zone

    # =========================================================
    # RISK CALCULATION
    # =========================================================

    def calculate_risk(
        self,
        zone
    ):

        people = int(
            zone.get(
                "people",
                0
            )
        )

        if people <= 0:

            return "SAFE"

        zone_capacity = max(
            0.1,
            float(
                zone.get(
                    "zone_capacity",
                    1.0
                )
            )
        )

        occupancy = (
            people
            /
            zone_capacity
        ) * 100

        warning = float(
            self.venue.warning_threshold
        )

        critical = float(
            self.venue.critical_threshold
        )

        # -----------------------------------------------------
        # LOCAL ZONE PROTECTION
        #
        # With a very small test capacity, a 5m x 5m zone can
        # mathematically have a capacity below 1 person.
        #
        # We don't want ONE detected person to immediately
        # become a local CRITICAL alert.
        #
        # Overall venue occupancy still independently handles
        # the actual venue capacity.
        # -----------------------------------------------------

        if people < 2:

            return "SAFE"

        if occupancy >= critical:

            return "CRITICAL"

        if occupancy >= warning:

            return "WARNING"

        return "SAFE"

    # =========================================================
    # GET ZONES
    # =========================================================

    def get_zones(self):

        return self.zones