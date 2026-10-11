import os
from datetime import datetime

from zones import PhysicalZoneManager


class AnalyticsManager:

    def __init__(
        self,
        log_file="data/logs/crowd_log.csv",
        alert_manager=None,
        incident_manager=None,
        session_manager=None
    ):

        self.log_file = log_file

        self.alert_manager = alert_manager
        self.incident_manager = incident_manager
        self.session_manager = session_manager

        # API will assign the current venue here.
        self.venue_config = None

    # =========================================================
    # CURRENT VENUE ZONES
    # =========================================================

    def get_current_zone_ids(self):

        venue = self.venue_config

        if venue is None:
            return []

        try:

            zone_manager = PhysicalZoneManager(
                venue
            )

            zones = (
                zone_manager.get_zones()
                or []
            )

            zone_ids = []

            for zone in zones:

                if not isinstance(
                    zone,
                    dict
                ):
                    continue

                zone_id = zone.get(
                    "id"
                )

                if zone_id is None:
                    continue

                zone_ids.append(
                    str(zone_id)
                )

            return zone_ids

        except Exception as error:

            print(
                "Analytics zone generation error:",
                error
            )

            return []

    # =========================================================
    # FILTER LOG ROWS TO CURRENT VENUE ZONES
    # =========================================================

    def filter_rows_to_current_zones(
        self,
        rows
    ):

        if not rows:
            return []

        current_zone_ids = (
            self.get_current_zone_ids()
        )

        if not current_zone_ids:
            return rows

        current_zone_ids = set(
            str(zone_id)
            for zone_id in current_zone_ids
        )

        filtered_rows = []

        for row in rows:

            zone_id = str(
                row.get(
                    "zone_id",
                    ""
                )
            )

            if zone_id in current_zone_ids:

                filtered_rows.append(
                    row
                )

        return filtered_rows

    # =========================================================
    # PEOPLE STATISTICS
    # =========================================================

    def calculate_people_statistics(
        self,
        rows
    ):

        if not rows:

            return {
                "peak_people": 0,
                "average_people": 0.0,
                "minimum_people": 0,
                "total_records": 0
            }

        timestamp_people = {}

        for row in rows:

            timestamp = row.get(
                "timestamp"
            )

            if not timestamp:
                continue

            try:

                people = int(
                    float(
                        row.get(
                            "total_people",
                            0
                        )
                    )
                )

            except Exception:

                people = 0

            timestamp_people[
                timestamp
            ] = people

        values = list(
            timestamp_people.values()
        )

        if not values:

            return {
                "peak_people": 0,
                "average_people": 0.0,
                "minimum_people": 0,
                "total_records": 0
            }

        return {

            "peak_people":
                max(values),

            "average_people":
                round(
                    sum(values)
                    / len(values),
                    2
                ),

            "minimum_people":
                min(values),

            "total_records":
                len(values)
        }

    # =========================================================
    # OCCUPANCY STATISTICS
    # =========================================================

    def calculate_occupancy_statistics(
        self,
        rows,
        capacity
    ):

        try:

            capacity = int(
                float(capacity)
            )

        except Exception:

            capacity = 0

        if capacity <= 0:

            return {
                "peak_occupancy": 0.0,
                "average_occupancy": 0.0,
                "minimum_occupancy": 0.0
            }

        timestamp_people = {}

        for row in rows:

            timestamp = row.get(
                "timestamp"
            )

            if not timestamp:
                continue

            try:

                people = int(
                    float(
                        row.get(
                            "total_people",
                            0
                        )
                    )
                )

            except Exception:

                people = 0

            timestamp_people[
                timestamp
            ] = people

        occupancy_values = []

        for people in timestamp_people.values():

            occupancy_values.append(
                (
                    people
                    / capacity
                ) * 100
            )

        if not occupancy_values:

            return {
                "peak_occupancy": 0.0,
                "average_occupancy": 0.0,
                "minimum_occupancy": 0.0
            }

        return {

            "peak_occupancy":
                round(
                    max(
                        occupancy_values
                    ),
                    1
                ),

            "average_occupancy":
                round(
                    sum(
                        occupancy_values
                    )
                    / len(
                        occupancy_values
                    ),
                    1
                ),

            "minimum_occupancy":
                round(
                    min(
                        occupancy_values
                    ),
                    1
                )
        }

    # =========================================================
    # DENSITY STATISTICS
    # =========================================================

    def calculate_density_statistics(
        self,
        rows
    ):

        if not rows:

            return {
                "peak_density": 0.0,
                "average_density": 0.0,
                "minimum_density": 0.0
            }

        density_values = []

        for row in rows:

            try:

                density_values.append(
                    float(
                        row.get(
                            "density",
                            0
                        )
                    )
                )

            except Exception:

                continue

        if not density_values:

            return {
                "peak_density": 0.0,
                "average_density": 0.0,
                "minimum_density": 0.0
            }

        return {

            "peak_density":
                round(
                    max(
                        density_values
                    ),
                    4
                ),

            "average_density":
                round(
                    sum(
                        density_values
                    )
                    / len(
                        density_values
                    ),
                    4
                ),

            "minimum_density":
                round(
                    min(
                        density_values
                    ),
                    4
                )
        }

    # =========================================================
    # ZONE STATISTICS
    # =========================================================

    def calculate_zone_statistics(
        self,
        rows
    ):

        current_zone_ids = (
            self.get_current_zone_ids()
        )

        rows = (
            self.filter_rows_to_current_zones(
                rows
            )
        )

        zones = {}

        # -----------------------------------------------------
        # CREATE CURRENT ZONES
        # -----------------------------------------------------

        for zone_id in current_zone_ids:

            zones[zone_id] = {

                "zone_id":
                    zone_id,

                # Compatibility fields used
                # by the report exporter.
                "people":
                    0,

                "density":
                    0.0,

                "risk":
                    "SAFE",

                "peak_people":
                    0,

                "peak_density":
                    0.0,

                "average_people":
                    0.0,

                "warning_records":
                    0,

                "critical_records":
                    0,

                "records":
                    0,

                # Internal field used to determine
                # the latest state of this zone.
                "_latest_timestamp":
                    None
            }

        # -----------------------------------------------------
        # PROCESS CURRENT ZONE DATA
        # -----------------------------------------------------

        for row in rows:

            zone_id = str(
                row.get(
                    "zone_id",
                    ""
                )
            )

            if not zone_id:
                continue

            if (
                current_zone_ids
                and zone_id not in current_zone_ids
            ):
                continue

            if zone_id not in zones:

                zones[zone_id] = {

                    "zone_id":
                        zone_id,

                    "people":
                        0,

                    "density":
                        0.0,

                    "risk":
                        "SAFE",

                    "peak_people":
                        0,

                    "peak_density":
                        0.0,

                    "average_people":
                        0.0,

                    "warning_records":
                        0,

                    "critical_records":
                        0,

                    "records":
                        0,

                    "_latest_timestamp":
                        None
                }

            zone = zones[
                zone_id
            ]

            # -------------------------------------------------
            # PEOPLE
            # -------------------------------------------------

            try:

                people = int(
                    float(
                        row.get(
                            "zone_people",
                            0
                        )
                    )
                )

            except Exception:

                people = 0

            # -------------------------------------------------
            # DENSITY
            # -------------------------------------------------

            try:

                density = float(
                    row.get(
                        "density",
                        0
                    )
                )

            except Exception:

                density = 0.0

            # -------------------------------------------------
            # RISK
            # -------------------------------------------------

            risk = str(
                row.get(
                    "risk",
                    "SAFE"
                )
            ).upper()

            if risk not in {
                "SAFE",
                "WARNING",
                "CRITICAL"
            }:

                risk = "SAFE"

            # -------------------------------------------------
            # PEAK VALUES
            # -------------------------------------------------

            zone[
                "peak_people"
            ] = max(
                zone[
                    "peak_people"
                ],
                people
            )

            zone[
                "peak_density"
            ] = max(
                zone[
                    "peak_density"
                ],
                density
            )

            # -------------------------------------------------
            # AVERAGE
            # -------------------------------------------------

            zone[
                "average_people"
            ] += people

            zone[
                "records"
            ] += 1

            # -------------------------------------------------
            # RISK RECORDS
            # -------------------------------------------------

            if risk == "WARNING":

                zone[
                    "warning_records"
                ] += 1

            elif risk == "CRITICAL":

                zone[
                    "critical_records"
                ] += 1

            # -------------------------------------------------
            # LATEST ZONE STATE
            # -------------------------------------------------

            timestamp_text = str(
                row.get(
                    "timestamp",
                    ""
                )
            ).strip()

            timestamp_value = None

            if timestamp_text:

                try:

                    timestamp_value = datetime.strptime(
                        timestamp_text,
                        "%Y-%m-%d %H:%M:%S"
                    )

                except Exception:

                    timestamp_value = None

            latest_timestamp = zone.get(
                "_latest_timestamp"
            )

            if (
                latest_timestamp is None
                or (
                    timestamp_value is not None
                    and timestamp_value >= latest_timestamp
                )
            ):

                zone[
                    "people"
                ] = people

                zone[
                    "density"
                ] = density

                zone[
                    "risk"
                ] = risk

                if timestamp_value is not None:

                    zone[
                        "_latest_timestamp"
                    ] = timestamp_value

        # -----------------------------------------------------
        # FINALIZE ZONES
        # -----------------------------------------------------

        for zone in zones.values():

            records = zone[
                "records"
            ]

            if records > 0:

                zone[
                    "average_people"
                ] = round(
                    zone[
                        "average_people"
                    ]
                    / records,
                    2
                )

            else:

                zone[
                    "average_people"
                ] = 0.0

            zone[
                "peak_density"
            ] = round(
                zone[
                    "peak_density"
                ],
                4
            )

            zone[
                "density"
            ] = round(
                zone[
                    "density"
                ],
                4
            )

            # If the report has historical rows,
            # "people" and "density" represent the
            # latest state, while peak_* remains available
            # for historical maximums.

            zone.pop(
                "_latest_timestamp",
                None
            )

        return zones

    # =========================================================
    # MOST CROWDED ZONE
    # =========================================================

    def get_most_crowded_zone(
        self,
        zone_statistics
    ):

        if not zone_statistics:

            return None

        zones = list(
            zone_statistics.values()
        )

        zones.sort(
            key=lambda zone:
                zone.get(
                    "peak_people",
                    0
                ),
            reverse=True
        )

        return zones[0].copy()

    # =========================================================
    # RISK STATISTICS
    # =========================================================

    def calculate_risk_statistics(
        self,
        rows
    ):

        statistics = {

            "safe_records":
                0,

            "warning_records":
                0,

            "critical_records":
                0
        }

        if not rows:

            return statistics

        timestamp_risk = {}

        risk_priority = {

            "SAFE": 0,
            "WARNING": 1,
            "CRITICAL": 2
        }

        for row in rows:

            timestamp = row.get(
                "timestamp"
            )

            if not timestamp:
                continue

            risk = str(
                row.get(
                    "risk",
                    "SAFE"
                )
            ).upper()

            if risk not in risk_priority:

                risk = "SAFE"

            current_risk = (
                timestamp_risk.get(
                    timestamp,
                    "SAFE"
                )
            )

            if (
                risk_priority[risk]
                >
                risk_priority[current_risk]
            ):

                timestamp_risk[
                    timestamp
                ] = risk

            elif (
                timestamp
                not in timestamp_risk
            ):

                timestamp_risk[
                    timestamp
                ] = risk

        for risk in timestamp_risk.values():

            if risk == "CRITICAL":

                statistics[
                    "critical_records"
                ] += 1

            elif risk == "WARNING":

                statistics[
                    "warning_records"
                ] += 1

            else:

                statistics[
                    "safe_records"
                ] += 1

        return statistics

    # =========================================================
    # TIME RANGE
    # =========================================================

    def calculate_time_range(
        self,
        rows
    ):

        if not rows:

            return {
                "start_time": None,
                "end_time": None,
                "duration_seconds": 0
            }

        timestamps = []

        for row in rows:

            timestamp = row.get(
                "timestamp"
            )

            if not timestamp:
                continue

            try:

                parsed = datetime.strptime(
                    timestamp,
                    "%Y-%m-%d %H:%M:%S"
                )

                timestamps.append(
                    parsed
                )

            except Exception:

                continue

        if not timestamps:

            return {
                "start_time": None,
                "end_time": None,
                "duration_seconds": 0
            }

        start_time = min(
            timestamps
        )

        end_time = max(
            timestamps
        )

        duration = (
            end_time
            - start_time
        ).total_seconds()

        return {

            "start_time":
                start_time.strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),

            "end_time":
                end_time.strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),

            "duration_seconds":
                int(duration)
        }

    # =========================================================
    # PARSE EVENT TIME
    # =========================================================

    @staticmethod
    def _parse_event_time(
        value
    ):

        if not value:
            return None

        formats = [

            "%Y-%m-%d %H:%M:%S",

            "%Y-%m-%d %H:%M:%S.%f"
        ]

        for fmt in formats:

            try:

                return datetime.strptime(
                    str(value),
                    fmt
                )

            except Exception:

                continue

        return None

    # =========================================================
    # ALERT STATISTICS
    # =========================================================

    def calculate_alert_statistics(
        self,
        alerts=None
    ):

        if alerts is None:

            if self.alert_manager is None:

                alerts = []

            else:

                try:

                    alerts = (
                        self.alert_manager
                        .get_alerts()
                        or []
                    )

                except Exception:

                    alerts = []

        statistics = {

            "warning": 0,
            "critical": 0,
            "total": 0
        }

        for alert in alerts:

            if not isinstance(
                alert,
                dict
            ):

                continue

            risk = str(
                alert.get(
                    "risk",
                    ""
                )
            ).upper()

            if risk == "CRITICAL":

                statistics[
                    "critical"
                ] += 1

            elif risk == "WARNING":

                statistics[
                    "warning"
                ] += 1

            statistics[
                "total"
            ] += 1

        return statistics

    # =========================================================
    # INCIDENT STATISTICS
    # =========================================================

    def calculate_incident_statistics(
        self,
        incidents=None
    ):

        if incidents is None:

            if self.incident_manager is None:

                incidents = []

            else:

                try:

                    incidents = (
                        self.incident_manager
                        .get_incidents()
                        or []
                    )

                except Exception:

                    incidents = []

        statistics = {

            "warning": 0,
            "critical": 0,
            "total": 0
        }

        for incident in incidents:

            if not isinstance(
                incident,
                dict
            ):

                continue

            risk = str(
                incident.get(
                    "risk",
                    ""
                )
            ).upper()

            if risk == "CRITICAL":

                statistics[
                    "critical"
                ] += 1

            elif risk == "WARNING":

                statistics[
                    "warning"
                ] += 1

            statistics[
                "total"
            ] += 1

        return statistics

    # =========================================================
    # COMPLETE ANALYTICS
    # =========================================================

    def generate_report_data(
        self,
        rows,
        capacity=0,
        venue_name="Unknown Venue",
        alerts=None,
        incidents=None
    ):

        if rows is None:

            rows = []

        people_statistics = (
            self.calculate_people_statistics(
                rows
            )
        )

        occupancy_statistics = (
            self.calculate_occupancy_statistics(
                rows,
                capacity
            )
        )

        density_statistics = (
            self.calculate_density_statistics(
                rows
            )
        )

        zone_statistics = (
            self.calculate_zone_statistics(
                rows
            )
        )

        risk_statistics = (
            self.calculate_risk_statistics(
                rows
            )
        )

        time_range = (
            self.calculate_time_range(
                rows
            )
        )

        most_crowded_zone = (
            self.get_most_crowded_zone(
                zone_statistics
            )
        )

        alert_statistics = (
            self.calculate_alert_statistics(
                alerts
            )
        )

        incident_statistics = (
            self.calculate_incident_statistics(
                incidents
            )
        )

        try:

            capacity_value = int(
                float(capacity)
            )

        except Exception:

            capacity_value = 0

        return {

            "venue":
                venue_name,

            "capacity":
                capacity_value,

            "time_range":
                time_range,

            "people":
                people_statistics,

            "occupancy":
                occupancy_statistics,

            "density":
                density_statistics,

            "risk":
                risk_statistics,

            "alerts":
                alert_statistics,

            "incidents":
                incident_statistics,

            "zones":
                zone_statistics,

            "most_crowded_zone":
                most_crowded_zone
        }

    # =========================================================
    # LOG FILE
    # =========================================================

    def get_log_file(self):

        return self.log_file