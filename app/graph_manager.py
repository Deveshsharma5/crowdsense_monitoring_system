import csv
import os
from datetime import datetime

# IMPORTANT:
# Use a non-GUI Matplotlib backend.
# This prevents Tkinter / Windows GUI errors when
# graphs are generated from a background thread.
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt


# ============================================================
# PATHS
# ============================================================

LOG_FILE = "data/logs/crowd_log.csv"

GRAPH_FOLDER = "data/graphs"


# ============================================================
# GRAPH MANAGER
# ============================================================

class CrowdGraphManager:

    def __init__(self):

        os.makedirs(
            GRAPH_FOLDER,
            exist_ok=True
        )

    # ========================================================
    # READ LOG
    # ========================================================

    def read_log(self):

        if not os.path.exists(LOG_FILE):
            return []

        rows = []

        try:

            with open(
                LOG_FILE,
                "r",
                newline="",
                encoding="utf-8"
            ) as file:

                reader = csv.DictReader(file)

                for row in reader:

                    try:

                        timestamp = datetime.strptime(
                            row["timestamp"],
                            "%Y-%m-%d %H:%M:%S"
                        )

                        total_people = int(
                            float(
                                row.get(
                                    "total_people",
                                    0
                                )
                            )
                        )

                        zone_people = int(
                            float(
                                row.get(
                                    "zone_people",
                                    0
                                )
                            )
                        )

                        density = float(
                            row.get(
                                "density",
                                0
                            )
                        )

                        risk = str(
                            row.get(
                                "risk",
                                "SAFE"
                            )
                        ).upper()

                        zone_id = row.get(
                            "zone_id",
                            ""
                        )

                        rows.append({

                            "timestamp":
                                timestamp,

                            "total_people":
                                total_people,

                            "zone_people":
                                zone_people,

                            "density":
                                density,

                            "risk":
                                risk,

                            "zone_id":
                                zone_id
                        })

                    except Exception:
                        continue

        except Exception as error:

            print(
                f"Graph log read error: {error}"
            )

            return []

        rows.sort(
            key=lambda row: row["timestamp"]
        )

        return rows

    # ========================================================
    # FILTER LOG BY TIME
    # ========================================================

    def filter_rows(
        self,
        rows,
        start_time=None,
        end_time=None
    ):

        if not rows:
            return []

        filtered = []

        for row in rows:

            timestamp = row["timestamp"]

            if start_time is not None:
                if timestamp < start_time:
                    continue

            if end_time is not None:
                if timestamp > end_time:
                    continue

            filtered.append(row)

        return filtered

    # ========================================================
    # PEOPLE OVER TIME
    # ========================================================

    def generate_people_graph(
        self,
        rows
    ):

        if not rows:
            return None

        # One total value per timestamp
        data = {}

        for row in rows:

            timestamp = row["timestamp"]

            data[timestamp] = (
                row["total_people"]
            )

        timestamps = sorted(
            data.keys()
        )

        people = [
            data[timestamp]
            for timestamp in timestamps
        ]

        plt.figure(
            figsize=(10, 5)
        )

        plt.plot(
            timestamps,
            people,
            marker="o"
        )

        plt.title(
            "CrowdSense - People Over Time"
        )

        plt.xlabel(
            "Time"
        )

        plt.ylabel(
            "People"
        )

        plt.xticks(
            rotation=45
        )

        plt.grid(
            True
        )

        plt.tight_layout()

        path = os.path.join(
            GRAPH_FOLDER,
            "people_over_time.png"
        )

        plt.savefig(
            path,
            dpi=120
        )

        plt.close()

        return path

    # ========================================================
    # ZONE OCCUPANCY
    # ========================================================

    def generate_zone_graph(
        self,
        rows
    ):

        if not rows:
            return None

        latest = {}

        for row in rows:

            zone_id = row["zone_id"]

            if zone_id:

                latest[zone_id] = (
                    row["zone_people"]
                )

        if not latest:
            return None

        zone_ids = sorted(
            latest.keys()
        )

        people = [
            latest[zone]
            for zone in zone_ids
        ]

        plt.figure(
            figsize=(10, 5)
        )

        plt.bar(
            zone_ids,
            people
        )

        plt.title(
            "CrowdSense - Zone Occupancy"
        )

        plt.xlabel(
            "Zone"
        )

        plt.ylabel(
            "People"
        )

        plt.grid(
            axis="y"
        )

        plt.tight_layout()

        path = os.path.join(
            GRAPH_FOLDER,
            "zone_occupancy.png"
        )

        plt.savefig(
            path,
            dpi=120
        )

        plt.close()

        return path

    # ========================================================
    # DENSITY OVER TIME
    # ========================================================

    def generate_density_graph(
        self,
        rows
    ):

        if not rows:
            return None

        data = {}

        for row in rows:

            timestamp = row["timestamp"]

            density = row["density"]

            if timestamp not in data:

                data[timestamp] = density

            else:

                data[timestamp] = max(
                    data[timestamp],
                    density
                )

        timestamps = sorted(
            data.keys()
        )

        density_values = [
            data[timestamp]
            for timestamp in timestamps
        ]

        plt.figure(
            figsize=(10, 5)
        )

        plt.plot(
            timestamps,
            density_values,
            marker="o"
        )

        plt.title(
            "CrowdSense - Crowd Density"
        )

        plt.xlabel(
            "Time"
        )

        plt.ylabel(
            "Density"
        )

        plt.xticks(
            rotation=45
        )

        plt.grid(
            True
        )

        plt.tight_layout()

        path = os.path.join(
            GRAPH_FOLDER,
            "density_over_time.png"
        )

        plt.savefig(
            path,
            dpi=120
        )

        plt.close()

        return path

    # ========================================================
    # RISK HISTORY
    # ========================================================

    def generate_risk_graph(
        self,
        rows
    ):

        if not rows:
            return None

        data = {}

        risk_values = {

            "SAFE": 0,

            "WARNING": 1,

            "CRITICAL": 2
        }

        for row in rows:

            timestamp = row["timestamp"]

            risk = row["risk"]

            value = risk_values.get(
                risk,
                0
            )

            if timestamp not in data:

                data[timestamp] = value

            else:

                data[timestamp] = max(
                    data[timestamp],
                    value
                )

        timestamps = sorted(
            data.keys()
        )

        values = [
            data[timestamp]
            for timestamp in timestamps
        ]

        plt.figure(
            figsize=(10, 5)
        )

        plt.plot(
            timestamps,
            values,
            marker="o"
        )

        plt.title(
            "CrowdSense - Risk History"
        )

        plt.xlabel(
            "Time"
        )

        plt.ylabel(
            "Risk Level"
        )

        plt.yticks(
            [0, 1, 2],
            [
                "SAFE",
                "WARNING",
                "CRITICAL"
            ]
        )

        plt.xticks(
            rotation=45
        )

        plt.grid(
            True
        )

        plt.tight_layout()

        path = os.path.join(
            GRAPH_FOLDER,
            "risk_history.png"
        )

        plt.savefig(
            path,
            dpi=120
        )

        plt.close()

        return path

    # ========================================================
    # SESSION SUMMARY
    # ========================================================

    def get_summary(
        self,
        rows=None
    ):

        if rows is None:
            rows = self.read_log()

        if not rows:

            return {
                "total_records": 0,
                "start_time": None,
                "end_time": None,
                "duration_seconds": 0,
                "peak_people": 0,
                "average_people": 0.0,
                "peak_density": 0.0,
                "safe_records": 0,
                "warning_records": 0,
                "critical_records": 0,
                "warning_events": 0,
                "critical_events": 0,
                "zone_summary": {}
            }

        # ----------------------------------------------------
        # Total / time
        # ----------------------------------------------------

        timestamps = [
            row["timestamp"]
            for row in rows
        ]

        start_time = min(
            timestamps
        )

        end_time = max(
            timestamps
        )

        duration_seconds = (
            end_time - start_time
        ).total_seconds()

        # ----------------------------------------------------
        # People statistics
        # ----------------------------------------------------

        # Total people is repeated for each zone row.
        # Therefore use one value per timestamp.

        timestamp_people = {}

        for row in rows:

            timestamp = row["timestamp"]

            timestamp_people[timestamp] = (
                row["total_people"]
            )

        people_values = list(
            timestamp_people.values()
        )

        peak_people = max(
            people_values
        ) if people_values else 0

        average_people = (
            sum(people_values)
            / len(people_values)
            if people_values
            else 0.0
        )

        # ----------------------------------------------------
        # Density
        # ----------------------------------------------------

        peak_density = 0.0

        for row in rows:

            peak_density = max(
                peak_density,
                float(row.get("density", 0.0))
            )

        # ----------------------------------------------------
        # Risk records
        # ----------------------------------------------------

        safe_records = 0
        warning_records = 0
        critical_records = 0

        for row in rows:

            risk = row.get(
                "risk",
                "SAFE"
            )

            if risk == "CRITICAL":

                critical_records += 1

            elif risk == "WARNING":

                warning_records += 1

            else:

                safe_records += 1

        # ----------------------------------------------------
        # Risk events
        # ----------------------------------------------------

        # Count transitions into WARNING/CRITICAL
        # instead of counting every repeated log row.

        risk_by_timestamp = {}

        for row in rows:

            timestamp = row["timestamp"]

            risk = row.get(
                "risk",
                "SAFE"
            )

            current_value = {
                "SAFE": 0,
                "WARNING": 1,
                "CRITICAL": 2
            }.get(
                risk,
                0
            )

            if timestamp not in risk_by_timestamp:

                risk_by_timestamp[timestamp] = (
                    current_value
                )

            else:

                risk_by_timestamp[timestamp] = max(
                    risk_by_timestamp[timestamp],
                    current_value
                )

        sorted_risk = sorted(
            risk_by_timestamp.items()
        )

        warning_events = 0
        critical_events = 0

        previous_risk = 0

        for _, current_risk in sorted_risk:

            if (
                current_risk >= 1
                and previous_risk < 1
            ):
                warning_events += 1

            if (
                current_risk >= 2
                and previous_risk < 2
            ):
                critical_events += 1

            previous_risk = current_risk

        # ----------------------------------------------------
        # Zone summary
        # ----------------------------------------------------

        zone_summary = {}

        for row in rows:

            zone_id = row.get(
                "zone_id",
                ""
            )

            if not zone_id:
                continue

            if zone_id not in zone_summary:

                zone_summary[zone_id] = {
                    "peak_people": 0,
                    "peak_density": 0.0,
                    "warning_records": 0,
                    "critical_records": 0
                }

            zone = zone_summary[zone_id]

            zone["peak_people"] = max(
                zone["peak_people"],
                int(row.get("zone_people", 0))
            )

            zone["peak_density"] = max(
                zone["peak_density"],
                float(row.get("density", 0.0))
            )

            if row.get("risk") == "WARNING":

                zone["warning_records"] += 1

            elif row.get("risk") == "CRITICAL":

                zone["critical_records"] += 1

        return {

            "total_records":
                len(rows),

            "start_time":
                start_time.strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),

            "end_time":
                end_time.strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),

            "duration_seconds":
                int(duration_seconds),

            "peak_people":
                int(peak_people),

            "average_people":
                round(
                    average_people,
                    2
                ),

            "peak_density":
                round(
                    peak_density,
                    4
                ),

            "safe_records":
                safe_records,

            "warning_records":
                warning_records,

            "critical_records":
                critical_records,

            "warning_events":
                warning_events,

            "critical_events":
                critical_events,

            "zone_summary":
                zone_summary
        }

    # ========================================================
    # GRAPH PATHS
    # ========================================================

    def get_graph_paths(self):

        return {

            "people":
                os.path.join(
                    GRAPH_FOLDER,
                    "people_over_time.png"
                ),

            "zones":
                os.path.join(
                    GRAPH_FOLDER,
                    "zone_occupancy.png"
                ),

            "density":
                os.path.join(
                    GRAPH_FOLDER,
                    "density_over_time.png"
                ),

            "risk":
                os.path.join(
                    GRAPH_FOLDER,
                    "risk_history.png"
                )
        }

    # ========================================================
    # GENERATE ALL
    # ========================================================

    def generate_all(
        self,
        rows=None
    ):

        try:

            if rows is None:

                rows = self.read_log()

            if not rows:

                print(
                    "No crowd log data available for graphs."
                )

                return False

            self.generate_people_graph(
                rows
            )

            self.generate_zone_graph(
                rows
            )

            self.generate_density_graph(
                rows
            )

            self.generate_risk_graph(
                rows
            )

            print(
                "CrowdSense graphs updated."
            )

            return True

        except Exception as error:

            print(
                f"Graph generation error: {error}"
            )

            return False