"""Landmark cache: load the OSM points and find candidates by spoken type/name."""
import json
import math
import unicodedata

import numpy as np

from . import config

# Spoken words (English + French) -> our landmark types.
# Longest phrases are matched first, so "water tower" wins over "tower".
SYNONYMS = {
    "water_tower": ["water tower", "château d'eau", "chateau d'eau"],
    "keep": ["castle keep", "keep", "donjon", "tower of the castle", "big tower of the castle"],
    "castle_tower": ["castle tower", "corner tower", "tour du château"],
    "castle": ["castle", "château", "chateau", "fort", "fortress", "forteresse"],
    "church": ["church", "chapel", "cathedral", "steeple", "bell tower", "église", "eglise",
               "chapelle", "cathédrale", "clocher"],
    "mosque": ["mosque", "mosquée", "mosquee", "minaret"],
    "tower": ["tower", "mast", "antenna", "radio mast", "tour", "antenne", "pylône"],
    "bridge": ["bridge", "overpass", "pont"],
    "station": ["station", "metro", "métro", "rer", "train station", "gare", "subway"],
    "school": ["school", "école", "ecole", "lycée", "lycee", "collège", "college"],
    "townhall": ["town hall", "city hall", "mairie", "hôtel de ville", "hotel de ville"],
    "hospital": ["hospital", "hôpital", "hopital", "clinic", "clinique"],
    "monument": ["monument", "memorial", "statue", "mémorial"],
    "park": ["park", "garden", "parc", "jardin", "square"],
    "wood": ["tree line", "treeline", "wood", "woods", "forest", "woodline", "bois", "forêt",
             "foret", "lisière", "lisiere", "trees", "arbres"],
    "cemetery": ["cemetery", "graveyard", "cimetière", "cimetiere"],
    "lake": ["lake", "pond", "lac", "étang", "etang"],
    "stadium": ["stadium", "stade"],
    "railway": ["railway", "railroad", "rail line", "train tracks", "tracks", "railway line",
                "voie ferrée", "voie ferree", "rails", "chemin de fer"],
    "river": ["river", "canal", "stream", "rivière", "riviere", "fleuve"],
    "main_road": ["main road", "highway", "avenue", "boulevard", "big road", "route",
                  "périphérique", "nationale"],
}

# What a spoken type may match in the data (castle may mean the keep too).
MATCHES = {
    "castle": ["castle", "keep"],
    "keep": ["keep"],
    "castle_tower": ["castle_tower", "keep"],
    "tower": ["tower", "keep", "castle_tower", "water_tower"],
}

# How to say each type out loud.
SPOKEN = {
    "en": {"water_tower": "water tower", "keep": "castle keep", "castle_tower": "castle tower",
           "townhall": "town hall", "main_road": "main road", "wood": "tree line",
           "railway": "railway line", "lake": "lake or pond"},
    "fr": {"water_tower": "château d'eau", "keep": "donjon", "castle_tower": "tour du château",
           "castle": "château", "church": "église", "mosque": "mosquée", "tower": "tour",
           "bridge": "pont", "station": "station", "school": "école", "townhall": "mairie",
           "hospital": "hôpital", "monument": "monument", "park": "parc", "wood": "lisière de bois",
           "cemetery": "cimetière", "lake": "lac ou étang", "stadium": "stade",
           "railway": "voie ferrée", "river": "rivière", "main_road": "grande route"},
}

# Types that only make sense for yes/no "can you see" questions.
QUESTION_TYPES = ["railway", "station", "bridge", "church", "lake", "cemetery", "stadium",
                  "hospital", "townhall", "school", "main_road", "wood", "castle", "water_tower"]


def _fold(s):
    """Lower case, no accents: 'Église' -> 'eglise'."""
    s = unicodedata.normalize("NFKD", (s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def normalise_type(word):
    """Map any spoken landmark word to one of our types (or None)."""
    if not word:
        return None
    w = _fold(word).replace("_", " ")
    if word in SYNONYMS:
        return word
    best, best_len = None, 0
    for t, words in SYNONYMS.items():
        for s in words:
            fs = _fold(s)
            if (w == fs or f" {fs} " in f" {w} ") and len(fs) > best_len:
                best, best_len = t, len(fs)
    return best


def spoken(t, lang="en"):
    return SPOKEN.get(lang, {}).get(t) or SPOKEN["en"].get(t) or t.replace("_", " ")


class LandmarkDB:
    """All landmark points, in lat/lon and in local metres (x east, y north)."""

    def __init__(self, path=config.LANDMARKS_FILE):
        data = json.loads(path.read_text(encoding="utf-8"))
        self.feats = []
        for f in data["features"]:
            lon, lat = f["geometry"]["coordinates"]
            p = f["properties"]
            self.feats.append({"id": p["id"], "type": p["type"], "name": p.get("name"),
                               "lat": lat, "lon": lon})
        s, w, n, e = config.BBOX
        self.lat0, self.lon0 = (s + n) / 2, (w + e) / 2
        self.kx = 111320 * math.cos(math.radians(self.lat0))   # metres per degree lon
        self.ky = 110540                                          # metres per degree lat
        self.lat = np.array([f["lat"] for f in self.feats])
        self.lon = np.array([f["lon"] for f in self.feats])
        self.x, self.y = self.to_xy(self.lat, self.lon)
        self.types = np.array([f["type"] for f in self.feats])
        self.names = [_fold(f["name"]) for f in self.feats]

    # --- coordinates -------------------------------------------------------
    def to_xy(self, lat, lon):
        return (np.asarray(lon) - self.lon0) * self.kx, (np.asarray(lat) - self.lat0) * self.ky

    def to_latlon(self, x, y):
        return self.lat0 + np.asarray(y) / self.ky, self.lon0 + np.asarray(x) / self.kx

    # --- lookup ------------------------------------------------------------
    def candidates(self, ltype, name=None, limit=250):
        """Indices of features that could be the landmark the speaker means."""
        if ltype is None:
            return np.array([], dtype=int)
        allowed = MATCHES.get(ltype, [ltype])
        idx = np.where(np.isin(self.types, allowed))[0]
        if name:
            # If a name was said and something matches it, keep only those.
            words = [w for w in _fold(name).replace("-", " ").split() if len(w) > 2
                     and w not in ("the", "church", "eglise", "saint", "sainte", "notre")]
            if words:
                named = [i for i in idx if self.names[i] and all(w in self.names[i] for w in words)]
                if named:
                    idx = np.array(named)
        if len(idx) > limit:  # long lines/edges: thin them out evenly
            idx = idx[np.linspace(0, len(idx) - 1, limit).astype(int)]
        return idx

    def feature(self, i):
        return self.feats[int(i)]


_db = None


def get_db():
    global _db
    if _db is None:
        _db = LandmarkDB()
    return _db
