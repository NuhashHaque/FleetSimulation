"""
routes.py
─────────
Static route definitions for the 4 buses operating in Dhaka, Bangladesh.

Each route is a list of waypoints, where every waypoint is a dict:
    {"lat": float, "lon": float, "name": str}

The simulator traverses these waypoints in order (FORWARD), then in reverse
(RETURN), incrementing ``trip_count`` each time it completes a full round-trip.
"""

ROUTES: dict[str, list[dict]] = {
    "BUS_01": [  # Mirpur → Motijheel corridor
        {"lat": 23.8223, "lon": 90.3654, "name": "Mirpur 10"},
        {"lat": 23.8100, "lon": 90.3750, "name": "Mirpur 2"},
        {"lat": 23.7982, "lon": 90.3872, "name": "Shyamoli"},
        {"lat": 23.7806, "lon": 90.3993, "name": "Farmgate"},
        {"lat": 23.7279, "lon": 90.4188, "name": "Motijheel"},
    ],
    "BUS_02": [  # Uttara → Gulshan corridor
        {"lat": 23.8759, "lon": 90.3795, "name": "Uttara"},
        {"lat": 23.8469, "lon": 90.3944, "name": "Airport"},
        {"lat": 23.8233, "lon": 90.4152, "name": "Banani"},
        {"lat": 23.7937, "lon": 90.4066, "name": "Gulshan 1"},
        {"lat": 23.7808, "lon": 90.4152, "name": "Gulshan 2"},
    ],
    "BUS_03": [  # Demra → Sadarghat corridor
        {"lat": 23.7208, "lon": 90.4800, "name": "Demra"},
        {"lat": 23.7150, "lon": 90.4600, "name": "Jatrabari"},
        {"lat": 23.7100, "lon": 90.4400, "name": "Postogola"},
        {"lat": 23.7192, "lon": 90.4200, "name": "Sutrapur"},
        {"lat": 23.7185, "lon": 90.4076, "name": "Sadarghat"},
    ],
    "BUS_04": [  # Dhanmondi → New Market corridor
        {"lat": 23.7461, "lon": 90.3742, "name": "Dhanmondi 27"},
        {"lat": 23.7524, "lon": 90.3804, "name": "Dhanmondi 15"},
        {"lat": 23.7590, "lon": 90.3880, "name": "Science Lab"},
        {"lat": 23.7640, "lon": 90.3950, "name": "Elephant Road"},
        {"lat": 23.7820, "lon": 90.4050, "name": "New Market"},
    ],
}
