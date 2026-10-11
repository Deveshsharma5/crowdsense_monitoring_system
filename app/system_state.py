class SystemState:

    def __init__(self):

        self.system = "READY"

        self.venue = "Not configured"

        self.total_people = 0

        self.capacity = 0

        self.occupancy = 0.0

        self.risk = "SAFE"

        self.zones = []

        self.last_alert = None

        self.last_update = None

        self.camera_source = "0"

        self.test_multiplier = 1


    # ========================================================
    # UPDATE
    # ========================================================

    def update(
        self,
        system=None,
        venue=None,
        total_people=None,
        capacity=None,
        risk=None,
        zones=None,
        last_alert=None,
        last_update=None,
        camera_source=None,
        test_multiplier=None
    ):

        if system is not None:

            self.system = system


        if venue is not None:

            self.venue = venue


        if total_people is not None:

            self.total_people = int(
                total_people
            )


        if capacity is not None:

            self.capacity = int(
                capacity
            )


        # ----------------------------------------------------
        # OCCUPANCY
        # ----------------------------------------------------

        if self.capacity > 0:

            self.occupancy = round(

                (
                    self.total_people
                    /
                    self.capacity
                )
                *
                100,

                1

            )

        else:

            self.occupancy = 0.0


        # ----------------------------------------------------
        # RISK
        # ----------------------------------------------------

        if risk is not None:

            self.risk = risk


        # ----------------------------------------------------
        # ZONES
        # ----------------------------------------------------

        if zones is not None:

            self.zones = zones


        # ----------------------------------------------------
        # LAST ALERT
        # ----------------------------------------------------

        if last_alert is not None:

            self.last_alert = last_alert


        # ----------------------------------------------------
        # LAST UPDATE
        # ----------------------------------------------------

        if last_update is not None:

            self.last_update = last_update


        # ----------------------------------------------------
        # CAMERA
        # ----------------------------------------------------

        if camera_source is not None:

            self.camera_source = (
                str(camera_source)
            )


        # ----------------------------------------------------
        # TEST MULTIPLIER
        # ----------------------------------------------------

        if test_multiplier is not None:

            try:

                self.test_multiplier = max(
                    1,
                    int(test_multiplier)
                )

            except Exception:

                self.test_multiplier = 1


    # ========================================================
    # GET DATA
    # ========================================================

    def get_data(self):

        return {

            "system":
                self.system,

            "venue":
                self.venue,

            "total_people":
                self.total_people,

            "capacity":
                self.capacity,

            "occupancy":
                self.occupancy,

            "risk":
                self.risk,

            "zones":
                self.zones,

            "last_alert":
                self.last_alert,

            "last_update":
                self.last_update,

            "camera_source":
                self.camera_source,

            "test_multiplier":
                self.test_multiplier

        }