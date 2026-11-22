# Near report: illustrations to generate (Nano Banana)

Generate each image and save it as `report/figures/<name>.png` (16:9 unless the prompt says otherwise). Rebuild the PDF and
the image replaces the prompt box automatically. Charts of results come from measured data, so they are not in this list.

Every prompt already includes the colour palette and asks for a plain white background (easy to remove): copy each one as is.

## cover.png

Title page.

Cinematic wide illustration at dusk. In the foreground a combat medic kneels in a tree line beside a wounded soldier, speaking into a handheld tactical radio; a small compass hangs from his vest. Behind them, across a field, the silhouette of a medieval castle keep and a church spire. In the sky, a faint red glitch overlay of a satellite icon crossed out (GPS jammed) and a distant small quadcopter drone. On the right third of the image, as if projected in the air, a translucent dark-blue tactical map with a cyan uncertainty ellipse shrinking onto a red casualty pin labelled "P1". Muted realistic colours, no gore, no national flags, no readable text except "P1". 16:9. Colour palette (use only these): navy #0D1110, cyan #1AA7C4, amber #E09A2B, red #E5484D, green #3FA877, grey #8B9A94, plus white for text on dark shapes.

## problem.png

The situation Near is built for: GPS denied, drones overhead, a medic who can describe what he sees but can't give a grid reference.

Split-panel editorial illustration, 16:9, flat vector style with subtle texture, plain white background, cyan, amber and red accents. Left panel titled "GPS DENIED": a soldier's wrist GPS showing a glitched screen with "NO FIX" and a red jamming wave pattern radiating from a distant antenna truck. Middle panel titled "DRONES OVERHEAD": a small quadcopter silhouette above a tree line, a dotted red cone below it, two medics crouched under trees with a stretcher. Right panel titled "WHERE ARE WE?": the medic holding a radio, a speech bubble with a small castle keep icon, a church icon and a sun icon with arrows, and a question mark over a blank map. Clean sans-serif labels, exactly these three titles, no other text, no gore. Colour palette (use only these): navy #0D1110, cyan #1AA7C4, amber #E09A2B, red #E5484D, green #3FA877, grey #8B9A94, plus white for text on dark shapes.

## concept.png

The Near loop: describe what you see, get located, answer one question, get the read-back.

Horizontal four-step infographic, 16:9, clean flat vector, plain white background, navy text, cyan and amber accents. Step 1 "DESCRIBE": a soldier icon with a radio and a speech bubble showing a castle icon with "11 o'clock", a church icon with "240°" and a sun icon with "1 o'clock". Step 2 "LOCATE": a top-down street map with a large translucent cyan ellipse and two smaller dashed circles labelled A and B. Step 3 "ASK": a speech bubble from a laptop saying "Is the church left or right of the keep?" with a small bar chart labelled "bits gained". Step 4 "READ BACK": the ellipse shrunk to a small circle on a street corner, a red pin labelled "P1", a timer "TQ 72:14" and the text "within 60 m". Thin arrows between steps, a curved arrow from step 3 back to step 2. Use exactly the quoted labels. Colour palette (use only these): navy #0D1110, cyan #1AA7C4, amber #E09A2B, red #E5484D, green #3FA877, grey #8B9A94, plus white for text on dark shapes.

## dashboard.png

The coordinator dashboard: evacuation order, casualty card, map with uncertainty and threat zones, location evidence, sound analysis, impact graph and the team to send.

High-fidelity dark-mode UI mockup of a tactical web dashboard, 16:9, the dashboard window itself in near-black navy tones on a plain white background, thin 1 px borders, monospace numbers. Top bar: "NEAR · COORDINATOR", a red "P1" badge, KPI boxes "POSITION ±60 m", "TOURNIQUET 72:14" (amber), "MOBILITY stretcher", "WORSE IN 4 min" (red), buttons "Radio", "Simulate". Left column: "EVACUATION ORDER" list of three rows with P1, P1, P2 badges and timers. Centre: a dark map of a small town with a castle, a cyan route line to a "CCP" marker, a translucent red circle labelled "SMALL-ARMS FIRE", a pink dashed circle labelled "DRONE", a cyan ellipse around a red pin. Right column: "CASUALTY" card with M A R C H rows coloured red/green/grey, "LOCATION" panel with a top-down building plan and echo rings. Bottom: a left-to-right graph of boxes "Reported → Body region → Possibly impacted → MARCH threat → Bring". Crisp, realistic product screenshot style. Colour palette (use only these): navy #0D1110, cyan #1AA7C4, amber #E09A2B, red #E5484D, green #3FA877, grey #8B9A94, plus white for text on dark shapes.

## modes.png

The three deployment modes side by side.

Three-column technical diagram, 16:9, flat vector on white, navy lines, cyan and amber highlights. Column "CONNECTED": a phone icon linked by a Wi-Fi symbol to a laptop icon. Column "RADIO ONLY": a handheld tactical radio linked by zig-zag radio waves to a second radio, which is linked by an audio cable to a laptop; a crossed-out satellite icon and a crossed-out cloud icon above. Column "RADIO + OFFLINE PHONE": a phone held next to a radio, small sound-wave tones drawn between the phone speaker and the radio microphone, a label "~2 s of tones, 30 bytes", radio waves to the laptop. Under each laptop a small map with a pin. Titles exactly "CONNECTED", "RADIO ONLY", "RADIO + OFFLINE PHONE". Colour palette (use only these): navy #0D1110, cyan #1AA7C4, amber #E09A2B, red #E5484D, green #3FA877, grey #8B9A94, plus white for text on dark shapes.

## architecture.png

System architecture. Everything inside the laptop box runs offline.

Detailed software architecture diagram, 16:9, plain white background, flat vector, navy outlines, rounded boxes, cyan for data flow, amber for audio flow. Left: three input boxes stacked: "Field phone (browser, offline app)", "Tactical radio (voice + data tones)", "Typed text". Centre: a large rounded box titled "Near server (laptop, offline)" containing a pipeline of boxes left to right: "Speech-to-text (Whisper)" → "Extraction (rules + Mistral 7B)" → "Constraints" → "Localisation grid" → "Question selector" → "Read-back"; below it a second row: "Acoustic analysis (YAMNet, AST, Near-small)", "Casualty model (MIST, MARCH, mobility)", "Danger zones", "Routing + guidance", "Modem + packets"; at the bottom a wide box "State store" and a box "WebSocket". Right: "Coordinator map (Leaflet, offline tiles)". Bottom strip of four database cylinders: "OSM landmarks", "IGN buildings + LiDAR", "Forest + paths", "Models". Arrows connecting everything logically. Exactly these labels, small clean sans-serif. Colour palette (use only these): navy #0D1110, cyan #1AA7C4, amber #E09A2B, red #E5484D, green #3FA877, grey #8B9A94, plus white for text on dark shapes.

## extraction.png

From a spoken sentence to constraints: each phrase becomes one typed, noisy observation.

Annotated text-to-structure diagram, 16:9, plain white background. At the top a long speech bubble with the sentence "This is Bravo 2. One casualty, blast, left leg bleeding, tourniquet on at 14:32. I see the castle keep at my 11 o'clock, a church at bearing 240, sun at my 1 o'clock. Over." Coloured highlighter marks on phrases: callsign in grey, casualty phrases in red, landmark phrases in cyan, sun in amber. Thin lines from each highlight down to cards below: grey card "callsign: BRAVO 2", red card "MIST: blast · left leg · TQ 14:32", cyan card "bearing: keep, 330°, σ 15°", cyan card "abs_bearing: church, 242°, σ 6°", amber card "sun: 1 o'clock". Clean flat vector, readable labels exactly as quoted. Colour palette (use only these): navy #0D1110, cyan #1AA7C4, amber #E09A2B, red #E5484D, green #3FA877, grey #8B9A94, plus white for text on dark shapes.

## resection.png

Resection from spoken clock directions. With the facing direction unknown, two landmarks leave a family of candidate positions; a third landmark, the sun or a compass bearing picks one.

Clean geometric diagram, top-down view, plain white background, flat vector. A small town map in light grey with a castle keep icon at top-left and a church icon at top-right and a water tower icon at bottom-right. A soldier symbol (small circle with an arrow showing facing direction) at the centre. From the soldier, a cyan line to the keep labelled "11 o'clock", an amber line to the church labelled "2 o'clock". A faint clock face drawn around the soldier with 12 aligned to his facing arrow. A dashed cyan circle arc passing through the keep, the church and the soldier, labelled "positions that fit two angles". A small sun icon at the upper right with a thin arrow labelled "sun at 1 o'clock". Title at top: "Pothenot's problem, spoken". Exactly these labels. Colour palette (use only these): navy #0D1110, cyan #1AA7C4, amber #E09A2B, red #E5484D, green #3FA877, grey #8B9A94, plus white for text on dark shapes.

## grid.png

The likelihood grid: each observation is a layer over cells and headings; their product, summed over headings, gives the position map with its areas A and B.

Exploded isometric technical illustration, 16:9, plain white background, flat vector. Four semi-transparent stacked square layers floating above a base map of a small town. Layer 1 labelled "keep at 11 o'clock" shows a curved cyan band. Layer 2 labelled "church, bearing 240°" shows a straight amber wedge. Layer 3 labelled "sun at 1 o'clock" shows a uniform yellow tint with a small heading dial. Layer 4 labelled "can't see the water tower" shows a grey hole. At the bottom, the base map shows the product: a bright cyan blob labelled "A 72%" and a smaller blob labelled "B 21%" with a dashed ellipse around A. A side axis labelled "72 headings" on the left. Exactly these labels. Colour palette (use only these): navy #0D1110, cyan #1AA7C4, amber #E09A2B, red #E5484D, green #3FA877, grey #8B9A94, plus white for text on dark shapes.

## aimtap.png

Aim & tap: the phone's tilt to a landmark's top gives its distance; the turn between two taps gives the angle between landmarks.

Technical side-and-top dual view illustration, 16:9, flat vector, plain white background. Left half, side view: a soldier holding a phone at eye level, the phone's top edge pointing at the top of a tall castle keep 300 m away; a dotted sight line, an angle arc labelled "tilt e", the keep height labelled "53 m (LiDAR)", ground line, distance arrow labelled "d = (z_top − z_ground − 1.5 m) / tan e". Right half, top view: the same soldier dot with two sight lines to a keep icon and a church icon, an angle arc between them labelled "turn between taps". A small gyroscope icon. Exactly these labels. Colour palette (use only these): navy #0D1110, cyan #1AA7C4, amber #E09A2B, red #E5484D, green #3FA877, grey #8B9A94, plus white for text on dark shapes.

## questions.png

Choosing a question: each candidate is scored by how much it is expected to shrink the position, given every answer it could get.

Decision-tree infographic, 16:9, plain white background, flat vector. At the top a small map with two blobs labelled "A 45%" and "B 30%". Below, three candidate question cards side by side: "Can you see a railway?" with two branches "yes" and "no" each showing a tiny map where the blobs change little, score "0.2 bits"; "Is the church left or right of the keep?" with branches "left" (only A remains) and "right" (only B remains), score "0.95 bits, 600 m → 150 m" highlighted with a cyan glow and a check mark; "How far is the church?" with five small branches, score "0.4 bits, effort high". A small label "asked" over the winning card. Exactly these labels. Colour palette (use only these): navy #0D1110, cyan #1AA7C4, amber #E09A2B, red #E5484D, green #3FA877, grey #8B9A94, plus white for text on dark shapes.

## echo.png

Chirp echo ranging in a street: the phone plays a sweep, and each wall returns it after a delay that gives its distance. One microphone gives distance, never direction.

Top-down urban street illustration, 16:9, flat vector, plain white background, buildings as grey blocks with darker roofs. A soldier with a phone in the middle of a narrow street. Concentric cyan rings radiating from the phone. Two building facades highlighted, one at 6 m labelled "echo 6.0 m" and one across the street at 9 m labelled "echo 9.0 m", a thin label "street width 15 m (wall-to-wall echo)". In the corner an inset graph titled "echogram" showing a large first spike labelled "direct" and two smaller spikes labelled "6 m" and "9 m" on a distance axis in metres, with a shaded band near 1 m labelled "ground". Exactly these labels. Colour palette (use only these): navy #0D1110, cyan #1AA7C4, amber #E09A2B, red #E5484D, green #3FA877, grey #8B9A94, plus white for text on dark shapes.

## casualty.png

The casualty view: MARCH state with countdowns, the body twin, and the impact graph from what was said to what to bring.

Medical decision-support infographic, 16:9, plain white background, clean flat vector, red, amber, green and grey status colours. Left: a vertical MARCH strip with five rows "M Massive bleeding: tourniquet" (amber), "A Airway: open" (green), "R Breathing: unknown" (grey), "C Circulation: shock signs" (red), "H Hypothermia risk" (amber), each with a small countdown bar; a label "worse in 4–10 min". Centre: a neutral grey 3D human body lying on its back, seen from above at an angle, left thigh glowing red with an orange band labelled "TQ 14:32 · 72 min". Right: a left-to-right graph of rounded boxes "left leg bleeding" → "left thigh" → "femoral artery (check)" (dashed) → "M · massive bleeding" → "tourniquet, packing". Small footer text "decision support, not a diagnosis". No gore. Exactly these labels. Colour palette (use only these): navy #0D1110, cyan #1AA7C4, amber #E09A2B, red #E5484D, green #3FA877, grey #8B9A94, plus white for text on dark shapes.

## danger.png

Danger zones on the coordinator map: circles and wedges around reporters, dashed when heard by a microphone, and a thick ring where two units' reports overlap.

Top-down dark tactical map of a small town, 16:9, the map drawn in near-black navy tones as a rounded rectangle on a plain white background, thin grey streets and building blocks. A translucent red circle with a solid outline labelled "SMALL-ARMS FIRE · voice" around a unit marker "C1". A second translucent red circle with a dashed outline labelled "SMALL-ARMS FIRE · heard" around unit "C2". Where the two circles overlap, a thick red ring labelled "likely source area". A pink dashed circle labelled "DRONE" around unit "C3". An orange 50-degree wedge labelled "SNIPER · bearing 1600 mils" pointing east from unit "C4". A small legend box at bottom right with coloured squares: Drone, Small-arms fire, Sniper, Explosions, Armour, Mines. Exactly these labels. Colour palette (use only these): navy #0D1110, cyan #1AA7C4, amber #E09A2B, red #E5484D, green #3FA877, grey #8B9A94, plus white for text on dark shapes.

## routing.png

A walking route that bends around a reported small-arms zone, cut into spoken legs with landmark cues.

Top-down map illustration, 16:9, plain white background, flat vector, streets in light grey, buildings in pale blocks, a castle keep icon. A start marker "casualty" at bottom-left and a "CCP" cross marker at top-right. A thin grey dashed straight-ish route labelled "shortest: 732 m" passing through a translucent red circle labelled "small-arms fire". A thick cyan route labelled "safest: 1,122 m" bending around the circle. Along the cyan route, numbered leg markers 1 to 5 at turns, with small callouts: "1: keep at your 7 o'clock, 30 m", "2: turn left, 40 m", "3: turn left, 100 m, keep on your right", "4: turn right", "5: CCP". Exactly these labels. Colour palette (use only these): navy #0D1110, cyan #1AA7C4, amber #E09A2B, red #E5484D, green #3FA877, grey #8B9A94, plus white for text on dark shapes.

## deadreckoning.png

The uncertainty of a walking casualty's position: it grows with distance walked and snaps back at each confirmed turn.

Clean technical chart-style illustration, 16:9, plain white background. A horizontal axis "distance walked (m)" and a vertical axis "uncertainty radius (m)". A cyan sawtooth line: rising slopes labelled "+25% of distance (time only)" and a gentler dashed amber line labelled "+10% (step counter)", dropping sharply at three vertical markers labelled "reached turn 1", "reached turn 2", "reached turn 3". Above the chart, a small top-down strip of a walking route with a moving pin and a circle that grows and shrinks. Minimal, exact labels only. Colour palette (use only these): navy #0D1110, cyan #1AA7C4, amber #E09A2B, red #E5484D, green #3FA877, grey #8B9A94, plus white for text on dark shapes.

## radiochain.png

Radio mode: the laptop listens to the radio, understands each transmission, and answers on it after the operator approves.

Horizontal signal-chain diagram, 16:9, plain white background, flat vector, navy outlines, amber audio waves, cyan data arrows. Left: a soldier with a handheld radio, a speech bubble "This is Bravo 2...". Zig-zag radio waves to a second radio on a table at the CCP. An audio cable from the radio's speaker to a laptop labelled "audio in". Inside a big laptop outline, a row of boxes: "Voice activity: cut transmission" → "Data tones? decode packet" → "Whisper (local)" → "Callsign: BRAVO 2" → "Near pipeline" → "Reply draft". Below the row, a small operator icon with a check mark labelled "approve". Then "Offline voice (SAPI)" → an audio cable labelled "audio out" back to the radio's microphone, and radio waves back to the soldier with a bubble "Bravo 2, this is CCP. Copy... Over.". A crossed-out cloud icon labelled "no internet". Exact labels. Colour palette (use only these): navy #0D1110, cyan #1AA7C4, amber #E09A2B, red #E5484D, green #3FA877, grey #8B9A94, plus white for text on dark shapes.

## modem.png

The modem: bytes become two audio tones; the frame is sent twice and the two copies are added before deciding each bit.

Technical signal illustration, 16:9, plain white background, flat vector. Top: a row of byte boxes "55 55 55 55 55 55" (grey, labelled "preamble"), then "2D D4" (navy, "sync"), "1C" ("length"), a long cyan block "payload 28 B", "CRC" (amber), then the same sync-length-payload-CRC sequence again labelled "copy 2". Middle: an audio waveform below the frame alternating between a lower-frequency sine labelled "1200 Hz = 1" and a higher-frequency sine labelled "2200 Hz = 0". Bottom: two rows of soft-bit bars labelled "copy 1" and "copy 2", each with a short gap labelled "20 ms dropout" at different places, plus a third row labelled "sum" with no gap. Exactly these labels. Colour palette (use only these): navy #0D1110, cyan #1AA7C4, amber #E09A2B, red #E5484D, green #3FA877, grey #8B9A94, plus white for text on dark shapes.

## packet.png

A 32-byte measurement packet, field by field.

Byte-map infographic, 16:9, plain white background, flat vector. A long horizontal strip of 32 small square cells grouped and coloured by field, with labels above each group: "type" (1), "callsign BRAVO 2" (8), "time+seq" (2), "mask" (2), "compass 75°" (1), "aim" (3), "steps 1234" (2), "space" (2), "dB(A) 62" (1), "walls 3.5 m, 9 m" (3), "traffic" (2), "drone 0.85" (2), "reached leg 2" (2), "strength" (1). Below the strip, a bracket labelled "32 bytes = about 2 s of tones". Pastel colours per group, navy labels. Exactly these labels. Colour palette (use only these): navy #0D1110, cyan #1AA7C4, amber #E09A2B, red #E5484D, green #3FA877, grey #8B9A94, plus white for text on dark shapes.

## radiosim.png

The simulated radio channel used for tests and training.

Signal-processing block diagram, 16:9, plain white background, flat vector. Left: a clean colourful spectrogram labelled "phone microphone". Then boxes in a row connected by arrows: "band-pass 300–3400 Hz", "automatic gain + soft clipping", "8 kHz", "8-bit µ-law (digital)", "lost 20 ms frames (digital)", "hiss 15–30 dB". Right: the same spectrogram now narrow in frequency, with two black vertical gaps and grainy noise, labelled "what the CCP hears". Exactly these labels. Colour palette (use only these): navy #0D1110, cyan #1AA7C4, amber #E09A2B, red #E5484D, green #3FA877, grey #8B9A94, plus white for text on dark shapes.

## phone.png

The offline phone: measure, send as tones, receive a route, follow the arrow.

Smartphone UI mockup, portrait, dark theme, shown on a plain white background, 9:16 phone inside a 16:9 canvas with callouts. Screen content top to bottom: header "NEAR · FIELD", a card titled "No network: talk on the radio, send data as tones", a text field "Bravo 2", a button "Measure 4 s", result chips "outdoors, between buildings 72%", "walls 3.5, 9 m", "drone 0.91", "62 dB(A)", a large button "Send by radio", two buttons "Receive route" and "Hand-over QR". Below, a guidance panel with a big cyan arrow pointing up-right, a chip "86 m to the next turn", text "Leg 2 of 5: bearing 043, about 120 metres. You should see Mairie de Saint-Mandé on your right." and a button "Reached the turn". Callouts outside the phone: "runs offline", "~30 bytes as 2 s of tones", "compass + step counter". Exactly these labels. Colour palette (use only these): navy #0D1110, cyan #1AA7C4, amber #E09A2B, red #E5484D, green #3FA877, grey #8B9A94, plus white for text on dark shapes.

## distill.png

Training Near-small: the big model hears the clean clip, the small one hears it through a simulated radio and learns to give the same answers, plus drone and gunfire.

Machine-learning training diagram, 16:9, plain white background, flat vector. Left: a waveform icon labelled "clean clip". It splits into two paths. Upper path: straight into a large box labelled "AST teacher, 86M" outputting a bar chart labelled "527 AudioSet probabilities". Lower path: through a box labelled "simulated radio: band-pass, 8 kHz, µ-law, dropouts" into a small box labelled "Near-small student, 5.5M" that has three outputs: a bar chart "527 AudioSet", a single bar "drone", a single bar "gunfire". Between the two bar charts a dashed double arrow labelled "distillation loss ×3". From the drone and gunfire bars, arrows to tags "labels: DADS" and "labels: forest gunshots". Small footer "8 minutes on a laptop GPU". Exactly these labels. Colour palette (use only these): navy #0D1110, cyan #1AA7C4, amber #E09A2B, red #E5484D, green #3FA877, grey #8B9A94, plus white for text on dark shapes.

## segments.png

Who Near is for: military medical chains first, then civilian rescue where people can't say where they are.

Clean business infographic, 16:9, plain white background, flat vector, navy text, cyan and amber accents. A central circle labelled "Near: locate from what people see". Around it, five segment cards connected by thin lines: "Military medical services (CASEVAC, CCP)" with a stretcher icon; "Command posts and training centres" with a tent and radio icon; "Ukraine and frontline partners" with a radio and drone-crossed icon; "Emergency call centres (lost callers)" with a headset icon; "Mountain rescue and disaster response" with a mountain and helicopter icon. Primary segments (first three) in cyan, secondary (last two) in amber, small legend "primary" / "next". No flags, no logos. Exactly these labels. Colour palette (use only these): navy #0D1110, cyan #1AA7C4, amber #E09A2B, red #E5484D, green #3FA877, grey #8B9A94, plus white for text on dark shapes.

## gtm.png

Go-to-market: from a field trial at Vincennes to funded pilots, then fielding and a civilian version.

Horizontal roadmap timeline infographic, 16:9, plain white background, flat vector, navy line with cyan milestones. Four phases left to right: "Now: hackathon prototype, Vincennes" (laptop icon), "3 months: field trials with a military medical training unit, real radios" (radio icon), "6–12 months: funded pilot (EDF consortium / AID / DIANA), Ukraine partner trial" (handshake icon), "12–24 months: fielded site licences + civilian version for rescue services" (map and headset icon). Under the line, small grey labels "validate", "prove", "scale". Exactly these labels. Colour palette (use only these): navy #0D1110, cyan #1AA7C4, amber #E09A2B, red #E5484D, green #3FA877, grey #8B9A94, plus white for text on dark shapes.
