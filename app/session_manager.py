import json
import os
import time
from datetime import datetime


SESSION_FOLDER = "data/sessions"
SESSION_FILE = os.path.join(
    SESSION_FOLDER,
    "sessions.json"
)


class SessionManager:

    def __init__(self):

        os.makedirs(
            SESSION_FOLDER,
            exist_ok=True
        )

        self.sessions = []
        self.current_session = None
        self.last_completed_session = None

        self.load()

    # =========================================================
    # START SESSION
    # =========================================================

    def start_session(
        self,
        venue_name="Unknown Venue",
        cameras=None,
        capacity=0
    ):

        # Prevent multiple active sessions
        if self.current_session is not None:

            if self.current_session.get(
                "status"
            ) == "ACTIVE":

                return self.current_session.copy()

        now = datetime.now()

        session_id = self._generate_session_id()

        if cameras is None:
            cameras = []

        self.current_session = {

            "session_id":
                session_id,

            "venue":
                str(venue_name),

            "capacity":
                int(capacity),

            "cameras":
                cameras,

            "start_time":
                now.strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),

            "end_time":
                None,

            "duration_seconds":
                0,

            "status":
                "ACTIVE",

            "peak_people":
                0,

            "average_people":
                0.0,

            "peak_occupancy":
                0.0,

            "warning_events":
                0,

            "warning_count":
                0,

            "warnings":
                0,

            "critical_events":
                0,

            "critical_count":
                0,

            "critical":
                0,

            "total_updates":
                0,

            "last_people":
                0,

            "last_update":
                None
        }

        self.save()

        print(
            f"Session started: {session_id}"
        )

        return self.current_session.copy()

    # =========================================================
    # UPDATE SESSION
    # =========================================================

    def update_session(
        self,
        total_people=0,
        capacity=None,
        warning=False,
        critical=False
    ):

        if self.current_session is None:
            return None

        if self.current_session.get(
            "status"
        ) != "ACTIVE":

            return self.current_session.copy()

        try:

            total_people = max(
                0,
                int(total_people)
            )

        except Exception:

            total_people = 0

        if capacity is not None:

            try:

                self.current_session[
                    "capacity"
                ] = int(capacity)

            except Exception:

                pass

        current_capacity = self.current_session.get(
            "capacity",
            0
        )

        # -----------------------------------------------------
        # PEOPLE
        # -----------------------------------------------------

        self.current_session[
            "last_people"
        ] = total_people

        self.current_session[
            "total_updates"
        ] += 1

        if total_people > self.current_session[
            "peak_people"
        ]:

            self.current_session[
                "peak_people"
            ] = total_people

        # -----------------------------------------------------
        # AVERAGE
        # -----------------------------------------------------

        update_count = self.current_session[
            "total_updates"
        ]

        previous_average = self.current_session[
            "average_people"
        ]

        self.current_session[
            "average_people"
        ] = (
            (
                previous_average
                * (update_count - 1)
            )
            + total_people
        ) / update_count

        self.current_session[
            "average_people"
        ] = round(
            self.current_session[
                "average_people"
            ],
            2
        )

        # -----------------------------------------------------
        # OCCUPANCY
        # -----------------------------------------------------

        occupancy = 0.0

        if current_capacity > 0:

            occupancy = (
                total_people
                / current_capacity
            ) * 100

        if occupancy > self.current_session[
            "peak_occupancy"
        ]:

            self.current_session[
                "peak_occupancy"
            ] = round(
                occupancy,
                1
            )

        # -----------------------------------------------------
        # RISK EVENTS
        # -----------------------------------------------------

        if warning:

            self.current_session[
                "warning_events"
            ] += 1
            self.current_session["warning_count"] = self.current_session["warning_events"]
            self.current_session["warnings"] = self.current_session["warning_events"]

        if critical:

            self.current_session[
                "critical_events"
            ] += 1
            self.current_session["critical_count"] = self.current_session["critical_events"]
            self.current_session["critical"] = self.current_session["critical_events"]

        # -----------------------------------------------------
        # TIME
        # -----------------------------------------------------

        now = datetime.now()

        self.current_session[
            "last_update"
        ] = now.strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        start_time = self._parse_time(
            self.current_session.get(
                "start_time"
            )
        )

        if start_time:

            self.current_session[
                "duration_seconds"
            ] = int(
                (
                    now - start_time
                ).total_seconds()
            )

        self.save()

        return self.current_session.copy()

    # =========================================================
    # END SESSION
    # =========================================================

    def end_session(self):

        if self.current_session is None:
            return None

        if self.current_session.get(
            "status"
        ) != "ACTIVE":

            return self.current_session.copy()

        now = datetime.now()

        self.current_session[
            "end_time"
        ] = now.strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        self.current_session[
            "status"
        ] = "COMPLETED"

        start_time = self._parse_time(
            self.current_session.get(
                "start_time"
            )
        )

        if start_time:

            self.current_session[
                "duration_seconds"
            ] = int(
                (
                    now - start_time
                ).total_seconds()
            )

        completed_session = (
            self.current_session.copy()
        )

        self._store_completed_session(
            completed_session
        )

        self.last_completed_session = completed_session
        self.current_session = None

        self.save()

        print(
            f"Session ended: "
            f"{completed_session['session_id']}"
        )

        return completed_session

    # =========================================================
    # GET CURRENT SESSION
    # =========================================================

    def get_current_session(self):

        if self.current_session is None:
            return None

        session = self.current_session.copy()

        # Update live elapsed duration dynamically if session is ACTIVE
        if session.get("status") == "ACTIVE" and session.get("start_time"):
            st = self._parse_time(session.get("start_time"))
            if st:
                now = datetime.now()
                dur = max(0, int((now - st).total_seconds()))
                session["duration_seconds"] = dur
                h = dur // 3600
                m = (dur % 3600) // 60
                s = dur % 60
                session["duration"] = f"{h:02d}:{m:02d}:{s:02d}"

        return session

    def get_last_session(self):
        """
        Returns the last completed session if available.
        """
        if getattr(self, "last_completed_session", None):
            return self.last_completed_session.copy()
        if self.sessions:
            return self.sessions[-1].copy()
        return None

    # =========================================================
    # CHECK ACTIVE
    # =========================================================

    def is_active(self):

        return (
            self.current_session is not None
            and self.current_session.get(
                "status"
            ) == "ACTIVE"
        )

    # =========================================================
    # GET SESSION HISTORY
    # =========================================================

    def get_sessions(self):

        sessions = list(
            self.sessions
        )

        if self.current_session is not None:

            sessions.append(
                self.current_session.copy()
            )

        sessions.sort(
            key=lambda session:
                session.get(
                    "start_time",
                    ""
                ),
            reverse=True
        )

        return sessions

    # =========================================================
    # GET SESSION
    # =========================================================

    def get_session(
        self,
        session_id
    ):

        if (
            self.current_session is not None
            and str(
                self.current_session.get(
                    "session_id"
                )
            ) == str(session_id)
        ):

            return self.current_session.copy()

        for session in self.sessions:

            if str(
                session.get(
                    "session_id"
                )
            ) == str(session_id):

                return session.copy()

        return None

    # =========================================================
    # DELETE SESSION
    # =========================================================

    def delete_session(
        self,
        session_id
    ):

        original_count = len(
            self.sessions
        )

        self.sessions = [
            session
            for session in self.sessions
            if str(
                session.get(
                    "session_id"
                )
            ) != str(session_id)
        ]

        removed = (
            len(self.sessions)
            < original_count
        )

        if removed:

            self.save()

        return removed

    # =========================================================
    # STORE COMPLETED SESSION
    # =========================================================

    def _store_completed_session(
        self,
        session
    ):

        self.sessions.append(
            session.copy()
        )

    # =========================================================
    # GENERATE SESSION ID
    # =========================================================

    def _generate_session_id(self):

        existing_ids = {
            str(
                session.get(
                    "session_id"
                )
            )
            for session in self.sessions
        }

        if self.current_session is not None:

            existing_ids.add(
                str(
                    self.current_session.get(
                        "session_id"
                    )
                )
            )

        number = 1

        while (
            f"SESSION{number}"
            in existing_ids
        ):

            number += 1

        return f"SESSION{number}"

    # =========================================================
    # PARSE TIME
    # =========================================================

    def _parse_time(
        self,
        value
    ):

        if not value:
            return None

        try:

            return datetime.strptime(
                value,
                "%Y-%m-%d %H:%M:%S"
            )

        except Exception:

            return None

    # =========================================================
    # SAVE
    # =========================================================

    def save(self):

        os.makedirs(
            SESSION_FOLDER,
            exist_ok=True
        )

        data = {

            "sessions":
                self.sessions,

            "current_session":
                self.current_session
        }

        try:

            with open(
                SESSION_FILE,
                "w",
                encoding="utf-8"
            ) as file:

                json.dump(
                    data,
                    file,
                    indent=4
                )

        except Exception as error:

            print(
                f"Session save error: {error}"
            )

    # =========================================================
    # LOAD
    # =========================================================

    def load(self):

        if not os.path.exists(
            SESSION_FILE
        ):

            self.sessions = []
            self.current_session = None

            return

        try:

            with open(
                SESSION_FILE,
                "r",
                encoding="utf-8"
            ) as file:

                data = json.load(
                    file
                )

            if isinstance(
                data,
                dict
            ):

                self.sessions = data.get(
                    "sessions",
                    []
                )

                self.current_session = data.get(
                    "current_session"
                )

                for s in self.sessions:
                    if isinstance(s, dict):
                        we = s.get("warning_events") or s.get("warning_count") or s.get("warnings") or 0
                        ce = s.get("critical_events") or s.get("critical_count") or s.get("critical") or 0
                        s["warning_events"] = we
                        s["warning_count"] = we
                        s["warnings"] = we
                        s["critical_events"] = ce
                        s["critical_count"] = ce
                        s["critical"] = ce

                if isinstance(self.current_session, dict):
                    we = self.current_session.get("warning_events") or self.current_session.get("warning_count") or self.current_session.get("warnings") or 0
                    ce = self.current_session.get("critical_events") or self.current_session.get("critical_count") or self.current_session.get("critical") or 0
                    self.current_session["warning_events"] = we
                    self.current_session["warning_count"] = we
                    self.current_session["warnings"] = we
                    self.current_session["critical_events"] = ce
                    self.current_session["critical_count"] = ce
                    self.current_session["critical"] = ce

                if self.sessions:
                    self.last_completed_session = self.sessions[-1]

            else:

                self.sessions = []
                self.current_session = None

        except Exception as error:

            print(
                f"Session load error: {error}"
            )

            self.sessions = []
            self.current_session = None

    # =========================================================
    # SESSION FILE
    # =========================================================

    def get_session_file(self):

        return SESSION_FILE