import os
import time
from datetime import datetime

import cv2


# ============================================================
# SNAPSHOT FOLDER
# ============================================================

SNAPSHOT_FOLDER = "data/snapshots"


class SnapshotManager:

    def __init__(self, cooldown_seconds=8):

        self.cooldown_seconds = cooldown_seconds

        self.last_snapshot_time = {}

        os.makedirs(
            SNAPSHOT_FOLDER,
            exist_ok=True
        )

    # =========================================================
    # COOLDOWN
    # =========================================================

    def _can_capture(self, key):

        current_time = time.time()

        last_time = self.last_snapshot_time.get(
            key,
            0
        )

        if (
            current_time - last_time
            < self.cooldown_seconds
        ):

            return False

        self.last_snapshot_time[key] = current_time

        return True

    # =========================================================
    # CAPTURE SNAPSHOT
    # =========================================================

    def capture(
        self,
        frame,
        zone_id="UNKNOWN",
        risk="UNKNOWN",
        camera_id=None,
        alert_id=None
    ):

        if frame is None:

            return None

        key = (
            f"{camera_id or 'SYSTEM'}_"
            f"{zone_id}_"
            f"{risk}"
        )

        if not self._can_capture(key):

            return None

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        safe_zone = str(
            zone_id
        ).replace(
            " ",
            "_"
        )

        safe_camera = str(
            camera_id or "SYSTEM"
        ).replace(
            " ",
            "_"
        )

        safe_risk = str(
            risk
        ).replace(
            " ",
            "_"
        )

        filename = (
            f"incident_"
            f"{timestamp}_"
            f"camera_{safe_camera}_"
            f"zone_{safe_zone}_"
            f"{safe_risk}.jpg"
        )

        path = os.path.join(
            SNAPSHOT_FOLDER,
            filename
        )

        try:

            success = cv2.imwrite(
                path,
                frame
            )

            if success:

                print(
                    f"Snapshot saved: {path}"
                )

                return path

            print(
                f"Could not save snapshot: {path}"
            )

        except Exception as error:

            print(
                f"Snapshot error: {error}"
            )

        return None

    # =========================================================
    # CAPTURE ALERT SNAPSHOTS
    # =========================================================

    def capture_alert_snapshots(
        self,
        frame,
        alerts,
        camera_id=None
    ):

        saved = []

        if frame is None:

            return saved

        if not alerts:

            return saved

        for alert in alerts:

            if not isinstance(
                alert,
                dict
            ):

                continue

            path = self.capture(

                frame=frame,

                zone_id=alert.get(
                    "zone_id",
                    "UNKNOWN"
                ),

                risk=alert.get(
                    "risk",
                    "UNKNOWN"
                ),

                camera_id=alert.get(
                    "camera_id",
                    camera_id
                ),

                alert_id=alert.get(
                    "alert_id",
                    alert.get(
                        "id"
                    )
                )
            )

            if path:

                saved.append(
                    path
                )

        return saved

    # =========================================================
    # LIST SNAPSHOTS
    # =========================================================

    def get_snapshots(self):

        if not os.path.exists(
            SNAPSHOT_FOLDER
        ):

            return []

        snapshots = []

        try:

            for filename in os.listdir(
                SNAPSHOT_FOLDER
            ):

                if not filename.lower().endswith(
                    ".jpg"
                ):

                    continue

                path = os.path.join(
                    SNAPSHOT_FOLDER,
                    filename
                )

                if not os.path.isfile(
                    path
                ):

                    continue

                modified_time = os.path.getmtime(
                    path
                )

                snapshots.append({

                    "filename":
                        filename,

                    "path":
                        path,

                    "timestamp":
                        datetime.fromtimestamp(
                            modified_time
                        ).strftime(
                            "%Y-%m-%d %H:%M:%S"
                        ),

                    "size":
                        os.path.getsize(
                            path
                        )

                })

        except Exception as error:

            print(
                f"Snapshot history error: {error}"
            )

            return []

        # Newest snapshot first

        snapshots.sort(
            key=lambda item:
                item["timestamp"],
            reverse=True
        )

        return snapshots

    # =========================================================
    # LATEST SNAPSHOT
    # =========================================================

    def get_latest_snapshot(self):

        snapshots = self.get_snapshots()

        if not snapshots:

            return None

        return snapshots[0]

    # =========================================================
    # SNAPSHOT COUNT
    # =========================================================

    def get_count(self):

        return len(
            self.get_snapshots()
        )

    # =========================================================
    # RESET COOLDOWNS
    # =========================================================

    def reset_cooldowns(self):

        self.last_snapshot_time = {}

    # =========================================================
    # SNAPSHOT FOLDER
    # =========================================================

    def get_snapshot_folder(self):

        return SNAPSHOT_FOLDER