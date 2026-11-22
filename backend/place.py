"""Is the speaker even inside the area this system has maps for?

The landmarks, buildings, woods and 3D model cover only the box in config.BBOX (Vincennes,
Saint-Mandé, Montreuil, Fontenay...). If someone says "we're in Limoges", placing them in
Vincennes would be wrong: we flag it, stop guessing a position, and say so.
"""
import re
import unicodedata

# Places inside the mapped box (and parts of them people may name).
COVERED = {"vincennes", "saint mande", "st mande", "montreuil", "fontenay sous bois", "fontenay", "paris",
           "paris 12", "paris 20", "12e", "20e", "nogent", "nogent sur marne", "charenton", "charenton le pont",
           "joinville", "joinville le pont", "saint maurice", "bagnolet", "romainville", "bois de vincennes",
           "chateau de vincennes", "porte de vincennes", "porte doree", "picpus", "nation", "daumesnil",
           "minimes", "lac des minimes", "lac daumesnil", "parc floral", "the woods", "the bois"}
# Well-known towns outside it (speech-to-text often writes them in lower case).
KNOWN_OUTSIDE = {"limoges", "lyon", "marseille", "toulouse", "bordeaux", "lille", "nantes", "strasbourg",
                 "rennes", "reims", "le havre", "toulon", "grenoble", "dijon", "angers", "nimes", "brest",
                 "tours", "amiens", "metz", "besancon", "perpignan", "orleans", "rouen", "caen", "nancy",
                 "clermont ferrand", "montpellier", "nice", "poitiers", "versailles", "saint denis", "creteil",
                 "nanterre", "boulogne", "argenteuil", "kyiv", "kiev", "kharkiv", "odessa", "lviv", "dnipro",
                 "zaporizhzhia", "kherson", "bakhmut", "berlin", "london", "brussels", "bruxelles", "madrid"}
NOT_PLACES = {"the", "a", "an", "my", "our", "his", "her", "position", "contact", "danger", "pain", "shock",
              "trouble", "building", "street", "open", "woods", "forest", "park", "field", "room", "car",
              "vehicle", "house", "ditch", "hole", "cover", "front", "back", "middle", "town", "city",
              "village", "area", "place", "zone", "bad", "good", "position", "sight", "view", "line"}


def _fold(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9 ]+", " ", s).strip()


def said_place(text):
    """('limoges', covered?) if the speaker names the town they are in, else None."""
    pat = (r"\b(?:i am|i'm|im|we are|we're|were|i'm currently|we're currently|located|currently|"
           r"je suis|nous sommes|on est|je me trouve|nous nous trouvons)\s+(?:currently\s+|now\s+|still\s+)?"
           r"(?:in|at|near|outside|à|a|en|pr[eè]s de|dans)\s+([A-Za-zÀ-ÿ'\- ]{3,40})")
    for m in re.finditer(pat, text or "", re.I):
        raw = re.split(r"[,.;!?]| and | et | with | avec | near | next ", m.group(1))[0].strip()
        words = raw.split()
        for n in (3, 2, 1):                       # "clermont ferrand", "saint mande", "limoges"
            cand = _fold(" ".join(words[:n]))
            if not cand or cand.split()[0] in NOT_PLACES:
                continue
            if cand in COVERED or any(cand.startswith(c) for c in COVERED if len(c) > 5):
                return cand, True
            if cand in KNOWN_OUTSIDE:
                return cand, False
        # An unknown proper noun right after "in" ("I'm in Brive"): outside, unless lower case.
        if words and words[0][:1].isupper() and _fold(words[0]) not in NOT_PLACES:
            return _fold(words[0]), False
    return None
