"""All tunable numbers in one place. Change these, not the code."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
FRONTEND_DIR = ROOT / "frontend"
LANDMARKS_FILE = DATA_DIR / "landmarks.geojson"


def _load_dotenv():
    """Tiny .env reader so we don't need python-dotenv."""
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()

# --- API keys / providers -------------------------------------------------
MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY", "")
# Cloud: https://api.mistral.ai/v1 (needs a key).
# Local with Ollama: http://127.0.0.1:11434/v1 and MISTRAL_MODEL=mistral:7b (no key).
MISTRAL_BASE_URL = os.environ.get("MISTRAL_BASE_URL", "https://api.mistral.ai/v1")
_LOCAL_LLM = "api.mistral.ai" not in MISTRAL_BASE_URL
MISTRAL_MODEL = os.environ.get("MISTRAL_MODEL", "mistral:7b" if _LOCAL_LLM else "mistral-small-latest")
LLM_ENABLED = bool(MISTRAL_API_KEY) or _LOCAL_LLM
LLM_TIMEOUT_S = float(os.environ.get("LLM_TIMEOUT_S", "20"))
STT_PROVIDER = os.environ.get("STT_PROVIDER", "browser")  # browser | mistral | openai
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# --- Search area (south, west, north, east) -------------------------------
BBOX = (48.830, 2.405, 48.865, 2.465)
CELL_M = 25            # grid cell size in metres
HEADING_STEP = 5       # heading resolution in degrees (72 values)

# --- Observation noise ----------------------------------------------------
SIGMA_CLOCK = 15.0     # degrees, for "at my 2 o'clock"
SIGMA_RELATIVE = 35.0  # degrees, for "on my left / behind me"
SIGMA_SUN = 15.0       # degrees, for "sun at my 1 o'clock"
SIGMA_DIST_LOG = 0.5   # log-normal sigma for spoken distances (~50 %)
SIGMA_COMPASS = 25.0   # degrees, phone compass held still (Elias & Maas 2020: median ~24 deg)
SIGMA_CARDINAL = 30.0  # degrees, "north of the church" (spoken cardinal directions)
WALK_M_PER_S = 1.4     # last GPS fix before jamming: how far they can have walked since
OUTLIER_FLOOR = 0.01   # each observation can be wrong: floor of its likelihood

# How far away a landmark can plausibly be seen (metres).
VIS_RADIUS_DEFAULT = 300
VIS_RADIUS = {
    "castle": 1500, "keep": 1500, "castle_tower": 900, "tower": 1200,
    "water_tower": 1500, "church": 700, "mosque": 500, "station": 300,
    "hospital": 500, "townhall": 500, "stadium": 600, "lake": 400,
    "wood": 500, "park": 300, "railway": 250, "river": 300, "main_road": 150,
}
HERE_RADIUS = 80       # "we're in a tree line / next to the railway"

# --- Woods (backend/forest.py; placeholders until one walk in the Bois calibrates them)
# Line of sight through trees survives with exp(-metres of wood / lambda). No published
# visibility distance for deciduous woods: ~60 m with leaves, 100-150 m without (Nov).
CANOPY_ENABLED = True          # off = the old distance-only visibility (evaluation)
VIEWSHED_ENABLED = True        # true 3D line of sight (backend/viewshed.py), else canopy model
SIGMA_TILT = 2.0               # deg: phone aimed at a landmark's top (pitch + aiming)
SIGMA_SWEEP = 2.5              # deg: angle between two landmarks swept with the gyroscope
SIGMA_TOP_M = 1.5              # m: landmark top and own eye altitude (LiDAR)
INDOOR_SIGHT = 0.3             # seeing a landmark from inside a building (a window), vs outside
CANOPY_LAMBDA_M = 100.0
CANOPY_TALL_FACTOR = 1.5       # keep, towers, spires show a little over the canopy
TALL_TYPES = {"castle", "keep", "castle_tower", "tower", "water_tower", "church", "mosque"}
NO_CANOPY_TYPES = {"wood", "park"}   # you see the trees themselves
GROUND_ERROR = 0.1             # chance a spoken ground answer is wrong (mixed cells, judgement)
# Extra attenuation of road noise through woodland (passive_forest_acoustics notes):
# nothing for the first 20 m, then 0.05 dB/m leaf-off (0.07 leaf-on), capped.
FOREST_NOISE_FREE_M = 20.0
FOREST_NOISE_DB_PER_M = 0.05
FOREST_NOISE_CAP_DB = 15.0

# --- Acoustic evidence (placeholders until calibrated on field recordings) -
# How far away a heard source can be (heard bearings ignore the trees in the way).
HEARD_BEARING_RADIUS = {"main_road": 600, "railway": 800, "church": 1500}
SIGMA_HEARD = 40.0      # degrees, "I hear a train at my 3 o'clock" (ears are worse than eyes)
ACOUSTIC_WEIGHT = 0.7   # temper machine-heard evidence: scores are uncalibrated
TWIN_DIR = DATA_DIR / "twin"
# Second sound classifier (AST). Off -> YAMNet alone. Downloaded once from Hugging Face.
AST_ENABLED = os.environ.get("AST_ENABLED", "1") != "0"
AST_DEVICE = os.environ.get("AST_DEVICE", "auto")    # auto | cpu
AST_WEIGHT = 0.6        # share of AST in the YAMNet + AST average (AST is the more accurate one)
# YAMNet raw score -> evidence strength q (0 below LO, 1 above HI).
ACOUSTIC_SCORE_LO = {"rail": 0.10, "traffic": 0.15, "bells": 0.10, "machinery": 0.15, "nature": 0.15}
ACOUSTIC_SCORE_HI = {"rail": 0.50, "traffic": 0.60, "bells": 0.45, "machinery": 0.55, "nature": 0.55}
# P(heard | next to the source), P(heard | far from it):
#   "audio" = in a 4 s clip, "voice" = the operator, over the last few minutes.
# A quiet 4 s clip near a railway is normal (trains are rare), so "not heard" is weak evidence.
HEAR_MODEL = {
    "rail":      {"audio": (0.35, 0.03), "voice": (0.75, 0.08)},
    "traffic":   {"audio": (0.85, 0.30), "voice": (0.90, 0.25)},
    "bells":     {"audio": (0.10, 0.01), "voice": (0.20, 0.02)},
    "machinery": {"audio": (0.30, 0.04), "voice": (0.50, 0.05)},
    "nature":    {"audio": (0.60, 0.25), "voice": (0.70, 0.25)},
}
# How far each source carries (metres). Roads by class: 1 motorway/trunk ... 4 tertiary.
HEAR_RADIUS = {"rail": 300, "tram": 120, "road1": 400, "road2": 220, "road3": 120, "road4": 60,
               "bells": 700, "machinery": 200}

# --- Spatial acoustics: what kind of space is the phone in? ----------------
SETTINGS = ["indoor_small", "indoor_large", "outdoor_enclosed", "outdoor_open"]
LARGE_BUILDING_M2 = 1200   # footprint big enough to hold a hall (station, church, gym)
ENCLOSED_FACADE_M = 15     # outdoors, closer than this to a facade = street / courtyard
OPEN_FACADE_M = 40         # further than this = open ground
SPEED_OF_SOUND = 343.0
PROBE = {"f0": 800.0, "f1": 12000.0, "dur": 0.5, "sr": 48000}   # active chirp (field.js uses the same)

# --- Question selector ----------------------------------------------------
TARGET_RADIUS_M = 75   # stop asking when the 2-sigma radius is below this
MAX_QUESTIONS = 6       # location questions per report (stress can lower it, questions.py)
MIN_GAIN_BITS = 0.05

# --- Casualty rules (placeholders, validate with a mentor) ----------------
TOURNIQUET_WARN_MIN = [60, 90, 120]
# Heart rate bands (bpm) for the condition estimate, to check with the medical mentor:
# < slow, normal up to fast, fast up to shock (ATLS class II-III range), severe above.
HR_BANDS = {"slow": 50, "fast": 100, "shock": 120, "severe": 140}
HR_FRESH_MIN = 15             # a pulse reading older than this is shown, not used
# Casualty collection point (CCP). Coordinator can move it on the map.
CCP = {"lat": 48.8472, "lon": 2.4365, "name": "CCP"}
