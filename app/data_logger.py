import csv
import os
from datetime import datetime


LOG_FOLDER = "data/logs"
LOG_FILE = os.path.join(
    LOG_FOLDER,
    "crowd_log.csv"
)


class CrowdLogger:

    def __init__(self):

        os.makedirs(
            LOG_FOLDER,
            exist_ok=True
        )

        self._create_file()


    # ========================================================
    # CREATE LOG FILE
    # ========================================================

    def _create_file(self):

        if os.path.exists(LOG_FILE):

            return


        with open(
            LOG_FILE,
            "w",
            newline="",
            encoding="utf-8"
        ) as file:

            writer = csv.writer(file)

            writer.writerow([
                "timestamp",
                "total_people",
                "zone_id",
                "zone_people",
                "density",
                "risk"
            ])


    # ========================================================
    # LOG CURRENT CROWD
    # ========================================================

    def log(
        self,
        total_people,
        zones
    ):

        timestamp = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )


        with open(
            LOG_FILE,
            "a",
            newline="",
            encoding="utf-8"
        ) as file:

            writer = csv.writer(file)


            for zone in zones:

                writer.writerow([

                    timestamp,

                    total_people,

                    zone.get(
                        "id",
                        ""
                    ),

                    zone.get(
                        "people",
                        0
                    ),

                    round(
                        zone.get(
                            "density",
                            0.0
                        ),
                        4
                    ),

                    zone.get(
                        "risk",
                        "SAFE"
                    )
                ])


    # ========================================================
    # LOG LOCATION
    # ========================================================

    def get_log_file(self):

        return LOG_FILE