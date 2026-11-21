# Pothenot

Find the wounded when GPS is jammed. A medic describes what they see ("castle keep at my 11 o'clock, church at 2 o'clock, sun at 1 o'clock"), and Pothenot works out where they are. If the position is still vague, it asks the one question that narrows it down most, reads the answer back out loud, and puts the casualty on the coordinator's map with a MIST card, a tourniquet timer and a place in the evacuation order.

Team Fricassé, EDTH Paris 2026, challenge 01.

## Run it

```
pip install -r requirements.txt
python run.py
```

The sound analysis also needs `ffmpeg` on the PATH (it decodes the phone's audio).

- **Coordinator dashboard (everything at once):** http://localhost:8000/map
  - **Header:** the selected casualty's priority, position, live tourniquet timer, mobility, people to send, and the pending question.
  - **Tiles, all visible together:** Evacuation order · Casualty (MIST, updates, plan, questions) · Map · 3D casualty (estimated posture) · Location (guessed vs real scenes, candidate areas) · Sound (spectrogram, sound classes) · Impact graph · Send & bring (people, kit).
  - **⤢** on any tile (or double-click its title) opens it large with all its details: echo plot, kind of space, clue checks, 3D notes and posture clues. **Esc** closes it.
  - **Live updates:** every new report or clip for the same casualty re-estimates everything. The Casualty tile lists what changed, and the tiles flash.
  - **Deep links:** `/map#body`, `/map#graph`, `/map#response`, `/map#location`, `/map#sound`, `/map#map` open that tile large, which is handy for the demo video.
- **Step-by-step demo view:** http://localhost:8000/pipeline. The same report, laid out as steps 1–6 for the jury.
- **Field page** (same laptop): http://localhost:8000/field. Hold Space or the big button to talk.

### On a phone

A phone's microphone only works over HTTPS, so:

```
python run.py --https
```

It prints two addresses (`https://<laptop-ip>:8443/...`). The phone has to be on the same Wi-Fi as the laptop, or the laptop on the phone's hotspot. Open `/field` in **Chrome** and accept the certificate warning once (Advanced → Proceed). Use Chrome on the laptop for `/map` too.

If the Wi-Fi blocks devices from seeing each other, use a tunnel instead: `cloudflared tunnel --url http://localhost:8000` gives a public HTTPS link.

### Keys (optional)

Extraction always runs a rule-based parser (English and French, instant). An LLM is optional and only fills what the rules missed (unusual phrasing, slang), never overrides them, and is skipped for short answers like "yes".

- **Local Mistral (default in `.env.example`, offline):** `ollama pull mistral:7b`. Fits fully on an 8 GB GPU with the 4k context we use. About 6 s per full report, and about 25 s for the first one while the model loads (the server warms it up at start).
- **Mistral cloud:** set `MISTRAL_BASE_URL=https://api.mistral.ai/v1` and `MISTRAL_API_KEY` in `.env`.

If the LLM is down or slow, the server falls back to the rules alone. Speech recognition is done by Chrome itself.

## Listening to the space (acoustic spatial sensing)

The microphone tells us what kind of space the phone is in, not just what was said:

| Clue | Where it comes from | What it gives |
|---|---|---|
| Reverberation from the voice | every push-to-talk report (raw audio captured next to Chrome's speech recognition) | how fast sound dies away after each word: ~0.1 s outdoors, 0.3-0.6 s small room, 1-5 s hall/church |
| Chirp echo ranging | **Listen 4 s** button with "chirp" on: the phone plays a 0.5 s sweep and records | room impulse response: reverberation time, direct-to-reverberant ratio, and the delay of each echo, so the distance to the nearest facade or wall (d = 343 x delay / 2) |
| Sound scene and sources | YAMNet (local, 4 MB, 521 AudioSet classes) on the Listen clip, speech windows removed | "inside small room / large hall / outside urban / rural", plus trains, road traffic, bells, machinery, birds. Explosion/gunfire-like sounds only raise an alert |

These become probabilities over four settings: **indoors small room, indoors large hall, outdoors between buildings, outdoors open ground**. They are then matched against a 5 m raster of the real building footprints and heights (IGN BD TOPO, 26,941 buildings in the area, 83 % with a measured height). For example, "street with a facade 6 m away" keeps cells that have a facade about 6 m from open ground, and "large hall" keeps cells inside big buildings. Sounds are matched against railways (tunnels excluded), roads by size, churches and industrial areas. The question selector can also ask "Are you inside a building, in a street between buildings, or in the open?", "Is the room small or large?" and "Have you heard a train in the last few minutes?".

What it can't do, said plainly:
- One microphone gives echo **distance, never direction**. A reflection around 0.8-1.8 m is usually the floor, ground or ceiling and is not counted as a wall.
- In a reverberant room the first wall echo hides in the tail, so we show it as low confidence and don't use it. There, reverberation gives "indoors" and a rough size range instead.
- Model scores and thresholds are not calibrated yet. They are starting points to tune on real recordings (`backend/config.py`).
- Sound evidence is deliberately weak (weight 0.7, outlier floor). It narrows the type of place but can't override landmarks. If recording or analysis fails, voice-only positioning works as before.
- Playing a chirp makes noise. Turn it off where that matters; reverberation from the voice still works passively.

Two sound classifiers run side by side: **YAMNet** (Google, 4 MB, CPU) and **AST**, the Audio Spectrogram Transformer (MIT, 87 M parameters, GPU when available). Their scores are averaged 0.4 / 0.6. On 85 real labelled recordings (ESC-50, `python -m scripts.eval_audio`), at a 0.15 threshold:

| Model | Recall | Precision | F1 | Top group right | False location alarms |
|---|---|---|---|---|---|
| YAMNet | 92 % | 73 % | 0.81 | 46/50 | 4/35 |
| AST | 80 % | 98 % | 0.88 | 45/50 | 0/35 |
| **YAMNet + AST** | 92 % | 87 % | **0.89** | **48/50** | 2/35 |

Reverberation estimated blind from real sounds (dog barks, knocks, horns, bells) played through rooms of known RT60: 0.6 s → 0.59 s, 1.2 s → 1.12 s, 2.4 s → 2.14 s. Small rooms are less precise (0.3 s → 0.38 s), and dry open air reads ~0.3 s because the sources have their own decay. The YAMNet/AST scene labels ("inside / outside") barely react to reverberation in that test, so they get a lower weight than the measured RT60.

In the simulated ask-back loop (`python -m scripts.eval_loop 100 --compare`), the median error drops from 102 m (landmarks only) to 83 m with the space/sound questions, and to 62 m with a Listen clip. That Listen clip is drawn from our own sound model, so it is an upper bound until real recordings are tested.

Tested on synthetic rooms (`tests/test_spatial.py`): reverberation within 20 % from the chirp and 25 % from voice-like sound, street facades at 4 / 8 / 15 m recovered within 0.3 m, and the four settings told apart.

Data for this (already downloaded): `python scripts/fetch_twin.py` (OSM roads, railways, noise sources) and `python scripts/fetch_ign.py` (IGN building heights). The YAMNet model is in `data/models/`.

## Pipeline view (for the demo)

http://localhost:8000/pipeline shows one report as three steps, live:

Steps 1–3 locate the speaker; step 4 is the casualty twin (below).

1. **Listen:** the clip's mel spectrogram (chirp boxed, speech hatched), one lane per sound class over time, the chirp echogram (level against distance, with the ground band and the facade echo marked), and the kind-of-space probabilities.
2. **Reconstruct:** the guessed 3D scene, with every element tagged by where it came from (said, heard, audio, measured, inferred or assumed).
3. **Match:** the candidate areas with their probability and fit, a mini map, the real 3D surroundings, and a ✓ / ~ / ✗ for every clue.

**Simulate report** places a soldier near the Château and adds a Listen clip. A simulated clip is synthesized from the simulated sounds (labelled SIMULATED) but goes through the same spectrogram and echo code as a real recording.

## Impact graph, kit and team (steps 5 and 6)

Below the four steps, `/pipeline` turns the same report into a response plan (`backend/response.py`, `frontend/impact.js`):

- **Impact graph**, left to right: what was **reported** → **body region** → structures **possibly impacted** (dashed, to check: e.g. thigh bleeding → femoral artery; blast → eardrums, blast lung, concussion, eye fragments, full body sweep) → **MARCH threat** (Massive bleeding, Airway, Respiration, Circulation, Hypothermia/Head) → **what to bring**. Hover a box to follow its chain.
- **Bring:** the kit in MARCH order with quantities, and who uses it (buddy or medic). Examples: tourniquets for limb bleeding, packing only for junctional wounds, chest seals for chest wounds, no splints for ribs, pelvic binder for blast with leg wounds. "Check" items from the mechanism (fall → spine, pelvis) only add kit for an urgent or unconscious casualty.
- **Send:** stretcher bearers (4; 2 for a carry under 100 m; +2 relief over 500 m), escorts for walking wounded, and 1 medic per 2 urgent casualties. Distance comes from the casualty to the collection point. It always aims for the smallest team that can carry.

**Mobility** (`backend/mobility.py`), one state per casualty: *can walk*, *needs help to walk*, *stretcher*, *trapped* or *unknown*.
- **Said first** (EN/FR): "he can walk", "il ne peut pas marcher", "limping", "pinned under rubble". The latest mention wins, and "ne marche pas" is never read as "marche".
- **Otherwise inferred**, and marked as inferred:
  - unconscious, massive bleeding, breathing problem, tourniquet on a leg, or thigh/pelvis wound → stretcher;
  - lower leg or foot wound only → needs help;
  - "conscious" said and no leg wound → can walk;
  - otherwise unknown, and a stretcher is planned.
- **Conflict:** if "can walk" is said but the report has a tourniquet on a leg, it shows what was said, flags the conflict, and plans the stretcher anyway.
- **Effects:** the state sizes the team (escort, helper, bearers, +2 for extraction) and adds extrication tools for trapped casualties. It's spoken in the read-back ("Stretcher needed."), added to the radio packet (`ML`, `MT`...), and shown on the 3D body and the coordinator map. Footsteps heard by the microphone are listed as a cue only, because they may be the buddy's.

Decision support only: it organises what was reported into a checklist. All rules and numbers are placeholders to validate with a medical mentor (`ANATOMY`, `KIT`, `TEAM` at the top of `backend/response.py`).

## Casualty twin (3D body from the voice report)

Step 4 of `/pipeline` shows a 3D body posed and marked from the same push-to-talk audio. It's the idea of our earlier image-to-3D project, with voice as the input instead of a photo:

- **Posture is estimated, never set by hand** (`estimate_posture` in `backend/body.py`), per casualty, and redone after every report or clip. Each clue adds points to some postures, and the scores become probabilities shown as small bars under the body:
  - said ("lying on his back", "face down", "sitting", "recovery position", EN/FR) weighs most. If a later report changes the state ("now unconscious", "can walk now"), the old said posture counts less, because the casualty may have been moved;
  - unconscious and breathing → recovery position; unconscious and not breathing → on the back;
  - breathing problem or chest wound, conscious → sitting up;
  - leg tourniquet, thigh/pelvis wound, massive bleeding, abdominal wound → on the back; wound on the back → face down or on the side;
  - can walk / needs help → standing; snoring or gasping heard → on the back (weak); footsteps → standing (very weak, may be the buddy).
  - The weights are planning defaults to validate with a mentor.
- **Follow-ups update the same casualty.** "He is now unconscious" or "he stopped breathing" (no "casualty" word needed) changes the signs. The posture, mobility, impact graph, kit and team are then rebuilt. The Casualty tile lists each update ("conscious: yes → no", "posture: on the back → recovery position (57%)", "send: 6 → 7 people"), and the tiles flash when new data arrives.
- **Injuries** go onto the body segment named ("left leg bleeding" → left thigh and lower leg, "shrapnel right forearm", "burn on his back" → back surface only). Colour shows the kind of wound. A paler colour means the side wasn't said, so both sides are marked. Massive bleeding pulses.
- **Tourniquet:** an orange band high on the stated limb, with its running time.
- **Signs:** conscious / breathing / massive bleeding badges, exactly as said.
- **Casualty sounds** the microphone heard (groaning, gasping, wheezing, coughing; YAMNet) are listed as cues to confirm. They never change the priority.

Decision support only: it draws what was reported and does not assess the casualty.

**One-time setup:** the body is the SMPL-X model, whose licence forbids redistribution, so it isn't in the repo. Build it from a local copy:

```
python -m scripts.build_body                      # default: "3D POSE EST/expose/data/models/smplx/SMPLX_NEUTRAL.npz"
python -m scripts.build_body path/to/SMPLX_NEUTRAL.npz
```

This writes `data/body/body.npz` (git-ignored): five postures posed with linear blend skinning, and every vertex labelled with a body segment using the model's own skinning weights. Code: `backend/body.py`, `frontend/body3d.js` (Three.js).

## Scene reconstruction (approximate 3D)

Select a report on the coordinator map and a panel shows two small 3D views side by side (drag to turn them, double-click to reset):

- **Guessed from the report**, using only what was said and heard, never the map. It shows the kind of space (small room, hall, street between buildings, open ground), the nearest facade from the chirp echo, the room size from reverberation, landmarks at their clock directions (a wedge of ±15°, at a typical distance when none was said), the sun, and trees, railway or road from "we're in a tree line" or from sounds. It's a rough sketch of the kind of place. Anything only assumed (building heights, which way the street runs) is drawn dashed and listed as assumed.
- **Real surroundings** at each likely area (tabs A/B/C, with the localiser's probability). These are the actual IGN buildings with their heights and the OSM landmarks, turned so 12 o'clock points the way the speaker most likely faces. Under the view, every clue gets ✓ / ~ / ✗ with the numbers, for example "said 7 o'clock, here 6.5 o'clock (12° off), 300 m". "Fit" is the weighted average of those scores (landmarks ×2, sounds ×½).

Code: `backend/scene.py` (served at `/api/report/{id}/scene`, rebuilt only when the report changes) and `frontend/scene3d.js` (plain canvas, no extra library).

## Rehearse without going outside

On the map, click **Rehearsal: simulate report**, then click anywhere. A fake soldier standing there describes the landmarks they would see, with realistic noise. A cyan **+** marks the true spot and the side panel shows the real error. Click **Auto-answer** to have the fake soldier answer each question truthfully and watch the ellipse shrink. **Simulate listen** adds a fake Listen clip drawn from the building map at the true spot. It tests the matching logic, not the microphone.

## How it works

| File | What it does |
|---|---|
| `scripts/fetch_osm.py` | Downloads landmarks around Vincennes from OpenStreetMap into `data/landmarks.geojson` (already done; rerun only to change the area) |
| `backend/extract.py` | Transcript → JSON (casualties, landmarks with clock directions, sun, answer). Mistral if a key is set, rules otherwise |
| `backend/localise.py` | The core. A 25 m grid × 72 headings. Each observation is a likelihood; multiply, sum over headings, find blobs and ellipses |
| `backend/sun.py` | Sun azimuth from time and place. "Sun at my 1 o'clock" fixes which way the speaker faces |
| `backend/acoustic.py` | Audio clip → YAMNet sound events, scene scores, quality checks, spectral features (local) |
| `backend/spatial.py` | Reverberation from voice, chirp impulse response (echo distances, RT60, DRR), the four-setting verdict |
| `backend/soundscape.py` | Per grid cell: what kind of space it is (from building footprints) and what you would hear there |
| `backend/questions.py` | Generates candidate questions and picks the one with the largest expected entropy drop |
| `backend/casualty.py` | MIST card, priority rule, tourniquet time |
| `backend/readback.py` | Spoken read-back text and the compact radio packet |
| `backend/state.py` | One utterance → whole pipeline; in-memory store |
| `backend/main.py` | FastAPI routes and the websocket that pushes state to every map |
| `frontend/field.*` | Push-to-talk page, speaks the read-back |
| `frontend/map.*` | Leaflet map, heat map of the position, evacuation list |

All tunable numbers (noise, visibility ranges, tourniquet warnings, CCP position, target radius) are in `backend/config.py`.

## Tests and numbers

```
python -m pytest -q              # synthetic scenes, question loop, parser
python -m scripts.eval_loop 30   # 30 random fake soldiers, full ask-back loop
```

Current `eval_loop` result (3 landmarks + sun, up to 3 questions, truthful answers, distances misjudged by ~30 %): median error about 75 m (80th percentile 140 m). The spoken radius goes from about 630 m to 240 m after the questions, and the truth falls inside it in 93 % of trials.

## Medical scope

The casualty side is decision support for trained medics: it organises what was said, keeps timers and suggests an order. It doesn't diagnose. The priority rule and the tourniquet thresholds (60/90/120 min) are placeholders to be checked with a mentor.

## Data and models

- Landmarks, roads, railways: © OpenStreetMap contributors (ODbL)
- Building footprints and heights: IGN BD TOPO (Licence Ouverte / Etalab 2.0)
- YAMNet sound classifier: Google, Apache 2.0 (`data/models/yamnet.tflite`)
- AST (Audio Spectrogram Transformer): MIT, `MIT/ast-finetuned-audioset-10-10-0.4593` on Hugging Face, BSD-3-Clause. It downloads once into the Hugging Face cache; set `AST_ENABLED=0` to run YAMNet alone
- Evaluation clips (`scripts/eval_audio.py`, not in the repo): ESC-50, Piczak 2015, CC BY-NC 3.0
