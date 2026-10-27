import csv
import os
from datetime import datetime


INCIDENT_FOLDER = "data/incidents"

INCIDENT_FILE = os.path.join(
    INCIDENT_FOLDER,
    "incidents.csv"
)


class IncidentManager:

    def __init__(self):

        os.makedirs(
            INCIDENT_FOLDER,
            exist_ok=True
        )

        self._create_file()

    # =========================================================
    # CREATE INCIDENT FILE
    # =========================================================

    def _create_file(self):

        if os.path.exists(
            INCIDENT_FILE
        ):
            return

        with open(
            INCIDENT_FILE,
            "w",
            newline="",
            encoding="utf-8"
        ) as file:

            writer = csv.writer(file)

            writer.writerow([
                "incident_id",
                "alert_id",
                "timestamp",
                "risk",
                "zone_id",
                "camera_id",
                "people",
                "density",
                "special_type",
                "message",
                "snapshot_path",
                "status"
            ])

    # =========================================================
    # CREATE INCIDENT
    # =========================================================

    def create_incident(
        self,
        alert,
        snapshot_path=None
    ):

        if not alert:
            return None

        # -----------------------------------------------------
        # TIMESTAMP
        # -----------------------------------------------------

        timestamp = alert.get(
            "timestamp"
        )

        if not timestamp:

            timestamp = datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )

        # -----------------------------------------------------
        # INCIDENT ID
        # -----------------------------------------------------

        incident_id = (
            self._generate_incident_id()
        )

        # -----------------------------------------------------
        # ALERT ID
        #
        # Support both:
        # alert_id
        # id
        # -----------------------------------------------------

        alert_id = (
            alert.get("alert_id")
            or
            alert.get("id")
            or
            ""
        )

        # -----------------------------------------------------
        # PEOPLE COUNT
        #
        # Support the different possible names used by
        # CrowdSense alert data.
        # -----------------------------------------------------

        people = alert.get(
            "people"
        )

        if people is None:

            people = alert.get(
                "zone_people"
            )

        if people is None:

            people = alert.get(
                "count"
            )

        if people is None:

            people = alert.get(
                "total_people"
            )

        if people is None:

            people = 0

        try:

            people = int(
                float(
                    people
                )
            )

        except Exception:

            people = 0

        # -----------------------------------------------------
        # DENSITY
        # -----------------------------------------------------

        density = alert.get(
            "density",
            0
        )

        try:

            density = round(
                float(
                    density
                ),
                4
            )

        except Exception:

            density = 0.0

        # -----------------------------------------------------
        # SNAPSHOT
        #
        # Only store the snapshot if the file actually exists.
        # -----------------------------------------------------

        valid_snapshot = None

        if snapshot_path:

            try:

                snapshot_path = os.path.normpath(
                    str(
                        snapshot_path
                    )
                )

                if os.path.isfile(
                    snapshot_path
                ):

                    valid_snapshot = (
                        snapshot_path
                    )

                else:

                    print(
                        "Incident snapshot "
                        "does not exist: "
                        f"{snapshot_path}"
                    )

            except Exception as error:

                print(
                    "Incident snapshot "
                    f"validation error: {error}"
                )

        # -----------------------------------------------------
        # INCIDENT OBJECT
        # -----------------------------------------------------

        incident = {

            "incident_id":
                incident_id,

            "alert_id":
                alert_id,

            "timestamp":
                timestamp,

            "risk":
                alert.get(
                    "risk",
                    "UNKNOWN"
                ),

            "zone_id":
                alert.get(
                    "zone_id",
                    "UNKNOWN"
                ),

            "camera_id":
                alert.get(
                    "camera_id"
                ),

            "people":
                people,

            "density":
                density,

            "special_type":
                alert.get(
                    "special_type"
                ),

            "message":
                alert.get(
                    "message",
                    ""
                ),

            "snapshot_path":
                valid_snapshot,

            "status":
                "OPEN"
        }

        # -----------------------------------------------------
        # WRITE INCIDENT
        # -----------------------------------------------------

        try:

            with open(
                INCIDENT_FILE,
                "a",
                newline="",
                encoding="utf-8"
            ) as file:

                writer = csv.writer(
                    file
                )

                writer.writerow([
                    incident["incident_id"],
                    incident["alert_id"],
                    incident["timestamp"],
                    incident["risk"],
                    incident["zone_id"],
                    incident["camera_id"],
                    incident["people"],
                    incident["density"],
                    incident["special_type"],
                    incident["message"],
                    incident["snapshot_path"] or "",
                    incident["status"]
                ])

        except Exception as error:

            print(
                f"Incident logging error: {error}"
            )

            return None

        # -----------------------------------------------------
        # CONSOLE LOG
        # -----------------------------------------------------

        print(
            f"INCIDENT CREATED: "
            f"{incident_id} | "
            f"{incident['risk']} | "
            f"Zone {incident['zone_id']} | "
            f"People {incident['people']} | "
            f"Snapshot "
            f"{incident['snapshot_path'] or 'NONE'}"
        )

        return incident

    # =========================================================
    # CREATE INCIDENTS FROM ALERTS
    # =========================================================

    def create_from_alerts(
        self,
        alerts,
        snapshot_paths=None
    ):

        incidents = []

        if not alerts:
            return incidents

        if snapshot_paths is None:

            snapshot_paths = []

        for index, alert in enumerate(
            alerts
        ):

            snapshot_path = None

            if index < len(
                snapshot_paths
            ):

                snapshot_path = (
                    snapshot_paths[index]
                )

            incident = (
                self.create_incident(
                    alert,
                    snapshot_path
                )
            )

            if incident:

                incidents.append(
                    incident
                )

        return incidents

    # =========================================================
    # READ INCIDENT HISTORY
    # =========================================================

    def get_incidents(self):

        if not os.path.exists(
            INCIDENT_FILE
        ):

            return []

        incidents = []

        try:

            with open(
                INCIDENT_FILE,
                "r",
                newline="",
                encoding="utf-8"
            ) as file:

                reader = csv.DictReader(
                    file
                )

                for row in reader:

                    # -----------------------------------------
                    # PEOPLE
                    # -----------------------------------------

                    try:

                        row["people"] = int(
                            float(
                                row.get(
                                    "people",
                                    0
                                )
                            )
                        )

                    except Exception:

                        row["people"] = 0

                    # -----------------------------------------
                    # DENSITY
                    # -----------------------------------------

                    try:

                        row["density"] = float(
                            row.get(
                                "density",
                                0
                            )
                        )

                    except Exception:

                        row["density"] = 0.0

                    incidents.append(
                        row
                    )

        except Exception as error:

            print(
                f"Incident history error: {error}"
            )

            return []

        # =====================================================
        # LATEST FIRST
        # =====================================================

        incidents.reverse()

        return incidents

    # =========================================================
    # GET LATEST INCIDENT
    # =========================================================

    def get_latest_incident(self):

        incidents = (
            self.get_incidents()
        )

        if not incidents:
            return None

        # get_incidents() is already newest first

        return incidents[0]

    # =========================================================
    # GET INCIDENTS BY RISK
    # =========================================================

    def get_by_risk(
        self,
        risk
    ):

        risk = str(
            risk
        ).upper()

        incidents = (
            self.get_incidents()
        )

        return [
            incident
            for incident in incidents
            if str(
                incident.get(
                    "risk",
                    ""
                )
            ).upper() == risk
        ]

    # =========================================================
    # GET INCIDENTS BY ZONE
    # =========================================================

    def get_by_zone(
        self,
        zone_id
    ):

        incidents = (
            self.get_incidents()
        )

        return [
            incident
            for incident in incidents
            if str(
                incident.get(
                    "zone_id",
                    ""
                )
            ) == str(zone_id)
        ]

    # =========================================================
    # INCIDENT COUNTS
    # =========================================================

    def get_counts(self):

        incidents = (
            self.get_incidents()
        )

        warning = 0
        critical = 0

        for incident in incidents:

            risk = str(
                incident.get(
                    "risk",
                    ""
                )
            ).upper()

            if risk == "WARNING":

                warning += 1

            elif risk == "CRITICAL":

                critical += 1

        return {

            "warning":
                warning,

            "critical":
                critical,

            "total":
                warning + critical
        }

    # =========================================================
    # UPDATE INCIDENT STATUS
    # =========================================================

    def update_status(
        self,
        incident_id,
        status
    ):

        if not os.path.exists(
            INCIDENT_FILE
        ):

            return False

        incidents = (
            self.get_incidents()
        )

        found = False

        for incident in incidents:

            if str(
                incident.get(
                    "incident_id",
                    ""
                )
            ) == str(
                incident_id
            ):

                incident["status"] = str(
                    status
                ).upper()

                found = True

                break

        if not found:

            return False

        try:

            with open(
                INCIDENT_FILE,
                "w",
                newline="",
                encoding="utf-8"
            ) as file:

                writer = csv.writer(
                    file
                )

                writer.writerow([
                    "incident_id",
                    "alert_id",
                    "timestamp",
                    "risk",
                    "zone_id",
                    "camera_id",
                    "people",
                    "density",
                    "special_type",
                    "message",
                    "snapshot_path",
                    "status"
                ])

                # ---------------------------------------------
                # get_incidents() is newest first.
                # Writing them back in that order is okay.
                # ---------------------------------------------

                for incident in incidents:

                    writer.writerow([
                        incident.get(
                            "incident_id",
                            ""
                        ),

                        incident.get(
                            "alert_id",
                            ""
                        ),

                        incident.get(
                            "timestamp",
                            ""
                        ),

                        incident.get(
                            "risk",
                            ""
                        ),

                        incident.get(
                            "zone_id",
                            ""
                        ),

                        incident.get(
                            "camera_id",
                            ""
                        ),

                        incident.get(
                            "people",
                            0
                        ),

                        incident.get(
                            "density",
                            0
                        ),

                        incident.get(
                            "special_type",
                            ""
                        ),

                        incident.get(
                            "message",
                            ""
                        ),

                        incident.get(
                            "snapshot_path",
                            ""
                        ),

                        incident.get(
                            "status",
                            "OPEN"
                        )
                    ])

            return True

        except Exception as error:

            print(
                f"Incident status update error: {error}"
            )

            return False

    # =========================================================
    # INCIDENT FILE
    # =========================================================

# =========================================================
    # SAVE ALL INCIDENTS
    # =========================================================

    def _save_all_incidents(self, incidents):

        try:

            with open(
                INCIDENT_FILE,
                "w",
                newline="",
                encoding="utf-8"
            ) as file:

                writer = csv.writer(file)

                writer.writerow([
                    "incident_id",
                    "alert_id",
                    "timestamp",
                    "risk",
                    "zone_id",
                    "camera_id",
                    "people",
                    "density",
                    "special_type",
                    "message",
                    "snapshot_path",
                    "status"
                ])

                for inc in incidents:

                    writer.writerow([
                        inc.get("incident_id", ""),
                        inc.get("alert_id", ""),
                        inc.get("timestamp", ""),
                        inc.get("risk", ""),
                        inc.get("zone_id", ""),
                        inc.get("camera_id", ""),
                        inc.get("people", 0),
                        inc.get("density", 0),
                        inc.get("special_type", ""),
                        inc.get("message", ""),
                        inc.get("snapshot_path", ""),
                        inc.get("status", "OPEN")
                    ])

            return True

        except Exception as error:

            print(f"Incident save error: {error}")

            return False

    # =========================================================
    # ACKNOWLEDGE INCIDENT
    # =========================================================

    def acknowledge_incident(self, incident_id):

        if not incident_id or not os.path.exists(INCIDENT_FILE):
            return False

        target = str(incident_id).strip().upper()

        incidents = self.get_incidents()

        found = False

        for inc in incidents:

            if str(inc.get("incident_id", "")).strip().upper() == target:

                inc["status"] = "ACKNOWLEDGED"

                found = True

                break

        if found:
            self._save_all_incidents(incidents)

        return found

    # =========================================================
    # ACKNOWLEDGE BY ALERT ID
    # =========================================================

    def acknowledge_by_alert_id(self, alert_id):

        if not alert_id or not os.path.exists(INCIDENT_FILE):
            return 0

        target = str(alert_id).strip().upper()

        incidents = self.get_incidents()

        count = 0

        for inc in incidents:

            if str(inc.get("alert_id", "")).strip().upper() == target:

                if str(inc.get("status", "")).upper() != "ACKNOWLEDGED":

                    inc["status"] = "ACKNOWLEDGED"

                    count += 1

        if count > 0:
            self._save_all_incidents(incidents)

        return count

    # =========================================================
    # ACKNOWLEDGE ALL
    # =========================================================

    def acknowledge_all(self):

        if not os.path.exists(INCIDENT_FILE):
            return 0

        incidents = self.get_incidents()

        count = 0

        for inc in incidents:

            if str(inc.get("status", "")).upper() != "ACKNOWLEDGED":

                inc["status"] = "ACKNOWLEDGED"

                count += 1

        if count > 0:
            self._save_all_incidents(incidents)

        return count

    def get_incident_file(self):

        return INCIDENT_FILE

    # =========================================================
    # GENERATE INCIDENT ID
    # =========================================================

    def _generate_incident_id(self):

        incidents = (
            self.get_incidents()
        )

        existing_ids = {

            str(
                incident.get(
                    "incident_id",
                    ""
                )
            )

            for incident in incidents
        }

        number = 1

        while (
            f"INC{number}"
            in existing_ids
        ):

            number += 1

        return f"INC{number}"