# Near — find the wounded when GPS is jammed

Team **Fricassé** (Taher Ayadi, Aziz Maatoug) · European Defense Tech Hackathon Paris, 20–22 Nov 2026
Challenge **01 · Voice-to-Map: Real-Time Positional Tracking** (sponsor: Lysk, mentors Henry Heinemann and Florent Ogès)

This file is the project brief. Read it fully before writing code.

---

## 1. Context

### The hackathon
- Venue: Metafore Vincennes-Foch, 39 Avenue Foch, Vincennes. The Château de Vincennes is a 3-minute walk away, so it's our demo ground.
- Pre-selection happens **Saturday evening and Sunday morning**. Only selected teams pitch on Sunday. We need a working demo by Saturday evening.
- Deck (PDF/PPTX) due **Sunday 12:00**. Pitch is **3 minutes** plus 1–2 questions, with a recorded demo video linked in the deck.
- The jury (Ukrainian and European military, industry, VCs, tech) scores 0–10 on each of: relevant problem, feasibility, originality, mass-manufacturability, business opportunity, market size, pitch/MVP.

### The official challenge (01)
> Teams give location updates by voice, but manual map updates are slow and error-prone. Build a web app that turns spoken updates into automatic live map updates.

Suggested stack from the sponsor: OpenStreetMap for geocoding, a speech-to-text API, Mistral for intent extraction.

### What other teams already build (do not compete on these)
About 11 teams took challenge 01. What they already cover:
- **LowKey** (working app): push-to-talk → speech-to-text → Mistral → offline OpenStreetMap geocoding → live markers, paths, timestamps, history replay. English and French, relative phrases ("south of the church").
- **Ground Truth, ELARIS**: trust scores for noisy or contradictory reports, ageing out stale positions, fully offline.
- **hasky labs**: voice → navigation directions.

They all assume **the speaker knows where they are**. That's the gap we fill.

---

## 2. The idea in one paragraph

Under GPS jamming, soldiers often don't know their exact position, but they can still say what they see. A buddy or medic speaks one report: the casualty's state, plus the landmarks around them with clock directions ("water tower at my 11 o'clock, church at 2 o'clock, sun at 1 o'clock"). Near works out **where they are** from those landmarks. If the position is still uncertain, it **asks the one spoken question that narrows it down the most**. It **reads the result back**, and puts the casualty on the coordinator's map with a MIST card, a tourniquet countdown and a place in the evacuation order. No GPS, no screen needed for the person in the field, and no model training.

The method is the "problème de Pothenot": in French surveying, finding your own position from the angles between known points (resection).

**Pitch line:** "Other teams map what you say. We find you when you don't know where you are, by asking the right question."

---

## 3. Scope and rules

**In scope:** locating yourself, your own unit and casualties. Casualty reporting and evacuation priority.

**Hard limits:**
- Medical output is **decision support** for trained medics: organising information, timers, priority ordering. It doesn't diagnose or prescribe. Thresholds stay configurable and get validated with a mentor.

**Not doing:**
- Don't rebuild what LowKey has as a selling point. Basic speech-to-text → pin is plumbing, not the pitch.

---

## 4. User flows

### Field user (medic or buddy): voice only
1. Holds push-to-talk (or presses a big button) and speaks a report. For example:
   > "One casualty, blast, left leg bleeding, tourniquet on at 14:32, conscious and breathing. We're in a tree line. I see the castle keep at my 11 o'clock, a church at 2 o'clock, sun at my 1 o'clock."
2. Hears a read-back:
   > "Copy: one urgent casualty, tourniquet 14:32. Position within about 300 metres. Question: is the church to the left or the right of the keep?"
3. Answers by voice. Each answer shrinks the uncertainty. After 1–3 exchanges, hears:
   > "Position confirmed within 60 metres. Evacuation priority 1."

### Coordinator (at the casualty collection point): map screen
- Live map with each casualty as a pin coloured by priority, plus the uncertainty shown as an ellipse or blobs (several blobs while ambiguous).
- Each pin has a MIST card and a running tourniquet timer.
- Side list: evacuation order (priority, then tourniquet time), with distance from the collection point.

---

## 5. Architecture

```
[Field page (browser, phone)]           [Coordinator page (browser, laptop)]
  push-to-talk, TTS playback               Leaflet map, casualty list
          |  audio / text                          ^  websocket updates
          v                                        |
                  [Backend (Python, FastAPI)]
   speech-to-text -> Mistral extraction -> localisation engine
   -> question selector -> read-back text -> casualty store -> websocket broadcast
                          |
                 [Local OSM landmark cache (GeoJSON)]
```

Suggested stack, so swap anything that slows us down:
- **Backend:** Python 3.11, FastAPI, uvicorn, numpy. Optionally scipy, plus `astral` or `pysolar` for the sun position.
- **Frontend:** plain HTML + JS (or Vite + vanilla TS), Leaflet, browser `speechSynthesis` for spoken output.
- **Speech-to-text:** whatever works first. Mistral Voxtral API, OpenAI Whisper API, or the browser Web Speech API in Chrome. Keep it behind one function `transcribe(audio) -> text`.
- **LLM:** Mistral API with JSON output (sponsor-suggested). Keep it behind `extract(text, context) -> dict`.
- **Realtime:** FastAPI WebSocket broadcasting state to all coordinator pages.
- **Map tiles:** standard OpenStreetMap tiles for the demo. Landmark data is cached locally.

Taher codes Python only at a basic level, so keep code readable, with small modules, short comments and a `README` with one-command run instructions. Aziz owns the geometry.

---

## 6. Components in detail

### 6.1 Landmark cache (OpenStreetMap)
- Pull once with the Overpass API for a bounding box around the venue (start with lat 48.835–48.860, lon 2.415–2.455, and widen if needed). Save as `data/landmarks.geojson`.
- Map spoken landmark types to OSM tags:

| Spoken | OSM tags |
|---|---|
| church, chapel | `amenity=place_of_worship`, `building=church/chapel` |
| castle, keep, tower of the castle | `historic=castle`, `historic=fort` |
| water tower | `man_made=water_tower` |
| tower, mast, antenna | `man_made=tower`, `man_made=mast` |
| bridge | `bridge=yes` (way centroid) |
| station, metro, RER | `railway=station`, `public_transport=station` |
| school, town hall, hospital | `amenity=school/townhall/hospital` |
| park, wood, tree line edge | `leisure=park`, `landuse=forest`, `natural=wood` (use edge points) |
| railway, river, main road | `railway=rail`, `waterway=river`, `highway=primary` (used for yes/no questions) |

- Keep the `name` tag for named matches ("Notre-Dame church"). Store each feature as `{id, type, name, lat, lon}`, with line features sampled into points.

### 6.2 Extraction (Mistral, JSON output)
Input: transcript, plus context (the time now, the last question asked, the current hypotheses summary). Output schema:

```json
{
  "callsign": "string|null",
  "casualties": [{
    "count": 1,
    "mechanism": "blast|gunshot|fall|vehicle|other|null",
    "injuries": ["left leg bleeding"],
    "signs": {"conscious": true, "breathing": true, "massive_bleeding": true},
    "treatments": [{"type": "tourniquet", "location": "left thigh", "time": "14:32"}],
    "priority_hint": "urgent|priority|routine|null"
  }],
  "observations": [{
    "landmark_type": "castle",
    "landmark_name": "string|null",
    "direction": {"clock": 11} ,
    "relative": "left|right|behind|ahead|null",
    "distance_m": null,
    "visible": true
  }],
  "sun": {"clock": 1},
  "answer_to_question": {"question_id": "q3", "value": "left"}
}
```
Rules for the prompt: never invent landmarks, keep the speaker's words in the `injuries` strings, return `null` when not said, and accept English and French.

### 6.3 Localisation engine (core, Aziz)
Use a **likelihood grid**, not a closed-form resection. It handles noise, missing data and ambiguous matches.

- Grid over the search area, 20–40 m cells. Heading `θ` unknown: sample every 5° (72 values), unless the sun fixes it (6.4).
- Convert each observation to a relative bearing `β_i`: clock `k` → `k·30°` (12 = straight ahead). "right" = 90°, "behind" = 180°, "left" = 270°. Noise: σ ≈ 15° for clock directions, 35° for left/right/behind.
- For grid point `p` and heading `θ`:
  `L(p,θ) = Π_i max_{c ∈ candidates(type_i, name_i)} N( wrap(bearing(p→c) − θ − β_i) ; σ_i ) · D_i`
  where `D_i` is a distance term if a distance was said (log-normal, σ ≈ 50%), else 1.
  The `max` over candidates does the landmark matching: wrong candidates simply don't fit.
- "Can't see X" / "no X nearby" adds a penalty near features of type X within a visibility radius (start at 300 m in town, configurable).
- Posterior over `p` = sum over `θ`. Report:
  - the top mode(s): cluster cells with the most probability, up to 3 blobs;
  - a 1-σ / 2-σ ellipse for the main mode (weighted covariance);
  - a confidence radius in metres for the read-back.
- If GPS is available and plausible, fuse it as one more likelihood term.
- Performance target: under 300 ms per update on a laptop (numpy vectorised).

### 6.4 Sun as compass
- Compute the sun azimuth and elevation from the timestamp and the rough area (centre of the search box) with `astral`/`pysolar` or the NOAA formula.
- "Sun at my k o'clock" → `θ = sun_azimuth − k·30°`, σ ≈ 15°. That collapses the heading dimension, so two landmarks become enough.
- If the sun is below the horizon or the speaker says it's overcast, ignore it.

### 6.5 Question selector: "ask the one question that helps most"
- Generate candidate questions from the current top hypotheses and nearby features:
  - "Is the {A} to the left or the right of the {B}?"
  - "Can you see a {railway / river / station / bridge}?"
  - "Is the {A} closer than 200 metres, 200 to 500, or further?"
  - "Where is the sun: give me a clock direction."
- For each question, predict the answer at every grid cell (with the right noise), then compute the **expected entropy of the posterior after the answer**. Ask the question with the largest expected reduction.
- Stop asking when the 2-σ radius drops under a target (default 75 m) or after 3 questions.
- Phrase questions for speech: short, one item at a time.

### 6.6 Read-back (spoken)
A template built from the state, spoken with `speechSynthesis` on the field page and also shown as text:
> "Copy: {n} {priority} casualty, tourniquet {time}. Position within {r} metres. {next question or 'Position confirmed.'}"

### 6.7 Casualty card and evacuation list
- **MIST card:** Mechanism, Injuries, Signs, Treatment (with times).
- **Priority** (rule-based, configurable, validated with a mentor): urgent if massive bleeding, tourniquet applied, unconscious, or breathing problems; otherwise priority/routine from `priority_hint`.
- **Tourniquet timer:** elapsed since the stated time. Colour change at configurable warnings (placeholder 60 / 90 / 120 min, to confirm with a mentor). Show it on the pin and in the list.
- **Evacuation order:** priority first, then longest tourniquet time, then distance from the collection point.

### 6.8 Friendlies as landmarks (stretch)
A unit or medic with a confirmed position becomes a landmark type `friendly:<callsign>` (for example "the medic's orange panel"). Observations of friendlies feed the same likelihood. Friendlies only, never other people.

### 6.9 Small packet (stretch)
Serialise a confirmed report to a compact message (target under 120 bytes: callsign, priority, lat/lon rounded to about 10 m, radius, tourniquet time) and show the byte count on screen. This is the pitch point that it fits through a jammed or low-bandwidth link.

---

## 7. Milestones (Saturday)

| By | Milestone | Done when |
|---|---|---|
| 12:00 | **M1: pipeline** | Speak a report → transcript → JSON → casualty pin with MIST card on the coordinator map (GPS or a fixed point for now). Two browsers in sync over WebSocket. |
| 15:00 | **M2: find me** | Landmark cache loaded. The localisation grid returns blobs plus an ellipse from 2–3 spoken landmarks. Shown on the map. |
| 17:00 | **M3: ask back** | Sun compass, question selector and spoken read-back working end to end. Ellipse shrinks after answers. |
| 18:30 | **M4: demo-ready** | Tourniquet timers, evacuation list, tested outside by the Château with GPS off. **Record the demo video.** |
| Stretch | M5 | Friendlies as landmarks, compact packet with byte counter. |

If time runs short, cut M5, then the sun compass. Never cut the ask-back loop: it's the originality.

---

## 8. Demo script (for the video and the jury)

1. On the coordinator laptop in the room: an empty map of Vincennes.
2. Outside by the Château de Vincennes, phone with GPS off, Aziz plays the casualty.
3. Taher speaks: "One casualty, tourniquet left leg at {time}. I see the castle keep at my 11 o'clock, a church at 2 o'clock, sun at my 1 o'clock."
4. Map: a big ellipse, sometimes two blobs. The phone asks, out loud: "Is the church left or right of the keep?"
5. Taher answers. The ellipse shrinks onto the right street. Read-back: "Position within 60 metres, priority 1."
6. A second, less urgent casualty comes in. The evacuation list reorders live, and the tourniquet timer keeps running.

---

## 9. Pitch outline (3 minutes, matches the judging criteria)

1. **Problem (30 s):** jamming kills GPS; drones make evacuation slow; medics lose time reporting where casualties are.
2. **What we built (40 s):** voice report → position from what you see → the map asks the best question → evacuation order.
3. **Demo (60 s):** the video above.
4. **Why it works / feasibility (20 s):** no special hardware, no model training, runs on phones soldiers already carry.
5. **Originality (10 s):** nobody else locates speakers who don't know where they are.
6. **Business and market (15 s):** military medicine and command posts; civilian version for emergency services (lost callers who can't give an address), mountain rescue, disaster response.
7. **Team and ask (5 s):** who we are, who should talk to us.

---

## 10. Repo layout (suggested)

```
near/
  CLAUDE.md
  README.md                  # one-command run, env vars, demo steps
  .env.example               # MISTRAL_API_KEY=..., STT_PROVIDER=...
  backend/
    main.py                  # FastAPI app, routes, websocket
    stt.py                   # transcribe(audio) -> text
    extract.py               # Mistral prompt + JSON validation
    landmarks.py             # load cache, candidate lookup by type/name
    localise.py              # likelihood grid, modes, ellipse
    sun.py                   # sun azimuth
    questions.py             # candidate questions + expected entropy
    casualty.py              # MIST card, priority, tourniquet timers
    state.py                 # in-memory store of reports/casualties
  scripts/
    fetch_osm.py             # Overpass -> data/landmarks.geojson
  data/
    landmarks.geojson
  frontend/
    field.html  field.js     # push-to-talk, TTS
    map.html    map.js       # Leaflet coordinator view
  tests/
    test_localise.py         # synthetic scenes: known position -> recovered within X m
```

Write a small synthetic test early: place a fake observer, generate noisy clock directions to real landmarks, and check that `localise.py` recovers the position. That's how we trust the demo.
