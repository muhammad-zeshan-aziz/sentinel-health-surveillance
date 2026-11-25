"""
Canonical District Crosswalk and HDX P-Code Resolver for Khyber Pakhtunkhwa (KP).
Maps every raw bulletin label, typo, subdivision, and reference hospital location
to its canonical HDX ADM2 P-Code (PK501 - PK535).
"""

from typing import Dict, Any, List, Optional
import re

# Ground-truth specifications for all 35 KP districts
# Population source: Pakistan Bureau of Statistics (PBS) 2023 Census Table 1
# Geographic coordinates & Area source: HDX OCHA Pakistan pak_admin2.geojson
CANONICAL_KP_DISTRICTS: Dict[str, Dict[str, Any]] = {
    "PK501": {
        "pcode": "PK501",
        "name": "Abbottabad",
        "division": "Hazara Division",
        "population_2023": 1419072,
        "population_male": 712218,
        "population_female": 706750,
        "center_lat": 34.094580,
        "center_lon": 73.291141,
        "area_sqkm": 1639.516516,
        "aliases": ["abbottabad", "abbottaba", "havelia", "havelian"]
    },
    "PK502": {
        "pcode": "PK502",
        "name": "Bajaur",
        "division": "Malakand Division",
        "population_2023": 1287960,
        "population_male": 650798,
        "population_female": 637147,
        "center_lat": 34.745785,
        "center_lon": 71.485718,
        "area_sqkm": 1366.310356,
        "aliases": ["bajaur", "bajur", "bajore"]
    },
    "PK503": {
        "pcode": "PK503",
        "name": "Bannu",
        "division": "Bannu Division",
        "population_2023": 1357890,
        "population_male": 706094,
        "population_female": 651777,
        "center_lat": 32.985017,
        "center_lon": 70.655320,
        "area_sqkm": 2027.750394,
        "aliases": ["bannu", "sd bannu", "subdivision bannu", "sd-bannu"]
    },
    "PK504": {
        "pcode": "PK504",
        "name": "Batagram",
        "division": "Hazara Division",
        "population_2023": 554133,
        "population_male": 281298,
        "population_female": 272825,
        "center_lat": 34.761819,
        "center_lon": 73.137432,
        "area_sqkm": 1485.179213,
        "aliases": ["batagram", "battagram", "batgram"]
    },
    "PK505": {
        "pcode": "PK505",
        "name": "Buner",
        "division": "Malakand Division",
        "population_2023": 1016869,
        "population_male": 508172,
        "population_female": 508669,
        "center_lat": 34.430747,
        "center_lon": 72.556257,
        "area_sqkm": 1774.047506,
        "aliases": ["buner", "bunair", "daggar"]
    },
    "PK506": {
        "pcode": "PK506",
        "name": "Charsadda",
        "division": "Peshawar Division",
        "population_2023": 1835504,
        "population_male": 950872,
        "population_female": 884613,
        "center_lat": 34.247859,
        "center_lon": 71.699396,
        "area_sqkm": 999.135692,
        "aliases": ["charsadda", "charsada", "shabqadar", "tangi"]
    },
    "PK507": {
        "pcode": "PK507",
        "name": "Chitral Lower",
        "division": "Malakand Division",
        "population_2023": 320407,
        "population_male": 163584,
        "population_female": 156823,
        "center_lat": 35.847399,
        "center_lon": 71.826438,
        "area_sqkm": 6077.269813,
        "aliases": ["chitral lower", "lower chitral", "chitral (lower)"]
    },
    "PK508": {
        "pcode": "PK508",
        "name": "Chitral Upper",
        "division": "Malakand Division",
        "population_2023": 195528,
        "population_male": 100495,
        "population_female": 95033,
        "center_lat": 36.328033,
        "center_lon": 72.268856,
        "area_sqkm": 8615.417080,
        "aliases": ["chitral upper", "upper chitral", "chitral (upper)"]
    },
    "PK509": {
        "pcode": "PK509",
        "name": "D. I. Khan",
        "division": "Dera Ismail Khan Division",
        "population_2023": 1829811,
        "population_male": 959405,
        "population_female": 870255,
        "center_lat": 31.849972,
        "center_lon": 70.625037,
        "area_sqkm": 9028.552371,
        "aliases": [
            "d. i. khan", "d.i. khan", "d.i khan", "di khan", "di khan",
            "dera ismail khan", "sd di khan", "subdivision di khan", "sd-di-khan"
        ]
    },
    "PK510": {
        "pcode": "PK510",
        "name": "Hangu",
        "division": "Kohat Division",
        "population_2023": 528902,
        "population_male": 260293,
        "population_female": 268601,
        "center_lat": 33.412165,
        "center_lon": 70.804159,
        "area_sqkm": 1372.016174,
        "aliases": ["hangu", "hangue", "tall"]
    },
    "PK511": {
        "pcode": "PK511",
        "name": "Haripur",
        "division": "Hazara Division",
        "population_2023": 1174783,
        "population_male": 591540,
        "population_female": 583198,
        "center_lat": 34.047845,
        "center_lon": 72.875637,
        "area_sqkm": 1953.899675,
        "aliases": ["haripur", "khanpur", "ghazi"]
    },
    "PK512": {
        "pcode": "PK512",
        "name": "Karak",
        "division": "Kohat Division",
        "population_2023": 815878,
        "population_male": 421292,
        "population_female": 394575,
        "center_lat": 33.101259,
        "center_lon": 71.110554,
        "area_sqkm": 2648.386217,
        "aliases": ["karak", "takht-e-nasrati", "banda daud shah"]
    },
    "PK513": {
        "pcode": "PK513",
        "name": "Khyber",
        "division": "Peshawar Division",
        "population_2023": 1146267,
        "population_male": 598268,
        "population_female": 547989,
        "center_lat": 34.039993,
        "center_lon": 71.205406,
        "area_sqkm": 2747.426820,
        "aliases": ["khyber", "landikotal", "jamrud", "bara"]
    },
    "PK514": {
        "pcode": "PK514",
        "name": "Kohat",
        "division": "Kohat Division",
        "population_2023": 1234661,
        "population_male": 629566,
        "population_female": 605066,
        "center_lat": 33.412245,
        "center_lon": 71.488227,
        "area_sqkm": 3438.498608,
        "aliases": ["kohat", "sd kohat", "subdivision kohat", "sd-kohat"]
    },
    "PK515": {
        "pcode": "PK515",
        "name": "Kohistan Lower",
        "division": "Hazara Division",
        "population_2023": 340017,
        "population_male": 173655,
        "population_female": 166351,
        "center_lat": 35.149689,
        "center_lon": 72.922961,
        "area_sqkm": 823.483913,
        "aliases": ["kohistan lower", "lower kohistan", "kohistan (lower)"]
    },
    "PK516": {
        "pcode": "PK516",
        "name": "Kohistan Upper",
        "division": "Hazara Division",
        "population_2023": 422947,
        "population_male": 216184,
        "population_female": 206759,
        "center_lat": 35.422813,
        "center_lon": 73.221321,
        "area_sqkm": 5484.727165,
        "aliases": ["kohistan upper", "upper kohistan", "kohistan (upper)", "dassu"]
    },
    "PK517": {
        "pcode": "PK517",
        "name": "Kolai Palas Kohistan",
        "division": "Hazara Division",
        "population_2023": 280162,
        "population_male": 142588,
        "population_female": 137572,
        "center_lat": 35.067438,
        "center_lon": 73.175075,
        "area_sqkm": 1229.715546,
        "aliases": [
            "kolai palas kohistan", "kolai palas", "kolai-palas",
            "kolai palas kohistan distric", "kolai-palas kohistan"
        ]
    },
    "PK518": {
        "pcode": "PK518",
        "name": "Kurram",
        "division": "Kohat Division",
        "population_2023": 785434,
        "population_male": 406914,
        "population_female": 378505,
        "center_lat": 33.689642,
        "center_lon": 70.384367,
        "area_sqkm": 3398.380652,
        "aliases": [
            "kurram", "lower & central kurram", "l & c kurram", "upper kurram",
            "central kurram", "lower kurram", "parachinar", "sadda"
        ]
    },
    "PK519": {
        "pcode": "PK519",
        "name": "Lakki Marwat",
        "division": "Bannu Division",
        "population_2023": 1040856,
        "population_male": 527121,
        "population_female": 513722,
        "center_lat": 32.570343,
        "center_lon": 70.879718,
        "area_sqkm": 3339.824225,
        "aliases": ["lakki marwat", "sd lakki", "lakki", "serai naurang"]
    },
    "PK520": {
        "pcode": "PK520",
        "name": "Lower Dir",
        "division": "Malakand Division",
        "population_2023": 1650183,
        "population_male": 813551,
        "population_female": 836605,
        "center_lat": 34.840940,
        "center_lon": 71.820222,
        "area_sqkm": 1604.744025,
        "aliases": ["lower dir", "dir lower", "timergara", "dir (lower)"]
    },
    "PK521": {
        "pcode": "PK521",
        "name": "Malakand",
        "division": "Malakand Division",
        "population_2023": 826250,
        "population_male": 422792,
        "population_female": 403446,
        "center_lat": 34.516635,
        "center_lon": 71.823629,
        "area_sqkm": 905.695489,
        "aliases": ["malakand", "malakand protected area", "batkhela", "dargai"]
    },
    "PK522": {
        "pcode": "PK522",
        "name": "Mansehra",
        "division": "Hazara Division",
        "population_2023": 1797177,
        "population_male": 912164,
        "population_female": 884906,
        "center_lat": 34.695734,
        "center_lon": 73.511943,
        "area_sqkm": 4032.013352,
        "aliases": ["mansehra", "balakot", "oghi", "baffa pakhal"]
    },
    "PK523": {
        "pcode": "PK523",
        "name": "Mardan",
        "division": "Mardan Division",
        "population_2023": 2744898,
        "population_male": 1408776,
        "population_female": 1336069,
        "center_lat": 34.303371,
        "center_lon": 72.080786,
        "area_sqkm": 1636.408516,
        "aliases": ["mardan", "takht bhai", "katlang", "rustam"]
    },
    "PK524": {
        "pcode": "PK524",
        "name": "Mohmand",
        "division": "Peshawar Division",
        "population_2023": 553933,
        "population_male": 281384,
        "population_female": 272543,
        "center_lat": 34.446085,
        "center_lon": 71.366493,
        "area_sqkm": 2261.952779,
        "aliases": ["mohmand", "ghallanai", "halimzai", "ekka ghund"]
    },
    "PK525": {
        "pcode": "PK525",
        "name": "North Waziristan",
        "division": "Bannu Division",
        "population_2023": 693332,
        "population_male": 354636,
        "population_female": 338681,
        "center_lat": 32.957051,
        "center_lon": 69.942817,
        "area_sqkm": 4929.680076,
        "aliases": ["north waziristan", "nwa", "miran shah", "mir ali"]
    },
    "PK526": {
        "pcode": "PK526",
        "name": "Nowshera",
        "division": "Peshawar Division",
        "population_2023": 1740705,
        "population_male": 886471,
        "population_female": 854184,
        "center_lat": 33.917092,
        "center_lon": 72.002809,
        "area_sqkm": 1725.712094,
        "aliases": ["nowshera", "risalpur", "akora khattak", "pabbi", "jehangira"]
    },
    "PK527": {
        "pcode": "PK527",
        "name": "Orakzai",
        "division": "Kohat Division",
        "population_2023": 387561,
        "population_male": 204870,
        "population_female": 182684,
        "center_lat": 33.694903,
        "center_lon": 70.878200,
        "area_sqkm": 1369.891427,
        "aliases": ["orakzai", "kalaya", "ghiljo"]
    },
    "PK528": {
        "pcode": "PK528",
        "name": "Peshawar",
        "division": "Peshawar Division",
        "population_2023": 4758762,
        "population_male": 2425808,
        "population_female": 2332767,
        "center_lat": 33.941726,
        "center_lon": 71.600011,
        "area_sqkm": 1539.071266,
        "aliases": ["peshawar", "sd peshawar", "subdivision peshawar", "sd-peshawar", "hayatabad"]
    },
    "PK529": {
        "pcode": "PK529",
        "name": "Shangla",
        "division": "Malakand Division",
        "population_2023": 891252,
        "population_male": 459965,
        "population_female": 431281,
        "center_lat": 34.846656,
        "center_lon": 72.789854,
        "area_sqkm": 1384.205886,
        "aliases": ["shangla", "alpuri", "besham", "chakesar"]
    },
    "PK530": {
        "pcode": "PK530",
        "name": "South Waziristan",
        "division": "Dera Ismail Khan Division",
        "population_2023": 888675,
        "population_male": 459531,
        "population_female": 429130,
        "center_lat": 32.291481,
        "center_lon": 69.677525,
        "area_sqkm": 6224.407365,
        "aliases": [
            "south waziristan", "south waziristan (undivided)", "swa",
            "south waziristan lower", "south waziristan (lower)", "sw (l)",
            "south waziristan upper", "south waziristan (upper)", "sw(u)", "swu",
            "wana", "spinkai raghzai", "sararogha"
        ]
    },
    "PK531": {
        "pcode": "PK531",
        "name": "Swabi",
        "division": "Mardan Division",
        "population_2023": 1894600,
        "population_male": 959045,
        "population_female": 935520,
        "center_lat": 34.141187,
        "center_lon": 72.476762,
        "area_sqkm": 1480.462809,
        "aliases": ["swabi", "topi", "lahor", "rajar", "chota lahor"]
    },
    "PK532": {
        "pcode": "PK532",
        "name": "Swat",
        "division": "Malakand Division",
        "population_2023": 2687384,
        "population_male": 1375358,
        "population_female": 1311939,
        "center_lat": 35.233076,
        "center_lon": 72.511850,
        "area_sqkm": 5348.329376,
        "aliases": ["swat", "mingora", "saidu sharif", "kabal", "barikot", "matta", "khwazakhela"]
    },
    "PK533": {
        "pcode": "PK533",
        "name": "Tank",
        "division": "Dera Ismail Khan Division",
        "population_2023": 470293,
        "population_male": 241589,
        "population_female": 228703,
        "center_lat": 32.318684,
        "center_lon": 70.373760,
        "area_sqkm": 2818.778582,
        "aliases": ["tank", "sd tank", "subdivision tank", "sd-tank"]
    },
    "PK534": {
        "pcode": "PK534",
        "name": "Tor Ghar",
        "division": "Hazara Division",
        "population_2023": 200445,
        "population_male": 102160,
        "population_female": 98281,
        "center_lat": 34.558593,
        "center_lon": 72.875953,
        "area_sqkm": 454.381199,
        "aliases": ["tor ghar", "torghar", "kala dhaka", "judba"]
    },
    "PK535": {
        "pcode": "PK535",
        "name": "Upper Dir",
        "division": "Malakand Division",
        "population_2023": 1083566,
        "population_male": 537290,
        "population_female": 546264,
        "center_lat": 35.310534,
        "center_lon": 72.048181,
        "area_sqkm": 3731.821610,
        "aliases": ["upper dir", "dir upper", "dir (upper)", "dir town", "kalkot", "wari"]
    }
}

# Construct reverse lookup dictionary
_ALIAS_LOOKUP: Dict[str, str] = {}
for pcode, info in CANONICAL_KP_DISTRICTS.items():
    _ALIAS_LOOKUP[info["name"].lower().strip()] = pcode
    _ALIAS_LOOKUP[pcode.lower().strip()] = pcode
    for alias in info["aliases"]:
        _ALIAS_LOOKUP[alias.lower().strip()] = pcode


def normalize_string(val: Any) -> str:
    """Normalize input string for matching."""
    if val is None:
        return ""
    s = str(val).lower().strip()
    # Remove redundant punctuation but preserve periods in initials like 'd.i.'
    s = re.sub(r"\s+", " ", s)
    return s


def resolve_district_pcode(raw_name: Any) -> Optional[str]:
    """
    Resolves any arbitrary district name, typo, acronym, or sub-division
    to its canonical HDX P-Code (e.g. 'PK501').
    Returns None if unmapped.
    """
    if raw_name is None:
        return None
    
    clean = normalize_string(raw_name)
    if not clean:
        return None
    
    # 1. Direct match
    if clean in _ALIAS_LOOKUP:
        return _ALIAS_LOOKUP[clean]
    
    # 2. Stripped common suffixes
    sub_clean = re.sub(r"\b(district|agency|protected area|distric)\b", "", clean).strip()
    if sub_clean in _ALIAS_LOOKUP:
        return _ALIAS_LOOKUP[sub_clean]
    
    # 3. Sub-division prefix check
    if clean.startswith("sd ") or clean.startswith("sd-"):
        core = clean[3:].strip()
        if core in _ALIAS_LOOKUP:
            return _ALIAS_LOOKUP[core]
            
    # 4. Inverted words (e.g. "dir lower" <-> "lower dir")
    parts = clean.split()
    if len(parts) == 2:
        inverted = f"{parts[1]} {parts[0]}"
        if inverted in _ALIAS_LOOKUP:
            return _ALIAS_LOOKUP[inverted]
            
    return None


def get_district_info(pcode: str) -> Optional[Dict[str, Any]]:
    """Returns canonical metadata for a given P-Code."""
    return CANONICAL_KP_DISTRICTS.get(pcode.upper())


def get_all_districts() -> List[Dict[str, Any]]:
    """Returns metadata for all 35 canonical KP districts."""
    return list(CANONICAL_KP_DISTRICTS.values())
