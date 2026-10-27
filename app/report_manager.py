import csv
import os
import json
from datetime import datetime


class ReportManager:

    def __init__(
        self,
        analytics_manager=None,
        alert_manager=None,
        incident_manager=None,
        session_manager=None,
        venue_config=None,
        log_file="data/logs/crowd_log.csv"
    ):

        self.analytics_manager = (
            analytics_manager
        )

        self.alert_manager = (
            alert_manager
        )

        self.incident_manager = (
            incident_manager
        )

        self.session_manager = (
            session_manager
        )

        self.venue_config = (
            venue_config
        )

        self.log_file = log_file

        self.report_folder = (
            "data/reports"
        )

        os.makedirs(
            self.report_folder,
            exist_ok=True
        )

    # ========================================================
    # LOAD LOG
    # ========================================================

    def load_log_rows(self):

        if not os.path.exists(
            self.log_file
        ):

            return []

        rows = []

        try:

            with open(
                self.log_file,
                "r",
                newline="",
                encoding="utf-8"
            ) as file:

                reader = csv.DictReader(
                    file
                )

                for row in reader:

                    rows.append(
                        dict(row)
                    )

        except Exception as error:

            print(
                f"Report log error: {error}"
            )

        return rows

    # ========================================================
    # VENUE INFORMATION
    # ========================================================

    def get_venue_data(self):

        if self.venue_config is None:
            try:
                from venue import VenueConfig
                self.venue_config = VenueConfig.load()
            except Exception:
                pass

        if self.venue_config is None:

            return {
                "name": "Unknown Venue",
                "capacity": 0,
                "shape": "rectangle",
                "length": 0,
                "width": 0,
                "diameter": 0,
                "warning_threshold": 70,
                "critical_threshold": 90,
                "zone_thresholds": {}
            }

        return {

            "name":
                getattr(
                    self.venue_config,
                    "name",
                    "Unknown Venue"
                ),

            "capacity":
                getattr(
                    self.venue_config,
                    "capacity",
                    0
                ),

            "shape":
                getattr(
                    self.venue_config,
                    "shape",
                    "rectangle"
                ),

            "length":
                getattr(
                    self.venue_config,
                    "length",
                    0
                ),

            "width":
                getattr(
                    self.venue_config,
                    "width",
                    0
                ),

            "diameter":
                getattr(
                    self.venue_config,
                    "diameter",
                    0
                ),

            "warning_threshold":
                getattr(
                    self.venue_config,
                    "warning_threshold",
                    70
                ),

            "critical_threshold":
                getattr(
                    self.venue_config,
                    "critical_threshold",
                    90
                ),

            "zone_thresholds":
                getattr(
                    self.venue_config,
                    "zone_thresholds",
                    {}
                )
        }

    # ========================================================
    # TIME PARSER
    # ========================================================

    @staticmethod
    def _parse_time(
        value
    ):

        if not value:
            return None

        value = str(
            value
        ).strip()

        formats = [

            "%Y-%m-%d %H:%M:%S",

            "%Y-%m-%d %H:%M:%S.%f"
        ]

        for fmt in formats:

            try:

                return datetime.strptime(
                    value,
                    fmt
                )

            except Exception:

                continue

        return None

    # ========================================================
    # GET RECORD TIME
    # ========================================================

    def _record_time(
        self,
        record
    ):

        if not isinstance(
            record,
            dict
        ):

            return None

        possible_fields = [

            "timestamp",

            "time",

            "created_at",

            "alert_time",

            "incident_time"
        ]

        for field in possible_fields:

            value = record.get(
                field
            )

            parsed = (
                self._parse_time(
                    value
                )
            )

            if parsed is not None:

                return parsed

        return None

    # ========================================================
    # SESSION INFORMATION
    # ========================================================

    def get_session_data(self):

        if self.session_manager is None:
            return None

        # ----------------------------------------------------
        # FIRST: CURRENT ACTIVE SESSION
        # ----------------------------------------------------

        try:

            current = (
                self.session_manager
                .get_current_session()
            )

            if current:

                return current

        except Exception as error:

            print(
                f"Current session error: {error}"
            )

        # ----------------------------------------------------
        # SECOND: LATEST COMPLETED SESSION
        # ----------------------------------------------------

        try:

            sessions = (
                self.session_manager
                .get_sessions()
                or []
            )

            if not sessions:
                return None

            valid_sessions = []

            for session in sessions:

                if not isinstance(
                    session,
                    dict
                ):

                    continue

                if session.get(
                    "start_time"
                ):

                    valid_sessions.append(
                        session
                    )

            if not valid_sessions:
                return None

            valid_sessions.sort(
                key=lambda session:
                    self._parse_time(
                        session.get(
                            "start_time"
                        )
                    )
                    or datetime.min,
                reverse=True
            )

            return valid_sessions[0]

        except Exception as error:

            print(
                f"Session history error: {error}"
            )

            return None

    # ========================================================
    # SESSION TIME RANGE
    # ========================================================

    def get_session_time_range(
        self,
        session
    ):

        if not session:
            return (
                None,
                None
            )

        start_time = (
            self._parse_time(
                session.get(
                    "start_time"
                )
            )
        )

        end_time = (
            self._parse_time(
                session.get(
                    "end_time"
                )
            )
        )

        # ----------------------------------------------------
        # ACTIVE SESSION
        # ----------------------------------------------------

        if start_time is not None and end_time is None:

            end_time = datetime.now()

        return (
            start_time,
            end_time
        )

    # ========================================================
    # FILTER LOG ROWS BY SESSION
    # ========================================================

    def filter_rows_by_session(
        self,
        rows,
        session
    ):

        if not rows:
            return []

        if not session:

            # No session information available.
            # Do not destroy valid historical data.

            return list(rows)

        start_time, end_time = (
            self.get_session_time_range(
                session
            )
        )

        if start_time is None:

            return list(rows)

        filtered = []

        for row in rows:

            record_time = (
                self._record_time(
                    row
                )
            )

            if record_time is None:
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

        if not filtered and rows:
            return list(rows)

        return filtered

    # ========================================================
    # FILTER EVENTS BY SESSION
    # ========================================================

    def filter_events_by_session(
        self,
        records,
        session
    ):

        if not records:
            return []

        if not session:

            return list(records)

        start_time, end_time = (
            self.get_session_time_range(
                session
            )
        )

        if start_time is None:

            return list(records)

        filtered = []

        for record in records:

            record_time = (
                self._record_time(
                    record
                )
            )

            if record_time is None:
                continue

            if record_time < start_time:
                continue

            if (
                end_time is not None
                and record_time > end_time
            ):
                continue

            filtered.append(
                record
            )

        return filtered

    # ========================================================
    # FILTER EVENTS BY LOG TIME
    # ========================================================

    def filter_events_by_time(
        self,
        records,
        rows
    ):

        if not records:
            return []

        if not rows:
            return []

        timestamps = []

        for row in rows:

            record_time = (
                self._record_time(
                    row
                )
            )

            if record_time is not None:

                timestamps.append(
                    record_time
                )

        if not timestamps:

            return []

        start_time = min(
            timestamps
        )

        end_time = max(
            timestamps
        )

        filtered = []

        for record in records:

            record_time = (
                self._record_time(
                    record
                )
            )

            if record_time is None:
                continue

            if record_time < start_time:
                continue

            if record_time > end_time:
                continue

            filtered.append(
                record
            )

        return filtered

    # ========================================================
    # GENERATE REPORT DATA
    # ========================================================

    def generate_report(
        self,
        rows=None
    ):

        # ----------------------------------------------------
        # LOAD LOG
        # ----------------------------------------------------

        if rows is None:

            rows = (
                self.load_log_rows()
            )

        # ----------------------------------------------------
        # GET SESSION
        # ----------------------------------------------------

        session = (
            self.get_session_data()
        )

        # ----------------------------------------------------
        # FILTER LOG DATA
        # ----------------------------------------------------

        filtered_rows = (
            self.filter_rows_by_session(
                rows,
                session
            )
        )

        # ----------------------------------------------------
        # VENUE
        # ----------------------------------------------------

        venue = (
            self.get_venue_data()
        )

        capacity = venue.get(
            "capacity",
            0
        )

        venue_name = venue.get(
            "name",
            "Unknown Venue"
        )

        # ----------------------------------------------------
        # ALERTS
        # ----------------------------------------------------

        alerts = []

        if self.alert_manager is not None:

            try:

                alerts = (
                    self.alert_manager
                    .get_alerts()
                    or []
                )

            except Exception as error:

                print(
                    f"Report alert error: {error}"
                )

                alerts = []

        alerts = (
            self.filter_events_by_session(
                alerts,
                session
            )
        )

        # ----------------------------------------------------
        # INCIDENTS
        # ----------------------------------------------------

        incidents = []

        if self.incident_manager is not None:

            try:

                incidents = (
                    self.incident_manager
                    .get_incidents()
                    or []
                )

            except Exception as error:

                print(
                    f"Report incident error: {error}"
                )

                incidents = []

        incidents = (
            self.filter_events_by_session(
                incidents,
                session
            )
        )

        # ----------------------------------------------------
        # ANALYTICS
        # ----------------------------------------------------

        if self.analytics_manager is None:
            try:
                from analytics_manager import AnalyticsManager
                self.analytics_manager = AnalyticsManager()
                if self.venue_config is not None:
                    self.analytics_manager.venue_config = self.venue_config
            except Exception:
                pass

        if self.analytics_manager is not None:

            try:

                analytics = (
                    self.analytics_manager
                    .generate_report_data(
                        filtered_rows,
                        capacity=capacity,
                        venue_name=venue_name,
                        alerts=alerts,
                        incidents=incidents
                    )
                )

            except Exception as error:

                print(
                    f"Analytics report error: {error}"
                )

                analytics = {}

        else:

            analytics = {}

        # ----------------------------------------------------
        # SESSION SUMMARY
        # ----------------------------------------------------

        report_session = None

        if session is not None:

            report_session = (
                dict(session)
            )

            report_session[
                "report_log_records"
            ] = len(
                filtered_rows
            )

            report_session[
                "report_alerts"
            ] = len(
                alerts
            )

            report_session[
                "report_incidents"
            ] = len(
                incidents
            )

        # ----------------------------------------------------
        # REPORT
        # ----------------------------------------------------

        report = {

            "report_id":
                datetime.now().strftime(
                    "%Y%m%d_%H%M%S"
                ),

            "generated_at":
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),

            "venue":
                venue,

            "session":
                report_session,

            "analytics":
                analytics,

            "alerts":
                alerts,

            "incidents":
                incidents,

            "log_records":
                len(
                    filtered_rows
                )
        }

        return report

    # ========================================================
    # SAVE JSON REPORT
    # ========================================================

    def save_json_report(
        self,
        report=None
    ):

        if report is None:

            report = (
                self.generate_report()
            )

        report_id = report.get(
            "report_id",
            datetime.now().strftime(
                "%Y%m%d_%H%M%S"
            )
        )

        filename = (
            f"crowdsense_report_"
            f"{report_id}.json"
        )

        path = os.path.join(
            self.report_folder,
            filename
        )

        try:

            with open(
                path,
                "w",
                encoding="utf-8"
            ) as file:

                json.dump(
                    report,
                    file,
                    indent=4,
                    default=str
                )

            return path

        except Exception as error:

            print(
                f"Report save error: {error}"
            )

            return None

    # ========================================================
    # REPORT SUMMARY
    # ========================================================

    def get_summary(
        self,
        report=None
    ):

        if report is None:

            report = (
                self.generate_report()
            )

        analytics = report.get(
            "analytics",
            {}
        )

        people = analytics.get(
            "people",
            {}
        )

        occupancy = analytics.get(
            "occupancy",
            {}
        )

        density = analytics.get(
            "density",
            {}
        )

        risk = analytics.get(
            "risk",
            {}
        )

        alerts = analytics.get(
            "alerts",
            {}
        )

        incidents = analytics.get(
            "incidents",
            {}
        )

        most_crowded_zone = (
            analytics.get(
                "most_crowded_zone"
            )
        )

        return {

            "venue":
                report.get(
                    "venue",
                    {}
                ),

            "generated_at":
                report.get(
                    "generated_at"
                ),

            "log_records":
                report.get(
                    "log_records",
                    0
                ),

            "peak_people":
                people.get(
                    "peak_people",
                    0
                ),

            "average_people":
                people.get(
                    "average_people",
                    0
                ),

            "minimum_people":
                people.get(
                    "minimum_people",
                    0
                ),

            "peak_occupancy":
                occupancy.get(
                    "peak_occupancy",
                    0
                ),

            "average_occupancy":
                occupancy.get(
                    "average_occupancy",
                    0
                ),

            "minimum_occupancy":
                occupancy.get(
                    "minimum_occupancy",
                    0
                ),

            "peak_density":
                density.get(
                    "peak_density",
                    0
                ),

            "average_density":
                density.get(
                    "average_density",
                    0
                ),

            "minimum_density":
                density.get(
                    "minimum_density",
                    0
                ),

            "safe_records":
                risk.get(
                    "safe_records",
                    0
                ),

            "warning_records":
                risk.get(
                    "warning_records",
                    0
                ),

            "critical_records":
                risk.get(
                    "critical_records",
                    0
                ),

            "warning_alerts":
                alerts.get(
                    "warning",
                    0
                ),

            "critical_alerts":
                alerts.get(
                    "critical",
                    0
                ),

            "total_alerts":
                alerts.get(
                    "total",
                    0
                ),

            "warning_incidents":
                incidents.get(
                    "warning",
                    0
                ),

            "critical_incidents":
                incidents.get(
                    "critical",
                    0
                ),

            "total_incidents":
                incidents.get(
                    "total",
                    0
                ),

            "most_crowded_zone":
                most_crowded_zone
        }

    # ========================================================
    # LIST SAVED REPORTS
    # ========================================================

    def list_reports(self):

        if not os.path.isdir(
            self.report_folder
        ):

            return []

        reports = []

        for filename in os.listdir(
            self.report_folder
        ):

            if not filename.endswith(
                ".json"
            ):

                continue

            path = os.path.join(
                self.report_folder,
                filename
            )

            try:

                modified = os.path.getmtime(
                    path
                )

                reports.append({

                    "filename":
                        filename,

                    "path":
                        path,

                    "modified":
                        datetime.fromtimestamp(
                            modified
                        ).strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )
                })

            except Exception:

                continue

        reports.sort(
            key=lambda item:
                item.get(
                    "modified",
                    ""
                ),
            reverse=True
        )

        return reports

    # ========================================================
    # LOAD SAVED REPORT
    # ========================================================

    def load_report(
        self,
        filename
    ):

        if not filename:
            return None

        safe_filename = (
            os.path.basename(
                filename
            )
        )

        path = os.path.join(
            self.report_folder,
            safe_filename
        )

        if not os.path.exists(
            path
        ):

            return None

        try:

            with open(
                path,
                "r",
                encoding="utf-8"
            ) as file:

                return json.load(
                    file
                )

        except Exception as error:

            print(
                f"Report load error: {error}"
            )

            return None

    # ========================================================
    # DELETE REPORT
    # ========================================================

    def delete_report(
        self,
        filename
    ):

        if not filename:
            return False

        safe_filename = (
            os.path.basename(
                filename
            )
        )

        path = os.path.join(
            self.report_folder,
            safe_filename
        )

        if not os.path.exists(
            path
        ):

            return False

        try:

            os.remove(
                path
            )

            return True

        except Exception as error:

            print(
                f"Report delete error: {error}"
            )

            return False

    # ========================================================
    # REPORT FOLDER
    # ========================================================

    def get_report_folder(self):

        return self.report_folder