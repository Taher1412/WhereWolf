# Fusing audio evidence with a city digital twin, and asking as few questions as possible

Scope: (a) predicting acoustic features per map cell from a digital twin (IGN buildings + heights, OSM noise sources) and matching them to a recording; (b) deciding what to infer passively and what to ask, for Pothenot (25 m grid, ~4x4 km, 72 headings, spoken landmarks + sun + YAMNet/AST sound events + setting from reverb/chirp, EIG question selector stopping at 75 m or 3 questions).

Method note: about 20 tool calls. Primary PDFs were read for Batphone (Tarzia et al. 2011) and Wu/Kang/Jin (2017). Several items below are standard textbook material that I did **not** re-verify this session. They are marked "(unverified this session)" and placed under Inferences, not Cited Findings.

---

## 1. Predicting acoustic features per cell from a digital twin (noise maps, street-canyon acoustics, fast simulation) and how accurate it is

### Takeaway
Level-type features (Lden or LAeq per source class) can be taken almost for free from existing CNOSSOS-EU strategic noise maps. Their real-world error is roughly 0–4 dB(A), which is far tighter than an uncalibrated phone mic (about ±4 dB or worse), so absolute level is only weak evidence. Reverberation-type features (RT30, EDT, echo delay) follow street geometry: RT30 is about 1–3 s in streets, rises with facade height, H/W and enclosure, and ODEON-class simulation matches measurement within about 15%. That means a cheap geometric proxy computed from the 5 m height raster (canyon H/W, facade distance, openness or sky-view) can stand in for ray tracing at hackathon scale.

### Cited Findings
**Noise maps / CNOSSOS-EU / NoiseModelling**
- NoiseModelling (Université Gustave Eiffel, open source) bases its validation on implementation tests, not field accuracy. Its "TCxx" unit tests come from ISO/TR 17534-4:2020, and it points users to independent CNOSSOS-EU papers for accuracy. — [NoiseModelling docs, Validation](https://noisemodelling.readthedocs.io/en/latest/Validation.html)
- Real-world CNOSSOS-EU errors: in Ireland, average deviation < 2 dB(A) from roadside measurements. In Sweden, under-prediction of about 0.1–4 dB(A) relative to Nord2000. In Dublin, systematic under-estimation of 0.2–2.0 dBA. A review notes that validation is mostly by test cases, with few real-world evaluations. — [Influence of Traffic Input Data Quality on Road Noise Estimates Using CNOSSOS-EU (PMC, 2025/26)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12899886/); see also [Noise Mapping journal 2025 paper](https://www.degruyterbrill.com/document/doi/10.1515/noise-2025-0023/html)
- The City of Paris updated its road noise maps in 2022 with CNOSSOS-EU. — [Paris RA2022 bruit routier](https://cdn.paris.fr/paris/2023/12/19/paris_ra2022-bruit-routier-2-pages-18-12-copie-kJqM.pdf)
- Bruitparif uses the 4th-round (E4, 2022) strategic noise maps for road, rail and air, built from 2019 traffic, with Lden as the combined indicator. There is a viewer at carto.bruitparif.fr. — [Bruitparif note méthodologique air-bruit 2024](https://bruitparif.fr/pages/A-la-une/500%20Cartographie%20air-bruit%20en%20%C3%8Ele-de-France/2024-08-12%20-%20Note%20m%C3%A9thodologique%20et%20de%20r%C3%A9sultats%20de%20la%20cartographie%20air-bruit.pdf)
- The national 2022 road/rail strategic noise-map shapefiles on data.gouv.fr **exclude** the Métropole du Grand Paris, so Vincennes is not covered there. — [data.gouv.fr CBS réseaux non concédés](https://www.data.gouv.fr/datasets/cartes-de-bruit-strategiques-des-reseaux-routiers-et-ferroviaires-non-concedes-directive-europeenne-2002-49-ce)
- Smartphone mic calibration is a recurring problem: one study found phone readings 4 dB below a reference SPL meter, and phone SPL is "limited precision". — [Mapping Urban Environmental Noise Using Smartphones (Sensors 2016, PMC)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5087480/); [ISPRS 2022 smartphone traffic noise mapping](https://isprs-archives.copernicus.org/articles/XLIII-B4-2022/613/2022/isprs-archives-XLIII-B4-2022-613-2022.pdf)

**Street-canyon acoustics (Kang and co-workers)**
- Wu, Kang & Jin (Environment and Planning B, 2017, DOI 10.1177/2399808317714799) simulated 144 real street samples (Harbin), with 13 spatial parameters. RT30 is "primarily distributed between 1.0 s and 3.0 s" and stabilises with distance. Mean RT30 increases with mean facade height, sidewalk width and cross-sectional enclosure degree in the near zone (60 m). EDT is near 0 close to the source, then plateaus at 0–3 s. Attenuation is linear in log-distance, and the minimum R² across samples is 0.977. — [Wu, Kang, Jin 2017 preprint (UCL)](https://discovery.ucl.ac.uk/10054793/1/Hupeng%20WU%20-%20street-parameter-paper-whiterose2.pdf)
- The same paper's setup: ODEON v9 hybrid (image sources for low orders, transition order 2, then ray tracing), 10^6 rays, reflection order 2000, 3 s impulse responses, facade absorption 0.1, scattering 0.3. It cites Lee & Kang (2015), who validated ODEON against Picaut et al.'s (2005) street measurements with **< 15% difference in SPL and RT30**. — [Wu, Kang, Jin 2017](https://discovery.ucl.ac.uk/10054793/1/Hupeng%20WU%20-%20street-parameter-paper-whiterose2.pdf)
- Lee & Kang (Acta Acustica united with Acustica, 2015): T30 and EDT increase as H/W rises, in both narrow and wide streets, while SPL depends on H/W only in narrow streets. — [Lee & Kang 2015, DOI 10.3813/AAA.918806](https://dx.doi.org/10.3813/AAA.918806) (via search snippet; full text 403)
- Picaut et al. (Applied Acoustics 66:149–173, 2005) measured impulse responses at many points in a real street canyon (RT30 in 1/3-octave bands from 250 Hz to 5 kHz). Citing papers report that the sound field is roughly uniform across a street cross-section. — [bibsonomy record](https://bibsonomy.org/bibtex/2a2cfd3ffacbe702ad58637a65562dd86/muhe); [Picaut et al. IN2010](https://orbi.uliege.be/bitstream/2268/31262/1/Full_Paper_Picaut_IN2010%283%29.pdf)
- Outdoor residential courtyards can show RT at 500/1000 Hz over 4 s (Yang, Kang & Kim 2017). — search snippet, [UCL discovery](https://discovery.ucl.ac.uk/id/eprint/10054786/1/Manuscript_Apartment%20RT.pdf)

**Fast simulation in Python**
- pyroomacoustics (Scheibler, Bezzam, Dokmanić, ICASSP 2018) offers a fast C/C++ image-source model, and later added ray tracing for general polyhedral rooms. Hybrid ISM plus stochastic ray tracing gave up to 35.8% relative improvement in far-field keyword spotting over single-absorption ISM (2020). — [pyroomacoustics arXiv 1710.04196](https://arxiv.org/pdf/1710.04196.pdf); [docs](https://pyroomacoustics.readthedocs.io/); [Realistic room simulation 2020](https://ar5iv.labs.arxiv.org/html/2006.02774)

### Inferences
- **What to precompute per 25 m cell (all numpy, minutes, from the 5 m height raster):**
  1. `L_class[c]`: expected level per source class (road, rail, tram/bus line, park/birds, church bells), from distance to OSM sources with geometric spreading (−20·log10 r for points, −10·log10 r for lines) plus a crude screening penalty (−10 to −15 dB) when the 5 m raster has a building taller than the line of sight. Better: import the Bruitparif/Paris CNOSSOS Lden raster if it can be downloaded (a gap, see below). Use **relative** levels between classes (rail vs road vs birds), not absolute dB, because phone calibration error (≥4 dB) is as large as the map error.
  2. `canyon[c]`: facade distance in 8 or 16 azimuth rays (march over the 5 m raster up to 100 m), mean facade height H, width W, H/W, and an "openness" or sky-view proxy (fraction of the sky not blocked, computed from heights along the rays). Expected first-echo delays are `2·d_facade/343` s (≈ 58 ms at 10 m, 0.29 s at 50 m). In a parallel canyon, flutter-echo period ≈ `W/343·2`.
  3. `RT_pred[c]`: a monotone function of H/W and enclosure, calibrated to the 1–3 s street range above. Open field/park → ~0 (no tail). Courtyards → >3 s. Treat it as a 3–4-bin categorical (open / wide street / narrow canyon / courtyard-indoor) rather than a regression, given ±15% simulation error plus phone/wind noise. This matches the existing indoor/outdoor/street/open setting classifier.
- A full ray tracer (NoiseModelling, I-Simpa, ODEON) over 4x4 km at 25 m (~25,600 cells) is not feasible in 1 day. The geometric proxy captures the variables that Kang's regressions say matter (H, W, enclosure).
- Feature likelihood per cell: `p(feature | cell) = softmax-like categorical with confusion matrix` for setting, and `p(event k heard | cell) = 1 − exp(−λ_k(cell)·T)` for sound events (a Poisson presence model with rate tied to source proximity and service frequency). This is far more robust than matching dB.
- (Unverified this session) The Sabine/Eyring formulas don't apply well to open-top canyons, because energy escapes through the roof. That's why empirical street regressions are preferred.

### Gaps
- I couldn't confirm a downloadable Lden raster for Vincennes / the Métropole du Grand Paris (Bruitparif shows a viewer; the national open data excludes MGP). Check carto.bruitparif.fr or the Paris open-data portal.
- No accuracy figure found for NoiseModelling specifically against field measurements.
- No published accuracy for sky-view-factor or H/W-based RT prediction **from a phone recording** (smartphone blind RT estimation in outdoor wind is not covered here).

---

## 2. Prior work on acoustic map-matching localisation and achieved accuracy

### Takeaway
Ambient-sound localisation works at **room or place granularity, not metres**. Batphone gets 69% over 33 rooms and 92% for adjacent pairs from a 10 s fingerprint. City-level audio geotagging is about 50–56% among 6 cities. There's no published system that localises outdoors on a noise map to tens of metres. So audio should act as a **coarse prior or region filter** (near rail, in a canyon, in a park) that multiplies the landmark likelihood, not as a primary locator.

### Cited Findings
- Batphone / Acoustic Background Spectrum (Tarzia, Dinda, Dick, Memik, MobiSys 2011): 33 rooms, 69% correct fingerprint matches, adjacent-room pairs distinguished with 92% accuracy (chance 3% and 50%). Adding ABS to Wi-Fi improved room-level accuracy from 30% to 69%. The fingerprint takes 10 s. Per-frequency **5th-percentile** of the spectrogram rejects transient sounds (speech) and beat mean, minimum and other percentiles. Accuracy varied by room type (one office 100%, one lounge 38%). — [Tarzia et al. 2011 PDF](https://users.cs.northwestern.edu/~pdinda/Papers/mobisys11.pdf)
- Known limitation: ABS assumes stable ambient sound. HVAC state and people talking change the fingerprint, so it's usually fused with other signals. — [SoundLoc / related summary, arXiv 1407.4409](https://arxiv.org/pdf/1407.4409); [King et al. 2024, MTAP](https://link.springer.com/content/pdf/10.1007/s11042-023-17885-3.pdf)
- City classification from sound scenes (DCASE 2018, 6 cities): a simple CNN gets ~50%, multi-task ~56%. Transport scenes (airport) discriminate cities best. — [arXiv 1905.00979](https://arxiv.org/pdf/1905.00979.pdf); augmentation gives a further ~23% relative gain — [arXiv 2110.04585](https://ar5iv.labs.arxiv.org/html/2110.04585)
- Global natural-sound geolocation benchmark (2025) uses species range maps as priors. — [arXiv 2505.18726](https://arxiv.org/html/2505.18726v2)
- Robotics: "auditory evidence grids" build sound maps but use laser localisation for pose, and note that source-localisation data are "very noisy and unreliable". Acoustic MCL work (KAIST, reflection/diffraction-aware) is indoor and localises **sources**, not the listener. A 2025 review lists outdoor acoustic modelling as an open problem. — [Auditory evidence grids](https://typeset.io/pdf/auditory-evidence-grids-18a0zfonh6.pdf); [KAIST DRA-SSL](https://sgvr.kaist.ac.kr/~ikan/papers/DRA_SSL/Diffraction-_and_Reflection-Aware_Multiple_Sound_Source_Localization.pdf); [Review arXiv 2507.01143](https://arxiv.org/pdf/2507.01143)
- Smartphone noise-mapping systems (NoiseSPY etc.) use GPS to tag levels, which is the inverse problem. I found no work using a noise map as a likelihood for GPS-free outdoor positioning. — [NoiseSPY](https://www.researchgate.net/publication/220134386_NoiseSPY_A_Real-Time_Mobile_Phone_Platform_for_Urban_Noise_Monitoring_and_Mapping)

### Inferences
- Pothenot's "audio as weak region evidence fused with resection" looks novel. No direct prior system was found, which is a pitch point, but it also means there's no published accuracy to quote. The honest claim is "audio narrows the search region; landmarks pin it".
- Borrow Batphone's trick: take the **5th percentile per band** over the clip as the stationary background (road hum vs quiet park), and run YAMNet/AST on the **transients** above it (train, bus brakes, bells). They are two complementary features.
- The most discriminative audio cues for metre-level work are **rare, geographically anchored sources**: rail/RER/metro surfacing, tram, church bells (on the hour), fountains, specific bus lines. Generic "traffic" is everywhere in Vincennes and nearly uninformative.

### Gaps
- No quantitative outdoor map-matching accuracy (metres) from ambient audio found.
- "SoundLoc" and "Acoustic SLAM" papers were not read in full. The latter is about mapping sources with arrays, not single-mic self-localisation.

---

## 3. Bayesian fusion of weak, uncalibrated, correlated evidence

### Takeaway
Treat every audio-derived term as a **tempered, floored, calibrated** likelihood: `L_i(c) = ε + (1−ε)·p_i(obs | c)^τ_i` with τ ≈ 0.3–0.7 for audio, a floor ε of about 0.05–0.2, and classifier scores calibrated by temperature scaling. Merge repeated clips of the same event into one observation rather than multiplying them. This keeps one wrong YAMNet tag from wiping out the true cell, which is the main failure mode of naive product-of-likelihoods grids.

### Cited Findings
- Modern neural nets are poorly calibrated (overconfident) even as accuracy rises. **Temperature scaling**, a single-parameter variant of Platt scaling fit by NLL on held-out data, is often the most effective post-hoc fix and leaves accuracy unchanged. ECE (Naeini et al. 2015) is the standard metric. — [Guo et al., ICML 2017](https://proceedings.mlr.press/v70/guo17a.html); [ar5iv](https://ar5iv.arxiv.org/html/1706.04599); [Minderer et al. 2021, Revisiting calibration](https://arxiv.org/pdf/2106.07998)
- Coarsened / power posteriors: conditioning on the data being "close" to the model under KL divergence approximates raising the likelihood to a power ζ ∈ [0,1] (the "power likelihood"). This makes inference robust to misspecification and contamination. — [Miller & Dunson, JASA 2019, 114(527):1113–1125](https://ar5iv.arxiv.org/html/1506.06101); [IDEAS record](https://ideas.repec.org/a/taf/jnlasa/v114y2019i527p1113-1125.html)

### Inferences
- **Tempering by source reliability.** Suggested starting exponents, to tune on 5–10 synthetic and real recordings: spoken clock bearings τ=1 (already noisy via σ=15°), sun τ=1, setting classifier τ≈0.7, sound events τ≈0.5, absolute level τ≈0.2 or off. The exponent effectively says "this evidence is worth τ independent observations".
- **Outlier floor (robust mixture).** `p = (1−ε)·model + ε·uniform`. With ε=0.1 a single contradicting term can reduce a cell's posterior at most ~10×, never to zero. This is also what lets the existing landmark `max over candidates` survive a mis-transcribed landmark.
- **Calibration without labelled field data.** YAMNet/AST sigmoid scores are not probabilities of "source within X m". Map them into a 3-level evidence (absent / weak / strong) with a hand-set confusion matrix, e.g. P(detect | source near)=0.7, P(detect | source far)=0.1. That's cruder than temperature scaling but honest given there's no calibration set. If time allows, fit a temperature on ~50 labelled clips from ESC-50 or UrbanSound8K classes.
- **Avoiding double counting.**
  - Collapse consecutive windows with the same top tag into one *event* (onset-offset). An event updates the grid once.
  - Background (5th-percentile spectrum) and setting/RT come from the same clip, so update each once per stationary location, not per 1 s frame.
  - YAMNet and AST tags for the same event are correlated: take max or average, never a product.
  - When the spoken report says "train passing" and the audio also detects a train, count it once (prefer the higher-confidence one).
- **Credibility check / conformal-style safeguard.** Report the posterior mass within the stated radius, and the predictive probability of the observed evidence `p(obs) = Σ_c p(obs|c)·prior(c)`. If `p(obs)` is very low (all hypotheses explain the data badly), flag "evidence inconsistent" in the read-back and drop the lowest-reliability term. A cheap model check that avoids confident wrong pins. A full conformal method needs calibration data we don't have (gap).

### Gaps
- No source found giving recommended tempering exponents for audio classifier evidence in localisation. The values above are engineering guesses.
- Conformal prediction for grid-posterior localisation wasn't researched in depth.

---

## 4. Minimising questions: active sensing, EIG per cost, stopping rules, passive listening, motion, best single report

### Takeaway
The current greedy "maximise expected entropy reduction" selector is theoretically well-founded: for noisy twenty-questions with entropy loss, the myopic one-step EIG policy is Bayes-optimal (Jedynak, Frazier & Sznitman 2012). The improvements are (1) divide EIG by a **cost** that makes passive listening and chirps nearly free and spoken questions expensive, (2) stop on a **posterior-mass radius**, not only entropy, and (3) get most of the information from a well-designed **first utterance template**, so the question loop often needs 0–1 questions.

### Cited Findings
- Bayesian experimental design: information gain = drop in Shannon entropy from prior to posterior. Choose the design maximising its expectation under the marginal predictive. The adaptive version is "Bayesian adaptive design". Computation is the main practical obstacle. — [Rainforth, Foster, Ivanova, Bickford Smith, "Modern Bayesian Experimental Design", Statistical Science 39(1):100–114, 2024](https://projecteuclid.org/journals/statistical-science/volume-39/issue-1/Modern-Bayesian-Experimental-Design/10.1214/23-STS915.full); [arXiv 2302.14545](https://pdf.arxiv.org/pdf/2302.14545)
- Twenty questions with noise (known noise model): any policy that myopically maximises one-step expected entropy reduction is also optimal in the fully sequential setting. Probabilistic bisection (Horstein), which asks "is it below the posterior median?", is one Bayes-optimal policy. — [Jedynak, Frazier, Sznitman, J. Appl. Prob. 49(1):114–136, 2012](https://www.cis.jhu.edu/~bruno/JedynakPaper-02-2011.pdf); [Cambridge](https://resolve.cambridge.org/core/journals/journal-of-applied-probability/article/twenty-questions-with-noise-bayes-optimal-policies-for-entropy-loss/6F51F7E5CE7D0B1ED4CEF0221D0B6E08)

### Inferences
**(a) Cost-aware selection.** Score each action `a` by `EIG(a) / cost(a)`, or `EIG(a) − λ·cost(a)`, over a unified action set:

| Action | Rough cost (buddy attention) | Typical EIG | Notes |
|---|---|---|---|
| Keep listening passively 30–60 s | ~0 | small per window, accumulates | always on during first aid |
| Emit chirp (phone speaker) | ~0 attention, small signature risk | setting / echo distance | do automatically once |
| Yes/no spoken question | high (hands busy, ~5–10 s) | ≤ 1 bit by construction | max 1 bit = halves posterior |
| Clock-direction question ("where's the church?") | higher (look + speak) | can be several bits | bearing answer worth more than yes/no |

Because a yes/no answer carries at most 1 bit, going from a 300 m to a 60 m radius (area ratio 25, ≈4.6 bits) needs ≥5 perfect binary questions. Clock-bearing questions (12 outcomes, ≈3.6 bits max) are far more efficient. Prefer "give me a clock direction to X" over "left or right?" whenever the posterior is multi-modal across a wide area. Use binary questions only to resolve 2–3 blobs.

**(b) Stopping rules.** Stop asking when any of these hold:
- 2-σ radius (or radius holding 95% posterior mass) < 75 m;
- the best action's EIG < ~0.3 bit (asking won't help);
- 3 questions asked;
- the user is silent or says "busy". Then fall back to passive listening and re-evaluate every 60 s.

Also gate on **decision relevance**: if all remaining modes lie within the same evac route or pickup point, stop. Value of information is zero when the decision (which collection point, which route) wouldn't change.

**(c) Passive accumulation during first aid (minutes).**
- Sliding windows of 10 s, an event detector and setting classifier, one grid update per *distinct event* (see §3).
- **Timetabled sources**: RER A crosses Vincennes, metro line 1 runs underground to Château de Vincennes, plus bus lines. A detected train or bus at time t gives a likelihood near the line, weighted by service frequency. With the scheduled time it can also say which direction. Church bells on the hour are anchored at known belfries, and the number of strikes confirms the clock.
- Silence also carries information. Not hearing any train in 5 minutes near a line with 3-minute headways is a negative observation: `p(no detection | near rail) = exp(−T/headway·p_det)`.
- Run passive updates as a background task that never speaks unless the posterior changes mode or the radius crosses 75 m ("position refined, 70 metres").

**(d) Motion.** If the casualty is carried along a path, the buddy's short phrase ("moving north along the road, 100 m") or a phone step count and compass give a transition kernel. Shift the grid by the motion vector convolved with a Gaussian (σ ≈ 30% of the distance), as an HMM predict step, then keep fusing. Landmarks seen from two points act like a doubled baseline and resolve ambiguity, as in classic intersection/resection.

**(e) Best single utterance.** Since EIG per spoken second is what matters, train users on a fixed template that front-loads the high-information items:
"[MIST] … Position: [nearest named feature I'm on or next to]. [Landmark A] at [clock], [Landmark B] at [clock], [Landmark C] at [clock]. Sun at [clock]. [Distance to nearest] about [N] metres. I hear [train/bells/traffic]."
- Three landmarks spread over 90° or more give a well-conditioned resection, the same geometry advice as FM 3-25.26 resection. Clustered landmarks give a poor fix.
- One stated distance ("church about 200 m") removes the scale ambiguity that bearings alone can't fix without a heading.
- The sun fixes heading, so 2 landmarks are enough (already in CLAUDE.md §6.4).
- Naming the feature you're *on* (road name, park, tree line, rail line) is a strong linear constraint that clock bearings don't give.

### Gaps
- No published cost model for "attention cost of a question vs first aid" was found. The values above are heuristic.
- No source found quantifying the information content of 9-line or MIST reports.
- RATP/SNCF timetables (GTFS) for RER A, metro 1 and bus lines weren't checked here. The IDFM GTFS feed is a likely source.

---

## 5. Military doctrine on reporting location without GPS, and maximising information in one utterance

### Takeaway
Doctrine gives three ways to fix a position without GPS: **resection** (azimuths to 2–3 known points from your unknown position), **polar plot** (known point + azimuth + distance), and **terrain association**. MEDEVAC Line 1 expects an MGRS grid "as accurate as possible" (6-digit ≈ 100 m or 8-digit ≈ 10 m). Pothenot effectively converts a resection-style or polar description into that grid. The ideal single utterance is a voice resection: 2–3 well-spread named landmarks with bearings, plus one distance.

### Cited Findings
- TC 3-25.26 (Nov 2013) supersedes FM 3-25.26 (2005). Chapter 6 covers intersection and resection, and Chapter 10 terrain association. The 2001 edition lists "Intersection, Resection, Modified Resection, Polar Coordinates". — [TC 3-25.26 PDF](https://armyrotc.mst.edu/media/academic/armyrotc/documents/manualsadpadrpfmetc/TC%203-25.26.pdf); [FM 3-25.26 (archive.org)](https://archive.org/download/MManuals/Fm3-25.26MapReadingAndLandNavigation.pdf)
- Resection: occupy the unknown point and take sightings to known points. Polar plot: location from a known start, an azimuth and a distance. Terrain association is "more forgiving of mistakes and far less time-consuming than dead reckoning". — [GlobalSecurity FM 3-25.26 ch. 11](https://www.globalsecurity.org/military/library/policy/army/fm/3-25-26/ch11.htm); [Wikipedia, angular resection](https://www.wikipedia.org/wiki/Angular_resection)
- 9-line MEDEVAC Line 1: location of the pickup site, "use as accurate a grid position as possible". Secondary sources disagree on 6-digit (≈ within 200 m) vs 8-digit grids, and say to include the 100 km square identifier. Line 1 is the **pickup site**, not necessarily the incident site. Primary ATP 4-02.2 text wasn't retrieved. — [UN 9-line PDF](https://indico.un.org/event/1003005/attachments/2107/6975/13%209line.pdf); [armystudyguide 9-line](https://www.armystudyguide.com/content/army_board_study_guide_topics/First_Aid/9-line-medevac-request.shtml); [Army.mil 7ATC](https://www.army.mil/article/189003/7atcs_safety_focus_9_line_medevac)

### Inferences
- The pitch can say Pothenot does "spoken resection" (the exact meaning of "problème de Pothenot") and outputs a Line 1 grid, with the radius as the honest precision (8-digit when < ~30 m, else 6-digit).
- Clock directions are a doctrinal reference style used by soldiers, so no new training is needed. The template in §4(e) maps onto resection (bearings to known points) + polar plot (one distance) + terrain association (feature I'm on).
- Since Line 1 is the pickup site, the system could propose the nearest suitable pickup point (open area, road access) to the posterior mode. That's cheap extra value with the existing OSM data.

### Gaps
- Primary ATP 4-02.2 and TC 3-25.26 full text weren't extracted, so the step-by-step procedures are secondary-sourced.
- No NATO doctrine found specifically for "describing position by voice under GPS denial" beyond general land navigation.

---

## 6. Recommendations ranked by gain/effort for a 1-day hackathon

### Takeaway
Do the cheap robustness and cost-aware items first: tempered/floored likelihoods, event de-duplication, clock-bearing questions, a better stop rule and the utterance template. Then add the geometric canyon proxy and the rail/bell timetable evidence. Skip full acoustic simulation and absolute-dB matching.

### Cited Findings
- Myopic EIG is optimal for noisy twenty-questions, so keep the current selector and just extend its action set. — [Jedynak et al. 2012](https://www.cis.jhu.edu/~bruno/JedynakPaper-02-2011.pdf)
- Ambient audio alone reaches room or place level only (69% / 33 rooms), so use it as region evidence. — [Tarzia et al. 2011](https://users.cs.northwestern.edu/~pdinda/Papers/mobisys11.pdf)
- Street RT is 1–3 s and grows with height and enclosure, so a categorical setting proxy from geometry is justified. — [Wu, Kang, Jin 2017](https://discovery.ucl.ac.uk/10054793/1/Hupeng%20WU%20-%20street-parameter-paper-whiterose2.pdf)
- Power likelihoods give robustness to misspecification. — [Miller & Dunson 2019](https://ar5iv.arxiv.org/html/1506.06101)

### Inferences (ranked list)
1. **Floor + temper every likelihood term** (≈30 min, high gain). One line in `localise.py`: `L = eps + (1-eps)*L**tau`. Prevents a bad tag from killing the true cell.
2. **Event de-duplication and once-per-clip updates** (≈1 h, high gain). An event table keyed by (class, onset). Avoids overconfident false shrinkage.
3. **Add clock-bearing questions plus a cost-weighted EIG** (≈1 h, high gain). Up to ~3.6 bits per answer vs ≤1 bit for yes/no, and fewer exchanges, which is the stated goal.
4. **Stop rule = 95%-mass radius < 75 m OR best EIG < 0.3 bit OR 3 questions OR user busy** (≈30 min, medium-high gain).
5. **Field "report template" card plus prompt support for stated distance and "I'm on <feature>"** (≈1 h, high gain in the demo). Most localisation done in utterance 1.
6. **Geometric canyon proxy per cell** (H/W, facade distance in 8 rays, openness), mapped to the existing setting classes (≈2 h, medium gain). Precompute once into `.npy`.
7. **Rail / bell / bus evidence with negative evidence over time** (≈2 h, medium gain near RER A / metro 1 / belfries). A Poisson presence model.
8. **Background passive loop** (re-fuse every 60 s, speak only on a mode change or a radius crossing) (≈1–2 h, medium gain, strong pitch story: "zero questions if you're busy").
9. **Motion HMM predict step** (≈1 h, low-medium gain for the demo).
10. **Skip:** NoiseModelling or ray tracing over the whole area, absolute-dB matching against Lden (phone ±4 dB error, map 0–4 dB error), learned calibration without data.

### Gaps
- None of the gain estimates are empirically measured. Validate with the synthetic test in `tests/` by comparing the number of questions to 75 m with and without each item.
