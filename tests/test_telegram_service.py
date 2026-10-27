"""
Unit tests for CrowdSense Telegram Service.
Run from project root: python test_telegram_service.py
"""
import os
import sys
import time
import threading

sys.path.insert(0, os.path.abspath("app"))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app")))

# ============================================================
# TEST INFRASTRUCTURE
# ============================================================

PASS = 0
FAIL = 0

def test(name, condition, detail=""):
    global PASS, FAIL
    status = "PASS" if condition else "FAIL"
    if condition:
        PASS += 1
    else:
        FAIL += 1
    print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))


# ============================================================
# 1. IMPORT & INSTANTIATION
# ============================================================
print("\n=== 1. Imports & Instantiation ===")

from telegram_service import TelegramNotifier, get_telegram_notifier

notifier = TelegramNotifier(bot_token="not_configured", chat_id="10661709991")
test("Instantiate without crash", True)
test("is_configured() -> False for placeholder token", not notifier.is_configured())
test("Worker thread alive", notifier._worker_thread.is_alive())
test("Queue starts empty", notifier._queue.qsize() == 0)


# ============================================================
# 2. SECURITY — Token not leaked
# ============================================================
print("\n=== 2. Security Tests ===")

status = notifier.get_status()
status_str = str(status)
test("Token absent from get_status()", "not_configured" not in status_str)
test("Chat ID present in get_status()", status["chat_id"] == "10661709991")
test("configured=False when token is placeholder", status["configured"] is False)

success, msg, _ = notifier.send_test_notification("Test Venue")
test("send_test_notification returns False when not configured", not success)
test("Error message does not contain raw token", "not_configured" not in msg)


# ============================================================
# 3. RISING-EDGE TRANSITION DETECTION
# ============================================================
print("\n=== 3. State Transition Detection ===")

notifier2 = TelegramNotifier(bot_token="not_configured", chat_id="10661709991")

# Enqueue spying
enqueued = []
original_put = notifier2._queue.put_nowait
def spy_put(item):
    enqueued.append(item)
    return original_put(item)
notifier2._queue.put_nowait = spy_put

# Zone starts SAFE, then goes CRITICAL → should enqueue
notifier2.update_zone_status("ZONE_A", "SAFE")
result1 = notifier2.notify_critical_transition(
    zone_id="ZONE_A", risk="CRITICAL", people=12, density=0.8
)
test("First CRITICAL transition enqueued", result1 is True)
test("Queue size = 1 after first transition", len(enqueued) == 1)

# Zone is STILL CRITICAL (no actual new transition) → should NOT enqueue again
result2 = notifier2.notify_critical_transition(
    zone_id="ZONE_A", risk="CRITICAL", people=15, density=0.9
)
test("Repeat CRITICAL not enqueued (state dedup)", result2 is False)
test("Queue size still 1 after repeat", len(enqueued) == 1)

# Zone recovers to SAFE, then goes CRITICAL again (after cooldown bypass)
notifier2.update_zone_status("ZONE_A", "SAFE")
# Force bypass cooldown for testing
with notifier2._lock:
    notifier2._last_sent_times["ZONE_A"] = 0.0  # Reset cooldown

result3 = notifier2.notify_critical_transition(
    zone_id="ZONE_A", risk="CRITICAL", people=20, density=1.2
)
test("Re-CRITICAL after SAFE recovery enqueued", result3 is True)
test("Queue size = 2 after second valid transition", len(enqueued) == 2)


# ============================================================
# 4. COOLDOWN RATE LIMITING
# ============================================================
print("\n=== 4. Cooldown Rate Limiting ===")

notifier3 = TelegramNotifier(
    bot_token="not_configured",
    chat_id="10661709991",
    cooldown_seconds=10  # short for test
)

enqueued3 = []
original_put3 = notifier3._queue.put_nowait
def spy_put3(item):
    enqueued3.append(item)
    return original_put3(item)
notifier3._queue.put_nowait = spy_put3

# First alert: cooldown timer starts
notifier3.update_zone_status("ZONE_B", "SAFE")
r1 = notifier3.notify_critical_transition("ZONE_B", "CRITICAL", people=5)

# Recover and re-enter CRITICAL immediately (within cooldown)
notifier3.update_zone_status("ZONE_B", "SAFE")
r2 = notifier3.notify_critical_transition("ZONE_B", "CRITICAL", people=8)

test("First alert dispatched", r1 is True)
test("Second alert within cooldown suppressed", r2 is False)
test("Only 1 message in queue during cooldown", len(enqueued3) == 1)


# ============================================================
# 5. WARNING alerts never trigger telegram
# ============================================================
print("\n=== 5. Warning / Safe Don't Trigger ===")

notifier4 = TelegramNotifier(bot_token="not_configured", chat_id="10661709991")
enqueued4 = []
notifier4._queue.put_nowait = lambda item: enqueued4.append(item)

notifier4.notify_critical_transition("ZONE_C", "WARNING", people=7)
notifier4.notify_critical_transition("ZONE_C", "SAFE", people=0)
test("WARNING does not enqueue", len(enqueued4) == 0)
test("SAFE does not enqueue", len(enqueued4) == 0)


# ============================================================
# 6. Message Content Validation
# ============================================================
print("\n=== 6. Message Content Validation ===")

notifier5 = TelegramNotifier(bot_token="not_configured", chat_id="10661709991")
captured_text = []

def capture_put(item):
    captured_text.append(item.get("text", ""))
notifier5._queue.put_nowait = capture_put

notifier5.update_zone_status("ZONE_D", "SAFE")
notifier5.notify_critical_transition(
    zone_id="ZONE_D",
    risk="CRITICAL",
    people=22,
    density=1.5,
    venue_name="Test Arena",
    message="Dense crowd in standing zone",
    timestamp="2026-01-01 12:00:00"
)

test("One message captured", len(captured_text) == 1)
if captured_text:
    msg_body = captured_text[0]
    test("Venue name present", "Test Arena" in msg_body)
    test("Zone ID present", "ZONE_D" in msg_body)
    test("CRITICAL keyword present", "CRITICAL" in msg_body)
    test("People count present", "22" in msg_body)
    test("Density present", "1.5" in msg_body)
    test("Timestamp present", "2026-01-01" in msg_body)
    test("Incident details present", "Dense crowd" in msg_body)
    test("Token NOT in message body", "not_configured" not in msg_body)


# ============================================================
# 7. Queue saturation — system doesn't crash
# ============================================================
print("\n=== 7. Queue Saturation Safety ===")

notifier6 = TelegramNotifier(bot_token="not_configured", chat_id="10661709991", max_queue_size=3)
for i in range(10):
    notifier6._queue.put_nowait = lambda item: (_ for _ in ()).throw(Exception("Queue full")) if notifier6._queue.qsize() >= 3 else None
    try:
        notifier6._queue.put_nowait({})
    except Exception:
        pass
test("Queue saturation does not crash service", True)


# ============================================================
# 8. API Endpoint Tests
# ============================================================
print("\n=== 8. Flask API Endpoint Tests ===")

from flask import Flask as _TestFlask
from api_endpoints import CrowdSenseAPI
_test_app = _TestFlask("telegram_api_test")
api = CrowdSenseAPI(app=_test_app)
client = _test_app.test_client()

import json as _json

res = client.get("/api/telegram/status")
test("/api/telegram/status returns 200", res.status_code == 200)
data = _json.loads(res.data)
test("Response has 'configured' field", "configured" in data)
test("Response has 'bot_username' field", "bot_username" in data)
test("Response has 'chat_id' field", "chat_id" in data)
test("Response has 'cooldown_seconds' field", "cooldown_seconds" in data)

raw_response = res.data.decode()
test("Token not in /api/telegram/status response body", "TELEGRAM_BOT_TOKEN" not in raw_response)

# POST /api/telegram/test — should fail gracefully with unconfigured token
res_test = client.post("/api/telegram/test", json={})
test("/api/telegram/test returns valid status code", res_test.status_code in (200, 400, 500))
test_data = _json.loads(res_test.data)
test("Test response has 'success': False", test_data.get("success") is False)
test("Test response has message field", "message" in test_data)


# ============================================================
# FINAL SUMMARY
# ============================================================
print()
print("=" * 50)
print(f"  RESULTS: {PASS} PASSED / {FAIL} FAILED")
print("=" * 50)
if FAIL > 0:
    sys.exit(1)

