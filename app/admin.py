from venue import VenueConfig


def get_number(prompt, default=None):

    while True:

        value = input(prompt)

        if value.strip() == "" and default is not None:
            return default

        try:
            return float(value)

        except ValueError:
            print("Please enter a valid number.")


def setup_venue():

    print("\n================================")
    print("       CROWDSENSE ADMIN")
    print("       VENUE SETUP")
    print("================================\n")

    name = input("Venue name: ").strip()

    if not name:
        name = "Default Venue"

    print("\nSelect venue shape:")
    print("1. Rectangle")
    print("2. Circle")

    shape_choice = input("Enter choice (1/2): ").strip()

    if shape_choice == "2":
        shape = "circle"

        diameter = get_number(
            "Enter diameter (meters): "
        )

        length = 0
        width = 0

    else:
        shape = "rectangle"

        length = get_number(
            "Enter length (meters): "
        )

        width = get_number(
            "Enter width (meters): "
        )

        diameter = 0

    capacity = get_number(
        "Maximum permitted occupancy: "
    )

    warning = get_number(
        "Warning threshold (%): ",
        70
    )

    critical = get_number(
        "Critical threshold (%): ",
        90
    )

    print("\nZone configuration")
    print("------------------")
    print("You can leave this empty.")
    print("CrowdSense will automatically create default zones.\n")

    zones_input = input(
        "Enter zone names separated by commas (optional): "
    ).strip()

    if zones_input:
        zones = [
            zone.strip()
            for zone in zones_input.split(",")
            if zone.strip()
        ]
    else:
        zones = []

    venue = VenueConfig(
        name=name,
        shape=shape,
        length=length,
        width=width,
        diameter=diameter,
        capacity=capacity,
        warning_threshold=warning,
        critical_threshold=critical,
        zones=zones
    )

    venue.save()

    print("\n--------------------------------")
    print("VENUE CONFIGURATION")
    print("--------------------------------")
    print(f"Name: {venue.name}")
    print(f"Shape: {venue.shape}")
    print(f"Area: {venue.calculate_area():.2f} m²")
    print(f"Capacity: {venue.capacity}")
    print(f"Warning: {venue.warning_threshold}%")
    print(f"Critical: {venue.critical_threshold}%")

    if venue.zones:
        print(f"Custom zones: {', '.join(venue.zones)}")
    else:
        print("Zones: DEFAULT SMART ZONING")

    print("--------------------------------\n")


if __name__ == "__main__":
    setup_venue()