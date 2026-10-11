import os
import shutil
import tempfile
from datetime import datetime

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import (
        getSampleStyleSheet,
        ParagraphStyle
    )
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
        Image,
        PageBreak
    )

    REPORTLAB_AVAILABLE = True

except ImportError:

    REPORTLAB_AVAILABLE = False


class ReportExporter:

    def __init__(
        self,
        report_manager=None,
        graph_manager=None,
        output_folder="data/reports"
    ):

        self.report_manager = report_manager

        self.graph_manager = graph_manager

        self.output_folder = output_folder

        os.makedirs(
            self.output_folder,
            exist_ok=True
        )

    # =========================================================
    # BASIC HELPERS
    # =========================================================

    def get_output_folder(self):

        return self.output_folder

    # =========================================================
    # ANALYTICS DATA HELPER
    # =========================================================

    def get_analytics_data(
        self,
        report
    ):

        if not isinstance(
            report,
            dict
        ):

            return {}

        analytics = report.get(
            "analytics"
        )

        if isinstance(
            analytics,
            dict
        ):

            return analytics

        return report

    # =========================================================
    # GRAPH DATA
    # =========================================================

    def get_report_rows(
        self,
        report
    ):

        if self.report_manager is None:

            return []

        try:

            rows = (
                self.report_manager
                .load_log_rows()
            )

        except Exception:

            return []

        if not rows:

            return []

        session = None

        if isinstance(
            report,
            dict
        ):

            session = report.get(
                "session"
            )

        # -----------------------------------------------------
        # Use the exact same session filtering as ReportManager.
        # -----------------------------------------------------

        if session:

            try:

                return (
                    self.report_manager
                    .filter_rows_by_session(
                        rows,
                        session
                    )
                )

            except Exception:

                pass

        # -----------------------------------------------------
        # Fallback:
        # use analytics time range if available.
        # -----------------------------------------------------

        analytics = (
            self.get_analytics_data(
                report
            )
        )

        time_range = analytics.get(
            "time_range",
            {}
        )

        start_text = time_range.get(
            "start_time"
        )

        end_text = time_range.get(
            "end_time"
        )

        if not start_text:

            return rows

        try:

            start_time = datetime.strptime(
                start_text,
                "%Y-%m-%d %H:%M:%S"
            )

        except Exception:

            return rows

        end_time = None

        if end_text:

            try:

                end_time = datetime.strptime(
                    end_text,
                    "%Y-%m-%d %H:%M:%S"
                )

            except Exception:

                end_time = None

        filtered = []

        for row in rows:

            timestamp = row.get(
                "timestamp"
            )

            if not timestamp:
                continue

            try:

                record_time = datetime.strptime(
                    timestamp,
                    "%Y-%m-%d %H:%M:%S"
                )

            except Exception:

                continue

            if record_time < start_time:

                continue

            if (
                end_time is not None
                and record_time > end_time
            ):

                continue

            filtered.append(
                row
            )

        return filtered

    # =========================================================
    # TEMPORARY REPORT GRAPHS
    # =========================================================

    def generate_report_graphs(
        self,
        rows,
        folder
    ):

        if not rows:

            return []

        os.makedirs(
            folder,
            exist_ok=True
        )

        generated = []

        # -----------------------------------------------------
        # PEOPLE OVER TIME
        # -----------------------------------------------------

        people_data = {}

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

            people_data[
                timestamp
            ] = people

        if people_data:

            timestamps = sorted(
                people_data.keys()
            )

            values = [
                people_data[
                    timestamp
                ]
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
                folder,
                "people_over_time.png"
            )

            plt.savefig(
                path,
                dpi=120
            )

            plt.close()

            generated.append(
                (
                    "People Over Time",
                    path
                )
            )

        # -----------------------------------------------------
        # ZONE OCCUPANCY
        # -----------------------------------------------------

        latest_zone = {}

        for row in rows:

            zone_id = str(
                row.get(
                    "zone_id",
                    ""
                )
            ).strip()

            if not zone_id:
                continue

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

            latest_zone[
                zone_id
            ] = people

        if latest_zone:

            zone_ids = sorted(
                latest_zone.keys()
            )

            values = [
                latest_zone[
                    zone
                ]
                for zone in zone_ids
            ]

            plt.figure(
                figsize=(10, 5)
            )

            plt.bar(
                zone_ids,
                values
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
                folder,
                "zone_occupancy.png"
            )

            plt.savefig(
                path,
                dpi=120
            )

            plt.close()

            generated.append(
                (
                    "Zone Occupancy",
                    path
                )
            )

        # -----------------------------------------------------
        # DENSITY OVER TIME
        # -----------------------------------------------------

        density_data = {}

        for row in rows:

            timestamp = row.get(
                "timestamp"
            )

            if not timestamp:
                continue

            try:

                density = float(
                    row.get(
                        "density",
                        0
                    )
                )

            except Exception:

                continue

            if timestamp not in density_data:

                density_data[
                    timestamp
                ] = density

            else:

                density_data[
                    timestamp
                ] = max(
                    density_data[
                        timestamp
                    ],
                    density
                )

        if density_data:

            timestamps = sorted(
                density_data.keys()
            )

            values = [
                density_data[
                    timestamp
                ]
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
                folder,
                "density_over_time.png"
            )

            plt.savefig(
                path,
                dpi=120
            )

            plt.close()

            generated.append(
                (
                    "Crowd Density",
                    path
                )
            )

        # -----------------------------------------------------
        # RISK HISTORY
        # -----------------------------------------------------

        risk_data = {}

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

            value = risk_priority.get(
                risk,
                0
            )

            if timestamp not in risk_data:

                risk_data[
                    timestamp
                ] = value

            else:

                risk_data[
                    timestamp
                ] = max(
                    risk_data[
                        timestamp
                    ],
                    value
                )

        if risk_data:

            timestamps = sorted(
                risk_data.keys()
            )

            values = [
                risk_data[
                    timestamp
                ]
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
                folder,
                "risk_history.png"
            )

            plt.savefig(
                path,
                dpi=120
            )

            plt.close()

            generated.append(
                (
                    "Risk History",
                    path
                )
            )

        return generated

    # =========================================================
    # GRAPH INSERTION
    # =========================================================

    def add_graphs_to_report(
        self,
        story,
        graph_paths
    ):

        if not graph_paths:

            return

        story.append(
            PageBreak()
        )

        story.append(
            Paragraph(
                "CrowdSense Analytics Graphs",
                self.styles["SectionTitle"]
            )
        )

        story.append(
            Spacer(
                1,
                8
            )
        )

        for graph_name, graph_path in graph_paths:

            story.append(
                Paragraph(
                    graph_name,
                    self.styles["SubTitle"]
                )
            )

            story.append(
                Spacer(
                    1,
                    5
                )
            )

            try:

                image = Image(
                    graph_path,
                    width=170 * mm,
                    height=90 * mm
                )

                story.append(
                    image
                )

            except Exception:

                story.append(
                    Paragraph(
                        "Unable to load this graph.",
                        self.styles["Normal"]
                    )
                )

            story.append(
                Spacer(
                    1,
                    12
                )
            )

    # =========================================================
    # SAFE VALUE CONVERSION
    # =========================================================

    def safe(
        self,
        value,
        default="N/A"
    ):

        if value is None:
            return default

        if isinstance(
            value,
            float
        ):

            return f"{value:.2f}"

        if isinstance(
            value,
            int
        ):

            return str(value)

        text = str(
            value
        ).strip()

        if not text:
            return default

        return text

    # =========================================================
    # DICTIONARY VALUE HELPER
    # =========================================================

    def get_value(
        self,
        data,
        *keys,
        default=None
    ):

        if not isinstance(
            data,
            dict
        ):

            return default

        for key in keys:

            if key in data:

                return data[key]

        return default

    # =========================================================
    # TABLE CREATION
    # =========================================================

    def make_table(
        self,
        data,
        column_widths=None
    ):

        table = Table(
            data,
            colWidths=column_widths,
            repeatRows=1
        )

        table.setStyle(
            TableStyle(
                [
                    (
                        "BACKGROUND",
                        (0, 0),
                        (-1, 0),
                        colors.HexColor(
                            "#173D2C"
                        )
                    ),
                    (
                        "TEXTCOLOR",
                        (0, 0),
                        (-1, 0),
                        colors.white
                    ),
                    (
                        "FONTNAME",
                        (0, 0),
                        (-1, 0),
                        "Helvetica-Bold"
                    ),
                    (
                        "FONTNAME",
                        (0, 1),
                        (-1, -1),
                        "Helvetica"
                    ),
                    (
                        "FONTSIZE",
                        (0, 0),
                        (-1, -1),
                        8
                    ),
                    (
                        "GRID",
                        (0, 0),
                        (-1, -1),
                        0.5,
                        colors.grey
                    ),
                    (
                        "VALIGN",
                        (0, 0),
                        (-1, -1),
                        "MIDDLE"
                    ),
                    (
                        "LEFTPADDING",
                        (0, 0),
                        (-1, -1),
                        6
                    ),
                    (
                        "RIGHTPADDING",
                        (0, 0),
                        (-1, -1),
                        6
                    ),
                    (
                        "TOPPADDING",
                        (0, 0),
                        (-1, -1),
                        5
                    ),
                    (
                        "BOTTOMPADDING",
                        (0, 0),
                        (-1, -1),
                        5
                    )
                ]
            )
        )

        return table

    # =========================================================
    # REPORT SECTIONS
    # =========================================================

    def add_venue_section(
        self,
        story,
        report
    ):

        venue = report.get(
            "venue",
            {}
        )

        story.append(
            Paragraph(
                "Venue Information",
                self.styles["SectionTitle"]
            )
        )

        story.append(
            Spacer(
                1,
                5
            )
        )

        data = [
            [
                "Field",
                "Value"
            ],
            [
                "Venue Name",
                self.safe(
                    self.get_value(
                        venue,
                        "name",
                        "venue_name"
                    )
                )
            ],
            [
                "Shape",
                self.safe(
                    self.get_value(
                        venue,
                        "shape"
                    )
                )
            ],
            [
                "Length",
                self.safe(
                    self.get_value(
                        venue,
                        "length",
                        "venue_length"
                    )
                )
            ],
            [
                "Width",
                self.safe(
                    self.get_value(
                        venue,
                        "width",
                        "venue_width"
                    )
                )
            ],
            [
                "Capacity",
                self.safe(
                    self.get_value(
                        venue,
                        "capacity"
                    )
                )
            ]
        ]

        story.append(
            self.make_table(
                data,
                [
                    60 * mm,
                    110 * mm
                ]
            )
        )

        story.append(
            Spacer(
                1,
                12
            )
        )

    # =========================================================
    # PEOPLE
    # =========================================================

    def add_people_section(
        self,
        story,
        report
    ):

        analytics = (
            self.get_analytics_data(
                report
            )
        )

        people = analytics.get(
            "people",
            {}
        )

        story.append(
            Paragraph(
                "Crowd Statistics",
                self.styles["SectionTitle"]
            )
        )

        story.append(
            Spacer(
                1,
                5
            )
        )

        data = [
            [
                "Metric",
                "Value"
            ],
            [
                "Peak People",
                self.safe(
                    self.get_value(
                        people,
                        "maximum_people",
                        "max_people",
                        "peak_people"
                    )
                )
            ],
            [
                "Minimum People",
                self.safe(
                    self.get_value(
                        people,
                        "minimum_people",
                        "min_people"
                    )
                )
            ],
            [
                "Average People",
                self.safe(
                    self.get_value(
                        people,
                        "average_people",
                        "avg_people"
                    )
                )
            ],
            [
                "Total Records",
                self.safe(
                    self.get_value(
                        people,
                        "total_records",
                        "records"
                    )
                )
            ]
        ]

        story.append(
            self.make_table(
                data,
                [
                    80 * mm,
                    90 * mm
                ]
            )
        )

        story.append(
            Spacer(
                1,
                12
            )
        )

    # =========================================================
    # OCCUPANCY
    # =========================================================

    def add_occupancy_section(
        self,
        story,
        report
    ):

        analytics = (
            self.get_analytics_data(
                report
            )
        )

        occupancy = analytics.get(
            "occupancy",
            {}
        )

        story.append(
            Paragraph(
                "Occupancy Statistics",
                self.styles["SectionTitle"]
            )
        )

        story.append(
            Spacer(
                1,
                5
            )
        )

        data = [
            [
                "Metric",
                "Value"
            ],
            [
                "Peak Occupancy",
                self.safe(
                    self.get_value(
                        occupancy,
                        "maximum_occupancy",
                        "max_occupancy",
                        "peak_occupancy"
                    )
                )
            ],
            [
                "Minimum Occupancy",
                self.safe(
                    self.get_value(
                        occupancy,
                        "minimum_occupancy",
                        "min_occupancy"
                    )
                )
            ],
            [
                "Average Occupancy",
                self.safe(
                    self.get_value(
                        occupancy,
                        "average_occupancy",
                        "avg_occupancy"
                    )
                )
            ]
        ]

        story.append(
            self.make_table(
                data,
                [
                    80 * mm,
                    90 * mm
                ]
            )
        )

        story.append(
            Spacer(
                1,
                12
            )
        )

    # =========================================================
    # DENSITY
    # =========================================================

    def add_density_section(
        self,
        story,
        report
    ):

        analytics = (
            self.get_analytics_data(
                report
            )
        )

        density = analytics.get(
            "density",
            {}
        )

        story.append(
            Paragraph(
                "Density Statistics",
                self.styles["SectionTitle"]
            )
        )

        story.append(
            Spacer(
                1,
                5
            )
        )

        data = [
            [
                "Metric",
                "Value"
            ],
            [
                "Peak Density",
                self.safe(
                    self.get_value(
                        density,
                        "maximum_density",
                        "max_density",
                        "peak_density"
                    )
                )
            ],
            [
                "Minimum Density",
                self.safe(
                    self.get_value(
                        density,
                        "minimum_density",
                        "min_density"
                    )
                )
            ],
            [
                "Average Density",
                self.safe(
                    self.get_value(
                        density,
                        "average_density",
                        "avg_density"
                    )
                )
            ]
        ]

        story.append(
            self.make_table(
                data,
                [
                    80 * mm,
                    90 * mm
                ]
            )
        )

        story.append(
            Spacer(
                1,
                12
            )
        )

    # =========================================================
    # RISK
    # =========================================================

    def add_risk_section(
        self,
        story,
        report
    ):

        analytics = (
            self.get_analytics_data(
                report
            )
        )

        risk = analytics.get(
            "risk",
            {}
        )

        story.append(
            Paragraph(
                "Risk Statistics",
                self.styles["SectionTitle"]
            )
        )

        story.append(
            Spacer(
                1,
                5
            )
        )

        data = [
            [
                "Risk Level",
                "Count"
            ],
            [
                "SAFE",
                self.safe(
                    self.get_value(
                        risk,
                        "safe",
                        "safe_count",
                        "safe_records"
                    )
                )
            ],
            [
                "WARNING",
                self.safe(
                    self.get_value(
                        risk,
                        "warning",
                        "warning_count",
                        "warning_records"
                    )
                )
            ],
            [
                "CRITICAL",
                self.safe(
                    self.get_value(
                        risk,
                        "critical",
                        "critical_count",
                        "critical_records"
                    )
                )
            ]
        ]

        story.append(
            self.make_table(
                data,
                [
                    80 * mm,
                    90 * mm
                ]
            )
        )

        story.append(
            Spacer(
                1,
                12
            )
        )

    # =========================================================
    # ALERTS
    # =========================================================

    def add_alert_section(
        self,
        story,
        report
    ):

        analytics = (
            self.get_analytics_data(
                report
            )
        )

        alerts = analytics.get(
            "alerts",
            {}
        )

        story.append(
            Paragraph(
                "Alert Statistics",
                self.styles["SectionTitle"]
            )
        )

        story.append(
            Spacer(
                1,
                5
            )
        )

        if isinstance(
            alerts,
            list
        ):

            count = len(
                alerts
            )

            data = [
                [
                    "Metric",
                    "Value"
                ],
                [
                    "Total Alerts",
                    str(count)
                ]
            ]

        else:

            data = [
                [
                    "Metric",
                    "Value"
                ],
                [
                    "Total Alerts",
                    self.safe(
                        self.get_value(
                            alerts,
                            "total",
                            "total_alerts",
                            "count"
                        )
                    )
                ],
                [
                    "Warnings",
                    self.safe(
                        self.get_value(
                            alerts,
                            "warning",
                            "warnings",
                            "warning_count"
                        )
                    )
                ],
                [
                    "Critical",
                    self.safe(
                        self.get_value(
                            alerts,
                            "critical",
                            "critical_count"
                        )
                    )
                ]
            ]

        story.append(
            self.make_table(
                data,
                [
                    80 * mm,
                    90 * mm
                ]
            )
        )

        story.append(
            Spacer(
                1,
                12
            )
        )

    # =========================================================
    # INCIDENTS
    # =========================================================

    def add_incident_section(
        self,
        story,
        report
    ):

        analytics = (
            self.get_analytics_data(
                report
            )
        )

        incidents = analytics.get(
            "incidents",
            {}
        )

        story.append(
            Paragraph(
                "Incident Statistics",
                self.styles["SectionTitle"]
            )
        )

        story.append(
            Spacer(
                1,
                5
            )
        )

        if isinstance(
            incidents,
            list
        ):

            count = len(
                incidents
            )

        else:

            count = self.get_value(
                incidents,
                "total",
                "total_incidents",
                "count",
                default=0
            )

        data = [
            [
                "Metric",
                "Value"
            ],
            [
                "Total Incidents",
                self.safe(
                    count
                )
            ]
        ]

        story.append(
            self.make_table(
                data,
                [
                    80 * mm,
                    90 * mm
                ]
            )
        )

        story.append(
            Spacer(
                1,
                12
            )
        )

    # =========================================================
    # MOST CROWDED ZONE
    # =========================================================

    def add_most_crowded_section(
        self,
        story,
        report
    ):

        analytics = (
            self.get_analytics_data(
                report
            )
        )

        zone = analytics.get(
            "most_crowded_zone"
        )

        if not zone:
            return

        story.append(
            Paragraph(
                "Most Crowded Zone",
                self.styles["SectionTitle"]
            )
        )

        story.append(
            Spacer(
                1,
                5
            )
        )

        if isinstance(
            zone,
            dict
        ):

            zone_id = self.get_value(
                zone,
                "id",
                "zone_id",
                default="N/A"
            )

            people = self.get_value(
                zone,
                "people",
                "zone_people",
                "peak_people",
                default="N/A"
            )

            density = self.get_value(
                zone,
                "density",
                "peak_density",
                default="N/A"
            )

            risk = self.get_value(
                zone,
                "risk",
                default="N/A"
            )

        else:

            zone_id = zone

            people = "N/A"

            density = "N/A"

            risk = "N/A"

        data = [
            [
                "Field",
                "Value"
            ],
            [
                "Zone",
                self.safe(
                    zone_id
                )
            ],
            [
                "People",
                self.safe(
                    people
                )
            ],
            [
                "Density",
                self.safe(
                    density
                )
            ],
            [
                "Risk",
                self.safe(
                    risk
                )
            ]
        ]

        story.append(
            self.make_table(
                data,
                [
                    80 * mm,
                    90 * mm
                ]
            )
        )

        story.append(
            Spacer(
                1,
                12
            )
        )

    # =========================================================
    # ZONE STATISTICS
    # =========================================================

    def add_zone_section(
        self,
        story,
        report
    ):

        analytics = (
            self.get_analytics_data(
                report
            )
        )

        zones = analytics.get(
            "zones",
            []
        )

        if not zones:
            return

        if isinstance(
            zones,
            dict
        ):

            zone_list = []

            for zone_id, zone_data in zones.items():

                if isinstance(
                    zone_data,
                    dict
                ):

                    item = dict(
                        zone_data
                    )

                    item.setdefault(
                        "id",
                        zone_id
                    )

                else:

                    item = {

                        "id":
                            zone_id,

                        "people":
                            zone_data
                    }

                zone_list.append(
                    item
                )

        elif isinstance(
            zones,
            list
        ):

            zone_list = zones

        else:

            return

        story.append(
            PageBreak()
        )

        story.append(
            Paragraph(
                "Zone Statistics",
                self.styles["SectionTitle"]
            )
        )

        story.append(
            Spacer(
                1,
                6
            )
        )

        data = [
            [
                "Zone",
                "People",
                "Density",
                "Risk"
            ]
        ]

        for zone in zone_list:

            if not isinstance(
                zone,
                dict
            ):

                continue

            data.append(
                [
                    self.safe(
                        self.get_value(
                            zone,
                            "id",
                            "zone_id"
                        )
                    ),

                    self.safe(
                        self.get_value(
                            zone,
                            "people",
                            "zone_people",
                            "peak_people"
                        )
                    ),

                    self.safe(
                        self.get_value(
                            zone,
                            "density",
                            "peak_density"
                        )
                    ),

                    self.safe(
                        self.get_value(
                            zone,
                            "risk"
                        )
                    )
                ]
            )

        if len(data) > 1:

            story.append(
                self.make_table(
                    data,
                    [
                        35 * mm,
                        35 * mm,
                        45 * mm,
                        45 * mm
                    ]
                )
            )

    # =========================================================
    # PDF HEADER / FOOTER
    # =========================================================

    def _header_footer(
        self,
        canvas,
        document
    ):

        canvas.saveState()

        width, height = A4

        canvas.setFont(
            "Helvetica",
            8
        )

        canvas.drawString(
            20 * mm,
            10 * mm,
            "CrowdSense"
        )

        canvas.drawRightString(
            width - 20 * mm,
            10 * mm,
            f"Page {document.page}"
        )

        canvas.restoreState()

    # =========================================================
    # EXPORT PDF
    # =========================================================

    def export_pdf(
        self,
        report=None
    ):

        if not REPORTLAB_AVAILABLE:

            raise RuntimeError(
                "ReportLab is not installed. "
                "Run: pip install reportlab"
            )

        if report is None:

            if self.report_manager is None:

                raise RuntimeError(
                    "ReportManager is not configured."
                )

            report = (
                self.report_manager
                .generate_report()
            )

        if report is None:

            report = {}

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        filename = (
            f"crowdsense_report_"
            f"{timestamp}.pdf"
        )

        filepath = os.path.join(
            self.output_folder,
            filename
        )

        self.styles = getSampleStyleSheet()

        self.styles.add(
            ParagraphStyle(
                name="ReportTitle",
                parent=self.styles["Title"],
                fontSize=22,
                leading=26,
                alignment=TA_CENTER,
                spaceAfter=15
            )
        )

        self.styles.add(
            ParagraphStyle(
                name="SectionTitle",
                parent=self.styles["Heading2"],
                fontSize=14,
                leading=18,
                spaceBefore=8,
                spaceAfter=8
            )
        )

        self.styles.add(
            ParagraphStyle(
                name="SubTitle",
                parent=self.styles["Heading3"],
                fontSize=11,
                leading=14,
                spaceBefore=5,
                spaceAfter=5
            )
        )

        self.styles.add(
            ParagraphStyle(
                name="NormalSmall",
                parent=self.styles["Normal"],
                fontSize=9,
                leading=12
            )
        )

        document = SimpleDocTemplate(
            filepath,
            pagesize=A4,
            rightMargin=20 * mm,
            leftMargin=20 * mm,
            topMargin=18 * mm,
            bottomMargin=18 * mm
        )

        story = []

        # -----------------------------------------------------
        # TITLE
        # -----------------------------------------------------

        story.append(
            Paragraph(
                "CrowdSense Crowd Safety Report",
                self.styles["ReportTitle"]
            )
        )

        story.append(
            Paragraph(
                "Generated by the CrowdSense monitoring system",
                self.styles["NormalSmall"]
            )
        )

        story.append(
            Spacer(
                1,
                12
            )
        )

        generated_time = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        story.append(
            Paragraph(
                f"Generated: {generated_time}",
                self.styles["NormalSmall"]
            )
        )

        story.append(
            Spacer(
                1,
                15
            )
        )

        # -----------------------------------------------------
        # REPORT SECTIONS
        # -----------------------------------------------------

        self.add_venue_section(
            story,
            report
        )

        self.add_people_section(
            story,
            report
        )

        self.add_occupancy_section(
            story,
            report
        )

        self.add_density_section(
            story,
            report
        )

        self.add_risk_section(
            story,
            report
        )

        self.add_alert_section(
            story,
            report
        )

        self.add_incident_section(
            story,
            report
        )

        self.add_most_crowded_section(
            story,
            report
        )

        self.add_zone_section(
            story,
            report
        )

        # -----------------------------------------------------
        # GENERATE GRAPHS FROM THIS REPORT'S DATA
        # -----------------------------------------------------

        temporary_graph_folder = tempfile.mkdtemp(
            prefix="crowdsense_report_graphs_",
            dir=self.output_folder
        )

        try:

            report_rows = (
                self.get_report_rows(
                    report
                )
            )

            report_graphs = (
                self.generate_report_graphs(
                    report_rows,
                    temporary_graph_folder
                )
            )

            self.add_graphs_to_report(
                story,
                report_graphs
            )

            # -------------------------------------------------
            # BUILD PDF
            # -------------------------------------------------

            document.build(
                story,
                onFirstPage=self._header_footer,
                onLaterPages=self._header_footer
            )

        finally:

            try:

                shutil.rmtree(
                    temporary_graph_folder,
                    ignore_errors=True
                )

            except Exception:

                pass

        return filepath