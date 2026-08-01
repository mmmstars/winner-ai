import re


ISRAELI_TEAM_NAMES = {
    "maccabi haifa": "מכבי חיפה",
    "maccabi tel aviv": "מכבי תל אביב",
    "hapoel beer sheva": "הפועל באר שבע",
    "hapoel be'er sheva": "הפועל באר שבע",
    "beitar jerusalem": "בית״ר ירושלים",
    "beitar jerusalem fc": "בית״ר ירושלים",
    "hapoel tel aviv": "הפועל תל אביב",
    "hapoel haifa": "הפועל חיפה",
    "maccabi netanya": "מכבי נתניה",
    "bnei sakhnin": "בני סכנין",
    "bnei sachnin": "בני סכנין",
    "maccabi bnei raina": "מכבי בני ריינה",
    "maccabi bnei reineh": "מכבי בני ריינה",
    "ironi tiberias": "עירוני טבריה",
    "hapoel petah tikva": "הפועל פתח תקווה",
    "maccabi petah tikva": "מכבי פתח תקווה",
    "hapoel jerusalem": "הפועל ירושלים",
    "ms ashdod": "מ.ס. אשדוד",
    "ashdod": "מ.ס. אשדוד",
    "ironi kiryat shmona": "עירוני קריית שמונה",
    "hapoel hadera": "הפועל חדרה",
    "hapoel raanana": "הפועל רעננה",
    "hapoel acre": "הפועל עכו",
    "hapoel kfar saba": "הפועל כפר סבא",
    "hapoel rishon lezion": "הפועל ראשון לציון",
    "hapoel ramat gan": "הפועל רמת גן",
    "bnei yehuda": "בני יהודה",
    "maccabi herzliya": "מכבי הרצליה",
    "hapoel umm al-fahm": "הפועל אום אל-פחם",
    "hapoel nof hagalil": "הפועל נוף הגליל",
    "kafr qasim": "מ.ס. כפר קאסם",
    "hapoel akko": "הפועל עכו",
    "hapoel afula": "הפועל עפולה",
    "hapoel ra'anana": "הפועל רעננה",
    "hapoel tel-aviv": "הפועל תל אביב",
    "hapoel ironi kiryat shmona": "עירוני קריית שמונה",
    "hapoel kfar shalem": "הפועל כפר שלם",
    "hapoel kiryat yam": "הפועל קריית ים",
    "ironi modi'in": "עירוני מודיעין",
    "maccabi akhi nazareth": "מכבי אחי נצרת",
    "maccabi kabilio jaffa": "מכבי קביליו יפו",
    "maccabi kiryat gat": "מכבי קריית גת",
}


def canonical_team_name(name: str) -> str:
    value = re.sub(r"\s+", " ", name.strip()).casefold()
    value = re.sub(r"\s+(fc|sc)$", "", value).strip()
    return value


def hebrew_team_name(name: str) -> str:
    return ISRAELI_TEAM_NAMES.get(canonical_team_name(name), name.strip())


def team_aliases(*names: str) -> list[str]:
    values = []
    for name in names:
        if name and name.strip() not in values:
            values.append(name.strip())
    return values
