import time
from datetime import datetime


class SafetyManager:

    SAFE = "SAFE"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"

    def __init__(
        self,
        alert_manager=None,
        incident_manager=None,
        snapshot_manager=None
    ):

        self.alert_manager = (
            alert_manager
        )

        self.incident_manager = (
            incident_manager
        )

        self.snapshot_manager = (
            snapshot_manager
        )

        self.last_alert_times = {}

        self.default_cooldown = 8

    # ========================================================
    # SET MANAGERS
    # ========================================================

    def set_alert_manager(
        self,
        alert_manager
    ):

        self.alert_manager = (
            alert_manager
        )

    def set_incident_manager(
        self,
        incident_manager
    ):

        self.incident_manager = (
            incident_manager
        )

    def set_snapshot_manager(
        self,
        snapshot_manager
    ):

        self.snapshot_manager = (
            snapshot_manager
        )

    # ========================================================
    # RISK
    # ========================================================

    def calculate_risk(
        self,
        people,
        capacity,
        warning_threshold=70,
        critical_threshold=90
    ):

        try:

            people = float(
                people
            )

        except Exception:

            people = 0

        try:

            capacity = float(
                capacity
            )

        except Exception:

            capacity = 0

        if capacity <= 0:

            return self.SAFE

        occupancy = (
            people /
            capacity
        ) * 100

        if occupancy >= float(
            critical_threshold
        ):

            return self.CRITICAL

        if occupancy >= float(
            warning_threshold
        ):

            return self.WARNING

        return self.SAFE

    # ========================================================
    # DENSITY RISK
    # ========================================================

    def calculate_density_risk(
        self,
        density,
        warning_density,
        critical_density
    ):

        try:

            density = float(
                density
            )

        except Exception:

            density = 0

        try:

            warning_density = float(
                warning_density
            )

        except Exception:

            warning_density = 0

        try:

            critical_density = float(
                critical_density
            )

        except Exception:

            critical_density = 0

        if (
            critical_density > 0
            and density >= critical_density
        ):

            return self.CRITICAL

        if (
            warning_density > 0
            and density >= warning_density
        ):

            return self.WARNING

        return self.SAFE

    # ========================================================
    # COMBINE RISK
    # ========================================================

    def combine_risk(
        self,
        occupancy_risk,
        density_risk
    ):

        priority = {
            self.SAFE: 0,
            self.WARNING: 1,
            self.CRITICAL: 2
        }

        occupancy_risk = str(
            occupancy_risk
        ).upper()

        density_risk = str(
            density_risk
        ).upper()

        if occupancy_risk not in priority:

            occupancy_risk = self.SAFE

        if density_risk not in priority:

            density_risk = self.SAFE

        if (
            priority[density_risk]
            >
            priority[occupancy_risk]
        ):

            return density_risk

        return occupancy_risk

    # ========================================================
    # COOLDOWN
    # ========================================================

    def can_alert(
        self,
        key,
        cooldown=None
    ):

        if cooldown is None:

            cooldown = (
                self.default_cooldown
            )

        now = time.time()

        last_time = (
            self.last_alert_times.get(
                key
            )
        )

        if last_time is None:

            return True

        return (
            now - last_time
            >= cooldown
        )

    # ========================================================
    # RECORD ALERT TIME
    # ========================================================

    def record_alert(
        self,
        key
    ):

        self.last_alert_times[
            key
        ] = time.time()

    # ========================================================
    # CREATE ALERT
    # ========================================================

    def create_alert(
        self,
        risk,
        zone_id=None,
        camera_id=None,
        people=0,
        density=0,
        message=None,
        cooldown=None
    ):

        risk = str(
            risk
        ).upper()

        if risk == self.SAFE:

            return None

        key = (
            str(camera_id)
            +
            ":"
            +
            str(zone_id)
            +
            ":"
            +
            risk
        )

        if not self.can_alert(
            key,
            cooldown
        ):

            return None

        self.record_alert(
            key
        )

        timestamp = (
            datetime.now()
            .strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        )

        if message is None:

            message = (
                f"{risk} crowd condition "
                f"detected"
            )

        alert_data = {

            "timestamp":
                timestamp,

            "risk":
                risk,

            "zone_id":
                zone_id,

            "camera_id":
                camera_id,

            "people":
                int(people),

            "density":
                float(density),

            "message":
                message
        }

        # ----------------------------------------------------
        # Save alert
        # ----------------------------------------------------

        if self.alert_manager is not None:

            try:

                self.alert_manager.create_alert(
                    risk=risk,
                    zone_id=zone_id,
                    camera_id=camera_id,
                    people=people,
                    density=density,
                    message=message
                )

            except TypeError:

                try:

                    self.alert_manager.create_alert(
                        risk,
                        zone_id,
                        camera_id,
                        people,
                        density,
                        message
                    )

                except Exception:
                    pass

            except Exception:
                pass

        return alert_data

    # ========================================================
    # CREATE INCIDENT
    # ========================================================

    def create_incident(
        self,
        risk,
        zone_id=None,
        camera_id=None,
        people=0,
        density=0,
        special_type=None,
        message=None,
        snapshot_path=None
    ):

        risk = str(
            risk
        ).upper()

        if risk == self.SAFE:

            return None

        timestamp = (
            datetime.now()
            .strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        )

        if message is None:

            message = (
                f"{risk} crowd incident"
            )

        incident_data = {

            "timestamp":
                timestamp,

            "risk":
                risk,

            "zone":
                zone_id,

            "camera":
                camera_id,

            "people":
                int(people),

            "density":
                float(density),

            "special_type":
                special_type,

            "message":
                message,

            "snapshot_path":
                snapshot_path,

            "status":
                "OPEN"
        }

        if self.incident_manager is not None:

            try:

                result = (
                    self.incident_manager
                    .create_incident(
                        risk=risk,
                        zone=zone_id,
                        camera=camera_id,
                        people=people,
                        density=density,
                        special_type=special_type,
                        message=message,
                        snapshot_path=snapshot_path
                    )
                )

                if result is not None:

                    return result

            except TypeError:

                pass

            except Exception:

                pass

        return incident_data

    # ========================================================
    # PROCESS ZONE
    # ========================================================

    def process_zone(
        self,
        zone,
        camera_id=None,
        snapshot_path=None
    ):

        if not isinstance(
            zone,
            dict
        ):

            return None

        zone_id = zone.get(
            "id"
        )

        people = zone.get(
            "people",
            0
        )

        density = zone.get(
            "density",
            0
        )

        risk = str(
            zone.get(
                "risk",
                self.SAFE
            )
        ).upper()

        if risk == self.SAFE:

            return {
                "risk": self.SAFE,
                "alert": None,
                "incident": None
            }

        message = (
            f"Zone {zone_id} is "
            f"{risk}. "
            f"People: {people}"
        )

        alert = self.create_alert(
            risk=risk,
            zone_id=zone_id,
            camera_id=camera_id,
            people=people,
            density=density,
            message=message
        )

        incident = None

        if risk == self.CRITICAL:

            incident = self.create_incident(
                risk=risk,
                zone_id=zone_id,
                camera_id=camera_id,
                people=people,
                density=density,
                message=message,
                snapshot_path=snapshot_path
            )

        return {
            "risk": risk,
            "alert": alert,
            "incident": incident
        }

    # ========================================================
    # PROCESS ALL ZONES
    # ========================================================

    def process_zones(
        self,
        zones,
        camera_id=None,
        snapshot_path=None
    ):

        if not isinstance(
            zones,
            list
        ):

            return []

        results = []

        for zone in zones:

            result = self.process_zone(
                zone,
                camera_id=camera_id,
                snapshot_path=snapshot_path
            )

            if result is not None:

                results.append(
                    result
                )

        return results

    # ========================================================
    # SYSTEM RISK
    # ========================================================

    def get_system_risk(
        self,
        zones
    ):

        highest_risk = self.SAFE

        priority = {
            self.SAFE: 0,
            self.WARNING: 1,
            self.CRITICAL: 2
        }

        if not isinstance(
            zones,
            list
        ):

            return highest_risk

        for zone in zones:

            if not isinstance(
                zone,
                dict
            ):

                continue

            risk = str(
                zone.get(
                    "risk",
                    self.SAFE
                )
            ).upper()

            if risk not in priority:

                continue

            if (
                priority[risk]
                >
                priority[highest_risk]
            ):

                highest_risk = risk

        return highest_risk

    # ========================================================
    # CLEAR COOLDOWNS
    # ========================================================

    def reset_cooldowns(self):

        self.last_alert_times = {}

    # ========================================================
    # STATUS
    # ========================================================

    def get_status(self):

        return {

            "alert_manager":
                self.alert_manager
                is not None,

            "incident_manager":
                self.incident_manager
                is not None,

            "snapshot_manager":
                self.snapshot_manager
                is not None,

            "active_cooldowns":
                len(
                    self.last_alert_times
                )
        }