# Audio geolocation and location fingerprinting: how far can ambient sound alone narrow down where a recording was made?

Scope: relevance to Pothenot (GPS-denied casualty reporting, a few km² around Vincennes / east Paris). The app already classifies sound events (YAMNet + AST) and matches them against OSM noise sources. Scale tags used below: **[GRID/CONTINENT]**, **[KM-SCALE]** (25 km and up), **[ROOM/STORE]** (needs a pre-recorded fingerprint database), **[STREET-SCALE]**.

## 1. Electrical Network Frequency (ENF): can mains hum place a recording?

### Takeaway
ENF tells you **which synchronous grid** a recording came from (about 85–92% accuracy on benchmarks), and **when** it was made (about 1 s timing accuracy against operator reference data). It cannot locate anything within a city. All of continental Europe, Paris included, is one synchronous 50 Hz grid, so for Vincennes ENF gives no spatial information at all. Its only possible use is as a timestamp or authenticity check. **[GRID/CONTINENT]**

### Cited Findings
- InterGridNet (2025, CNN) reaches 92% overall accuracy at classifying which of 9 grids (A–I, the SP Cup 2016 benchmark) a recording comes from. — [arXiv 2502.10011](https://arxiv.org/html/2502.10011v1)
- Earlier multi-grid work reached 88.4% on power recordings and 84.3% on audio recordings across 11 grids. These are different grid sets, so the figures are not directly comparable with the 92%. — [arXiv 2502.10011](https://arxiv.org/pdf/2502.10011)
- Intra-grid localisation is "more challenging due to the highly subtle distinctions in the ENF signatures". — [arXiv 2502.10011](https://ar5iv.labs.arxiv.org/html/2502.10011)
- Feasibility study on intra-grid location (2021, US Eastern grid, 5 cities hundreds of km apart, 4 anchors plus 1 query): ENF correlation falls as distance grows, which enables a coarse trilateration. Mean distance-estimation error was about 24 miles for the Princeton–Atlanta pair (15-min segment). Queries were 4–8 min long, and longer was better. — [Feasibility Study on Intra-Grid Location Estimation (arXiv 2105.00668)](https://ar5iv.labs.arxiv.org/html/2105.00668)
- The same study found that localisation needs about 20 dB SNR, approaching clean-signal performance above about 30 dB. Audio-derived ENF had only about 15 dB SNR (16 s frames) or about 9 dB (8 s frames). The authors conclude it is "not yet practical for typical audio or video recordings" without a breakthrough in extraction. — [arXiv 2105.00668](https://ar5iv.labs.arxiv.org/html/2105.00668)
- A 2025 Scientific Reports paper extracts ENF from smartphone videos (Australian Eastern grid), compared against power-supplier anchor data. Sensor noise and aliasing make this hard. — [PMC12137870](https://pmc.ncbi.nlm.nih.gov/articles/PMC12137870)
- Timing: cross-correlating estimated ENF with grid-operator reference ENF resolves timing errors at about the 1 s level. Continental Europe holds deviations from 50 Hz to roughly 10–50 mHz. — [Seismica (McGill)](https://seismica.library.mcgill.ca/article/download/1082/1229/7414)
- ENF is used in journalism to check leaked audio and video for recording time and continuity, but use is "mostly ad hoc". — [GridRadar blog](https://gridradar.net/en/blog/post/electric-network-frequency-analysis-20)
- ENF appears in audio near mains-powered devices. In video it shows up at 100/120 Hz through light flicker, and several seconds of clip are needed per frequency estimate. The University of Maryland frames this as a way to verify Ukraine-related media. — [UMD ECE news](https://ece.umd.edu/news/story/electric-power-grid-signatures-may-aid-in-image-and-video-verification)

### Inferences
- In the field, a casualty outdoors in a park or tree line will usually have no mains hum at all. ENF needs proximity to powered equipment (indoors, near transformers or lighting).
- Even with a perfect ENF trace, Vincennes and the whole of continental Europe (Portugal to Poland, plus the synchronised Ukraine and Moldova grid) give the same answer. Spatial value for Pothenot is **zero**. ENF could at most timestamp a report or detect a replayed or forged recording, which is a security feature and not a localisation one.

### Gaps
- I found no public evidence that Ukrainian or other militaries use ENF for geolocation. The search returned only terrain-matching and OSINT examples. Treat claims of military ENF geolocation as unverified.
- I found no figure for the minimum recording length needed for a reliable timestamp from phone-mic audio in Europe.

## 2. Deep-learning audio geolocation and soundscape mapping (Freesound, iNat, GeoCLAP, PSM)

### Takeaway
State-of-the-art audio-only geolocation is **continent and country scale**. The best 2025 model has a median error of about 1,082 km and places only 6.4% of clips within 25 km. Classifying which city a recording came from (among 10–12 European cities) reaches only about 50–56%. GeoCLAP and PSM are *soundscape mapping* models: they predict what a place sounds like from satellite imagery, and they report retrieval recall, not localisation error. **Nothing published works at street or block scale.** **[KM-SCALE]**

### Cited Findings
- *Audio Geolocation: A Natural Sounds Benchmark* (2025, iNatSounds: about 230K clips, average 20 s, 5,500+ species). Audio-only results:
  - **AG-CLIP** (proposed, GeoCLIP-style retrieval plus a species-checklist loss): median error 1,082 km; 6.4% within 25 km; 17.2% within 200 km; 41.0% within 750 km.
  - Hierarchical H3 classification: median 1,117 km; 0.3% within 25 km.
  - Haversine regression: median 1,602 km.
  - **GeoCLAP off the shelf:** median 6,856 km; 0.2% within 25 km, close to the random baseline (7,475 km). The authors attribute this to domain shift from GeoCLAP's urban training data.
  - The finest threshold reported is 25 km. No 1 km or street-level results are given.
  - Source: [arXiv 2505.18726](https://arxiv.org/html/2505.18726v2)
- GeoCLAP (Khanal et al., BMVC 2023) aligns geotagged audio, text and overhead imagery from SoundingEarth in a contrastive tri-modal embedding, and uses it to build zero-shot soundscape maps from text or audio queries. Its headline metric is image-to-audio Recall@100, up from 0.256 to 0.450. — [arXiv 2309.10667](https://arxiv.org/abs/2309.10667); code at github.com/mvrl/geoclap
- PSM (Khanal et al., ACM MM 2024) uses probabilistic embeddings over multi-scale satellite imagery plus metadata (location, time, source). It introduced **GeoSound**, with 300k+ geotagged audio clips paired with low- and high-resolution satellite imagery, and beats GeoCLAP at cross-modal retrieval. — [arXiv 2408.07050](https://arxiv.org/html/2408.07050v1); [project page](https://subash-khanal.github.io/PSM/index.html)
- Earlier GeoCLAP training used about 35k SoundingEarth samples. — [PSM paper](https://arxiv.org/html/2408.07050v1)
- City classification from acoustic scenes (DCASE 2018 cities): a simple CNN reaches 50%, and multi-task learning (city plus scene) reaches 56%. — [arXiv 1905.00979](https://arxiv.org/abs/1905.00979)
- The TAU Urban Acoustic Scenes 2020 dataset includes **Paris** among 12 cities (Amsterdam, Barcelona, Helsinki, Lisbon, London, Lyon, Madrid, Milan, Prague, Paris, Stockholm, Vienna). It has 10 scene classes: airport, shopping mall, metro station, pedestrian street, public square, street with traffic, tram, bus, metro, and urban park. — [DCASE 2020 Task 1](https://dcase.community/challenge2020/task-acoustic-scene-classification)

### Inferences
- These models cannot be used for in-city localisation. The useful part is the *scene* label (park, street with traffic, metro station, pedestrian street). TAU-style acoustic scene classification is a mature task, and it can act as a coarse **land-use prior** on Pothenot's likelihood grid: for example, "urban park" upweights the Bois de Vincennes cells and "street with traffic" upweights cells near primary roads.
- The GeoCLAP and PSM idea (predict the expected sound embedding from overhead imagery for every cell) is conceptually what Pothenot already does by hand with OSM noise sources. A hackathon-feasible version: score each grid cell by the similarity between the clip's CLAP or AST embedding and a text prompt built from that cell's OSM tags. This is unvalidated, and the published accuracy suggests weak discrimination at 20–40 m cells.

### Gaps
- I found no published audio geolocation result at a 1 km or finer threshold.
- I did not find the specific recording locations of the TAU Paris clips, or a count of geotagged Freesound or aporee clips inside the Vincennes bounding box. These would have to be queried directly through the Freesound API geotag filter.

## 3. Ambient-sound location fingerprinting (SurroundSense, Batphone/ABS)

### Takeaway
Fingerprinting works at **room or store scale**, but only against a **pre-recorded database of the same places**, and it is fragile to noise. SurroundSense reached 87% across 51 stores using sound, light, colour and motion together. Batphone's acoustic background spectrum (ABS) reached 69% across 33 rooms combined with Wi-Fi, and only 40% in an independent re-test. Neither is usable for an un-surveyed outdoor area under fire. **[ROOM/STORE]**

### Cited Findings
- SurroundSense (Duke, MobiCom 2009) fuses microphone, camera (light and colour) and accelerometer into a fingerprint matched on a server. It reported **87% average accuracy across 51 stores** using all modalities, and could distinguish adjacent shops on either side of a wall. The phone had to be held camera-down. — [ScienceDaily](https://www.sciencedaily.com/releases/2009/09/090924093345.htm); [phys.org](https://phys.org/news/2009-09-room-ambience-fingerprinted.pdf)
- Batphone / ABS (Tarzia et al., MobiSys 2011) builds a fingerprint from a 10 s sample (0–7 kHz) and matches it with k-NN. Adding ABS improved room-level accuracy **from 30% (Wi-Fi only) to 69% (Wi-Fi plus ABS)** across 33 rooms. — [MobiSys 2011 paper](https://users.cs.northwestern.edu/~pdinda/Papers/mobisys11.pdf)
- An independent 2018 re-test (iPhone 6s, 5 rooms) gave Batphone **40%** accuracy in one room even in quiet conditions, because neighbouring rooms have similar spectra. It "fails in the presence of chatters and ambient music". — [Deep Room Recognition Using Inaudible Echos (arXiv 1809.00531)](https://arxiv.org/pdf/1809.00531)
- A later patent notes that these systems need cumbersome "fingerprint factories" (surveys of every location). — summarised from [USPTO 9332363](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/9332363)

### Inferences
- Fingerprinting presumes someone has already walked the area and recorded it. In an adversary-held or unsurveyed area this is impossible. Around Vincennes for a demo it would be possible but pointless: 20–40 m outdoor cells change with traffic, weather and time of day.
- The transferable lesson: stationary background spectra (HVAC, transformer hum, fountain, highway roar) are informative only relative to *known* sources. That argues for Pothenot's current approach (sound events matched to mapped sources) over raw spectral fingerprints.

### Gaps
- I found no outdoor, street-scale ambient fingerprinting study with reported metre-level accuracy.

## 4. Noise maps and soundscape datasets for Paris and Vincennes

### Takeaway
Strategic noise maps under the EU Environmental Noise Directive (2002/49/EC) exist for Paris and the Métropole du Grand Paris. They give Lden and Lnight from road, rail and air traffic as **open shapefiles plus WMS/WFS** under Licence Ouverte 2.0. Bruitparif models at **5 m × 5 m** resolution and runs about 200–219 permanent sensor stations. These are *modelled long-term averages* (Lden). A single phone recording, uncalibrated and lasting seconds, can only be compared coarsely: "loud road-dominated" versus "quiet park interior", and rail versus road spectra. **[STREET-SCALE as a prior, weak]**

### Cited Findings
- data.gouv.fr: *Lot de données relatives aux cartes de bruit stratégiques pour Paris*, producer DRIEAT Île-de-France, updated 27 May 2025. It covers roads with more than 3M vehicles/year, railways with more than 30,000 trains/year, and agglomerations of more than 100k inhabitants. Formats: 2 Esri shapefiles plus 2 WMS and 2 WFS APIs. Licence Ouverte / Open Licence 2.0. — [data.gouv.fr](https://www.data.gouv.fr/datasets/lot-de-donnees-relatives-aux-cartes-de-bruit-strategiques-pour-paris)
- The national dataset of non-conceded road and rail networks has type A and type C maps, Lden and Lnight, in ESRI Shapefile, with an .xlsx descriptive table. — [data.gouv.fr CBS](https://www.data.gouv.fr/datasets/cartes-de-bruit-strategiques-des-reseaux-routiers-et-ferroviaires-non-concedes-directive-europeenne-2002-49-ce)
- Bruitparif's air-and-noise maps are hosted at carto.bruitparif.fr at **5 m × 5 m** resolution. Only Lden was kept for the global transport noise map. — [Bruitparif methodology note](https://www.bruitparif.fr/pages/En-tete/800%20Le%20bruit%20en%20%C3%8Ele-de-France/300%20carto-air-bruit-en-idf/700%20Principaux%20r%C3%A9sultats%20et%20statistiques/Note%20m%C3%A9thodologique%20et%20de%20r%C3%A9sultats%20cartographie%20air-bruit.pdf)
- Bruitparif reports 219 permanent stations for 2025 ("densest network in the world"). Its brochure describes the RUMEUR network of about 200 stations. — [Bruitparif 2025 report](https://www.bruitparif.fr/pages/En-tete/400%20Nos%20publications/900%20Rapports%20d'activit%C3%A9/2025%20R%C3%A9sonance%20-%20L'essentiel%20de%202025.pdf)
- A data.gouv.fr dataset from Bruitparif gives annual average Lden and Ln per station type in Paris (WHO 2018 guideline: Lden < 53 dB(A)). — [data.gouv.fr](https://www.data.gouv.fr/datasets/662732be4dd2b5b9fe906c8d)
- Strategic noise maps of the 4th round (E4) for the Métropole du Grand Paris were presented by Bruitparif in 2023. — [Bruitparif CSB E4 MGP](https://bruitparif.fr/pages/En-tete/400%20Nos%20publications/650%20Diagnostics%20territoriaux%20sur%20le%20bruit%20et%20ses%20impacts/2023-09-07%20-%20Pr%C3%A9sentation%20des%20CSB%20E4%20MGP.pdf)
- TAU Urban Acoustic Scenes 2020 includes Paris recordings in 10 scene classes. — [DCASE 2020](https://dcase.community/challenge2020/task-acoustic-scene-classification)

### Inferences
- **How to use the maps in a hackathon:** download the WFS or shapefile Lden isophone layer for road and rail. Each grid cell gets an expected Lden band (for example 55–60 or 70–75 dB). A phone mic is uncalibrated (offsets of ±5–10 dB are typical, which is my estimate, not sourced), so use **relative** cues instead. Did the classifier hear rail or tram? Is road traffic dominant or faint? Rank the cells by consistency. That is coarse and works best as a soft likelihood term with a broad σ.
- Lden is a 24-h weighted average, so it misrepresents the instantaneous level at 3 a.m. or during a lockdown or conflict, when traffic may be absent. The *source geometry* (where the roads and rails are, already in OSM) carries most of the usable information. The maps add mainly a propagation-aware "how far does this road's noise reach" footprint, which is useful for the "can you hear X" likelihood without writing a propagation model.
- SONYC and UrbanSound8K are New York datasets, useful only for training event classifiers (sirens, jackhammers, engines), not for Paris locations.

### Gaps
- I could not confirm whether the DRIEAT Paris dataset covers Vincennes (Val-de-Marne, 94) or only Paris intra-muros. The Métropole du Grand Paris E4 maps should cover Vincennes, but I did not find a direct download link. Check carto.bruitparif.fr or data.gouv.fr ("bruit Val-de-Marne" / "Métropole du Grand Paris CBS").
- I did not verify current SONYC dataset licensing or Freesound geotag density around Vincennes.

## 5. Time-based acoustic clues (bells, rail timetables, aircraft, school bells)

### Takeaway
Time-structured sounds are the most promising audio cue for **street-scale** discrimination near Vincennes. They are not location fingerprints by themselves, but they confirm *which* mapped source is audible when combined with the time. The literature I found covers the physics (bell partials, flight altitudes) but **no off-the-shelf system** that identifies a specific church by its bell or locates a listener from transit periodicity.

### Cited Findings
- **Bells:** a bell's perceived "strike note" is often a *virtual* pitch inferred from partials, not a spectral peak. The practical acoustic signature is the pattern of partial ratios (hum, prime, tierce, quint, nominal). One modelled bell had ratios of 0.54 / 1.00 / 1.18 / 1.58 / 1.93. In Terhardt and Seewann's study of 137 historic bells, 3% had no clear strike note. — [Hibberts: Terhardt & Seewann 1984](https://www.hibberts.co.uk/terhardt-and-seewan-1984/); [Physics Today](https://physicstoday.aip.org/quick-study/what-did-the-liberty-bell-sound-like); [Wikipedia: Strike tone](https://en.wikipedia.org/wiki/Strike_tone)
- **Aircraft over east Paris:** parliamentary answers say Orly arrivals overfly communes of the eastern Paris suburbs at about 1,500–1,700 m, and Roissy and Le Bourget departures at 2,500–4,500 m. The axis depends on wind direction (east versus west configuration). Aéroports de Paris' *Vitrail* app shows real flight tracks. — [Assemblée nationale written questions](https://questions.assemblee-nationale.fr/dyn/13/questions/QANR5L13QE23660.pdf); [Ministère: riverains aéroports parisiens](https://www.ecologie.gouv.fr/politiques-publiques/riverains-aeroports-parisiens)

### Inferences
- **Church bells:** hour strikes and the Angelus (traditionally 7:00, 12:00, 19:00) are audible over a few hundred metres to about 1 km in town. That distance is my estimate and not sourced. Hearing bells at a given time therefore flags "within about 1 km of a church that rings". Identifying *which* church from its pitch would need a reference recording of each bell, so it is a fingerprint database again. Hackathon value: a bell heard at :00 yields a likelihood term "near a place_of_worship with bells" with a radius of about 500–1,000 m. Many Paris churches no longer ring regularly, so this is a weak cue.
- **Metro, RER, tram:** near Vincennes, RER A (Vincennes station), metro line 1 (Château de Vincennes terminus, largely underground) and SNCF lines could be audible. RER A runs every few minutes at peak, so the rail class detected repeatedly at a 2–5 min period is consistent with RER A near the surface or viaduct sections. Underground metro is mostly inaudible from the street except near ventilation shafts and entrances. These timetable figures are not verified here, and an IDFM GTFS feed would supply them.
- **Aircraft:** at 1,500–4,500 m, overflights cover tens of km². They constrain the area only to "east Paris under an approach corridor", which is useless at block scale. They can confirm wind configuration but not position.
- **School bells and playground noise:** these cues depend on the time and day (weekdays, school hours) and are audible over about 100–300 m (my estimate). Children's voices plus a weekday daytime timestamp could support a term "near amenity=school".
- **General pattern:** combine *event class × timestamp × OSM source with a schedule* into a likelihood with a distance-decay audibility radius per class. This is the same max-over-candidates structure as Pothenot's landmark likelihood.

### Gaps
- I found no published work that identifies a specific church from its bell recording in the wild, and no published audibility ranges for bells, RER or school bells in Paris.
- I did not retrieve the RER A, metro 1 or tram timetables, or Vincennes church ringing schedules. Sources would be IDFM GTFS open data and the parishes.

## 6. What is realistically achievable in one day with existing data

### Takeaway
Audio alone will not locate a casualty to street level. Realistically it provides **soft priors**: scene type (park versus street versus station), audible source classes (rail, primary road, bells, school, water) matched to OSM or noise-map footprints, and time gating. Combined with Pothenot's spoken landmark bearings, these priors help break ties between ambiguous blobs. They do not replace the ask-back loop.

### Cited Findings
- Best audio-only geolocation: 6.4% of clips within 25 km (2025). — [arXiv 2505.18726](https://arxiv.org/html/2505.18726v2)
- Fingerprinting requires a surveyed database and gets 40–87% at room or store level. — [Batphone](https://users.cs.northwestern.edu/~pdinda/Papers/mobisys11.pdf); [arXiv 1809.00531](https://arxiv.org/pdf/1809.00531); [SurroundSense](https://www.sciencedaily.com/releases/2009/09/090924093345.htm)
- ENF has grid-level identification only, and intra-grid localisation is impractical from audio (needs about 20 dB SNR, while audio gives about 9–15 dB). — [arXiv 2105.00668](https://ar5iv.labs.arxiv.org/html/2105.00668)
- Open noise maps for Paris come as shapefile and WFS (Licence Ouverte 2.0), and Bruitparif models at 5 m resolution. — [data.gouv.fr](https://www.data.gouv.fr/datasets/lot-de-donnees-relatives-aux-cartes-de-bruit-strategiques-pour-paris); [Bruitparif note](https://www.bruitparif.fr/pages/En-tete/800%20Le%20bruit%20en%20%C3%8Ele-de-France/300%20carto-air-bruit-en-idf/700%20Principaux%20r%C3%A9sultats%20et%20statistiques/Note%20m%C3%A9thodologique%20et%20de%20r%C3%A9sultats%20cartographie%20air-bruit.pdf)

### Inferences (one-day plan, ranked by value per hour)
1. **Audibility likelihood from OSM sources (already partly built).** For each detected class (rail, road, bells, water, construction, children), multiply the grid by a soft term that is high within the class's audibility radius of a matching OSM feature, and low (but not zero) elsewhere. Also model "not heard" as a mild penalty near loud sources, which mirrors the brief's "can't see X" rule.
2. **Noise map as a footprint (2–3 h).** Pull the Lden road and rail layers via WFS, rasterise them onto the grid, and use "loud road heard at a high relative level" as more likely in ≥65 dB Lden cells. Treat the phone level as relative only.
3. **Scene prior (1 h).** Map the AST or YAMNet output to TAU-like scenes (park / street with traffic / pedestrian / station), then onto OSM land use (leisure=park, landuse=forest, highway=primary).
4. **Time gating (1 h).** Accept the bells class only near churches, and use it more strongly at :00 and :30. Accept school noise only on weekdays during the daytime.
5. **Skip:** ENF (no spatial value inside the European grid), GeoCLAP/PSM inference (continent-scale, heavy models), and fingerprint databases (need surveys).
- **Pitch framing:** "Sound narrows the search area. Landmarks and the question loop pin it down." Avoid claiming audio-only street-level localisation, because the literature does not support it.

### Gaps
- There is no measured accuracy for the combined sound-event and OSM audibility approach in a real urban area. Pothenot would have to validate it with its own synthetic tests and a walk around the Château.
