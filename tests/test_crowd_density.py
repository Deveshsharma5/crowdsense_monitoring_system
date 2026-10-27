"""
Unit tests for CrowdSense Crowd Counting & Spatial Density Calculation.
Tests metric area calculation, coordinate resolution, person accumulation,
density (people/m2), occupancy percentage, and risk escalation.
"""
import sys
import os

_cur = os.path.dirname(os.path.abspath(__file__))
for _p in [os.path.join(_cur, "app"), os.path.join(_cur, "..", "app"), os.path.abspath("app")]:
    if os.path.exists(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

from venue import VenueConfig
from zones import PhysicalZoneManager


def run_tests():
    print("==================================================")
    print("RUNNING CROWD COUNTING & DENSITY UNIT TESTS")
    print("==================================================")

    # 1. Initialize 20m x 10m venue with 5m grid (200m2 total, 100 capacity)
    venue = VenueConfig(
        name="Density Test Hall",
        shape="rectangle",
        length=20.0,
        width=10.0,
        grid_size=5.0,
        capacity=100,
        warning_threshold=70.0,
        critical_threshold=90.0
    )
    zm = PhysicalZoneManager(venue)

    # Expected: ceil(20/5)=4 columns, ceil(10/5)=2 rows -> 8 zones total
    assert len(zm.zones) == 8, f"Expected 8 zones, got {len(zm.zones)}"
    print(f"[PASS] Grid generated {len(zm.zones)} zones for 20m x 10m venue")

    # 2. Verify Zone Geometry and Calculated Capacities
    # Total area: 200m2. Capacity: 100 people. Baseline: 0.5 people/m2.
    # Each 5m x 5m cell = 25m2 -> capacity = 25 * 0.5 = 12.5 people.
    z_a1 = next((z for z in zm.zones if z["id"] == "A1"), None)
    assert z_a1 is not None, "Zone A1 not found"
    assert z_a1["area"] == 25.0, f"Expected area 25.0 m2, got {z_a1['area']}"
    assert abs(z_a1["zone_capacity"] - 12.5) < 0.1, f"Expected zone_capacity 12.5, got {z_a1['zone_capacity']}"
    print(f"[PASS] Zone A1 area: {z_a1['area']} m2 | allocated capacity: {z_a1['zone_capacity']} persons")

    # 3. Test Coordinate Resolution
    # Point (2.5, 2.5) -> Row 0, Col 0 -> Zone A1
    target_zone = zm.find_zone(2.5, 2.5)
    assert target_zone is not None and target_zone["id"] == "A1", f"Expected A1, got {target_zone}"
    # Point (7.5, 2.5) -> Row 0, Col 1 -> Zone A2
    target_zone_a2 = zm.find_zone(7.5, 2.5)
    assert target_zone_a2 is not None and target_zone_a2["id"] == "A2", f"Expected A2, got {target_zone_a2}"
    # Point (2.5, 7.5) -> Row 1, Col 0 -> Zone B1
    target_zone_b1 = zm.find_zone(2.5, 7.5)
    assert target_zone_b1 is not None and target_zone_b1["id"] == "B1", f"Expected B1, got {target_zone_b1}"
    print("[PASS] Coordinate mapping accurately maps (X, Y) metric coordinates to grid zones")

    # 4. Test Single Person Addition & Density
    zm.reset_counts()
    res = zm.add_person(2.5, 2.5)
    assert res is not None and res["id"] == "A1"
    assert z_a1["people"] == 1
    # Density: 1 person / 25 m2 = 0.04 people/m2
    expected_density = 1.0 / 25.0
    assert abs(z_a1["density"] - expected_density) < 1e-4, f"Expected density {expected_density}, got {z_a1['density']}"
    # Single person protection: < 2 people remains SAFE to prevent false alarms on isolated persons
    assert z_a1["risk"] == "SAFE"
    print(f"[PASS] Single person detection: count=1, density={z_a1['density']:.4f} people/m2, risk={z_a1['risk']}")

    # 5. Test Multi-Person Accumulation (multiplier support)
    zm.add_person(2.5, 2.5, multiplier=4)
    assert z_a1["people"] == 5
    # Density: 5 / 25 = 0.20 people/m2
    assert abs(z_a1["density"] - 0.20) < 1e-4
    # Occupancy: (5 / 12.5) * 100 = 40.0%
    assert abs(z_a1["occupancy"] - 40.0) < 0.1
    assert z_a1["risk"] == "SAFE"
    print(f"[PASS] Multi-person addition: count=5, occupancy={z_a1['occupancy']}%, risk={z_a1['risk']}")

    # 6. Test WARNING Escalation Transition
    # Adding 4 more -> 9 people. Occupancy = 9 / 12.5 = 72.0% (Threshold >= 70%)
    zm.add_person(2.5, 2.5, multiplier=4)
    assert z_a1["people"] == 9
    assert z_a1["occupancy"] >= 70.0
    assert z_a1["risk"] == "WARNING", f"Expected WARNING at 72% occupancy, got {z_a1['risk']}"
    print(f"[PASS] Density threshold transition to WARNING: count=9, occupancy={z_a1['occupancy']}%, risk=WARNING")

    # 7. Test CRITICAL Escalation Transition
    # Adding 3 more -> 12 people. Occupancy = 12 / 12.5 = 96.0% (Threshold >= 90%)
    zm.add_person(2.5, 2.5, multiplier=3)
    assert z_a1["people"] == 12
    assert z_a1["occupancy"] >= 90.0
    assert z_a1["risk"] == "CRITICAL", f"Expected CRITICAL at 96% occupancy, got {z_a1['risk']}"
    print(f"[PASS] Density threshold transition to CRITICAL: count=12, occupancy={z_a1['occupancy']}%, risk=CRITICAL")

    # 8. Test Count Reset
    zm.reset_counts()
    assert z_a1["people"] == 0
    assert z_a1["density"] == 0.0
    assert z_a1["occupancy"] == 0.0
    assert z_a1["risk"] == "SAFE"
    print("[PASS] reset_counts() successfully restored all zone states to zero")

    # 9. Test Out-of-bounds Clamping
    # Point (-2.0, 15.0) is outside 20x10 bounds; clamp_to_venue should constrain to (0, 10)
    clamped = zm.clamp_to_venue(-2.0, 15.0)
    assert clamped == (0.0, 10.0), f"Expected (0.0, 10.0), got {clamped}"
    resolved = zm.resolve_zone(-2.0, 15.0)
    assert resolved is not None, "Out-of-bounds point should resolve to edge zone after clamping"
    print(f"[PASS] Spatial boundary clamp handled out-of-bounds coordinate to zone {resolved['id']}")

    # 10. Test Circular Venue Grid & In-Circle Filtering
    circle_venue = VenueConfig(
        name="Circular Arena",
        shape="circle",
        diameter=20.0,
        grid_size=5.0,
        capacity=100
    )
    zm_circle = PhysicalZoneManager(circle_venue)
    # Circular grid only retains cells whose center is inside the diameter radius
    assert len(zm_circle.zones) > 0
    for z in zm_circle.zones:
        cx = z["x"] + z["width"] / 2.0
        cy = z["y"] + z["height"] / 2.0
        dist = ((cx - 10.0) ** 2 + (cy - 10.0) ** 2) ** 0.5
        assert dist <= 10.0 + 1e-4, f"Zone center ({cx}, {cy}) is outside circular radius"
    print(f"[PASS] Circular venue grid generated {len(zm_circle.zones)} zones strictly inside diameter boundary")

    print()
    print("==================================================")
    print("ALL 10 CROWD COUNTING & DENSITY TESTS PASSED!")
    print("==================================================")


if __name__ == "__main__":
    run_tests()
