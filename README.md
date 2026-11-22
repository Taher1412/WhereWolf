# Near

Find the wounded when GPS is jammed. A medic describes what they see ("castle keep at my 11 o'clock, church at 2 o'clock, sun at 1 o'clock"), and Near works out where they are. If the position is still vague, it asks the one question that narrows it down most, reads the answer back out loud, and puts the casualty on the coordinator's map with a MIST card, a tourniquet timer and a place in the evacuation order.

Team Fricassé, EDTH Paris 2026, challenge 01.

## Run it

```
pip install -r requirements.txt
python run.py
```

The sound analysis also needs `ffmpeg` on the PATH (it decodes the phone's audio).

- **Coordinator dashboard (everything at once):** http://localhost:8000/map
  - **Header:** the selected casualty's priority, position, live tourniquet timer, mobility, people to send, and the pending question.
  - **Tiles, all visible together:** Evacuation order · Casualty (MIST, updates, plan, questions) · Map (with an **Audio match** layer) · 3D casualty (estimated posture) · Location (real buildings at each candidate area, with the measured echoes on top) · What the audio says (measured numbers, bits per cue; ⤢ for the spectrogram and echo plot) · Impact graph · Send & bring (people, kit).
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
| Chirp echo ranging | **automatic at the end of every push-to-talk** (field page, "chirp at the end"), or the **Listen 4 s** button: the phone plays a 0.5 s sweep and records | room impulse response: reverberation time, direct-to-reverberant ratio, and the delay of **every** echo, so the distance to every reflecting wall (d = 343 x delay / 2) |
| Background noise level | every push-to-talk report: **the operator's own voice is the loudness reference** (~76 dB(A) at the phone), so no calibration | the noise floor in dB(A), ±7 dB, e.g. "58 dB(A): residential street". Listen clips reuse the phone's offset found on the last voice clip |
| Sound scene and sources | YAMNet + AST (local) on the Listen clip, speech windows removed; on a voice report, **under the speech** (half weight, only what was heard counts) | "inside small room / large hall / outside urban / rural", plus trains, road traffic, bells, machinery, birds. Explosion/gunfire-like sounds only raise an alert |

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

### Matching the surroundings against the real places (`backend/surround.py`)

Every measurement is compared with what the phone **should** measure at every spot of the map (9 spots per 25 m cell, 245,520 in all), computed from real data and cached in `data/twin/surround_cache.npz` (rebuilt automatically in ~25 s when missing):

- **Echoes.** From each spot, 36 rays over a 1 m raster of the IGN footprints. A flat wall sends the chirp back from the foot of the perpendicular, which is where the distance along the rays has a local minimum. Those minima are the echo distances expected there. Two walls on opposite sides also give a wall-to-wall echo at their sum, which is the street width. Each measured echo is matched to the closest expected one (σ = 0.5 m + 5 %). A false-alarm floor covers cars, trees and people. A big wall within 15 m that sent nothing back costs a penalty.
- **Noise level.** A road-noise model: every OSM road / rail point is a source, louder for bigger roads (78 dB(A) at 10 m from a motorway down to 65 for a tertiary road), falling as a line source, −15 dB when a building is in between (checked on the raster). Indoors: −25 dB through the facade. The measured level is compared with it at ±7 dB.
- **Per cue, the bits it removed** from a flat prior are shown, plus the area that still holds 90 % of the probability with audio alone. The **Audio match** button on the map shows that audio-only map.

What it gives, measured honestly on simulated clips built from the real place (`tests/test_surround.py`, and the evaluation scripts):
- The measurements are accurate. Wall echoes come back within 0.3 m of the true walls, and the noise level is within ~3 dB of the model.
- Audio alone narrows the **kind** of spot, not the place. The true spot ranks in the top 6 % of the map (median), within the top 10 % two times out of three, and removes ~0.8 bits.
- With 3 landmarks + the sun, adding one voice clip with its end chirp raises "best guess within 75 m" from 12 % to 18 % and cuts the median error of the best guess from 1060 m to 810 m.
- One microphone hears distance, not direction. Echoes repeat all along a uniform street, so inside a known 300 m area audio alone is only ~1.5× better than chance. The landmarks and the question loop still do the main job.

## In the woods (Bois de Vincennes)

Under trees, far landmarks are hidden, the sun often is too, and there are no walls to echo. Research notes and the full report: `reports/Casualty localisation in forests.md`. What the app now does there (`backend/forest.py`, data from `python scripts/fetch_forest.py`, OSM, cached in `data/twin/forest_cache.npz`):

- **Forest map per 25 m cell:** share under trees / open / water, distance to the nearest paved and unpaved path, depth inside the wood, distance to water, open ground and fences.
- **Seeing through trees:** a landmark is seen with the chance exp(−metres of wood on the line of sight / 100 m) (leaf-off; ~60 m with leaves; ×1.5 for the keep, towers, spires). "I can't see the keep" under trees no longer means "far from the keep". Line-of-sight profiles: 36 directions per cell.
- **Ground clues, said or asked:** "under trees / in the open", "tarmac / dirt or gravel path / no path", "can you see water?". Spoken in the report ("we're in the woods on a dirt track", "sous les arbres, sur un chemin goudronné") or asked when the information gain says so.
- **Traffic by ear:** "Where do you hear road traffic from? Give a clock direction, or say none." Roads cross the Bois, and trees don't hide a sound.
- **Phone compass:** "🧭 My 12 o'clock" on the field page (phone flat, top edge where you face). Fixes the heading like the sun, at ±25° (phone compasses held still, Elias & Maas 2020).
- **Spoken dead reckoning:** "10 minutes north of the keep", "300 metres east of the church", "à 5 minutes au sud du château" (75 m per minute).
- **Last GPS fix before jamming** (opt-in, field page): the casualty is within walking distance of it (1.4 m/s since the fix).
- **Acoustics:** trees soak up road noise (nothing for the first 20 m of wood, then 0.05 dB/m, capped at 15 dB). Echoes no wall explains are expected among trunks, so wooded spots are no longer pushed out by the echo match. Forest reverberation looks like a hall to the room-tuned classifier, so its verdict counts less there.
- The "what landmarks can you see?" question is skipped once the speaker said they are under trees.

Measured (`python -m scripts.eval_forest 60`): 60 simulated casualties in wooded cells, one report then up to 3 questions. Same spots, headings and draws in every row:

| | median error | within 75 m | within 150 m |
|---|---|---|---|
| before | 1123 m | 3 % | 5 % |
| + canopy-aware visibility | 1155 m | 0 % | 3 % |
| + "in the woods, dirt track", ground and traffic questions | 473 m | 10 % | 23 % |
| + phone compass | 458 m | 12 % | 22 % |

Read it honestly: in the woods the speaker sees no landmark at all at 47 % of the spots, so this stays much worse than in the streets. The ground clues and the traffic direction more than halve the error. Canopy-aware visibility does not improve the numbers by itself; it removes wrong conclusions. The simulated speaker uses the same canopy and ground model as the localiser, so these numbers are optimistic until one walk in the Bois calibrates the 100 m visibility, the noise attenuation and the compass (field tests A–E in the report). The map stops at latitude 48.830, so the southern half of the Bois (Gravelle, racecourse) is outside it; widening `config.BBOX` means re-running the fetch scripts.

## 3D line of sight and aiming with the phone (geomatics)

**Who can see what.** `backend/viewshed.py` builds a 2 m 3D model from IGN LiDAR HD (`python scripts/fetch_lidar.py`: ground MNT + height of everything on it MNH, so buildings, trees, street trees and spires; 21 MB in `data/twin/lidar.npz`). For each of the 304 landmarks with a top (keep, towers, churches, schools, stations...) and each cell in range, it checks the sight line from eye height to the top: buildings and terrain block it, trees let some through (exp(−metres / 100 m)). Cached in `data/twin/viewshed_cache.npz` (~35 s once). Without the LiDAR file it falls back to building heights + OSM woods.

It replaces "close enough to see". In the streets the keep's top is in sight from only ~11 % of the spots within 1.5 km (the old rule assumed ~40 %), mostly within 200 m. The LiDAR also gives the real tops: the Église Saint-Louis bell tower is 33 m (the building table said 17 m), the keep 53 m.

**Aim & tap** (field page). Put the top edge of the phone on the top of each landmark you see, tap, then name them in the same order ("the keep, then the church"). Each tap records:
- the **tilt** = elevation angle of the top. With the LiDAR top altitude and each cell's ground altitude, that gives the distance (trigonometric levelling), ±2°;
- the **turn** between taps (gyroscope, no compass): the angle between two landmarks seen from the spot. That is the classical resection (Pothenot's problem itself), with no heading needed, ±2.5°.

Taps sent before any landmark is named wait for the next report. The read-back says "Used 2 aimed landmarks".

Measured (`python -m scripts.eval_geomatics 60 --seen`): 60 simulated casualties per area, at spots where at least one landmark top is truly in sight. The speaker sees and answers from the 3D model. Same spots and draws in every row.

| | streets: median error | within 50 m | woods: median error | within 50 m |
|---|---|---|---|---|
| before (distance + canopy) | 417 m | 7 % | 492 m | 5 % |
| + 3D line of sight | 190 m | 23 % | 427 m | 8 % |
| + Aim & tap (tilt, turn) | **75 m** | **45 %** | 469 m | 10 % |

Read it honestly:
- In the streets the speaker often sees **no landmark at all**. With the 3D model that is 57 % of random street spots, and 73 % in the woods. There only the questions and ground or traffic clues remain, and the median error stays around 850 m (streets) and 1.5 km (woods) (`python -m scripts.eval_geomatics 60`, without `--seen`). Our older city numbers assumed landmarks are visible whenever close, so they were too optimistic.
- In the woods the landmarks you can see are far and low on the horizon. A tilt of 1–2° error then means a large distance error, so aiming adds little there.
- The 3D model plays reality here and is also what the localiser uses, so these numbers are optimistic where the model is wrong: leaves in summer, trucks, scaffolding, and landmark points that OSM puts off the structure.
- Field check before relying on it: aim at the keep from 3–4 surveyed spots, and compare the tilt and turn with the model.

## Heart rate, better extraction, adaptive questions

**Heart rate from audio** (`backend/heart.py`). On the field page, **🫀 Pulse**: press the bottom of the phone (the microphone) firmly on the casualty's chest, left of the breastbone, and keep still for 10 s. The heart sounds ("lub-dub", 25–200 Hz) give the rate:
- envelope of the heart-sound band, autocorrelation, and a check of every multiple of each candidate period, so the "lub-dub" gap is not taken for a beat;
- tested on synthetic chest recordings: clean ones 96 % within 5 bpm; readings flagged reliable 92 % within 5 bpm; noisy recordings are marked "unclear: press firmly, repeat";
- rhythm (regular / irregular) is not reported: on test signals a 10 s recording could not tell them apart.

A voice recording does **not** carry a usable heart rate (voice-only estimates are research models with about 10 bpm error in the lab), so the dashboard shows a value only from a chest recording, with its age. Voice stress is shown next to it, never as a heart rate.

The dashboard's graph tile has a **heart panel** on the right:
- the heart beats at the measured rate (grey when nothing is measured, dimmed when the reading is older than 15 min);
- bpm and band: normal / fast > 100 / shock range > 120 / severe > 140 / slow < 50 (`config.HR_BANDS`, to check with the mentor);
- source and age, and a trend line with the 120 bpm line.

The rate feeds the condition: shock range adds a shock threat, and fast raises the casualty's distress. **Pulse (sim)** on simulated reports makes a synthetic chest recording at a rate that fits the casualty's state, measured by the same code.

**Better extraction** (rules, every report). Fixes from real phrasing:
- "ahead" is no longer a head wound, and "surface" no longer a face; "right side" / flank is a wound site;
- "kind of out of it", "dazed" = responds to voice;
- distances in words ("two hundred metres", "deux cents mètres");
- "behind a wall near a water tower" = close to the water tower, not behind it;
- "the tower" right after "a water tower" is the same tower;
- the ring road / périphérique / motorway heard ahead = traffic with a direction.

A local LLM (Ollama) is supported by `extract.py` (`MISTRAL_BASE_URL=http://127.0.0.1:11434/v1`, `MISTRAL_MODEL=...` in `.env`). On this laptop `qwen2.5:7b` runs half on the CPU (4 GB GPU): even a two-word reply takes ~24 s, so it is too slow for live use. A small model that fits the GPU (`ollama pull qwen2.5:3b`) would be the one to try.

**Adaptive questions**, rebuilt every turn from the current likely spots A / B / C and the real named features (3D line of sight):
- "Which of these can you see: the Sainte-Chapelle de Vincennes, a tower, or the Tour des Salves? Say all you see, or none." These are the features whose visibility differs most between the likely spots. "I see the chapel but not the tower" and French answers are understood.
- "Where is the Sainte-Chapelle de Vincennes from you? Give a clock direction, or say you can't see it." This is a named landmark that should be in sight from the leading spot.

The question selector compares them with the fixed questions on expected error removed, and asks the best. Measured on 40 simulated street casualties that see a landmark: median error 142 m -> 104 m, within 100 m 38 % -> 45 %, but within 250 m 62 % -> 57 % (40 cases: partly noise).

**Coverage.** Everything above works inside the mapped box (`config.BBOX`, Vincennes sector, including the northern half of the Bois). A place outside it is detected when named ("we're in Limoges") and no position is guessed. Locating people elsewhere needs that area's data (OSM, IGN buildings and LiDAR: the fetch scripts with a new BBOX).

## Casualty condition and time before it gets worse

`backend/condition.py`, shown at the top of the **Casualty** tile, in the header (**Worse in**), on every row of the evacuation list, and as a chip on the field phone. Decision support for trained medics: it organises what was said and heard, it does not diagnose.

- **MARCH state** per item, with what it rests on:
  - Massive bleeding: not controlled / controlled / tourniquet / control unknown.
  - Airway: at risk if unresponsive, gurgling, snoring or gasping; open if talking or vocalising.
  - Breathing.
  - Circulation: pale, cold, sweaty, thirsty, weak pulse = shock signs.
  - Head / hypothermia.
- **Responsiveness** (AVPU), from what is said ("confused", "only to pain", "unconscious"), from "the speaker is the casualty" ("I'm hit", "my leg"), or from vocalising. A scream counts as responsive, to confirm.
- **Distress** (pain / panic):
  - the casualty's own voice when they report themselves (`stress.py`);
  - screaming, crying or groaning heard on the clips;
  - the buddy's words ("screaming", "panicking", "in a lot of pain").
  Each source can only raise it.
- **Overall condition**: stable / serious / critical / very critical (0–100). Any airway or breathing threat, or a life threat whose window has been reached, is at least critical.
- **Threats with a time window** and a live countdown. The clock starts at the injury, which is said ("hit 6 minutes ago"), or before the tourniquet, or at the latest at the first report. Placeholder windows (textbook orders of magnitude, **to check with the medical mentor**):

| threat | window | counted from |
|---|---|---|
| massive bleeding not controlled | 3–10 min | injury |
| airway at risk | 3–5 min | now |
| breathing problem | 5–30 min | now |
| shock signs | 15–45 min | now |
| bleeding, control unknown | 10–30 min | injury |
| torso / junctional bleeding (no tourniquet possible) | 30–60 min | injury |
| head injury or blast with reduced consciousness | 30–120 min | injury |
| hypothermia (November, lying still) | 30–90 min | injury |
| tourniquet on (limb) | 120–360 min | tourniquet time |

  The read-back says the soonest one when it is within 15 min ("Warning, critical within the next 4 minutes: massive bleeding not controlled"). The evacuation order is now priority, then who gets worse first, then tourniquet time, then distance.
- **How it happened → where to look.** Blast → eardrums, eyes, blast lung, concussion, abdomen. Fall → neck / spine, pelvis, head. Vehicle → neck, ribs, pelvis. A penetrating wound → possible exit on the other side. These show as **"to check"** (dashed red) in the body parts graph, next to the red parts that were said.

**Health questions** (asked by the phone, in MARCH order, not counted in the location budget). Life threats come first: is the bleeding stopped, is the casualty awake and answering, are they breathing normally, and where the wound is when an injury has no body part. Then location and health questions take turns: how it happened, pale / cold / sweaty, how many minutes ago. When the speaker is the casualty the phone says "you" ("Has your bleeding stopped?").

**More questions, more than one place.** Up to 6 location questions per report (5 if the speaker sounds stressed, 4 if highly stressed), until the position is good or no question helps any more. Besides the connected areas, the localiser now lists up to **3 distinct likely spots** (A / B / C, peaks at least 300 m apart, each with its share). They are on the map, in the Location tile and in the read-back ("Also possible: area B, 900 metres west"), and the question goals use them ("tell area A from area B").

## Speaker stress and questions with a goal

**Stress from the voice** (`backend/stress.py`). Every push-to-talk clip is measured as soon as you release (`/api/voice_quick`, ~0.3 s), so the question asked right away already fits:
- pitch raised above the speaker's own floor, and pitch range (own numpy pitch tracker, ±2 Hz on test tones);
- brightness: energy at 1–5 kHz against 50 Hz–1 kHz, which rises with a strained voice;
- articulation rate, and choppy speech (short bursts between pauses);
- the words: "hurry", "he's dying", "please", "vite", repeats, exclamations;
- within one report, the pitch change since the first clip.

The result is low / elevated / high, with the cues behind it (hover the **Voice stress** box in the dashboard header; the field page shows a chip). These are rule-of-thumb reference values from the speech-stress literature, not a trained or validated model. Shouting over noise (Lombard effect) raises pitch and brightness too, so those cues count less when the background is loud. Stress only changes **how** we ask; it never touches medical priority.

**How the questions adapt.** Each question type has an effort: 1 = a glance and yes / no ("See a church?"), 2 = one clock direction or left / right, 2.5 = a distance, 3 = "describe what you see". Easy questions are favoured more as stress rises:

| speaker | hardest question allowed | questions | wording |
|---|---|---|---|
| low / unknown | describe everything (3) | 3 | normal |
| elevated | distances (2.5) | 3 | normal |
| high | one clock direction or left / right (2) | 3 | shortest ("Under trees? Yes or no.", "Sun at what o'clock?"), slower read-back, no extras in it |

**A goal for every question.** Questions are now chosen for the position error they remove (metres), blended with the uncertainty they remove (bits). Each one says what it is for, on the dashboard ("Asking:" line and the questions list) and under the question on the phone:
- "Goal: tell area A (45 %) from area B (30 %) · yes → A, no → B · error ~600 m → ~150 m"
- "Goal: fix which way you face, so the landmark directions line up"
- "Goal: narrow area A · error ~420 m → ~150 m"
- "Goal: where the wound is, for the medic"

Measured (`python -m scripts.eval_questions 40`), simulated casualties in the streets (3D line of sight), same spots and draws in every row:

| | random street spots: median error | spots that see a landmark: median error | within 250 m |
|---|---|---|---|
| bits only (before) | 735 m | 359 m | 42 % |
| metres only | 666 m | 344 m | 45 % |
| **blend (now)** | 669 m | **201 m** | **52 %** |
| blend, elevated stress | 666 m | 276 m | 50 % |
| blend, high stress (3 easy questions) | n/a | 617 m | 35 % |

Easier questions cost accuracy. Under high stress, the best tested setting keeps 3 quick questions (617 m); cutting to 2 gave 791 m. That trade (simpler and faster, against precision) is a choice to check with the mentors. The stress levels themselves still need checking on real recordings of calm and stressed speakers.
## Danger zones

The coordinator map shows the threats each unit heard or named, as coloured zones (legend bottom right, one checkbox per type).

- **Said by the soldier** (solid outline): "drone overhead", "sniper at my 2 o'clock", "taking fire from the north", "mortar rounds landing nearby", "mines on the track", in English or French. "No drones" and injury words ("gunshot to the chest", "blast") don't count. These sentences also no longer change the casualty's MIST mechanism.
- **Heard by the phone** (dashed outline): gunfire and explosions from YAMNet + AST (AudioSet classes), and drones from a dedicated drone detector, because AudioSet has no drone class.

One phone cannot tell where the shooter or the drone is. So each zone is centred on the **reporter's** estimated position, and its size is how far that threat is usually heard or seen from (drone 150 m, small arms 400 m, sniper 600 m, explosions 800 m, armour 500 m, mines 60 m: placeholders to check with a mentor), plus the reporter's own uncertainty.
- If a direction is given and the heading is known (sun, or a compass word), the zone becomes a 50° wedge.
- When reports from two or more units overlap, the overlap is drawn as a thick ring: the likely source area.
- Zones fade out (drone after 10 min, mines after 24 h).
- A unit whose own position is uncertain by more than 500 m gets a "?" label instead of an area.

Threats also appear as chips in the evacuation list. The read-back says "Danger logged: drone" and warns a unit when another unit reported a threat where it stands. The radio packet carries one letter per threat (`DGU` = gunfire + drone).

Measured on real recordings (`python -m scripts.eval_danger --fetch`, then `python -m scripts.eval_danger`):

| Test | Result |
|---|---|
| 88 real gunshot recordings | small-arms alert on 97 % (small arms or explosion: 100 %) |
| 150 drone clips (DADS) | drone alert on 72 % |
| 85 no-danger ESC-50 clips (incl. helicopter, airplane, engine, door knocks, hand saw) | false alarm on 2 % (wind read as an explosion; now flagged "doubtful: wind on the microphone") |

The drone detector may have been trained on the DADS clips used here, so 72 % is optimistic. Its model card claims 99.6 %, which we don't reproduce. The 0 drone false alarms on ESC-50 (helicopter and airplane included) is the more trustworthy number.

## Back to the CCP: guiding a casualty who can walk

Once a casualty who **can walk** is located within 200 m, Near guides them to the CCP by voice and their pin moves on the map. No GPS is used. The coordinator can also start it by hand ("Guide to CCP" in the header).

- **Route** (`backend/route.py`):
  - built on every walkable OSM way already cached (45,565 nodes);
  - each edge costs its length × (1 + risk), where risk adds weight(type) × confidence × freshness for every danger zone the edge is inside;
  - Dijkstra, ~30 ms per route;
  - the map shows the detour and what it avoids, e.g. "+390 m, avoids small-arms fire".
- **Spoken legs**, with landmarks instead of street signs:
  - "Walk with the Donjon at your 7 o'clock, about 30 metres along Passage des Vignerons. You should see the school on your left.";
  - the first leg is oriented with the speaker's own heading if known, else a landmark they said they see, else the sun.
- **The pin follows them** (dead reckoning):
  - the phone counts steps (×0.7 m); without a step counter, walking speed × time;
  - the circle grows with the distance walked (10 % / 25 %);
  - without steps, the pin waits at the next turn until they tap **Reached** or say "next", which puts it back on the junction and shrinks the circle;
  - a new landmark report while walking re-locates them around where the pin says they are, and the route restarts from there.
- **Voice commands** while walking: "next / reached", "repeat", "I'm lost", "arrived", "stop guidance" (also in French: "suivant", "répète", "perdu", "arrivé").
- **Rerouting:** a new danger zone on the way gives a new route if a safer one exists, otherwise a spoken warning.
- **Danger zones stay where they were reported** when the reporting unit walks away.
- **Can't walk** (stretcher, trapped): instead, a dashed amber **medic route** CCP → casualty, with time out and time back with a stretcher (1.3 / 0.6 m/s, placeholders).
- **Rehearsal:** a simulated soldier walks the route 5× faster than real time, a bit slower than assumed, and confirms each turn. The pin's circle grows and shrinks as it would for real. `POST /api/simulate` takes `"walking": true` for a casualty who can walk.

Why plain shortest paths and not reinforcement learning, and where RL would help (planning over the position uncertainty, threats found on the way, learned risk weights, dispatching several teams): `reports/Route planning and reinforcement learning.md`.

## Pipeline view (for the demo)

http://localhost:8000/pipeline shows one report as three steps, live:

Steps 1–3 locate the speaker; step 4 is the casualty twin (below).

1. **Listen:** the clip's mel spectrogram (chirp boxed, speech hatched), one lane per sound class over time, the chirp echogram (level against distance, with the ground band and the facade echo marked), and the kind-of-space probabilities.
2. **Measure:** the echo rings around the phone (one per wall, at its distance), and what the audio says: echoes, background level, kind of space, sounds, each with the bits it removed.
3. **Match:** the candidate areas with their probability and fit, a mini map, a top-down plan of the real buildings around the best-fitting spot of the selected area (free space seen from it, walls that should echo in green when heard, grey when not, the measured rings on top), and a ✓ / ~ / ✗ for every clue.

**Simulate report** places a soldier near the Château. Its audio is a synthetic recording built from the real place at the true spot: a voice at the reference level, road noise at the level the noise map predicts, and the end chirp with echoes from the real walls (or a ringing room indoors). It is labelled SIMULATED and measured by the same code as a real clip. The kind-of-space classifier and the sound events are still drawn from our model.

## Impact graph, kit and team (steps 5 and 6)

Below the four steps, `/pipeline` turns the same report into a response plan (`backend/response.py`, `frontend/impact.js`):

- **Impact graph**, left to right: what was **reported** → **body region** → structures **possibly impacted** (dashed, to check: e.g. thigh bleeding → femoral artery; blast → eardrums, blast lung, concussion, eye fragments, full body sweep) → **MARCH threat** (Massive bleeding, Airway, Respiration, Circulation, Hypothermia/Head) → **what to bring**. Hover a box to follow its chain.
- **Body parts** (dashboard toggle next to the title): every body part as a node, body → head / neck / torso / arms / legs → 40 parts (knee, wrist, eyes, ribs, lower back...). **Red = affected**, said in a report (wound or tourniquet location). **Orange = no data yet**, which does not mean fine. A region turns red when one of its parts is affected, or when only the region was said ("leg wound": the leg is red, its parts stay orange because where on the leg is unknown). An injury with no body part ("very hurt") turns only "Body" red. Side not said → both sides, flagged. Hover a box for what was said. One graph per casualty. Code: `backend/bodygraph.py`.
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

## Surroundings panel (replaces the old guessed 3D scene)

The Location tile shows the **real** buildings (IGN footprints, darker = taller) around the best-fitting spot of each candidate area, north up and to scale. On top are the free space seen from that spot, the walls that should echo there, and the echo rings actually measured. Rings that touch walls mean a match. Under it, every clue gets ✓ / ~ / ✗ with numbers ("6.0 m → wall at 6.0 m", "measured 58 dB(A), expected here 54"). Code: `backend/surround.py` (served at `/api/report/{id}/surround`) and `frontend/surround.js` (plain canvas).

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
| `backend/route.py` | Walking network from OSM, safest route away from danger zones (Dijkstra), legs and landmark cues |
| `backend/guide.py` | Guides a walking casualty to the CCP (spoken legs, dead reckoning, reroutes); medic route for the others |
| `backend/danger.py` | Threats from words and from sound → events → zones on the map, overlaps, "near you" warnings |
| `backend/soundscape.py` | Per grid cell: what kind of space it is (from building footprints) and what you would hear there |
| `backend/surround.py` | Echo distances and road-noise level expected at every spot, the noise-level measurement (own voice as reference), the matching, the bits per cue, the surroundings panel |
| `backend/heart.py` | Heart rate from a chest recording (phone microphone on the chest, 10 s), quality, bands |
| `backend/place.py` | Detects a named town outside the mapped area (no position guessed there) |
| `backend/condition.py` | Casualty condition: MARCH states, responsiveness, distress, overall state, threats with time windows and countdowns, hidden injuries from how it happened |
| `backend/stress.py` | Speaker stress from the voice (pitch, range, brightness, rate, choppiness) and the words; adapts the questions |
| `backend/bodygraph.py` | Body parts graph: every body part as a node (body → 7 regions → 40 parts), red = said affected, orange = no data |
| `backend/viewshed.py` | 3D line of sight from every cell to the top of every landmark (IGN LiDAR HD), landmark top altitudes, elevation angles |
| `backend/forest.py` | Woods: trees / open / water per cell, paths and surfaces, depth in the wood, line of sight through trees, ground answers |
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

Current `eval_loop` result (22 Nov, speaker sees with the 3D model, only spots where at least 2 landmarks are truly in sight, up to 3 questions, truthful answers): median error 43 m, 80th percentile 190 m. The spoken radius goes from about 720 m to 80 m after the questions, and the truth falls inside it in 73 % of trials, so the radius is a little too confident. Spots that see fewer than 2 landmarks are skipped by this script, and in the streets they are the majority: see the geomatics section for the honest picture.

In the woods: `python -m scripts.eval_forest 60` (see "In the woods" above).

## Medical scope

The casualty side is decision support for trained medics: it organises what was said, keeps timers and suggests an order. It doesn't diagnose. The priority rule and the tourniquet thresholds (60/90/120 min) are placeholders to be checked with a mentor.

## Data and models

- Landmarks, roads, railways: © OpenStreetMap contributors (ODbL)
- Building footprints and heights: IGN BD TOPO (Licence Ouverte / Etalab 2.0)
- YAMNet sound classifier: Google, Apache 2.0 (`data/models/yamnet.tflite`)
- AST (Audio Spectrogram Transformer): MIT, `MIT/ast-finetuned-audioset-10-10-0.4593` on Hugging Face, BSD-3-Clause. It downloads once into the Hugging Face cache; set `AST_ENABLED=0` to run YAMNet alone
- Drone detector: `preszzz/drone-audio-detection-05-17-trial-0` on Hugging Face (AST fine-tuned on drone / no-drone audio), BSD-3-Clause. Downloaded once by `python -m scripts.eval_danger --fetch`; without it everything else still works. `DRONE_ENABLED=0` turns it off
- Evaluation clips (not in the repo): ESC-50 (Piczak 2015, CC BY-NC 3.0); gunshots from HEAR "Gunshot triangulation" (`mteb/GunshotTriangulationHear`); drones from DADS (`geronimobasso/drone-audio-detection-samples`, MIT)
