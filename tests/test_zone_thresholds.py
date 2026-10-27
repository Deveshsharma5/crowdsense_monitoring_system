import sys
import os
import json

_cur = os.path.dirname(os.path.abspath(__file__))
for _p in [os.path.join(_cur, "app"), os.path.join(_cur, "..", "app"), os.path.abspath("app")]:
    if os.path.exists(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

from venue import VenueConfig
from zones import PhysicalZoneManager
from analytics_manager import AnalyticsManager
from report_manager import ReportManager
from report_exporter import ReportExporter
from api_endpoints import CrowdSenseAPI
from flask import Flask

def run_tests():
    print("========================================")
    print("RUNNING ZONE THRESHOLD INTEGRATION TESTS")
    print("========================================")

    # 1. Test VenueConfig
    v = VenueConfig(
        name="Test Arena",
        shape="rectangle",
        length=20,
        width=10,
        grid_size=10,
        warning_threshold=70,
        critical_threshold=90
    )
    assert v.zone_thresholds == {}
    print("[PASS] VenueConfig initializes with empty zone_thresholds")

    # 2. Test PhysicalZoneManager creation gate
    zm = PhysicalZoneManager(v)
    assert len(zm.zones) == 2, f"Expected 2 zones, got {len(zm.zones)}"
    z1 = zm.zones[0]
    z2 = zm.zones[1]
    assert z1["warning_threshold"] == 70.0
    assert z1["critical_threshold"] == 90.0
    assert z1["has_custom_threshold"] is False
    print(f"[PASS] PhysicalZoneManager created {len(zm.zones)} zones with venue defaults")

    # 3. Test validation: cannot edit invalid zone
    try:
        zm.set_zone_threshold("INVALID_ZONE", 60, 80)
        assert False, "Should have raised ValueError for invalid zone"
    except ValueError as e:
        assert "not found" in str(e)
        print("[PASS] Rejects non-existent zone ID")

    # 4. Test validation: min >= max
    try:
        zm.set_zone_threshold(z1["id"], 85, 75)
        assert False, "Should have raised ValueError when min >= max"
    except ValueError as e:
        assert "strictly less" in str(e)
        print("[PASS] Rejects warning threshold >= critical threshold")

    # 5. Test validation: thresholds <= 0
    try:
        zm.set_zone_threshold(z1["id"], 0, 90)
        assert False, "Should have raised ValueError when threshold <= 0"
    except ValueError as e:
        assert "greater than 0" in str(e)
        print("[PASS] Rejects zero or negative thresholds")

    # 6. Test setting custom thresholds
    zm.set_zone_threshold(z1["id"], warning_threshold=50.0, critical_threshold=75.0)
    assert z1["warning_threshold"] == 50.0
    assert z1["critical_threshold"] == 75.0
    assert z1["has_custom_threshold"] is True
    assert v.zone_thresholds[z1["id"]]["warning_threshold"] == 50.0
    assert v.zone_thresholds[z1["id"]]["critical_threshold"] == 75.0
    # Zone 2 should still be venue defaults
    assert z2["warning_threshold"] == 70.0
    assert z2["critical_threshold"] == 90.0
    assert z2["has_custom_threshold"] is False
    print("[PASS] Successfully updated zone 1 with custom thresholds while preserving zone 2 defaults")

    # 7. Test Risk Engine uses custom thresholds
    # Zone 1 capacity:
    z1["zone_capacity"] = 10.0
    z1["people"] = 6  # 60% occupancy
    # With global default (70%), 60% would be SAFE.
    # But zone 1 custom warning threshold is 50%, so it should be WARNING!
    risk = zm.calculate_risk(z1)
    assert risk == "WARNING", f"Expected WARNING at 60% occ with 50% threshold, got {risk}"
    print("[PASS] Risk calculation respects custom zone threshold (60% occ triggers WARNING with 50% custom threshold)")

    # 8. Test Resetting threshold
    zm.set_zone_threshold(z1["id"], reset=True)
    assert z1["warning_threshold"] == 70.0
    assert z1["critical_threshold"] == 90.0
    assert z1["has_custom_threshold"] is False
    assert z1["id"] not in v.zone_thresholds
    risk_after_reset = zm.calculate_risk(z1)
    assert risk_after_reset == "SAFE", f"Expected SAFE after reset to 70% threshold, got {risk_after_reset}"
    print("[PASS] Successfully reset zone threshold to venue defaults")

    # 9. Test API Endpoints
    app = Flask(__name__)
    api = CrowdSenseAPI(app=app, venue_config=v, zone_manager=zm)

    client = app.test_client()

    # GET /api/zones/<zone_id>/thresholds
    res = client.get(f"/api/zones/{z1['id']}/thresholds")
    assert res.status_code == 200
    data = json.loads(res.data)
    assert data["success"] is True
    assert data["warning_threshold"] == 70.0
    assert data["critical_threshold"] == 90.0
    print("[PASS] API GET /api/zones/<id>/thresholds returns valid data")

    # POST /api/zones/<zone_id>/thresholds
    res = client.post(
        f"/api/zones/{z1['id']}/thresholds",
        json={"warning_threshold": 55, "critical_threshold": 80}
    )
    assert res.status_code == 200
    data = json.loads(res.data)
    assert data["success"] is True
    assert z1["warning_threshold"] == 55.0
    assert z1["critical_threshold"] == 80.0
    assert z1["has_custom_threshold"] is True
    print("[PASS] API POST /api/zones/<id>/thresholds updates thresholds")

    # POST when min >= max should return 400
    res = client.post(
        f"/api/zones/{z1['id']}/thresholds",
        json={"warning_threshold": 85, "critical_threshold": 80}
    )
    assert res.status_code == 400
    print("[PASS] API POST rejects min >= max with 400 Bad Request")

    # Gate check: when no zones exist
    empty_v = VenueConfig(length=0, width=0, grid_size=5)
    empty_zm = PhysicalZoneManager(empty_v)
    empty_zm.zones = []
    empty_api = CrowdSenseAPI(app=Flask("empty"), venue_config=empty_v, zone_manager=empty_zm)
    empty_client = empty_api.app.test_client()
    res = empty_client.post(
        "/api/zones/A1/thresholds",
        json={"warning_threshold": 50, "critical_threshold": 80}
    )
    assert res.status_code == 400
    err = json.loads(res.data)["error"]
    assert "All venue zones must be created" in err
    print(f"[PASS] API Gate: Rejects threshold editing when zones are not created: '{err}'")

    # 10. Test AnalyticsManager
    am = AnalyticsManager()
    am.venue_config = v
    rows = [
        {"timestamp": "2026-10-23 00:00:00", "zone_id": z1["id"], "zone_people": 6, "density": 0.06, "risk": "WARNING"},
        {"timestamp": "2026-10-23 00:00:01", "zone_id": z2["id"], "zone_people": 2, "density": 0.02, "risk": "SAFE"}
    ]
    zone_stats = am.calculate_zone_statistics(rows)
    assert z1["id"] in zone_stats
    z1_stat = zone_stats[z1["id"]]
    assert z1_stat["warning_threshold"] == 55.0
    assert z1_stat["critical_threshold"] == 80.0
    assert z1_stat["has_custom_threshold"] is True
    assert z1_stat["warning_records"] == 1
    print("[PASS] AnalyticsManager correctly embeds custom zone thresholds and tracks risk records")

    # 11. Test ReportManager
    rm = ReportManager(venue_config=v, analytics_manager=am)
    venue_data = rm.get_venue_data()
    assert "warning_threshold" in venue_data
    assert "critical_threshold" in venue_data
    assert "zone_thresholds" in venue_data
    assert z1["id"] in venue_data["zone_thresholds"]
    print("[PASS] ReportManager includes warning/critical and custom zone thresholds in venue data")

    # 12. Test PDF Report Exporter
    report_mock = {
        "venue": venue_data,
        "analytics": {
            "zones": zone_stats,
            "most_crowded_zone": z1_stat,
            "people": {"peak_people": 8, "average_people": 4},
            "occupancy": {"peak_occupancy": 60, "average_occupancy": 30},
            "density": {"peak_density": 0.06, "average_density": 0.03},
            "risk": {"peak_risk": "WARNING"},
            "time_range": {"start_time": "2026-10-22 23:00:00", "end_time": "2026-10-22 23:05:00"}
        },
        "session": None
    }
    exporter = ReportExporter(report_manager=rm)
    pdf_path = exporter.export_pdf(report=report_mock)
    assert os.path.exists(pdf_path), f"PDF file not found at {pdf_path}"
    print(f"[PASS] ReportExporter generated PDF with custom zone thresholds: {pdf_path}")

    print()
    print("========================================")
    print("ALL 12 INTEGRATION TESTS PASSED SUCCESSFULLY!")
    print("========================================")

if __name__ == "__main__":
    run_tests()
