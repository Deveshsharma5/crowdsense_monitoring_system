"""
CrowdSense - Real-Time Telegram Notification Service
=====================================================
Dispatches real emergency notifications to Telegram when a venue zone
transitions into CRITICAL status.

Features:
- Reads credentials securely from environment variables / local .env
- Fully asynchronous background worker (queue.Queue + daemon Thread)
- Zero-blocking: Camera inference, UI, and Flask routes are never delayed
- Rising-edge state transition detection (only fires on transition into CRITICAL)
- Thread-safe per-zone cooldown rate limiter (default: 300s)
- Delivery verification via Telegram Bot HTTP API (verifies ok: true)
- Dedicated safe test notification utility without modifying session/alert data
"""

import json
import logging
import os
import queue
import sys
import threading
import time
from datetime import datetime
from typing import Any, Dict, Optional, Tuple
import urllib.error
import urllib.parse
import urllib.request

logger = logging.getLogger("CrowdSenseTelegram")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[CrowdSense Telegram] %(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def load_dotenv(env_path: Optional[str] = None) -> Dict[str, str]:
    """
    Parse a local .env file and populate os.environ without overwriting existing vars.
    Checks project root, app folder, and current working directory.
    """
    if env_path is None:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.dirname(current_dir)
        candidates = [
            os.path.join(root_dir, ".env"),
            os.path.join(current_dir, ".env"),
            os.path.join(os.getcwd(), ".env"),
        ]
        for c in candidates:
            if os.path.isfile(c):
                env_path = c
                break

    if not env_path or not os.path.isfile(env_path):
        return {}

    loaded = {}
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip("'\"")
                    if key:
                        if key not in os.environ:
                            os.environ[key] = val
                        loaded[key] = val
    except Exception as e:
        logger.warning(f"Error reading .env from {env_path}: {e}")

    return loaded


class TelegramNotifier:
    """
    Thread-safe, asynchronous Telegram alert dispatcher with state transition
    detection and per-zone cooldown rate limiting.
    """

    BOT_USERNAME = "@CrowdSense_Alert_System_bot"
    DEFAULT_CHAT_ID = "10661709991"
    DEFAULT_COOLDOWN = 300

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        cooldown_seconds: Optional[int] = None,
        max_queue_size: int = 100,
    ):
        # Automatically load from local .env if available
        load_dotenv()

        self._bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        self._chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID", self.DEFAULT_CHAT_ID).strip()

        # Cooldown in seconds
        try:
            env_cooldown = int(os.getenv("TELEGRAM_COOLDOWN_SECONDS", str(self.DEFAULT_COOLDOWN)))
        except (ValueError, TypeError):
            env_cooldown = self.DEFAULT_COOLDOWN

        self.cooldown_seconds = cooldown_seconds if cooldown_seconds is not None else env_cooldown

        # Thread synchronization
        self._lock = threading.Lock()
        self._zone_states: Dict[str, str] = {}  # {zone_id: "SAFE" | "WARNING" | "CRITICAL"}
        self._last_sent_times: Dict[str, float] = {}  # {zone_id: timestamp}

        # Background worker queue
        self._queue: queue.Queue = queue.Queue(maxsize=max_queue_size)
        self._running = True
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            name="CrowdSense-TelegramWorker",
            daemon=True
        )
        self._worker_thread.start()

        # Masked token for safe logging
        masked_token = (
            f"{self._bot_token[:4]}...{self._bot_token[-4:]}"
            if len(self._bot_token) > 8
            else ("<NOT_CONFIGURED>" if not self._bot_token else "<SET>")
        )
        logger.info(
            f"Telegram Service initialized | Bot: {self.BOT_USERNAME} | Chat: {self._chat_id} | "
            f"Token: {masked_token} | Cooldown: {self.cooldown_seconds}s"
        )

    # =========================================================
    # REFRESH / CONFIGURATION
    # =========================================================

    def reload_config(self):
        """Reload credentials from environment / .env at runtime."""
        load_dotenv()
        with self._lock:
            self._bot_token = os.getenv("TELEGRAM_BOT_TOKEN", self._bot_token).strip()
            self._chat_id = os.getenv("TELEGRAM_CHAT_ID", self._chat_id).strip()
            try:
                self.cooldown_seconds = int(
                    os.getenv("TELEGRAM_COOLDOWN_SECONDS", str(self.cooldown_seconds))
                )
            except (ValueError, TypeError):
                pass

    def is_configured(self) -> bool:
        """Returns True if a real-looking bot token and chat ID are present."""
        token = self._bot_token
        # Reject known placeholder values from .env.example / .env template
        placeholders = {
            "",
            "your_new_telegram_bot_token_here",
            "your_telegram_bot_token_here",
            "not_configured",
        }
        return bool(token and token not in placeholders and self._chat_id)

    def get_status(self) -> Dict[str, Any]:
        """Safe status dictionary without leaking credentials."""
        with self._lock:
            configured = self.is_configured()
            active_zones = dict(self._zone_states)
            cooldown = self.cooldown_seconds
            chat_id = self._chat_id

        return {
            "configured": configured,
            "bot_username": self.BOT_USERNAME,
            "chat_id": chat_id,
            "cooldown_seconds": cooldown,
            "queue_size": self._queue.qsize(),
            "tracked_zones": len(active_zones),
        }

    # =========================================================
    # STATE TRANSITIONS & NOTIFICATION ENQUEUEING
    # =========================================================

    def update_zone_status(self, zone_id: str, status: str) -> None:
        """
        Record current non-critical status (SAFE / WARNING) for a zone
        so that subsequent entries into CRITICAL are recognized as transitions.
        """
        zone_id = str(zone_id or "UNKNOWN").strip().upper()
        status = str(status or "SAFE").strip().upper()

        with self._lock:
            prev = self._zone_states.get(zone_id)
            self._zone_states[zone_id] = status
            if prev == "CRITICAL" and status != "CRITICAL":
                logger.info(f"Zone {zone_id} cleared critical state -> now {status}")

    def notify_critical_transition(
        self,
        zone_id: str,
        risk: str,
        people: Any = 0,
        density: Any = 0.0,
        venue_name: str = "CrowdSense Venue",
        message: Optional[str] = None,
        special_type: Optional[str] = None,
        timestamp: Optional[str] = None
    ) -> bool:
        """
        Evaluate if this alert represents a transition into CRITICAL and
        satisfies the per-zone cooldown. If valid, enqueues the Telegram message.

        Returns True if enqueued, False if suppressed (not critical, not transition, or in cooldown).
        """
        risk = str(risk or "").strip().upper()
        if risk != "CRITICAL":
            self.update_zone_status(zone_id, risk)
            return False

        zone_id = str(zone_id or "UNKNOWN").strip().upper()
        now = time.time()

        with self._lock:
            prev_status = self._zone_states.get(zone_id, "SAFE")
            last_sent = self._last_sent_times.get(zone_id, 0.0)

            # Check 1: Is this an actual transition into CRITICAL?
            # A transition occurs if previous status was NOT CRITICAL,
            # OR if this is the very first detection of this zone.
            is_transition = (prev_status != "CRITICAL")

            # Always record the zone as CRITICAL
            self._zone_states[zone_id] = "CRITICAL"

            if not is_transition:
                # Still in existing critical state - do not re-notify every frame
                return False

            # Check 2: Has the per-zone cooldown elapsed since the last Telegram alert?
            elapsed = now - last_sent
            if elapsed < self.cooldown_seconds:
                logger.info(
                    f"Telegram alert for Zone {zone_id} suppressed: "
                    f"Cooldown active ({int(elapsed)}s < {self.cooldown_seconds}s)"
                )
                return False

            # Lock in the new sent timestamp
            self._last_sent_times[zone_id] = now

        # Build payload outside the lock
        ts_str = timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Format clean density string
        try:
            d_val = float(density)
            density_str = f"{d_val:.4f} people/m²"
        except (ValueError, TypeError):
            density_str = str(density) if density is not None else "N/A"

        try:
            p_val = int(people)
        except (ValueError, TypeError):
            p_val = people

        alert_details = message or f"Critical crowd level in zone {zone_id}"
        if special_type:
            alert_details += f" ({special_type})"

        telegram_text = (
            f"🚨 CROWDSENSE CRITICAL ALERT\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"📍 Venue: {venue_name}\n"
            f"🛑 Zone: {zone_id}\n"
            f"⚠️ Severity: CRITICAL\n"
            f"👥 People Detected: {p_val}\n"
            f"📊 Density: {density_str}\n"
            f"🕒 Timestamp: {ts_str}\n"
            f"📝 Details: {alert_details}\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"⚠️ ACTION REQUIRED: Immediate crowd control response advised."
        )

        item = {
            "type": "alert",
            "zone_id": zone_id,
            "text": telegram_text,
            "timestamp": now
        }

        try:
            self._queue.put_nowait(item)
            logger.info(f"Enqueued Telegram CRITICAL notification for Zone {zone_id}")
            return True
        except queue.Full:
            logger.warning("Telegram alert queue is full. Dropping message to protect system stability.")
            return False

    # =========================================================
    # SAFE TEST NOTIFICATION
    # =========================================================

    def send_test_notification(
        self,
        venue_name: str = "CrowdSense Venue"
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Sends a single test message directly to verify Telegram connectivity.
        Does NOT alter zone states, does NOT create alert records, and does NOT
        affect live session analytics.

        Returns (success, message, response_data).
        """
        if not self.is_configured():
            err = (
                "Telegram credentials not configured. Please set TELEGRAM_BOT_TOKEN in .env"
            )
            logger.warning(err)
            return False, err, {"error": "unconfigured"}

        ts_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        test_text = (
            f"🧪 CROWDSENSE — TEST NOTIFICATION\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"📍 Venue: {venue_name}\n"
            f"🟢 Status: Monitoring System Online\n"
            f"🤖 Bot: {self.BOT_USERNAME}\n"
            f"🕒 Timestamp: {ts_str}\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"✅ Verification Successful!\n"
            f"Your Telegram notification pipeline is connected. Real-time CRITICAL alerts will be delivered here."
        )

        # Dispatch test synchronously so the caller / UI gets immediate confirmation
        return self._send_http_request(test_text)

    # =========================================================
    # HTTP DISPATCH WORKER
    # =========================================================

    def _worker_loop(self):
        """Asynchronous daemon worker that consumes items from the queue."""
        while self._running:
            try:
                item = self._queue.get(timeout=1.0)
            except queue.Empty:
                continue

            try:
                text = item.get("text", "")
                zone_id = item.get("zone_id", "UNKNOWN")

                if not self.is_configured():
                    logger.warning(
                        f"[SIMULATION / UNCONFIGURED] Would send Telegram alert for Zone {zone_id}:\n{text}"
                    )
                else:
                    success, msg, _ = self._send_http_request(text)
                    if success:
                        logger.info(f"Telegram notification successfully delivered for Zone {zone_id}")
                    else:
                        logger.error(f"Failed to deliver Telegram notification for Zone {zone_id}: {msg}")

            except Exception as e:
                logger.error(f"Unexpected error in Telegram worker loop: {e}")
            finally:
                self._queue.task_done()

    def _send_http_request(self, text: str) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Executes outbound HTTPS POST to api.telegram.org/bot<TOKEN>/sendMessage.
        Never reveals the token in error logs or return values.
        Uses requests (with certifi CA certificates) when available, falling back
        to standard library urllib.
        """
        token = self._bot_token
        chat_id = self._chat_id

        if not token:
            return False, "Missing TELEGRAM_BOT_TOKEN", {}
        if not chat_id:
            return False, "Missing TELEGRAM_CHAT_ID", {}

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text
        }

        # Preferred method: requests library (handles system/certifi CA bundles seamlessly)
        try:
            import requests
            resp = requests.post(
                url,
                json=payload,
                headers={"User-Agent": "CrowdSense-Alert-System/1.0"},
                timeout=10.0
            )
            try:
                resp_json = resp.json()
            except Exception:
                resp_json = {}

            if resp.status_code == 200 and resp_json.get("ok") is True:
                return True, "Message delivered successfully", resp_json
            else:
                desc = resp_json.get("description") or f"HTTP {resp.status_code}"
                safe_desc = desc.replace(token, "<TOKEN>")
                logger.error(f"Telegram API Error: {safe_desc}")
                return False, f"Telegram API error: {safe_desc}", resp_json

        except ImportError:
            pass  # Fall through to standard urllib
        except requests.exceptions.Timeout:
            logger.error("Telegram request timed out after 10 seconds")
            return False, "Request timed out after 10 seconds", {}
        except requests.exceptions.RequestException as e:
            safe_err = str(e).replace(token, "<TOKEN>")
            logger.error(f"Telegram Network Request Error: {safe_err}")
            return False, f"Network request error: {safe_err}", {}
        except Exception as e:
            safe_err = str(e).replace(token, "<TOKEN>")
            logger.error(f"Telegram send error: {safe_err}")
            return False, f"Send error: {safe_err}", {}

        # Fallback method: urllib.request (standard library)
        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data_bytes,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "CrowdSense-Alert-System/1.0"
            },
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                resp_bytes = resp.read()
                resp_json = json.loads(resp_bytes.decode("utf-8"))

                if resp_json.get("ok") is True:
                    return True, "Message delivered successfully", resp_json
                else:
                    desc = resp_json.get("description", "Unknown Telegram API error")
                    return False, f"Telegram API error: {desc}", resp_json

        except urllib.error.HTTPError as e:
            try:
                error_body = e.read().decode("utf-8")
                err_json = json.loads(error_body)
                desc = err_json.get("description", str(e))
            except Exception:
                desc = str(e)

            safe_desc = desc.replace(token, "<TOKEN>")
            logger.error(f"Telegram HTTP {e.code} Error: {safe_desc}")
            return False, f"Telegram HTTP {e.code}: {safe_desc}", {}

        except urllib.error.URLError as e:
            logger.error(f"Telegram Network Connection Error: {e.reason}")
            return False, f"Network connection error: {e.reason}", {}

        except TimeoutError:
            logger.error("Telegram request timed out after 10 seconds")
            return False, "Request timed out after 10 seconds", {}

        except Exception as e:
            safe_err = str(e).replace(token, "<TOKEN>")
            logger.error(f"Telegram send error: {safe_err}")
            return False, f"Send error: {safe_err}", {}

    def stop(self):
        """Clean shutdown of worker thread."""
        self._running = False


# Module-level singleton instance for convenient access across components
_instance: Optional[TelegramNotifier] = None
_instance_lock = threading.Lock()


def get_telegram_notifier() -> TelegramNotifier:
    """Get or create global singleton TelegramNotifier instance."""
    global _instance
    with _instance_lock:
        if _instance is None:
            _instance = TelegramNotifier()
        return _instance


# =========================================================
# STANDALONE CLI TEST & VERIFICATION UTILITY
# =========================================================

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print(" CrowdSense Telegram Notification Diagnostic")
    print("=" * 60)

    notifier = get_telegram_notifier()
    status = notifier.get_status()

    print(f"Bot Username : {status['bot_username']}")
    print(f"Chat ID      : {status['chat_id']}")
    print(f"Cooldown     : {status['cooldown_seconds']}s")
    print(f"Configured   : {status['configured']}")

    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        print("\nAttempting test notification delivery...")
        success, message, _ = notifier.send_test_notification(venue_name="CrowdSense Diagnostics")
        print(f"Result: {'SUCCESS' if success else 'FAILED'}")
        print(f"Message: {message}")
    else:
        print("\nUsage:")
        print("  python app/telegram_service.py --test    # Dispatch a safe test notification")
    print("=" * 60 + "\n")
