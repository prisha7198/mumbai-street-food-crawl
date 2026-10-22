"""Generate the synthetic Mumbai street food dataset.

Stalls are fictional; the areas, landmarks and rough coordinates are real.
Everything is driven by a fixed seed so the files are reproducible:

    python data/generate_data.py

Writes stalls.json, users.json and ratings.json next to this file.
"""
from __future__ import annotations

import json
import math
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 42
SPREAD_SCALE = 0.55  # food streets are dense; keeps most stalls within a 1 km walk of each other
OUT = Path(__file__).resolve().parent
rng = random.Random(SEED)

# ---------------------------------------------------------------- areas
# centre, spread (lat, lng degrees), lng_bias keeps coastal areas on land,
# category weights reflect what each neighbourhood is known for.
AREAS = {
    "Dadar": dict(
        centre=(19.0190, 72.8430), spread=(0.0075, 0.0060), lng_min=-1.0,
        landmarks=["near Kabutarkhana", "outside Dadar station west", "opposite Plaza cinema",
                   "on Ranade Road", "near Shivaji Park gate 5", "by the flower market",
                   "at the corner of Gokhale Road", "behind Dadar TT circle"],
        cats={"vada_pav": 4, "misal": 3, "chaat": 2, "south_indian": 2, "kulfi_desserts": 2,
              "juice_falooda": 2, "chai_snacks": 2, "sandwich": 1, "pav_bhaji": 1, "frankie_rolls": 1},
        jain=0.3, late=0.1),
    "Mohammed Ali Road": dict(
        centre=(18.9580, 72.8345), spread=(0.0060, 0.0035), lng_min=-1.0,
        landmarks=["in the lane behind Minara Masjid", "near Bohri Mohalla", "under the JJ flyover",
                   "opposite Mandvi post office", "at the Khau Galli corner", "near Bhendi Bazaar junction",
                   "by Sardar Patel Road signal"],
        cats={"kebabs": 6, "biryani": 3, "kulfi_desserts": 3, "juice_falooda": 2, "chai_snacks": 1,
              "frankie_rolls": 2},
        jain=0.0, late=0.85),
    "Ghatkopar": dict(
        centre=(19.0790, 72.9085), spread=(0.0060, 0.0060), lng_min=-1.0,
        landmarks=["in Khau Galli", "outside Ghatkopar station east", "near R B Mehta Marg",
                   "opposite Rajawadi garden", "at Pant Nagar corner", "by the Jain temple lane",
                   "near Garodia Nagar bus stop"],
        cats={"chaat": 4, "sandwich": 3, "pav_bhaji": 3, "south_indian": 2, "indo_chinese": 2,
              "juice_falooda": 2, "kulfi_desserts": 2, "vada_pav": 1},
        jain=0.8, late=0.15),
    "Juhu": dict(
        centre=(19.0985, 72.8275), spread=(0.0090, 0.0050), lng_min=0.0,
        landmarks=["at the Juhu beach food court", "near Juhu Tara Road", "opposite the beach entrance",
                   "by Gandhigram Road", "near Juhu Circle", "on the beach promenade"],
        cats={"chaat": 3, "pav_bhaji": 3, "kulfi_desserts": 3, "juice_falooda": 3, "sandwich": 1,
              "indo_chinese": 2, "frankie_rolls": 1, "seafood": 1},
        jain=0.3, late=0.25),
    "Colaba": dict(
        centre=(18.9150, 72.8300), spread=(0.0070, 0.0025), lng_min=-1.0,
        landmarks=["on Colaba Causeway", "behind the Taj lane", "near Regal Circle",
                   "opposite Electric House", "by Sassoon Dock road", "near Colaba market"],
        cats={"kebabs": 3, "frankie_rolls": 3, "seafood": 2, "chai_snacks": 2, "sandwich": 2,
              "kulfi_desserts": 1, "juice_falooda": 1, "indo_chinese": 1},
        jain=0.1, late=0.45),
    "Bandra": dict(
        centre=(19.0590, 72.8330), spread=(0.0070, 0.0060), lng_min=-0.3,
        landmarks=["on Hill Road", "near Carter Road promenade", "by Elco Market",
                   "near Mount Mary steps", "on Linking Road", "outside Bandra station west",
                   "near Chapel Road"],
        cats={"frankie_rolls": 3, "kebabs": 2, "indo_chinese": 2, "seafood": 2, "kulfi_desserts": 2,
              "juice_falooda": 2, "sandwich": 2, "chai_snacks": 1, "pav_bhaji": 1},
        jain=0.15, late=0.35),
    "Girgaum Chowpatty": dict(
        centre=(18.9550, 72.8150), spread=(0.0050, 0.0040), lng_min=0.0,
        landmarks=["on the Chowpatty sands", "near Wilson College", "opposite Babulnath temple road",
                   "by the Tilak statue", "on Marine Drive end", "near Kennedy Bridge"],
        cats={"chaat": 3, "pav_bhaji": 3, "kulfi_desserts": 3, "juice_falooda": 2, "sandwich": 1,
              "south_indian": 1},
        jain=0.4, late=0.2),
    "Matunga": dict(
        centre=(19.0275, 72.8555), spread=(0.0050, 0.0050), lng_min=-1.0,
        landmarks=["near King's Circle", "outside Matunga station east", "on Bhandarkar Road",
                   "by the Ram Mandir lane", "opposite Five Gardens", "on Telang Road"],
        cats={"south_indian": 5, "chai_snacks": 2, "kulfi_desserts": 1, "juice_falooda": 2,
              "sandwich": 1, "misal": 1},
        jain=0.4, late=0.05),
    "Vile Parle": dict(
        centre=(19.0995, 72.8445), spread=(0.0055, 0.0055), lng_min=-1.0,
        landmarks=["in the Parle Khau Galli", "outside Vile Parle station east", "near Hanuman Road",
                   "opposite Mithibai College", "by Nehru Road", "near Parle Tilak school"],
        cats={"vada_pav": 2, "sandwich": 3, "chaat": 3, "pav_bhaji": 2, "juice_falooda": 2,
              "kulfi_desserts": 1, "indo_chinese": 1, "frankie_rolls": 1},
        jain=0.7, late=0.1),
    "Fort": dict(
        centre=(18.9330, 72.8345), spread=(0.0055, 0.0045), lng_min=-1.0,
        landmarks=["near Kala Ghoda", "outside CSMT subway", "by Horniman Circle",
                   "on DN Road arcade", "near Flora Fountain", "opposite Bombay High Court gate"],
        cats={"vada_pav": 2, "sandwich": 3, "chai_snacks": 3, "south_indian": 2, "frankie_rolls": 1,
              "juice_falooda": 1, "indo_chinese": 1, "misal": 1},
        jain=0.25, late=0.05),
}
STALLS_PER_AREA = {"Dadar": 20, "Mohammed Ali Road": 18, "Ghatkopar": 20, "Juhu": 18, "Colaba": 18,
                   "Bandra": 18, "Girgaum Chowpatty": 14, "Matunga": 14, "Vile Parle": 16, "Fort": 16}

# ---------------------------------------------------------------- categories
CATS = {
    "vada_pav": dict(dishes=["Vada pav", "Chura pav", "Cheese vada pav", "Bhajji pav", "Schezwan vada pav", "Samosa pav"],
                     price=(18, 45), spice=(3, 4), veg="veg", hours="snack", type=["cart", "stall"],
                     names=["Vada Pav", "Vada Pav Centre", "Wada Pav Stall"]),
    "pav_bhaji": dict(dishes=["Butter pav bhaji", "Cheese pav bhaji", "Masala pav", "Tawa pulao", "Jain pav bhaji"],
                      price=(110, 220), spice=(2, 4), veg="veg", hours="evening", type=["stall", "counter"],
                      names=["Pav Bhaji", "Pav Bhaji Centre", "Bhaji House"]),
    "chaat": dict(dishes=["Pani puri", "Sev puri", "Dahi puri", "Ragda pattice", "Bhel puri", "Masala puri"],
                  price=(40, 110), spice=(2, 4), veg="veg", hours="evening", type=["cart", "stall"],
                  names=["Chaat Corner", "Pani Puri Wala", "Bhel House"]),
    "sandwich": dict(dishes=["Bombay masala toast", "Cheese chutney sandwich", "Grilled veg sandwich", "Chocolate sandwich", "Club sandwich"],
                     price=(50, 160), spice=(1, 3), veg="veg", hours="day", type=["cart", "stall"],
                     names=["Sandwich", "Toast Corner", "Sandwich Point"]),
    "south_indian": dict(dishes=["Mysore masala dosa", "Idli sambar", "Medu vada", "Rava dosa", "Uttapam", "Filter coffee"],
                         price=(50, 150), spice=(1, 3), veg="veg", hours="morning", type=["counter", "eatery"],
                         names=["Udupi", "Idli House", "Dosa Corner", "Cafe"]),
    "kebabs": dict(dishes=["Seekh kebab", "Chicken tikka", "Bheja fry", "Nalli nihari", "Chicken malai tikka", "Mutton baida roti", "Tandoori chicken"],
                   price=(140, 360), spice=(3, 5), veg="non_veg", hours="late", type=["stall", "eatery"],
                   names=["Kebab Centre", "Grill House", "Tikka Point", "Kebab Corner"]),
    "frankie_rolls": dict(dishes=["Chicken frankie", "Paneer frankie", "Egg roll", "Mutton kathi roll", "Schezwan veg frankie"],
                          price=(70, 190), spice=(2, 4), veg="both", hours="evening", type=["stall", "counter"],
                          names=["Frankie", "Roll House", "Kathi Roll Corner"]),
    "indo_chinese": dict(dishes=["Veg manchurian", "Schezwan noodles", "Triple schezwan rice", "Chicken lollipop", "Chilli paneer", "Veg momos"],
                         price=(90, 210), spice=(3, 5), veg="both", hours="evening", type=["cart", "stall"],
                         names=["Chinese Corner", "Wok Express", "Chinese Point"]),
    "seafood": dict(dishes=["Bombil fry", "Prawn koliwada", "Surmai thali", "Crab masala", "Fish fry pav"],
                    price=(200, 460), spice=(3, 5), veg="non_veg", hours="evening", type=["stall", "eatery"],
                    names=["Seafood Corner", "Koliwada", "Fish Fry Centre"]),
    "misal": dict(dishes=["Misal pav", "Kolhapuri misal", "Usal pav", "Sabudana vada", "Kanda poha"],
                  price=(60, 130), spice=(4, 5), veg="veg", hours="morning", type=["counter", "eatery"],
                  names=["Misal House", "Misal Point", "Kolhapuri Misal"]),
    "kulfi_desserts": dict(dishes=["Malai kulfi", "Mango kulfi", "Malpua with rabdi", "Phirni", "Jalebi rabdi", "Kesar pista kulfi"],
                           price=(45, 150), spice=(1, 1), veg="veg", hours="evening", type=["cart", "stall"],
                           names=["Kulfi Centre", "Kulfi House", "Mithai Corner", "Sweets"]),
    "juice_falooda": dict(dishes=["Royal falooda", "Sugarcane juice", "Mango milkshake", "Kala khatta gola", "Sitaphal cream", "Lassi"],
                          price=(50, 160), spice=(1, 1), veg="veg", hours="day", type=["cart", "stall"],
                          names=["Juice Centre", "Falooda House", "Juice Bar"]),
    "chai_snacks": dict(dishes=["Cutting chai", "Bun maska", "Kanda bhaji", "Khari biscuit", "Irani chai", "Samosa"],
                        price=(15, 60), spice=(1, 2), veg="veg", hours="morning", type=["cart", "stall"],
                        names=["Chai Stall", "Tea Point", "Chai Corner"]),
    "biryani": dict(dishes=["Mutton dum biryani", "Chicken biryani", "Kheema pav", "Mutton pulao", "Egg biryani"],
                    price=(140, 300), spice=(3, 4), veg="non_veg", hours="late", type=["eatery", "counter"],
                    names=["Biryani House", "Biryani Centre", "Handi Corner"]),
}

PREFIXES_VEG = ["Shree Sai", "Jai Bhavani", "Laxmi", "Navrang", "Gokul", "Madhuban", "Annapurna", "Sagar",
                "Ganesh", "Krishna", "Mahalaxmi", "Shiv Shakti", "Om Sai", "Balaji", "Ambika", "Shubham",
                "Vithal", "Kamat", "Rajdhani", "Mangal", "Anand", "Hari Om", "Datta", "Swami", "Parle",
                "Ganga", "Sneha", "Kailash", "Mahesh", "Prakash", "Shanti", "Guru Kripa", "Sharda"]
PREFIXES_NONVEG = ["Al-Noor", "Zaika", "Noorani", "Shalimar", "Barkat", "Haji", "Rehmat", "Taj", "Mehfil",
                   "Delhi Darbar", "Lucky", "Sultan", "Karim Bhai", "Bismillah", "Chand", "Hyderabadi",
                   "Mughal", "Salim", "Royal", "Gulshan"]
PREFIXES_SEA = ["Koli", "Sea Breeze", "Sagar Kinara", "Mahim", "Malvani", "Gomantak", "Konkan"]

VIBES = ["late_night", "quick_bite", "family_friendly", "iconic", "hidden_gem", "beachside",
         "office_crowd", "student_favourite", "queue_worthy", "breakfast", "sit_down", "crowded_lanes"]
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

HOURS = {
    "morning": [("07:00", "14:00"), ("06:30", "13:30"), ("07:30", "22:00"), ("07:00", "21:30")],
    "day": [("10:00", "22:00"), ("11:00", "23:00"), ("09:30", "21:30")],
    "snack": [("07:00", "22:30"), ("10:00", "23:00"), ("16:00", "23:30"), ("06:30", "21:00")],
    "evening": [("16:00", "23:00"), ("17:00", "23:30"), ("12:00", "23:00"), ("16:30", "00:30")],
    "late": [("18:00", "02:30"), ("19:00", "03:00"), ("17:00", "01:30"), ("12:00", "00:30")],
}

REVIEW_TEMPLATES = [
    "The {dish} is exactly how it should be. {mood}",
    "Came for the {dish}, stayed for a second plate. {mood}",
    "{dish} was {adj}. {mood2}",
    "Reliable {dish}, {adj} every time. {mood2}",
    "Worth the walk just for the {dish}. {mood}",
    "Had the {dish} after work, {adj}. {mood2}",
]
MOODS = ["Will be back.", "Bit of a wait but worth it.", "Go before the rush.", "Cash and UPI both work.",
         "The owner remembers regulars.", "Gets crowded after 8.", "Perfect after a long day.",
         "Portions are generous for the price."]
MOODS_LOW = ["Service was slow tonight.", "A little oily for me.", "Prices have gone up recently.",
             "Hygiene could be better.", "Not as good as it used to be."]
ADJ = ["fresh and hot", "properly spiced", "crisp", "generous", "consistent", "full of flavour", "balanced"]
ADJ_LOW = ["a bit bland", "lukewarm", "too salty", "average"]


def price_band(p: int) -> str:
    return "₹" if p < 100 else ("₹₹" if p <= 250 else "₹₹₹")


def allocate(weights: dict[str, float], n: int) -> list[str]:
    """Split n stalls across categories in proportion to weights (largest remainder)."""
    total = sum(weights.values())
    raw = {k: n * w / total for k, w in weights.items()}
    counts = {k: int(v) for k, v in raw.items()}
    for k in sorted(raw, key=lambda k: raw[k] - counts[k], reverse=True)[: n - sum(counts.values())]:
        counts[k] += 1
    out = [k for k, c in counts.items() for _ in range(c)]
    rng.shuffle(out)
    return out


def make_stall(sid: int, area: str, cat: str, used_names: set[str]) -> dict:
    a = AREAS[area]
    c = CATS[cat]

    # location: gaussian around the centre, coastal areas pushed inland
    for _ in range(100):
        dlat = rng.gauss(0, a["spread"][0] * SPREAD_SCALE)
        dlng = rng.gauss(0, a["spread"][1] * SPREAD_SCALE)
        if dlng / a["spread"][1] >= a["lng_min"]:
            break
    lat = round(a["centre"][0] + dlat, 6)
    lng = round(a["centre"][1] + dlng, 6)

    veg_type = c["veg"]
    if cat == "biryani" and rng.random() < 0.15:
        veg_type = "both"
    if cat == "indo_chinese" and rng.random() < 0.45:
        veg_type = "veg"
    if cat == "frankie_rolls" and rng.random() < 0.25:
        veg_type = "veg"

    if area == "Mohammed Ali Road":
        prefixes = PREFIXES_NONVEG
    elif veg_type == "non_veg":
        prefixes = PREFIXES_SEA if cat == "seafood" else PREFIXES_NONVEG
    else:
        prefixes = PREFIXES_VEG
    for _ in range(200):
        name = f"{rng.choice(prefixes)} {rng.choice(c['names'])}"
        if name not in used_names:
            break
    used_names.add(name)

    jain = veg_type == "veg" and rng.random() < a["jain"]
    lo, hi = c["price"]
    price = int(round(rng.uniform(lo, hi) / 5) * 5)
    spice = max(1, min(5, rng.randint(*c["spice"]) + (1 if area == "Mohammed Ali Road" and c["spice"][0] > 1 and rng.random() < 0.3 else 0)))

    hours_kind = c["hours"]
    if rng.random() < a["late"] and hours_kind in ("evening", "snack", "day"):
        hours_kind = "late"
    open_t, close_t = rng.choice(HOURS[hours_kind])
    closed_day = rng.choice(DAYS) if rng.random() < 0.35 else None

    quality = rng.betavariate(5, 2)  # latent 0..1, skewed good
    rating = round(min(4.9, max(2.9, 3.0 + quality * 1.9 + rng.gauss(0, 0.12))), 1)
    review_count = int(min(4200, max(8, rng.lognormvariate(4.9, 1.0) * (0.6 + quality))))
    hygiene = max(1, min(5, int(round(2.4 + quality * 2.2 + rng.gauss(0, 0.6)))))
    wait = max(2, int(round(rng.gauss(4 + quality * 10, 4))))

    vibes = set()
    open_h = int(open_t[:2])
    close_h = int(close_t[:2])
    if close_h < 6 or close_t >= "23:30":
        vibes.add("late_night")
    if open_h <= 8:
        vibes.add("breakfast")
    if c["type"][0] == "cart" or wait < 6:
        vibes.add("quick_bite")
    if review_count > 900 and rating >= 4.3:
        vibes.add("iconic")
    if review_count < 120 and rating >= 4.3:
        vibes.add("hidden_gem")
    if area in ("Juhu", "Girgaum Chowpatty") or (area == "Bandra" and rng.random() < 0.3):
        vibes.add("beachside")
    if area in ("Fort",) or (open_h <= 10 and rng.random() < 0.3):
        vibes.add("office_crowd")
    if area in ("Vile Parle", "Matunga") or rng.random() < 0.15:
        vibes.add("student_favourite")
    if wait >= 14:
        vibes.add("queue_worthy")
    stype = rng.choice(c["type"])
    seating = {"cart": "standing", "stall": rng.choice(["standing", "a few stools"]),
               "counter": rng.choice(["a few stools", "standing"]), "eatery": "seated"}[stype]
    if seating == "seated":
        vibes.add("sit_down")
        if rng.random() < 0.6:
            vibes.add("family_friendly")
    if area in ("Mohammed Ali Road", "Ghatkopar", "Vile Parle") and rng.random() < 0.6:
        vibes.add("crowded_lanes")
    if veg_type != "non_veg" and spice <= 3 and rng.random() < 0.3:
        vibes.add("family_friendly")

    dishes = rng.sample(c["dishes"], k=min(len(c["dishes"]), rng.choice([2, 3, 3])))
    if veg_type == "veg":
        dishes = [d for d in dishes if not any(w in d.lower() for w in ("chicken", "mutton", "egg", "fish", "prawn"))] or [c["dishes"][0]]
    if veg_type == "non_veg" and cat in ("frankie_rolls", "indo_chinese"):
        dishes = [d for d in dishes if "veg" not in d.lower() and "paneer" not in d.lower()] or [c["dishes"][0]]

    peak_start = rng.choice([13, 19, 20, 21]) if hours_kind != "morning" else rng.choice([8, 9])
    if hours_kind == "late":
        peak_start = rng.choice([21, 22, 23])
    peak = f"{peak_start:02d}:00-{(peak_start + 2) % 24:02d}:00"

    payment = ["cash", "upi"] + (["card"] if stype == "eatery" or rng.random() < 0.15 else [])

    landmark = rng.choice(a["landmarks"])
    desc_bits = {
        "veg": "Pure veg", "non_veg": "Non-veg", "both": "Veg and non-veg",
    }[veg_type]
    description = (f"{desc_bits} {stype} {landmark}, best known for its {dishes[0].lower()}. "
                   f"{'Jain versions on request. ' if jain else ''}"
                   f"{'Expect a queue at peak hours.' if wait >= 12 else 'Service is quick.'}")

    reviews = []
    low = rating < 3.8
    for t in rng.sample(REVIEW_TEMPLATES, 3):
        reviews.append(t.format(
            dish=rng.choice(dishes),
            adj=rng.choice(ADJ_LOW if low and rng.random() < 0.6 else ADJ),
            mood=rng.choice(MOODS),
            mood2=rng.choice(MOODS_LOW if low and rng.random() < 0.6 else MOODS),
        ))

    return {
        "id": f"s{sid:03d}",
        "name": name,
        "type": stype,
        "area": area,
        "landmark_hint": landmark,
        "lat": lat,
        "lng": lng,
        "category": cat,
        "signature_dishes": dishes,
        "veg_type": veg_type,
        "jain_options": jain,
        "spice_level": spice,
        "price_per_person_inr": price,
        "price_band": price_band(price),
        "rating": rating,
        "review_count": review_count,
        "open_time": open_t,
        "close_time": close_t,
        "closed_day": closed_day,
        "peak_hours": peak,
        "avg_wait_minutes": wait,
        "seating": seating,
        "hygiene_score": hygiene,
        "payment": payment,
        "vibe_tags": sorted(vibes),
        "description": description,
        "sample_reviews": reviews,
        "_quality": quality,  # latent, stripped before writing
    }


FIRST_NAMES = ["Aarav", "Ananya", "Rohan", "Isha", "Kabir", "Meera", "Vihaan", "Saanvi", "Arjun", "Diya",
               "Aditya", "Kavya", "Reyansh", "Tara", "Ishaan", "Riya", "Zoya", "Farhan", "Neha", "Siddharth",
               "Pooja", "Yusuf", "Nikhil", "Sana", "Rahul", "Priya", "Omkar", "Sneha", "Kunal", "Aisha",
               "Varun", "Mihika", "Tanvi", "Imran", "Gauri", "Dev", "Nisha", "Harsh", "Alia", "Parth",
               "Shreya", "Aman", "Juhi", "Manav", "Fatima", "Rishi", "Anika", "Kiran"]
LAST_INITIALS = list("ABDGJKMNPRSTV")


def make_users(n: int) -> list[dict]:
    users = []
    areas = list(AREAS)
    cats = list(CATS)
    for i in range(n):
        diet = rng.choices(["veg", "jain", "non_veg", "any"], weights=[40, 12, 28, 20])[0]
        allowed = [c for c in cats if diet in ("non_veg", "any") or CATS[c]["veg"] != "non_veg"]
        if diet == "non_veg":
            favs = rng.sample([c for c in allowed if CATS[c]["veg"] != "veg"], 2) + rng.sample(
                [c for c in allowed if CATS[c]["veg"] == "veg"], 1)
        else:
            favs = rng.sample(allowed, 3)
        users.append({
            "user_id": f"u{i + 1:02d}",
            "name": f"{FIRST_NAMES[i % len(FIRST_NAMES)]} {rng.choice(LAST_INITIALS)}.",
            "home_area": rng.choice(areas),
            "diet": diet,
            "spice_tolerance": rng.choices([1, 2, 3, 4, 5], weights=[1, 2, 3, 3, 2])[0],
            "budget_per_person_inr": rng.choice([250, 300, 400, 500, 600, 800, 1000]),
            "favourite_categories": favs,
        })
    return users


def make_ratings(users: list[dict], stalls: list[dict]) -> list[dict]:
    ratings = []
    start = date(2025, 6, 1)
    for u in users:
        diet = u["diet"]
        ok = [s for s in stalls
              if not (diet in ("veg", "jain") and s["veg_type"] == "non_veg")]
        home = [s for s in ok if s["area"] == u["home_area"]]
        fav = [s for s in ok if s["category"] in u["favourite_categories"]]
        n = rng.randint(24, 42)
        chosen: dict[str, dict] = {}
        while len(chosen) < n:
            r = rng.random()
            pool = home if r < 0.4 else (fav if r < 0.75 else ok)
            s = rng.choice(pool)
            chosen[s["id"]] = s
        for s in chosen.values():
            score = 1.4 + 2.6 * s["_quality"]
            score += 0.9 if s["category"] in u["favourite_categories"] else -0.25
            score -= 0.45 * max(0, s["spice_level"] - u["spice_tolerance"])
            per_stop = u["budget_per_person_inr"] / 4
            if s["price_per_person_inr"] > per_stop * 1.5:
                score -= 0.4
            if diet == "jain" and not s["jain_options"]:
                score -= 0.8
            score += rng.gauss(0, 0.55)
            rating = int(min(5, max(1, round(score))))
            ratings.append({
                "user_id": u["user_id"],
                "stall_id": s["id"],
                "rating": rating,
                "visited_on": (start + timedelta(days=rng.randint(0, 480))).isoformat(),
            })
    return ratings


def main() -> None:
    stalls: list[dict] = []
    used: set[str] = set()
    sid = 1
    for area, n in STALLS_PER_AREA.items():
        for cat in allocate(AREAS[area]["cats"], n):
            stalls.append(make_stall(sid, area, cat, used))
            sid += 1
    users = make_users(48)
    ratings = make_ratings(users, stalls)
    for s in stalls:
        s.pop("_quality")
    (OUT / "stalls.json").write_text(json.dumps(stalls, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT / "users.json").write_text(json.dumps(users, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT / "ratings.json").write_text(json.dumps(ratings, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{len(stalls)} stalls, {len(users)} users, {len(ratings)} ratings")


if __name__ == "__main__":
    main()
