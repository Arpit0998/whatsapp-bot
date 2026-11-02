"""Autoveer bot content: every piece of text and catalogue data lives here.

Edit this file to change models, branches or wording; no code changes needed.
Source: autoveer.com (public website). Prices are intentionally NOT listed:
on-road prices change often, so the bot captures a lead and an executive calls back.
"""

CONTENT = {
    "company": {
        "name": "Autoveer Pvt Ltd",
        "short_name": "Autoveer",
        "region": "Haryana",
        "website": "https://autoveer.com",
        "phone": "9812000912",
        "hq": "Rohtak, Haryana 124001",
        "about": (
            "Autoveer Pvt Ltd is an authorised multi-brand automobile dealer in Haryana with "
            "24+ years of experience. It started as *Choudhary Tractors* and today sells and services "
            "*Nissan* cars, *Bajaj* two & three wheelers, *Ashok Leyland* commercial vehicles and "
            "*Massey Ferguson* tractors, with genuine spare parts, authorised service, finance and insurance support."
        ),
    },
    # `kind` decides wording: car -> "Test Drive", bike -> "Test Ride", cv/tractor -> "Demo".
    "brands": [
        {
            "id": "nissan",
            "name": "Nissan",
            "emoji": "🚗",
            "title": "Nissan Cars",
            "kind": "car",
            "models": [
                {
                    "id": "magnite",
                    "name": "Nissan Magnite",
                    "group": "SUV",
                    "highlights": [
                        "Compact SUV with 1.0L Turbo petrol option",
                        "8-inch touchscreen, wireless Apple CarPlay & Android Auto",
                        "360° Around View Monitor camera",
                        "Manual, AMT and CVT options",
                    ],
                },
                {
                    "id": "xtrail",
                    "name": "Nissan X-Trail",
                    "group": "SUV",
                    "highlights": ["Premium 7-seater SUV", "1.5L VC-Turbo petrol with mild-hybrid", "Panoramic sunroof"],
                },
                {
                    "id": "nissan-other",
                    "name": "Other / Upcoming Nissan models",
                    "group": "More",
                    "highlights": ["Ask our executive about new launches and bookings"],
                },
            ],
        },
        {
            "id": "bajaj",
            "name": "Bajaj",
            "emoji": "🏍️",
            "title": "Bajaj Two & Three Wheelers",
            "kind": "bike",
            "models": [
                {"id": "platina", "name": "Bajaj Platina", "group": "Motorcycles", "highlights": ["Best-in-class mileage", "Comfortec suspension for daily commute"]},
                {"id": "ct", "name": "Bajaj CT 110X", "group": "Motorcycles", "highlights": ["Rugged commuter", "Low running cost"]},
                {"id": "pulsar", "name": "Bajaj Pulsar range", "group": "Motorcycles", "highlights": ["125cc to 400cc sporty range", "NS, N and classic Pulsar variants"]},
                {"id": "freedom", "name": "Bajaj Freedom 125 CNG", "group": "Motorcycles", "highlights": ["World's first CNG motorcycle", "Petrol + CNG, very low cost per km"]},
                {"id": "chetak", "name": "Bajaj Chetak (Electric)", "group": "Scooters", "highlights": ["Electric scooter, metal body", "Home charging"]},
                {"id": "bajaj-3w", "name": "Bajaj RE / Maxima (3-Wheeler)", "group": "Three Wheelers", "highlights": ["Passenger & cargo autos", "Petrol, CNG, LPG and electric options"]},
            ],
        },
        {
            "id": "ashok",
            "name": "Ashok Leyland",
            "emoji": "🚚",
            "title": "Ashok Leyland Commercial Vehicles",
            "kind": "cv",
            "models": [
                {"id": "dost", "name": "Ashok Leyland Dost", "group": "Light Commercial", "highlights": ["Small commercial vehicle", "High payload, low maintenance"]},
                {"id": "bada-dost", "name": "Ashok Leyland Bada Dost", "group": "Light Commercial", "highlights": ["Bigger loading deck", "Driver comfort for long routes"]},
                {"id": "al-trucks", "name": "Trucks (ICV / MCV / HCV)", "group": "Trucks", "highlights": ["Haulage, tippers and tractor-trailers", "Fleet & finance support"]},
                {"id": "al-bus", "name": "Buses", "group": "Buses", "highlights": ["School, staff and route buses"]},
            ],
        },
        {
            "id": "mf",
            "name": "Massey Ferguson",
            "emoji": "🚜",
            "title": "Massey Ferguson Tractors",
            "kind": "tractor",
            "models": [
                {"id": "mf-241", "name": "MF 241 DI", "group": "Tractors", "highlights": ["Popular 42 HP tractor", "Fuel efficient, great for haulage & farming"]},
                {"id": "mf-1035", "name": "MF 1035 DI", "group": "Tractors", "highlights": ["36 HP all-rounder", "Trusted by small & medium farms"]},
                {"id": "mf-7250", "name": "MF 7250 Power", "group": "Tractors", "highlights": ["46 HP, heavy implements", "Strong lifting capacity"]},
                {"id": "mf-other", "name": "Other HP ranges / implements", "group": "More", "highlights": ["Tell us your farm needs, we will suggest the right model"]},
            ],
        },
    ],
    # Branch list from autoveer.com. Add "address" / "phone" per branch when available.
    "branches": [
        {"id": "rohtak", "city": "Rohtak", "note": "Head office", "address": "Rohtak, Haryana 124001"},
        {"id": "karnal", "city": "Karnal"},
        {"id": "bhiwani", "city": "Bhiwani"},
        {"id": "kurukshetra", "city": "Kurukshetra"},
        {"id": "ladwa", "city": "Ladwa"},
        {"id": "bahadurgarh", "city": "Bahadurgarh"},
        {"id": "jhajjar", "city": "Jhajjar"},
        {"id": "dadri", "city": "Charkhi Dadri"},
    ],
    "service_types": [
        {"id": "periodic", "label": "Periodic / free service"},
        {"id": "repair", "label": "Repair / breakdown"},
        {"id": "accident", "label": "Accident repair / insurance claim"},
        {"id": "parts", "label": "Genuine spare parts & accessories"},
    ],
    "insurance_types": [
        {"id": "new", "label": "New vehicle insurance"},
        {"id": "renew", "label": "Renew existing insurance"},
        {"id": "claim", "label": "Insurance claim help"},
        {"id": "loan", "label": "Vehicle loan / EMI"},
    ],
    "vehicle_types": [
        {"id": "car", "label": "Car"},
        {"id": "bike", "label": "Two wheeler"},
        {"id": "threewheeler", "label": "Three wheeler"},
        {"id": "cv", "label": "Commercial vehicle"},
        {"id": "tractor", "label": "Tractor"},
    ],
    # Free-text shortcuts: if a customer types a word instead of a number, jump straight there.
    # Intents (service, insurance, ...) are checked before brands, so "car insurance" -> insurance.
    "keywords": {
        "nissan": ["nissan", "car", "cars", "suv"],
        "bajaj": ["bajaj", "bike", "bikes", "motorcycle", "scooter", "auto", "rickshaw", "three wheeler", "3 wheeler", "e-rickshaw"],
        "ashok": ["ashok", "leyland", "truck", "trucks", "bus", "tempo", "commercial", "pickup"],
        "mf": ["massey", "ferguson", "tractor", "tractors", "farm", "kisan"],
        "service": ["service", "servicing", "repair", "workshop", "breakdown", "spare", "parts"],
        "insurance": ["insurance", "insure", "policy", "claim", "loan", "emi", "finance"],
        "showroom": ["showroom", "address", "location", "branch", "near", "directions", "kahan"],
        "executive": ["agent", "executive", "human", "call me", "callback", "talk", "baat"],
        "about": ["about", "who are you", "company"],
    },
    # Session expires after this many minutes of silence; the next message starts fresh.
    "session_timeout_min": 30,
}
