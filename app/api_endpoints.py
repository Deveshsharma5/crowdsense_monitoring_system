import csv
import os
from datetime import datetime

from flask import jsonify, request


class CrowdSenseAPI:

    def __init__(
        self,
        app,
        camera_manager=None,
        alert_manager=None,
        incident_manager=None,
        snapshot_manager=None,
        session_manager=None,
        analytics_manager=None,
        graph_manager=None,
        venue_config=None,
        calibration=None,
        camera_calibration_manager=None,
        report_manager=None,
        report_exporter=None,
        zone_manager=None
    ):

        self.app = app

        self.camera_manager = camera_manager
        self.alert_manager = alert_manager
        self.incident_manager = incident_manager
        self.snapshot_manager = snapshot_manager
        self.session_manager = session_manager
        self.analytics_manager = analytics_manager
        self.graph_manager = graph_manager
        self.venue_config = venue_config
        self.calibration = calibration
        self.zone_manager = zone_manager
        if self.zone_manager is None and self.venue_config is not None:
            try:
                from zones import PhysicalZoneManager
                self.zone_manager = PhysicalZoneManager(self.venue_config)
            except Exception:
                self.zone_manager = None

        # =====================================================
        # CONNECT VENUE TO ANALYTICS
        # =====================================================

        if self.analytics_manager is not None:

            self.analytics_manager.venue_config = (
                self.venue_config
            )

        # =====================================================
        # CAMERA CALIBRATION
        # =====================================================

        self.camera_calibration_manager = (
            camera_calibration_manager
        )

        # =====================================================
        # REPORTS
        # =====================================================

        self.report_manager = (
            report_manager
        )

        self.report_exporter = (
            report_exporter
        )

        # =====================================================
        # PROJECT PATHS
        # =====================================================

        self.app_folder = os.path.dirname(
            os.path.abspath(__file__)
        )

        self.project_folder = os.path.dirname(
            self.app_folder
        )

        self.snapshot_folder = os.path.join(
            self.project_folder,
            "data",
            "snapshots"
        )

        self._register_routes()

    def update_managers(
        self,
        camera_manager=None,
        alert_manager=None,
        incident_manager=None,
        snapshot_manager=None,
        session_manager=None,
        analytics_manager=None,
        graph_manager=None,
        venue_config=None,
        calibration=None,
        camera_calibration_manager=None,
        report_manager=None,
        report_exporter=None,
        zone_manager=None
    ):
        if camera_manager is not None:
            self.camera_manager = camera_manager
        if alert_manager is not None:
            self.alert_manager = alert_manager
        if incident_manager is not None:
            self.incident_manager = incident_manager
        if snapshot_manager is not None:
            self.snapshot_manager = snapshot_manager
        if session_manager is not None:
            self.session_manager = session_manager
        if analytics_manager is not None:
            self.analytics_manager = analytics_manager
            if self.venue_config is not None:
                self.analytics_manager.venue_config = self.venue_config
        if graph_manager is not None:
            self.graph_manager = graph_manager
        if venue_config is not None:
            self.venue_config = venue_config
            if self.analytics_manager is not None:
                self.analytics_manager.venue_config = self.venue_config
        if calibration is not None:
            self.calibration = calibration
        if camera_calibration_manager is not None:
            self.camera_calibration_manager = camera_calibration_manager
        if report_manager is not None:
            self.report_manager = report_manager
        if report_exporter is not None:
            self.report_exporter = report_exporter
        if zone_manager is not None:
            self.zone_manager = zone_manager

    # =========================================================
    # HELPERS
    # =========================================================

    @staticmethod
    def _json_body():

        data = request.get_json(
            silent=True
        )

        if isinstance(data, dict):
            return data

        return {}

    @staticmethod
    def _json_safe(value):

        if value is None:
            return None

        if isinstance(value, dict):

            return {
                str(key):
                    CrowdSenseAPI._json_safe(item)
                for key, item in value.items()
            }

        if isinstance(value, (list, tuple)):

            return [
                CrowdSenseAPI._json_safe(item)
                for item in value
            ]

        if hasattr(value, "tolist"):

            try:
                return value.tolist()
            except Exception:
                pass

        if hasattr(value, "item"):

            try:
                return value.item()
            except Exception:
                pass

        return value

    # =========================================================
    # LOAD CROWD LOG
    # =========================================================

    @staticmethod
    def _load_log_rows():

        base_folder = os.path.dirname(
            os.path.dirname(
                os.path.abspath(__file__)
            )
        )

        log_file = os.path.join(
            base_folder,
            "data",
            "logs",
            "crowd_log.csv"
        )

        if not os.path.exists(log_file):
            return []

        rows = []

        try:

            with open(
                log_file,
                "r",
                newline="",
                encoding="utf-8"
            ) as file:

                reader = csv.DictReader(file)

                for row in reader:
                    rows.append(dict(row))

        except Exception as error:

            print(
                f"Analytics log read error: {error}"
            )

        return rows

    # =========================================================
    # SNAPSHOT FILE SCANNER
    #
    # IMPORTANT:
    # We read the actual snapshot directory instead of relying
    # only on SnapshotManager's metadata.
    # =========================================================

    def _scan_snapshot_files(self):

        snapshots = []

        folder = os.path.abspath(
            self.snapshot_folder
        )

        if not os.path.isdir(folder):

            return snapshots

        try:

            for filename in os.listdir(folder):

                full_path = os.path.join(
                    folder,
                    filename
                )

                if not os.path.isfile(full_path):
                    continue

                extension = os.path.splitext(
                    filename
                )[1].lower()

                if extension not in (
                    ".jpg",
                    ".jpeg",
                    ".png",
                    ".webp"
                ):
                    continue

                try:

                    modified_time = os.path.getmtime(
                        full_path
                    )

                    timestamp = datetime.fromtimestamp(
                        modified_time
                    ).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )

                except Exception:

                    timestamp = ""

                snapshots.append({

                    # Exact filename used by /snapshots/<filename>
                    "filename": filename,

                    # Absolute local path
                    "path": full_path,

                    # Relative path for display/debugging
                    "relative_path": os.path.join(
                        "data",
                        "snapshots",
                        filename
                    ),

                    "timestamp": timestamp,

                    "size": (
                        os.path.getsize(full_path)
                        if os.path.exists(full_path)
                        else 0
                    )
                })

        except Exception as error:

            print(
                f"Snapshot directory scan error: {error}"
            )

        snapshots.sort(
            key=lambda item: item.get(
                "timestamp",
                ""
            ),
            reverse=True
        )

        return snapshots

    # =========================================================
    # ROUTES
    # =========================================================

    def _register_routes(self):

        app = self.app

        # =====================================================
        # CAMERAS
        # =====================================================

        @app.route(
            "/api/cameras",
            methods=["GET"]
        )
        def get_cameras():

            if self.camera_manager is None:
                return jsonify([])

            try:

                cameras = (
                    self.camera_manager
                    .list_cameras()
                )

                return jsonify(
                    self._json_safe(cameras)
                )

            except Exception as error:

                return jsonify({
                    "error": str(error)
                }), 500

        @app.route(
            "/api/cameras",
            methods=["POST"]
        )
        def add_camera():

            if self.camera_manager is None:

                return jsonify({
                    "success": False,
                    "error":
                        "Camera manager unavailable"
                }), 503

            data = self._json_body()

            try:

                try:

                    camera = (
                        self.camera_manager
                        .add_camera(data)
                    )

                except TypeError:

                    camera = (
                        self.camera_manager
                        .add_camera(
                            name=data.get(
                                "name",
                                "Camera"
                            ),
                            source=data.get(
                                "source",
                                ""
                            ),
                            enabled=data.get(
                                "enabled",
                                True
                            ),
                            camera_id=data.get(
                                "camera_id"
                            )
                        )
                    )

                return jsonify({
                    "success": True,
                    "camera":
                        self._json_safe(camera)
                }), 201

            except Exception as error:

                return jsonify({
                    "success": False,
                    "error": str(error)
                }), 400

        @app.route(
            "/api/cameras/<camera_id>",
            methods=["PUT"]
        )
        def update_camera(camera_id):

            if self.camera_manager is None:

                return jsonify({
                    "success": False,
                    "error":
                        "Camera manager unavailable"
                }), 503

            data = self._json_body()

            try:

                try:

                    camera = (
                        self.camera_manager
                        .update_camera(
                            camera_id,
                            data
                        )
                    )

                except TypeError:

                    camera = (
                        self.camera_manager
                        .update_camera(
                            camera_id,
                            name=data.get(
                                "name"
                            ),
                            source=data.get(
                                "source"
                            ),
                            enabled=data.get(
                                "enabled"
                            )
                        )
                    )

                return jsonify({
                    "success": True,
                    "camera":
                        self._json_safe(camera)
                })

            except Exception as error:

                return jsonify({
                    "success": False,
                    "error": str(error)
                }), 400

        @app.route(
            "/api/cameras/<camera_id>",
            methods=["DELETE"]
        )
        def delete_camera(camera_id):

            if self.camera_manager is None:

                return jsonify({
                    "success": False,
                    "error":
                        "Camera manager unavailable"
                }), 503

            try:

                result = (
                    self.camera_manager
                    .remove_camera(camera_id)
                )

                return jsonify({
                    "success": True,
                    "result":
                        self._json_safe(result)
                })

            except Exception as error:

                return jsonify({
                    "success": False,
                    "error": str(error)
                }), 400

        @app.route(
            "/api/cameras/check",
            methods=["POST"]
        )
        def check_cameras():

            if self.camera_manager is None:

                return jsonify({
                    "success": False,
                    "error":
                        "Camera manager unavailable"
                }), 503

            try:

                if hasattr(
                    self.camera_manager,
                    "check_all_cameras"
                ):

                    result = (
                        self.camera_manager
                        .check_all_cameras()
                    )

                else:

                    result = (
                        self.camera_manager
                        .check_all()
                    )

                return jsonify({
                    "success": True,
                    "cameras":
                        self._json_safe(result)
                })

            except Exception as error:

                return jsonify({
                    "success": False,
                    "error": str(error)
                }), 500

        @app.route(
            "/api/cameras/<camera_id>/check",
            methods=["POST"]
        )
        def check_single_camera(camera_id):

            if self.camera_manager is None:

                return jsonify({
                    "success": False,
                    "error":
                        "Camera manager unavailable"
                }), 503

            try:

                result = (
                    self.camera_manager
                    .check_camera(camera_id)
                )

                return jsonify({
                    "success": True,
                    "camera":
                        self._json_safe(result)
                })

            except Exception as error:

                return jsonify({
                    "success": False,
                    "error": str(error)
                }), 400

        # =====================================================
        # CAMERA CALIBRATION
        # =====================================================

        @app.route(
            "/api/cameras/calibrations",
            methods=["GET"]
        )
        def get_all_camera_calibrations():

            if (
                self.camera_calibration_manager
                is None
            ):

                return jsonify({})

            try:

                calibrations = (
                    self.camera_calibration_manager
                    .get_all()
                )

                return jsonify(
                    self._json_safe(
                        calibrations
                    )
                )

            except Exception as error:

                return jsonify({
                    "error": str(error)
                }), 500

        @app.route(
            "/api/cameras/<camera_id>/calibration",
            methods=["GET"]
        )
        def get_camera_calibration(camera_id):

            if (
                self.camera_calibration_manager
                is None
            ):

                return jsonify({
                    "success": False,
                    "error":
                        "Camera calibration manager unavailable"
                }), 503

            try:

                calibration_data = (
                    self.camera_calibration_manager
                    .get_calibration(
                        camera_id
                    )
                )

                if calibration_data is None:

                    return jsonify({
                        "success": True,
                        "calibrated": False,
                        "camera_id": camera_id,
                        "calibration": None
                    })

                return jsonify({
                    "success": True,
                    "calibrated": True,
                    "camera_id": camera_id,
                    "calibration":
                        self._json_safe(
                            calibration_data
                        )
                })

            except Exception as error:

                return jsonify({
                    "success": False,
                    "error": str(error)
                }), 500

        @app.route(
            "/api/cameras/<camera_id>/calibration",
            methods=["POST"]
        )
        def save_camera_calibration(camera_id):

            if (
                self.camera_calibration_manager
                is None
            ):

                return jsonify({
                    "success": False,
                    "error":
                        "Camera calibration manager unavailable"
                }), 503

            data = self._json_body()

            try:

                matrix = data.get(
                    "matrix"
                )

                venue_length = data.get(
                    "venue_length",
                    0
                )

                venue_width = data.get(
                    "venue_width",
                    0
                )

                if matrix is None:

                    return jsonify({
                        "success": False,
                        "error":
                            "Calibration matrix is required."
                    }), 400

                result = (
                    self.camera_calibration_manager
                    .set_calibration(
                        camera_id=camera_id,
                        matrix=matrix,
                        venue_length=venue_length,
                        venue_width=venue_width
                    )
                )

                if not result:

                    return jsonify({
                        "success": False,
                        "error":
                            "Failed to save camera calibration."
                    }), 500

                return jsonify({
                    "success": True,
                    "camera_id": camera_id,
                    "message":
                        "Camera calibration saved successfully."
                })

            except Exception as error:

                return jsonify({
                    "success": False,
                    "error": str(error)
                }), 400

        @app.route(
            "/api/cameras/<camera_id>/calibration",
            methods=["DELETE"]
        )
        def delete_camera_calibration(camera_id):

            if (
                self.camera_calibration_manager
                is None
            ):

                return jsonify({
                    "success": False,
                    "error":
                        "Camera calibration manager unavailable"
                }), 503

            try:

                result = (
                    self.camera_calibration_manager
                    .remove_calibration(
                        camera_id
                    )
                )

                return jsonify({
                    "success": result,
                    "camera_id": camera_id
                })

            except Exception as error:

                return jsonify({
                    "success": False,
                    "error": str(error)
                }), 500

        # =====================================================
        # REPORTS
        # =====================================================

        @app.route(
            "/api/reports",
            methods=["GET"]
        )
        def get_reports():

            if self.report_manager is None:

                return jsonify({
                    "success": False,
                    "error":
                        "Report manager unavailable",
                    "reports": []
                }), 503

            try:

                reports = (
                    self.report_manager
                    .list_reports()
                )

                return jsonify({
                    "success": True,
                    "reports":
                        self._json_safe(
                            reports
                        )
                })

            except Exception as error:

                return jsonify({
                    "success": False,
                    "error": str(error),
                    "reports": []
                }), 500

        @app.route(
            "/api/reports/generate",
            methods=["POST"]
        )
        def generate_report():

            if self.report_manager is None:

                return jsonify({
                    "success": False,
                    "error":
                        "Report manager unavailable"
                }), 503

            try:

                report = (
                    self.report_manager
                    .generate_report()
                )

                path = (
                    self.report_manager
                    .save_json_report(
                        report
                    )
                )

                return jsonify({
                    "success": True,
                    "report":
                        self._json_safe(
                            report
                        ),
                    "path": path
                })

            except Exception as error:

                return jsonify({
                    "success": False,
                    "error": str(error)
                }), 500

        @app.route(
            "/api/reports/pdf",
            methods=["POST"]
        )
        def generate_report_pdf():

            if self.report_exporter is None:

                return jsonify({
                    "success": False,
                    "error":
                        "Report exporter unavailable"
                }), 503

            try:

                report = None

                if self.report_manager is not None:

                    report = (
                        self.report_manager
                        .generate_report()
                    )

                path = (
                    self.report_exporter
                    .export_pdf(
                        report
                    )
                )

                if not path:

                    return jsonify({
                        "success": False,
                        "error":
                            "Failed to generate PDF report."
                    }), 500

                return jsonify({
                    "success": True,
                    "path": path,
                    "filename":
                        os.path.basename(
                            path
                        ),
                    "message":
                        "PDF report generated successfully."
                })

            except Exception as error:

                return jsonify({
                    "success": False,
                    "error": str(error)
                }), 500

        @app.route(
            "/api/reports/<filename>",
            methods=["GET"]
        )
        def get_report(filename):

            if self.report_manager is None:

                return jsonify({
                    "success": False,
                    "error":
                        "Report manager unavailable"
                }), 503

            try:

                report = (
                    self.report_manager
                    .load_report(
                        filename
                    )
                )

                if report is None:

                    return jsonify({
                        "success": False,
                        "error":
                            "Report not found"
                    }), 404

                return jsonify({
                    "success": True,
                    "report":
                        self._json_safe(
                            report
                        )
                })

            except Exception as error:

                return jsonify({
                    "success": False,
                    "error": str(error)
                }), 500

        @app.route(
            "/api/reports/<filename>",
            methods=["DELETE"]
        )
        def delete_report(filename):

            if self.report_manager is None:

                return jsonify({
                    "success": False,
                    "error":
                        "Report manager unavailable"
                }), 503

            try:

                deleted = (
                    self.report_manager
                    .delete_report(
                        filename
                    )
                )

                if not deleted:

                    return jsonify({
                        "success": False,
                        "error":
                            "Report not found"
                    }), 404

                return jsonify({
                    "success": True,
                    "message":
                        "Report deleted successfully."
                })

            except Exception as error:

                return jsonify({
                    "success": False,
                    "error": str(error)
                }), 500

        # =====================================================
        # ALERTS
        # =====================================================

        @app.route(
            "/api/alerts",
            methods=["GET"]
        )
        def get_alerts():

            if self.alert_manager is None:

                return jsonify([])

            try:

                alerts = (
                    self.alert_manager
                    .get_alerts()
                )

                return jsonify(
                    self._json_safe(
                        alerts
                    )
                )

            except Exception as error:

                return jsonify({
                    "error": str(error)
                }), 500

        @app.route(
            "/api/alerts/<alert_id>/acknowledge",
            methods=["POST"]
        )
        def acknowledge_alert(alert_id):

            if self.alert_manager is None:

                return jsonify({
                    "success": False,
                    "error":
                        "Alert manager unavailable"
                }), 503

            if not hasattr(
                self.alert_manager,
                "acknowledge_alert"
            ):

                return jsonify({
                    "success": False,
                    "error":
                        "Alert acknowledgement is not implemented yet."
                }), 501

            try:

                result = (
                    self.alert_manager
                    .acknowledge_alert(
                        alert_id
                    )
                )

                return jsonify({
                    "success": True,
                    "result":
                        self._json_safe(
                            result
                        )
                })

            except Exception as error:

                return jsonify({
                    "success": False,
                    "error": str(error)
                }), 500

        # =====================================================
        # INCIDENTS
        # =====================================================

        @app.route(
            "/api/incidents",
            methods=["GET"]
        )
        def get_incidents():

            if self.incident_manager is None:

                return jsonify([])

            try:

                incidents = (
                    self.incident_manager
                    .get_incidents()
                )

                return jsonify(
                    self._json_safe(
                        incidents
                    )
                )

            except Exception as error:

                return jsonify({
                    "error": str(error)
                }), 500

        # =====================================================
        # SNAPSHOTS
        #
        # IMPORTANT:
        # Read the actual files from data/snapshots.
        # This guarantees that snapshots physically present
        # on disk appear in the dashboard.
        # =====================================================

        @app.route(
            "/api/snapshots",
            methods=["GET"]
        )
        def get_snapshots():

            try:

                snapshots = (
                    self._scan_snapshot_files()
                )

                return jsonify(
                    self._json_safe(
                        snapshots
                    )
                )

            except Exception as error:

                print(
                    f"Snapshot API error: {error}"
                )

                return jsonify({
                    "error": str(error)
                }), 500

        # =====================================================
        # CURRENT SESSION
        # =====================================================

        @app.route(
            "/api/session",
            methods=["GET"]
        )
        def get_current_session():

            if self.session_manager is None:

                return jsonify({
                    "status":
                        "NO SESSION"
                })

            try:

                session = (
                    self.session_manager
                    .get_current_session()
                )

                if session is None:

                    return jsonify({
                        "status":
                            "NO SESSION"
                    })

                return jsonify(
                    self._json_safe(
                        session
                    )
                )

            except Exception as error:

                return jsonify({
                    "error": str(error)
                }), 500

        # =====================================================
        # SESSION HISTORY
        # =====================================================

        @app.route(
            "/api/sessions",
            methods=["GET"]
        )
        def get_sessions():

            if self.session_manager is None:

                return jsonify([])

            try:

                sessions = (
                    self.session_manager
                    .get_sessions()
                )

                return jsonify(
                    self._json_safe(
                        sessions
                    )
                )

            except Exception as error:

                return jsonify({
                    "error": str(error)
                }), 500

        # =====================================================
        # ANALYTICS
        # =====================================================

        @app.route(
            "/api/analytics",
            methods=["GET"]
        )
        def get_analytics():

            if self.analytics_manager is None:

                return jsonify({})

            try:

                rows = (
                    self._load_log_rows()
                )

                capacity = 0
                venue_name = "Unknown Venue"

                if self.venue_config is not None:

                    capacity = getattr(
                        self.venue_config,
                        "capacity",
                        0
                    )

                    venue_name = getattr(
                        self.venue_config,
                        "name",
                        "Unknown Venue"
                    )

                data = (
                    self.analytics_manager
                    .generate_report_data(
                        rows,
                        capacity=capacity,
                        venue_name=venue_name
                    )
                )

                return jsonify(
                    self._json_safe(
                        data
                    )
                )

            except Exception as error:

                return jsonify({
                    "error": str(error)
                }), 500

        # =====================================================
        # SUMMARY
        # =====================================================

        @app.route(
            "/api/summary",
            methods=["GET"]
        )
        def get_summary():

            if self.analytics_manager is None:

                return jsonify({})

            try:

                rows = (
                    self._load_log_rows()
                )

                capacity = 0
                venue_name = "Unknown Venue"

                if self.venue_config is not None:

                    capacity = getattr(
                        self.venue_config,
                        "capacity",
                        0
                    )

                    venue_name = getattr(
                        self.venue_config,
                        "name",
                        "Unknown Venue"
                    )

                report = (
                    self.analytics_manager
                    .generate_report_data(
                        rows,
                        capacity=capacity,
                        venue_name=venue_name
                    )
                )

                summary = {

                    "venue":
                        report.get(
                            "venue",
                            venue_name
                        ),

                    "capacity":
                        report.get(
                            "capacity",
                            capacity
                        ),

                    "peak_people":
                        report.get(
                            "people",
                            {}
                        ).get(
                            "peak_people",
                            0
                        ),

                    "average_people":
                        report.get(
                            "people",
                            {}
                        ).get(
                            "average_people",
                            0
                        ),

                    "peak_occupancy":
                        report.get(
                            "occupancy",
                            {}
                        ).get(
                            "peak_occupancy",
                            0
                        ),

                    "average_occupancy":
                        report.get(
                            "occupancy",
                            {}
                        ).get(
                            "average_occupancy",
                            0
                        ),

                    "peak_density":
                        report.get(
                            "density",
                            {}
                        ).get(
                            "peak_density",
                            0
                        ),

                    "risk":
                        report.get(
                            "risk",
                            {}
                        ),

                    "alerts":
                        report.get(
                            "alerts",
                            {}
                        ),

                    "incidents":
                        report.get(
                            "incidents",
                            {}
                        ),

                    "most_crowded_zone":
                        report.get(
                            "most_crowded_zone"
                        )
                }

                return jsonify(
                    self._json_safe(
                        summary
                    )
                )

            except Exception as error:

                return jsonify({
                    "error": str(error)
                }), 500

        # =====================================================
        # GRAPH PATHS
        # =====================================================

        @app.route(
            "/api/graph-paths",
            methods=["GET"]
        )
        def get_graph_paths():

            if self.graph_manager is None:

                return jsonify({})

            try:

                if hasattr(
                    self.graph_manager,
                    "get_graph_paths"
                ):

                    paths = (
                        self.graph_manager
                        .get_graph_paths()
                    )

                else:

                    paths = {}

                return jsonify(
                    self._json_safe(
                        paths or {}
                    )
                )

            except Exception as error:

                return jsonify({
                    "error": str(error)
                }), 500

        # =====================================================
        # VENUE GET
        # =====================================================

        @app.route(
            "/api/venue",
            methods=["GET"]
        )
        def get_venue():

            if self.venue_config is None:

                return jsonify({})

            try:

                data = {

                    "name":
                        getattr(
                            self.venue_config,
                            "name",
                            ""
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

                    "capacity":
                        getattr(
                            self.venue_config,
                            "capacity",
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

                    "grid_size":
                        getattr(
                            self.venue_config,
                            "grid_size",
                            5
                        ),

                    "zones":
                        getattr(
                            self.venue_config,
                            "zones",
                            []
                        ),

                    "zone_thresholds":
                        getattr(
                            self.venue_config,
                            "zone_thresholds",
                            {}
                        ),

                    "special_areas":
                        getattr(
                            self.venue_config,
                            "special_areas",
                            []
                        ),

                    "floorplan":
                        getattr(
                            self.venue_config,
                            "floorplan",
                            None
                        )
                }

                return jsonify(
                    self._json_safe(
                        data
                    )
                )

            except Exception as error:

                return jsonify({
                    "error": str(error)
                }), 500

        # =====================================================
        # VENUE SAVE
        # =====================================================

        @app.route(
            "/api/venue",
            methods=["POST"]
        )
        def save_venue():

            if self.venue_config is None:

                return jsonify({
                    "success": False,
                    "error":
                        "Venue configuration unavailable"
                }), 503

            data = self._json_body()

            try:

                if "name" in data:

                    self.venue_config.name = str(
                        data["name"]
                    )

                if "shape" in data:

                    shape = str(
                        data["shape"]
                    ).lower()

                    if shape not in (
                        "rectangle",
                        "circle"
                    ):

                        return jsonify({
                            "success": False,
                            "error":
                                "Shape must be rectangle or circle."
                        }), 400

                    self.venue_config.shape = shape

                numeric_fields = [
                    "length",
                    "width",
                    "diameter",
                    "capacity",
                    "warning_threshold",
                    "critical_threshold",
                    "grid_size"
                ]

                for field in numeric_fields:

                    if field not in data:
                        continue

                    if field == "capacity":

                        value = int(
                            float(
                                data[field]
                            )
                        )

                    else:

                        value = float(
                            data[field]
                        )

                    setattr(
                        self.venue_config,
                        field,
                        value
                    )

                if "zones" in data:

                    self.venue_config.zones = (
                        data["zones"]
                    )

                if "special_areas" in data:

                    self.venue_config.special_areas = (
                        data["special_areas"]
                    )

                if "floorplan" in data:

                    self.venue_config.floorplan = (
                        data["floorplan"]
                    )

                if "zone_thresholds" in data:

                    self.venue_config.zone_thresholds = (
                        data["zone_thresholds"]
                    )

                self.venue_config.save()

                if self.zone_manager is not None:
                    self.zone_manager.venue = self.venue_config
                    self.zone_manager.apply_zone_thresholds()

                if self.analytics_manager is not None:

                    self.analytics_manager.venue_config = (
                        self.venue_config
                    )

                return jsonify({
                    "success": True,
                    "message":
                        "Venue saved successfully."
                })

            except Exception as error:

                return jsonify({
                    "success": False,
                    "error": str(error)
                }), 400

        # =====================================================
        # ZONE THRESHOLDS (GET & UPDATE)
        # =====================================================

        @app.route(
            "/api/zones/<zone_id>/thresholds",
            methods=["GET"]
        )
        def get_zone_thresholds(zone_id):

            if self.venue_config is None:
                return jsonify({
                    "success": False,
                    "error": "Venue configuration unavailable"
                }), 503

            zm = self.zone_manager
            if zm is None:
                try:
                    from zones import PhysicalZoneManager
                    zm = PhysicalZoneManager(self.venue_config)
                    self.zone_manager = zm
                except Exception:
                    zm = None

            zones = zm.get_zones() if zm is not None else []
            if not zones:
                return jsonify({
                    "success": False,
                    "error": "No zones created yet. Configure venue dimensions first."
                }), 400

            target = next((z for z in zones if str(z.get("id")) == str(zone_id)), None)
            if target is None:
                return jsonify({
                    "success": False,
                    "error": f"Zone '{zone_id}' not found among created zones."
                }), 404

            thresholds_map = getattr(self.venue_config, "zone_thresholds", {}) or {}
            custom_th = thresholds_map.get(zone_id, {})
            has_custom = zone_id in thresholds_map

            default_warn = float(getattr(self.venue_config, "warning_threshold", 70.0))
            default_crit = float(getattr(self.venue_config, "critical_threshold", 90.0))

            return jsonify({
                "success": True,
                "zone_id": zone_id,
                "warning_threshold": float(target.get("warning_threshold", custom_th.get("warning_threshold", default_warn))),
                "critical_threshold": float(target.get("critical_threshold", custom_th.get("critical_threshold", default_crit))),
                "venue_warning_threshold": default_warn,
                "venue_critical_threshold": default_crit,
                "has_custom_threshold": has_custom,
                "zone_capacity": float(target.get("zone_capacity", 0.0))
            })

        @app.route(
            "/api/zones/<zone_id>/thresholds",
            methods=["POST", "PUT"]
        )
        def update_zone_thresholds(zone_id):

            if self.venue_config is None:
                return jsonify({
                    "success": False,
                    "error": "Venue configuration unavailable"
                }), 503

            zm = self.zone_manager
            if zm is None:
                try:
                    from zones import PhysicalZoneManager
                    zm = PhysicalZoneManager(self.venue_config)
                    self.zone_manager = zm
                except Exception:
                    zm = None

            zones = zm.get_zones() if zm is not None else []
            if not zones:
                return jsonify({
                    "success": False,
                    "error": "Cannot edit thresholds: All venue zones must be created before custom thresholds can be edited. Configure venue dimensions in Venue settings first."
                }), 400

            target = next((z for z in zones if str(z.get("id")) == str(zone_id)), None)
            if target is None:
                return jsonify({
                    "success": False,
                    "error": f"Zone '{zone_id}' not found among created zones."
                }), 404

            data = self._json_body()
            reset = bool(data.get("reset", False))

            try:
                if reset:
                    updated_zone = zm.set_zone_threshold(
                        zone_id=zone_id,
                        reset=True
                    )
                    message = f"Zone {zone_id} thresholds reset to venue defaults."
                else:
                    if "warning_threshold" not in data or "critical_threshold" not in data:
                        return jsonify({
                            "success": False,
                            "error": "Both warning_threshold (Min) and critical_threshold (Max) must be provided."
                        }), 400

                    warn_val = float(data["warning_threshold"])
                    crit_val = float(data["critical_threshold"])

                    if warn_val <= 0 or crit_val <= 0:
                        return jsonify({
                            "success": False,
                            "error": "Thresholds must be positive percentage values greater than 0%."
                        }), 400

                    if warn_val >= crit_val:
                        return jsonify({
                            "success": False,
                            "error": "Warning threshold (Min) must be strictly less than Critical threshold (Max)."
                        }), 400

                    updated_zone = zm.set_zone_threshold(
                        zone_id=zone_id,
                        warning_threshold=warn_val,
                        critical_threshold=crit_val,
                        reset=False
                    )
                    message = f"Zone {zone_id} thresholds updated successfully (Min: {warn_val}%, Max: {crit_val}%)."

                if self.analytics_manager is not None:
                    self.analytics_manager.venue_config = self.venue_config

                return jsonify({
                    "success": True,
                    "message": message,
                    "zone": self._json_safe(updated_zone)
                })

            except Exception as error:
                return jsonify({
                    "success": False,
                    "error": str(error)
                }), 400

        # =====================================================
        # OLD / PRIMARY CALIBRATION
        # =====================================================

        @app.route(
            "/api/calibration",
            methods=["GET"]
        )
        def get_calibration():

            if self.calibration is None:

                return jsonify({})

            try:

                data = {}

                attributes = [
                    "venue_length",
                    "venue_width",
                    "points",
                    "matrix",
                    "calibrated"
                ]

                for attribute in attributes:

                    if hasattr(
                        self.calibration,
                        attribute
                    ):

                        data[attribute] = getattr(
                            self.calibration,
                            attribute
                        )

                return jsonify(
                    self._json_safe(
                        data
                    )
                )

            except Exception as error:

                return jsonify({
                    "error": str(error)
                }), 500

        # =====================================================
        # TELEGRAM
        # =====================================================

        @app.route(
            "/api/telegram/status",
            methods=["GET"]
        )
        def get_telegram_status():

            try:

                from telegram_service import get_telegram_notifier
                notifier = get_telegram_notifier()
                return jsonify(self._json_safe(notifier.get_status()))

            except Exception as error:

                return jsonify({"error": str(error)}), 500

        @app.route(
            "/api/telegram/test",
            methods=["POST"]
        )
        def send_telegram_test():

            try:

                from telegram_service import get_telegram_notifier
                notifier = get_telegram_notifier()
                venue_name = "CrowdSense Venue"
                if self.venue_config is not None:
                    venue_name = getattr(self.venue_config, "name", venue_name)
                result = notifier.send_test_notification(venue_name=venue_name)
                # send_test_notification returns (success, message, details)
                if isinstance(result, tuple) and len(result) >= 2:
                    success, message = result[0], result[1]
                else:
                    success, message = bool(result), "Test sent"
                if success:
                    return jsonify({"success": True, "message": message})
                else:
                    return jsonify({"success": False, "message": message}), 400

            except Exception as error:

                return jsonify({"success": False, "message": str(error)}), 500

        # =====================================================
        # HEALTH
        # =====================================================

        @app.route(
            "/api/health",
            methods=["GET"]
        )
        def health():

            return jsonify({
                "status": "OK",
                "service": "CrowdSense API"
            })