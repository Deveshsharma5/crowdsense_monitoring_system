import csv
import io
import os
import re
import time
from datetime import datetime


ALERT_FOLDER = "data/alerts"

ALERT_FILE = os.path.join(
    ALERT_FOLDER,
    "alerts.csv"
)


class AlertManager:

    def __init__(
        self,
        cooldown_seconds=8,
        venue_config=None,
        telegram_service=None
    ):

        self.cooldown_seconds = (
            cooldown_seconds
        )

        self.last_alert_time = {}
        self.venue_config = venue_config

        if telegram_service is None:
            try:
                from telegram_service import get_telegram_notifier
                self.telegram_service = get_telegram_notifier()
            except Exception:
                self.telegram_service = None
        else:
            self.telegram_service = telegram_service

        os.makedirs(
            ALERT_FOLDER,
            exist_ok=True
        )

        self._create_file()

    def set_telegram_service(self, telegram_service):
        self.telegram_service = telegram_service

    def set_venue_config(self, venue_config):
        self.venue_config = venue_config

    def _get_venue_name(self):
        if self.venue_config and hasattr(self.venue_config, "name") and self.venue_config.name:
            return str(self.venue_config.name)
        try:
            cfg_file = "data/venue_config.json"
            if os.path.isfile(cfg_file):
                import json
                with open(cfg_file, "r", encoding="utf-8") as f:
                    return json.load(f).get("name") or "CrowdSense Venue"
        except Exception:
            pass
        return "CrowdSense Venue" 

    # =========================================================
    # CREATE ALERT FILE
    # =========================================================

    def _create_file(self):

        if os.path.exists(
            ALERT_FILE
        ):
            return

        with open(
            ALERT_FILE,
            "w",
            newline="",
            encoding="utf-8"
        ) as file:

            writer = csv.writer(file)

            writer.writerow([
                "alert_id",
                "timestamp",
                "zone_id",
                "risk",
                "people",
                "density",
                "special_type",
                "camera_id",
                "message",
                "status"
            ])

    # =========================================================
    # COOLDOWN
    # =========================================================

    def _can_alert(
        self,
        key
    ):

        current_time = time.time()

        last_time = (
            self.last_alert_time.get(
                key,
                0
            )
        )

        if (
            current_time - last_time
            <
            self.cooldown_seconds
        ):

            return False

        self.last_alert_time[key] = (
            current_time
        )

        return True

    # =========================================================
    # GENERATE ALERT ID
    # =========================================================

    def _generate_alert_id(
        self,
        alerts=None
    ):

        if alerts is None:

            alerts = self.get_alerts(
                migrate=False
            )

        max_num = 0

        for alert in alerts:

            alert_id = str(
                alert.get(
                    "alert_id",
                    ""
                )
            ).strip()

            if alert_id:

                match = re.search(r'\d+', alert_id)

                if match:

                    try:

                        num = int(match.group())

                        if num > max_num:

                            max_num = num

                    except Exception:
                        pass

        return f"ALERT{max_num + 1}"

    # =========================================================
    # MIGRATE OLD ALERT FILE
    # =========================================================

    def _migrate_old_alert_file(self):

        if not os.path.exists(
            ALERT_FILE
        ):

            return

        try:

            with open(
                ALERT_FILE,
                "r",
                newline="",
                encoding="utf-8"
            ) as file:

                reader = csv.DictReader(
                    file
                )

                rows = list(
                    reader
                )

                fieldnames = (
                    reader.fieldnames or []
                )

            # -------------------------------------------------
            # Already using new format
            # -------------------------------------------------

            if "alert_id" in fieldnames:

                return

            print(
                "Migrating old alert history..."
            )

            existing_ids = set()

            new_rows = []

            number = 1

            for row in rows:

                while (
                    f"ALERT{number}"
                    in existing_ids
                ):

                    number += 1

                alert_id = (
                    f"ALERT{number}"
                )

                existing_ids.add(
                    alert_id
                )

                new_rows.append({

                    "alert_id":
                        alert_id,

                    "timestamp":
                        row.get(
                            "timestamp",
                            ""
                        ),

                    "zone_id":
                        row.get(
                            "zone_id",
                            ""
                        ),

                    "risk":
                        row.get(
                            "risk",
                            ""
                        ),

                    "people":
                        row.get(
                            "people",
                            0
                        ),

                    "density":
                        row.get(
                            "density",
                            0
                        ),

                    "special_type":
                        row.get(
                            "special_type",
                            ""
                        ),

                    "camera_id":
                        row.get(
                            "camera_id",
                            ""
                        ),

                    "message":
                        row.get(
                            "message",
                            ""
                        ),

                    "status":
                        "OPEN"
                })

                number += 1

            with open(
                ALERT_FILE,
                "w",
                newline="",
                encoding="utf-8"
            ) as file:

                writer = csv.writer(
                    file
                )

                writer.writerow([
                    "alert_id",
                    "timestamp",
                    "zone_id",
                    "risk",
                    "people",
                    "density",
                    "special_type",
                    "camera_id",
                    "message",
                    "status"
                ])

                for row in new_rows:

                    writer.writerow([
                        row["alert_id"],
                        row["timestamp"],
                        row["zone_id"],
                        row["risk"],
                        row["people"],
                        row["density"],
                        row["special_type"],
                        row["camera_id"],
                        row["message"],
                        row["status"]
                    ])

            print(
                f"Alert history migrated: "
                f"{len(new_rows)} alerts"
            )

        except Exception as error:

            print(
                f"Alert migration error: {error}"
            )

    # =========================================================
    # CREATE ALERT
    # =========================================================

    def create_alert(
        self,
        zone_id,
        risk,
        people,
        density,
        special_type=None,
        camera_id=None,
        message=None
    ):

        risk = str(
            risk
        ).upper()

        if risk not in [
            "WARNING",
            "CRITICAL"
        ]:

            return None

        alert_key = (
            f"{camera_id or 'SYSTEM'}_"
            f"{zone_id or 'UNKNOWN'}_"
            f"{risk}"
        )

        if not self._can_alert(
            alert_key
        ):

            return None

        timestamp = (
            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        )

        if message is None:

            if risk == "CRITICAL":

                message = (
                    f"Critical crowd level "
                    f"in zone {zone_id}"
                )

            else:

                message = (
                    f"Warning crowd level "
                    f"in zone {zone_id}"
                )

        alert_id = (
            self._generate_alert_id()
        )

        alert = {

            "alert_id":
                alert_id,

            "timestamp":
                timestamp,

            "zone_id":
                zone_id,

            "risk":
                risk,

            "people":
                int(people),

            "density":
                round(
                    float(density),
                    4
                ),

            "special_type":
                special_type,

            "camera_id":
                camera_id,

            "message":
                message,

            "status":
                "OPEN"
        }

        # -----------------------------------------------------
        # SAVE ALERT
        # -----------------------------------------------------

        try:

            with open(
                ALERT_FILE,
                "a",
                newline="",
                encoding="utf-8"
            ) as file:

                writer = csv.writer(
                    file
                )

                writer.writerow([
                    alert["alert_id"],
                    alert["timestamp"],
                    alert["zone_id"],
                    alert["risk"],
                    alert["people"],
                    alert["density"],
                    alert["special_type"],
                    alert["camera_id"],
                    alert["message"],
                    alert["status"]
                ])

        except Exception as error:

            print(
                f"Alert logging error: {error}"
            )

            return None

        print(
            f"ALERT: "
            f"{alert_id} - "
            f"Zone {zone_id} - "
            f"{risk} - "
            f"{people} people"
        )

        # -----------------------------------------------------
        # TELEGRAM REAL-TIME EMERGENCY NOTIFICATION
        # -----------------------------------------------------
        if self.telegram_service is not None and risk == "CRITICAL":
            try:
                venue_name = self._get_venue_name()
                self.telegram_service.notify_critical_transition(
                    zone_id=zone_id,
                    risk=risk,
                    people=people,
                    density=density,
                    venue_name=venue_name,
                    message=message,
                    special_type=special_type,
                    timestamp=timestamp
                )
            except Exception as tg_err:
                print(f"[AlertManager] Telegram notification error: {tg_err}")

        # IMPORTANT:
        # Do NOT create an incident here.
        #
        # main.py handles the correct order:
        #
        # ALERT
        #   ↓
        # SNAPSHOT
        #   ↓
        # INCIDENT + SNAPSHOT PATH
        #
        # This prevents duplicate incidents and prevents
        # incidents from being created without snapshots.

        return alert

    # =========================================================
    # PROCESS ZONES
    # =========================================================

    def process_zones(
        self,
        zones,
        camera_id=None
    ):

        alerts = []

        for zone in zones:

            risk = str(
                zone.get(
                    "risk",
                    "SAFE"
                )
            ).upper()

            # Track non-critical zone status for rising-edge transition detection
            if self.telegram_service is not None and risk != "CRITICAL":
                try:
                    self.telegram_service.update_zone_status(
                        zone.get("id", "UNKNOWN"),
                        risk
                    )
                except Exception:
                    pass

            if risk not in [
                "WARNING",
                "CRITICAL"
            ]:

                continue

            alert = self.create_alert(

                zone_id=zone.get(
                    "id",
                    "UNKNOWN"
                ),

                risk=risk,

                people=zone.get(
                    "people",
                    0
                ),

                density=zone.get(
                    "density",
                    0
                ),

                special_type=zone.get(
                    "special_type"
                ),

                camera_id=camera_id
            )

            if alert:

                alerts.append(
                    alert
                )

        return alerts

    # =========================================================
    # =========================================================
    # READ ALERT HISTORY
    # =========================================================

    def get_alerts(
        self,
        migrate=True
    ):

        if not os.path.exists(
            ALERT_FILE
        ):

            return []

        if migrate:

            self._migrate_old_alert_file()

        alerts = []

        try:

            with open(
                ALERT_FILE,
                "rb"
            ) as binary_file:

                raw_bytes = binary_file.read().replace(b"\x00", b"")
                raw_text = raw_bytes.decode("utf-8", errors="ignore")

            reader = csv.DictReader(
                io.StringIO(raw_text)
            )

            for row in reader:

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

                try:

                    row["density"] = float(
                        row.get(
                            "density",
                            0
                        )
                    )

                except Exception:

                    row["density"] = 0.0

                status = str(
                    row.get("status", "OPEN") or "OPEN"
                ).strip().upper()

                row["status"] = (
                    status
                    if status in ("OPEN", "ACKNOWLEDGED")
                    else "OPEN"
                )

                alerts.append(
                    row
                )

        except Exception as error:

            print(
                f"Alert history read error: "
                f"{error}"
            )

            return []

        return alerts

    # =========================================================
    # ACKNOWLEDGE ALERT
    # =========================================================

    def acknowledge_alert(
        self,
        alert_id
    ):

        if not alert_id:

            return False

        target_id = str(alert_id).strip().upper()

        alerts = self.get_alerts()

        found = False

        for alert in alerts:

            cur_id = str(
                alert.get(
                    "alert_id",
                    ""
                )
            ).strip().upper()

            if cur_id == target_id:

                alert["status"] = (
                    "ACKNOWLEDGED"
                )

                found = True

        if not found:

            return False

        return self._save_all_alerts(alerts)

    # =========================================================
    # ACKNOWLEDGE ALL ALERTS
    # =========================================================

    def acknowledge_all(self):

        alerts = self.get_alerts()

        count = 0

        for alert in alerts:

            status = str(
                alert.get("status", "OPEN")
            ).strip().upper()

            if status == "OPEN":

                alert["status"] = "ACKNOWLEDGED"

                count += 1

        if count > 0:

            self._save_all_alerts(alerts)

        return count

    # =========================================================
    # SAVE ALL ALERTS HELPER
    # =========================================================

    def _save_all_alerts(self, alerts):

        try:

            with open(
                ALERT_FILE,
                "w",
                newline="",
                encoding="utf-8"
            ) as file:

                writer = csv.writer(
                    file
                )

                writer.writerow([
                    "alert_id",
                    "timestamp",
                    "zone_id",
                    "risk",
                    "people",
                    "density",
                    "special_type",
                    "camera_id",
                    "message",
                    "status"
                ])

                for alert in alerts:

                    writer.writerow([

                        alert.get(
                            "alert_id",
                            ""
                        ),

                        alert.get(
                            "timestamp",
                            ""
                        ),

                        alert.get(
                            "zone_id",
                            ""
                        ),

                        alert.get(
                            "risk",
                            ""
                        ),

                        alert.get(
                            "people",
                            0
                        ),

                        alert.get(
                            "density",
                            0
                        ),

                        alert.get(
                            "special_type",
                            ""
                        ),

                        alert.get(
                            "camera_id",
                            ""
                        ),

                        alert.get(
                            "message",
                            ""
                        ),

                        alert.get(
                            "status",
                            "OPEN"
                        )
                    ])

                file.flush()
                try:
                    os.fsync(file.fileno())
                except Exception:
                    pass

            return True

        except Exception as error:

            print(
                f"Alert save error: "
                f"{error}"
            )

            return False

    # =========================================================
    # LATEST ALERT
    # =========================================================

    def get_latest_alert(self):

        alerts = self.get_alerts()

        if not alerts:

            return None

        return alerts[-1]

    # =========================================================
    # ALERT COUNTS
    # =========================================================

    def get_counts(self):

        alerts = self.get_alerts()

        warning = 0
        critical = 0

        for alert in alerts:

            risk = str(
                alert.get(
                    "risk",
                    "SAFE"
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
    # CLEAR COOLDOWN
    # =========================================================

    def reset_cooldowns(self):

        self.last_alert_time = {}

    # =========================================================
    # ALERT FILE
    # =========================================================

    def get_alert_file(self):

        return ALERT_FILE