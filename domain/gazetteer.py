"""
NammaSignal Bengaluru Landmark Gazetteer
Authoritative gazetteer and coordinate resolver for Bengaluru arterial roads,
underpasses, and chronic flood hotspots.
"""

from typing import Dict, List, Optional, Tuple
import re
from domain.entities import GeoPoint


# Curated dictionary of major Bengaluru junctions and known flood hotspots
BENGALURU_HOTSPOTS: Dict[str, Dict[str, any]] = {
    "silk_board": {
        "canonical_name": "Silk Board Junction & Underpass",
        "latitude": 12.9176,
        "longitude": 77.6238,
        "aliases": [
            "silk board", "silkboard", "silk board underpass", "silkboard junction", 
            "central silk board", "csb", "hosur road silk board"
        ]
    },
    "bellandur_ecospace": {
        "canonical_name": "Outer Ring Road - Ecospace / Bellandur",
        "latitude": 12.9260,
        "longitude": 77.6835,
        "aliases": [
            "ecospace", "bellandur", "bellandur ecospace", "orr ecospace", 
            "outer ring road ecospace", "rmz ecospace", "bellandur junction"
        ]
    },
    "koramangala_sony_world": {
        "canonical_name": "Sony World Junction, Koramangala",
        "latitude": 12.9348,
        "longitude": 77.6288,
        "aliases": [
            "sony world", "sony world signal", "koramangala 80ft road", 
            "sony world junction", "koramangala 4th block"
        ]
    },
    "hebbal_flyover": {
        "canonical_name": "Hebbal Flyover & Underpass",
        "latitude": 13.0358,
        "longitude": 77.5970,
        "aliases": [
            "hebbal", "hebbal flyover", "hebbal junction", "hebbal underpass", 
            "airport road hebbal", "ballari road hebbal"
        ]
    },
    "windsor_manor": {
        "canonical_name": "Windsor Manor Railway Underpass",
        "latitude": 12.9965,
        "longitude": 77.5843,
        "aliases": [
            "windsor manor", "windsor manor underpass", "windsor manor bridge", 
            "sankey road underpass", "golf course underpass"
        ]
    },
    "tin_factory": {
        "canonical_name": "Tin Factory / KR Puram Suspension Bridge",
        "latitude": 13.0034,
        "longitude": 77.6644,
        "aliases": [
            "tin factory", "tinfactory", "kr puram bridge", "kr puram railway station", 
            "old madras road tin factory", "kasturi nagar tin factory"
        ]
    },
    "majestic_underpass": {
        "canonical_name": "Anand Rao Circle / Majestic Underpass",
        "latitude": 12.9774,
        "longitude": 77.5729,
        "aliases": [
            "anand rao circle", "majestic underpass", "race course road underpass", 
            "anand rao underpass", "subhash nagar underpass", "majestic"
        ]
    },
    "dairy_circle": {
        "canonical_name": "Dairy Circle / Bannerghatta Road",
        "latitude": 12.9360,
        "longitude": 77.5996,
        "aliases": [
            "dairy circle", "dairy circle underpass", "bannerghatta road start", 
            "nimhans junction", "dairy circle flyover"
        ]
    },
    "marathahalli": {
        "canonical_name": "Marathahalli Bridge & Multiplex Junction",
        "latitude": 12.9569,
        "longitude": 77.7011,
        "aliases": [
            "marathahalli", "marathahalli bridge", "marathahalli junction", 
            "kalamandir marathahalli", "marathahalli underpass"
        ]
    },
    "domlur_flyover": {
        "canonical_name": "Domlur Flyover & Inner Ring Road",
        "latitude": 12.9608,
        "longitude": 77.6387,
        "aliases": [
            "domlur", "domlur flyover", "domlur junction", "inner ring road domlur", 
            "eGL domlur", "intermediate ring road"
        ]
    },
    "varthur_kodi": {
        "canonical_name": "Varthur Kodi & Whitefield Main Road",
        "latitude": 12.9575,
        "longitude": 77.7470,
        "aliases": [
            "varthur", "varthur kodi", "varthur lake road", "varthur junction", 
            "whitefield varthur road"
        ]
    }
}


def normalize_text(text: str) -> str:
    """Lowercase and strip punctuation for canonical alias matching."""
    return re.sub(r"[^\w\s]", " ", text.lower()).strip()


def resolve_landmark(text: str) -> Optional[GeoPoint]:
    """
    Scans a given text string for known Bengaluru landmarks.
    Returns GeoPoint if recognized, otherwise None.
    """
    clean_text = normalize_text(text)
    
    # Priority check: longest alias matches first to prevent greedy substring collisions
    matched_spot = None
    longest_match_len = 0

    for spot_key, data in BENGALURU_HOTSPOTS.items():
        for alias in data["aliases"]:
            normalized_alias = normalize_text(alias)
            # Match word boundary
            pattern = rf"\b{re.escape(normalized_alias)}\b"
            if re.search(pattern, clean_text):
                if len(normalized_alias) > longest_match_len:
                    longest_match_len = len(normalized_alias)
                    matched_spot = data

    if matched_spot:
        return GeoPoint(
            latitude=matched_spot["latitude"],
            longitude=matched_spot["longitude"],
            landmark_name=matched_spot["canonical_name"],
            accuracy_meters=50.0
        )
    return None


def get_all_canonical_landmarks() -> List[Dict[str, any]]:
    """Returns list of all canonical hotspots for maps and UI pickers."""
    return [
        {
            "id": k,
            "name": v["canonical_name"],
            "latitude": v["latitude"],
            "longitude": v["longitude"]
        }
        for k, v in BENGALURU_HOTSPOTS.items()
    ]
