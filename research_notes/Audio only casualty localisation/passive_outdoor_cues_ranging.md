# Passive outdoor acoustic cues for single-phone distance/proximity estimation (Pothenot, Vincennes)

Scope: how one uncalibrated phone recording can give per-grid-cell likelihoods of "distance to nearest source of class X" (roads, rail/tram, aircraft, bells, water, birds/parks, gunfire), with no direction and no questions asked. Hackathon feasibility flagged as **[1-DAY]** (doable Saturday) or **[RESEARCH]**.

Note on sourcing: about 15 searches/fetches. Several primary documents (ISO 9613-1 tables, CNOSSOS coefficient tables, the VERA PDF) could not be read in full. Values not taken from a fetched source are labelled as inferences or gaps.

---

## 1. Road traffic noise: level vs distance, spectrum, typical levels, phone accuracy

### Takeaway
Steady traffic on a road acts as a line source (about -3 dB per doubling of distance, about -4.5 dB over soft ground). A single vehicle acts as a point source (-6 dB per doubling). So the level falls only about 10–15 dB between 10 m and 160 m. Combined with ±2–10 dB uncertainty on an uncalibrated phone, absolute dBA alone can only sort cells into coarse bands: "next to a busy road", "one block back", "deep inside a park/courtyard". Ratios between frequency bands and the temporal pattern (steady hum vs discrete pass-bys) are more robust than absolute level.

### Cited Findings
- Point source (single vehicle pass-by): about 6 dBA per doubling of distance (spherical spreading). Continuous traffic stream (line source, cylindrical spreading): 3 dB(A) per doubling — [FHWA noise policy guide](https://www.fhwa.dot.gov/environMent/noise/regulations_and_guidance/polguide/polguide02.cfm); [HK EPD Environmental Noise](https://www.epd.gov.hk/epd/noise_education/web/ENG_EPD_HTML/m1/intro_6.html)
- The line-source result holds because individual vehicles are incoherent point sources along the road — [NASA TM (19920005563)](https://ntrs.nasa.gov/api/citations/19920005563/downloads/19920005563.pdf)
- Over "soft" ground (grass, crops, ploughed land) the recommended drop-off for highways is 4.5 dBA per doubling instead of 3 — [FHWA barrier design guidance](https://www.fhwa.dot.gov/Environment/noise/noise_barriers/design_construction/design/design03.cfm)
- 4.5 dB is a simplified "modified line source" rule. Current practice models ground type more finely — [Acoustics Today 2016 Winter p.42](https://acousticstoday.org/issues/2016AT/2016Winter/files/basic-html/page42.html). A 1970s study found the line-source assumption may fail at low traffic volumes, where discrete vehicles dominate — [same source](https://acousticstoday.org/issues/2016AT/2016Winter/files/basic-html/page42.html)
- CNOSSOS-EU (EU Directive 2015/996) road emission: sound power per metre of road per octave band (63 Hz–8 kHz) for a line source carrying Q_m vehicles/h of category m at mean speed v_m. Per-vehicle rolling noise = A_R,i,m + B_R,i,m·log10(v/70) + corrections (temperature, surface). Propulsion noise uses A_P + B_P·(v−70)/70. The total for categories 1–3 is the energetic sum of the two; two-wheelers use propulsion only. Speeds below 20 km/h are clamped to 20 km/h. Source heights are about 0.05 m (rolling) and 0.3–0.75 m (propulsion) — [CadnaA CNOSSOS-EU Road doc](https://doku.datakustik.com/CadnaA/en/Str_CNOSSOS.html); [JRC CNOSSOS-EU Reference Report](https://circabc.europa.eu/sd/a/6004362a-9169-4aed-ba33-73b46081f059/CNOSSOS-EU%20JRC%20Reference%20Report_V3_22%20September_2011_without%20authors.pdf)
- Bruitparif runs near-real-time CNOSSOS-EU maps of the Boulevard Périphérique, using Paris traffic counts updated every 3 min. The study strip is 170–500 m each side of the road. The mean night level at Porte d'Auteuil was 76.4 dB in 2022. The French road Lden limit is 68 dB(A), and the WHO recommends below 53 dB(A) — [Bruitparif CFA 2025 article](https://www.bruitparif.fr/pages/En-tete/800%20Le%20bruit%20en%20%C3%8Ele-de-France/600%20Les%20observatoires%20sp%C3%A9cifiques/900%20L'observatoire%20du%20bruit%20du%20boulevard%20p%C3%A9riph%C3%A9rique/2025-04-27%20-%20Article%20pr%C3%A9sent%C3%A9%20au%20CFA%20-%20Cartographie%20dynamique%20du%20bruit%20associ%C3%A9%20au%20trafic%20routier%20du%20BP.pdf); [Bruitparif 2011 BP study](https://www.bruitparif.fr/pages/En-tete/400%20Nos%20publications/700%20Rapports%20d'%C3%A9tude/2011-04-01%20-%20Impact%20potentiel%20de%20diverses%20mesures%20de%20r%C3%A9duction%20du%20bruit%20sur%20le%20boulevard%20p%C3%A9riph%C3%A9rique%20parisien.pdf)
- Strategic noise maps for Paris/Île-de-France (Lden per road) are published by Bruitparif and on data.gouv.fr — [data.gouv.fr dataset](https://www.data.gouv.fr/datasets/662732be4dd2b5b9fe906c8d); [Paris noise page](https://www.paris.fr/pages/bruit-et-nuisances-sonores-162)
- Atmospheric absorption (ISO 9613-1) is tabulated for 50 Hz–10 kHz, -20 to +50 °C and 10–100 % RH at 1 atm. The standard was confirmed in 2021 — [ISO 9613-1 page](https://www.iso.org/standard/17426.html)
- Approximate absorption at 20 °C: about 5.6 dB/km at 1 kHz and about 90–105 dB/km at 4 kHz (40–50 % RH), i.e. about 0.56 vs about 9–10 dB per 100 m. The table header is hard to read, so verify — [Stanford CCRMA, Air Absorption](https://ccrma.stanford.edu/~jos/pasp/Air_Absorption.html). At 8 kHz, absorption can reach about 5 dB/100 m (20 °C, 10 % RH). Around 2 kHz it is about 0.25 dB/100 m (30 % RH) — [SFU Handbook for Acoustic Ecology, Sound Propagation](https://www.sfu.ca/sonic-studio-webdav/handbook/Sound_Propagation.html). At 500 Hz it is 2.7 dB/km (10 °C, 50 % RH) — [USDA Forest Service helo appendix 5](https://www.fs.usda.gov/t-d/programs/im/sound_measure/helo_appendix5.shtml)
- Reference calculator implementing ANSI S1.26 / ISO 9613-1 — [Penn State, Absorption and Attenuation of Sound in Air](https://www.acs.psu.edu/drussell/Demos/Absorption/Absorption.html)

### Inferences
- **Level model per grid cell [1-DAY]:** for each road segment class (OSM `highway=motorway/trunk/primary/secondary/tertiary/residential`), assign a reference level L_ref at 10 m. Placeholder values to tune: primary about 70–75 dBA, secondary about 65, residential about 55. Predicted level at a cell: L(d) = L_ref − 10·k·log10(d/10), with k = 1 (3 dB/doubling) on hard urban ground and k = 1.5 over parkland. Add a shielding penalty of about −10 to −20 dB when building footprints block the line of sight. The cell's predicted total is the energetic sum over all segments within about 1 km. The likelihood is N(measured − predicted − offset; σ), with σ ≈ 5–6 dB and the unknown phone offset marginalised or fixed by calibration (section 9). The barrier figure is general noise-control practice, not taken from a fetched source here.
- Because the decay is logarithmic, 3 dB of level error equals a factor of 2 in distance on a line source. **Absolute level alone gives distance to ±100 % at best.** Useful mainly as a "near a main road (<50 m) vs not (>200 m)" classifier.
- **Spectral tilt as a distance cue:** air absorption differs by about 9 dB/100 m between 1 kHz and 4 kHz (CCRMA values). So the ratio of the 4 kHz band to the 1 kHz band from traffic falls by about 1 dB per 10 m beyond the first few tens of metres, plus ground-effect dips (typically 200–800 Hz). Band ratios cancel the phone's broadband gain offset, though not its frequency response. Usable as a weak secondary feature [1-DAY as a feature, RESEARCH to calibrate].
- **Temporal statistics [1-DAY]:** near a busy road the level is steady (L10−L90 small, continuous hum). Far away, or near a quiet street, you get discrete peaks over a low background (L10−L90 large). This directly reflects the line-source vs discrete-point-source regime and does not depend on calibration.
- Use the Bruitparif/EU Lden raster, if downloadable, as a ready-made prior map for "expected level at each cell". It already includes CNOSSOS propagation and building shielding. Daytime instantaneous LAeq is roughly Lden minus a few dB. The relationship needs tuning and is not sourced.

### Gaps
- Exact CNOSSOS coefficient values (A_R, B_R, A_P, B_P per band) were not retrieved. They are in the JRC report appendix / Directive 2015/996 annex.
- No source found that measured distance-to-road inference accuracy from a phone recording.
- The full ISO 9613-1 table was not retrieved.

---

## 2. Single-vehicle pass-by: Doppler and level profile for closest-approach distance

### Takeaway
One microphone can estimate a vehicle's speed and time of closest approach from the Doppler curve or the level envelope. Closest-approach distance (CPA) can also be recovered in principle, because the steepness of the frequency/level transition scales with v/d. Published single-mic systems mostly report speed (error about 8 km/h) rather than distance. CPA from a phone is plausible but research-grade. As a map cue it is strong when it works: a sharp, fast transition means a road within about 10–20 m.

### Cited Findings
- Couvreur & Bresler (ICASSP 1997): analytical relation between the Doppler parameters seen at a roadside microphone and vehicle speed, time of closest approach and CPA distance — [ICASSP 97 paper](https://www2.spsc.tugraz.at/people/franklyn/ICASSP97/pdf/author/ic973537.pdf)
- Cevher, Chellappa & McClellan: single-mic acoustic wave pattern model with parameters speed, Doppler shift factor and CPA distance. Notes a scaling ambiguity (speed and distance are coupled) — [EPFL infoscience](https://infoscience.epfl.ch/record/150568/files/Vehicle%20speed%20estimation%20using%20acoustic%20wave%20patterns.pdf?version=2)
- Bulatović & Djukanović: mel-spectrogram features plus supervised learning detect the pass-by instant and estimate speed from a single mic, with mean error 7.87 km/h — [arXiv 2204.04013](https://arxiv.org/pdf/2204.04013); follow-up label correction — [arXiv 2204.05082](https://arxiv.org/pdf/2204.05082.pdf)
- Patent US 9911336: CPA instant = time of maximum intensity; speed from the frequency shift measured before vs after it — [USPTO 9911336](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/9911336)
- Euracoustics 2025: single microphone used for both SPL and Doppler speed estimation in outdoor pass-by tests — [FA2025 paper 000943](https://dael.euracoustics.org/confs/fa2025/data/articles/000943.pdf)

### Inferences
- Geometry (standard physics, not from a fetched source): f(t) = f0 · c / (c − v·cosφ(t)), with cosφ = v(t0−t)/sqrt(d² + v²(t0−t)²). The total shift is f_approach/f_recede ≈ (c+v)/(c−v), which gives v without d. The transition duration Δt ≈ d/v, which then gives d. Example: at v = 50 km/h (13.9 m/s), d = 5 m gives Δt ≈ 0.4 s, while d = 30 m gives about 2.2 s.
- Level envelope (point source): L(t) = L_max − 10·log10(1 + (v(t−t0)/d)²). Its −3 dB width is 2d/v. This is the same d/v ratio, measurable without a tonal component.
- **[1-DAY] heuristic:** measure the −3 dB width of isolated pass-by peaks and assume v ≈ city speed limit (30–50 km/h in Paris). Then d ≈ v·width/2, with about ±50 % error dominated by the speed assumption. Output a likelihood for "distance to nearest drivable road ≈ d". Requires isolated vehicles, so it fails in dense traffic.
- **[RESEARCH]:** fitting the full Doppler curve on engine/tyre tonal components. Phone audio at 16–48 kHz is adequate in principle, but tones are often weak for EV/hybrid traffic.

### Gaps
- No published single-mic CPA-distance accuracy figure was found (papers report speed).

---

## 3. Rail, tram, metro/RER

### Takeaway
A train is a finite line source. Close in (d below about L/π, i.e. under about 60 m for a 200 m train) the level falls 3 dB per doubling, and further out 6 dB. Pass-by duration ≈ (train length + geometry)/speed, so duration plus level helps tell RER/train (long, loud) from tram (about 30–45 m, quieter) from a bus. Timetable periodicity only shows that a line is within earshot. Underground metro/RER rumble is ground-borne and only audible very close to the alignment, inside buildings. It is weak outdoors.

### Cited Findings
- A moving train is commonly modelled as a line source: −3 dB per doubling (line) vs −6 dB (point) — [Svantek, railway noise](https://svantek.com/services/railway-noise/); [Archives of Acoustics paper on railroad noise as a finite moving line source](https://acoustics.ippt.pan.pl/index.php/aa/article/download/418/349/726)
- UK IoA: train SEL fitted against speed holds within about ±6 dB(A) for most data. 5–6 measurements per train type gave a reasonable average SEL — [Hood, Williams et al., The calculation of train noise (IoA)](https://www.ioa.org.uk/system/files/publications/RA%20HOOD%20PR%20WILLIAMS%20KM%20COLLINS%20RJ%20GREER%20THE%20CALCULATION%20OF%20TRAIN%20NOISE.pdf)
- FRA high-speed ground transportation noise manuals give the SEL/Lmax/distance relationships and train-length corrections (contents only seen) — [FRA HSR NV Manual 2012](https://railroads.dot.gov/sites/fra.dot.gov/files/fra_net/2680/20120220_FRA_HSR_NV_Manual_FINAL_102412.pdf)

### Inferences
- The L/π transition distance is a standard finite-line result. It was given only as unverified background by the search tool, so treat it as an inference. For RER A (about 225 m for a double unit) the transition is about 70 m. For a Paris tram (about 45 m) it is about 15 m, so trams behave like point sources at most listening distances.
- **[1-DAY]:** classify a "rail pass-by" event (long, broadband, lasting 5–20 s) with a pretrained audio tagger (YAMNet/PANNs have "train"/"rail transport" classes). Use event presence as a likelihood: P(heard | distance to nearest surface rail in OSM), as a logistic in distance with a 50 % point at about 300–500 m in town (placeholder). Near Vincennes the relevant surface rail is limited (RER A is mostly underground in Vincennes town; check OSM `tunnel=yes`). Surface/underground status matters a lot.
- **[RESEARCH]:** matching event times to GTFS timetables (IDFM open data) to identify which line. Headways of 2–10 min make this ambiguous without many events.

### Gaps
- No quantitative source found for outdoor audibility of underground metro/RER rumble.
- No tram-specific Lmax vs distance figures retrieved.

---

## 4. Aircraft

### Takeaway
Aircraft are audible over large areas, so the single-phone cue is weak for fine localisation (constant over km). At most it gives a coarse constraint ("under an Orly approach/departure corridor in this runway configuration"). Vincennes is not directly under the main Orly axis according to what was found, and no altitude data for Vincennes was found. Low value for the demo.

### Cited Findings
- Orly, west-facing configuration: arrivals overfly Val-de-Marne in descent on the runway axis, 3° ILS glide, engines throttled back. East-facing: departures overfly Val-de-Marne (procedures since Feb 2002) — [Assemblée nationale QE (14th leg.)](https://www.assemblee-nationale.fr/dyn/14/questions/QANR5L14QE78150.pdf)
- East-facing departures may turn south after 4.5 NM once at 1,700 m altitude (order of 18 Feb 2003) — [Assemblée nationale question](https://questions.assemblee-nationale.fr/dyn/14/questions/QANR5L14QE63346.pdf)
- Orly PBN-to-ILS continuous-descent project, public inquiry 2022–23 — [dossier enquête publique PBN Orly](https://www.consultations-publiques.developpement-durable.gouv.fr/IMG/pdf/dossier_enquete_publique_pbn_orly.pdf)
- Official airport-resident traffic data pages — [ecologie.gouv.fr, riverains aéroports parisiens](https://www.ecologie.gouv.fr/riverains-des-aeroports-parisiens-donnees-trafic-aerien)

### Inferences
- A 3° glide gives height ≈ 0.052 × distance to threshold. At about 10 km from Orly the height is about 500 m, but Vincennes is about 12–14 km NNE of Orly and not on the runway axis (the runways are roughly E-W/NE-SW). So overflights there are higher and lateral. The cue barely varies across the 2.5 km demo box. **Skip** for the hackathon. Use it as an "outdoors, not in a tunnel/basement" cue if anything.

### Gaps
- No overflight altitudes or noise contours for Vincennes found (the AIP/SIA charts and Bruitparif aircraft maps would have them).

---

## 5. Church bells

### Takeaway
Bells are loud (110–125 dB at the tower) and impulsive with a tonal strike note, so detection is easy when they ring. But in documented field studies the effective coverage was only about 200–350 m, and ringing is time-limited (hours, quarters, services). Useful as an occasional "within a few hundred metres of a church with a bell" cue that matches OSM `amenity=place_of_worship` + `building=church`. Bell pitch identification is research-grade and needs a reference recording per tower.

### Cited Findings
- Near the tower, bell levels can reach 110–125 dB. The sound is impulsive and irregular. Measurement uses LAmax, LCpeak, SEL, LAeq with Class 1 meters — [Svantek, church bell noise](https://svantek.com/services/church-bells-noise/)
- Field measurement plus simulation in the Àneu valley (Catalonia): minimum bell coverage distances of about 200–350 m for several parishes. Bell sound can sit more than 10 dB below background in places — [Studia Universitatis Hereditati 12(2) 2024, pp.65–84](https://www.hippocampus.si/ISSN/2350-5443/2-2024/SUH_2350-5443.12(2)65-84.pdf); [p.79](https://zalozba.upr.si/ISSN/2350-5443/2-2024/files/basic-html/page79.html)

### Inferences
- **[1-DAY]:** if a tagger detects "church bell", multiply cells by a logistic in distance to the nearest church, with 50 % at about 400–600 m in town (placeholder, larger than the Àneu "coverage" figure because detection ≠ coverage). Knowing the clock time and that bells ring the hour adds little extra.
- Strike-note (fundamental/hum) pitch and partial structure differ between bells. A per-church fingerprint would need recordings of each tower. **[RESEARCH]**.

### Gaps
- No source for km-scale bell audibility in urban noise, or for the accuracy of automatic bell identification.

---

## 6. Water, wind in trees, birdsong (park/wood indicators)

### Takeaway
BirdNET-style species detection works at moderate precision (about 0.55–0.76) but low recall (about 0.24–0.52). Abundant bird activity, plus low traffic level and wind-in-foliage noise, is a reasonable "inside a large green area" indicator, e.g. the Bois de Vincennes vs the street grid. Species-to-habitat mapping (woodland species like woodpeckers vs urban pigeons/sparrows) is plausible but unvalidated for this site. Fountains/rivers give steady broadband noise audible only within tens of metres. Treat as a very local cue.

### Cited Findings
- Global BirdNET assessment (4,224 one-minute recordings, 67 sites): precision 0.57–0.71 across continents and 0.55–0.76 across biomes, recall 0.24–0.52. Best in North America, Oceania and Europe — [Global assessment of BirdNET performance (XJTLU listing)](https://scholar.xjtlu.edu.cn/en/publications/a-global-assessment-of-birdnet-performance-differences-among-cont/); [INRAE HAL document](https://hal.inrae.fr/hal-04633976v1/document)
- A confidence threshold of 0.1–0.3 is best for detecting vocalisations, and about 0.5 for characterising communities — [Pérez-Granados blog/BOU](https://bou.org.uk/blog-perez-granados-optimizing-birdnet-lessons-from-a-global-initiative/); [Napier optimisation paper](https://napier.ac.uk/-/media/worktribe/output-4294834/optimisation-of-passive-acoustic-bird-surveys-a-global-assessment-of-birdnet-settings.ashx)
- BirdNET can infer European bird communities from large-scale ecoacoustic data — [bioRxiv 2023.12.06.570351](https://www.biorxiv.org/content/10.1101/2023.12.06.570351.full.pdf)
- Accuracy drops in unfamiliar soundscapes — [arXiv 2503.15576](https://arxiv.org/pdf/2503.15576.pdf)
- Species-level variation: about 88–93 % precision for some forest species (AudioMoth study) vs 16.6 % recall / 50.8 % precision for a poorly represented species — [PMC10459908](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10459908/); [PMC12838248](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12838248/)

### Inferences
- **[1-DAY]:** ecoacoustic proxy feature = ratio of 2–8 kHz band energy (birds) to 50–500 Hz energy (traffic), roughly the NDSI idea. A high value means a park/wood interior. Map to a likelihood using distance from cell to the nearest `leisure=park` / `landuse=forest` / `natural=wood` edge (positive inside, negative outside). Bois de Vincennes and the château moat/park are the obvious targets. In late November, bird activity is low (no dawn chorus season), so expect weak signal at the hackathon.
- Running BirdNET itself (TFLite, about 3 s windows) is feasible in Python. The species-to-habitat mapping would need hand-made lists. Marginal for one day.
- Water and wind: no quantitative sources found. Treat as tagger presence → "within about 30–50 m of `amenity=fountain` / `waterway`" (placeholder).

### Gaps
- No source on the audible range of fountains, or on wind-in-trees as a habitat classifier.
- No Vincennes-specific bird survey consulted.

---

## 7. General single-microphone distance estimation (DRR, spectral tilt, learned models)

### Takeaway
State of the art for single-channel distance estimation is learned models trained in rooms: about 0.5 m absolute error indoors for a speaker (Neri et al. 2024), and relative distance error about 0.25–0.32 for DCASE 2024 SELD systems, which use multichannel arrays. Outdoors there is little reverberation, so the direct-to-reverberant cue that drives these models is weak. Outdoor ranging from one mic relies on level with assumed source power, spectral tilt from air absorption, and temporal smearing. Expect order-of-magnitude (factor ~2) accuracy, not metres.

### Cited Findings
- Neri, Politis, Krause, Carli, Virtanen, "Speaker Distance Estimation in Enclosures from Single-Channel Audio", IEEE/ACM TASLP 32 (2024) 2242–2254. CRNN with attention, continuous distance, about 0.50 m absolute error in a real noisy scenario. Code/data at github michaelneri/audio-distance-estimation — [arXiv 2403.17514](https://arxiv.org/pdf/2403.17514); [project page](https://michaelneri.github.io/publication/2024-03-27-TASLP-Distance)
- Follow-up (May 2026): the model relies on early/late reverberation. With time calibration, it reaches 0.14 m MAE using propagation delay alone — [arXiv 2605.07694](https://arxiv.org/abs/2605.07694)
- Prior single-channel work mostly did coarse distance classes or near/far — [arXiv 2403.17514](https://arxiv.org/html/2403.17514v1)
- DCASE 2024 Task 3 (SELD with distance estimation): best reported relative distance error (RDE) about 0.25 (MVANet) — [arXiv 2411.14153](https://arxiv.org/pdf/2411.14153). Another audio-only system reached RDE 0.32 on the dev test set — [arXiv 2507.17941](https://www.arxiv.org/pdf/2507.17941). Joint-modelling paper ranked first — [arXiv 2501.10755](https://arxiv.org/html/2501.10755v1). These are multichannel (FOA/mic array), indoor, STARSS23-type data — [DCASE2024 challenge](https://dcase.community/challenge2024/); [Berghi tech report](https://dcase.community/documents/challenge2024/technical_reports/DCASE2024_Berghi_93_t3.pdf); [reverberation + visual depth cues paper](https://arxiv.org/html/2410.22271v1)

### Inferences
- An RDE of 0.25–0.32 means about 25–30 % distance error with arrays indoors. A single phone outdoors will be worse. Do not plan on learned outdoor single-mic ranging for the hackathon **[RESEARCH]**.
- The practical outdoor approach is a hand-built physical model per source class: assumed emission ± σ_source (about 5 dB for traffic class, more for unknowns), plus geometric spreading, plus air absorption (band-dependent), plus building shielding from footprints. Compare measured band levels (with unknown gain offset) against predicted ones. This plugs directly into the existing likelihood-grid design (CLAUDE.md §6.3) as extra multiplicative terms.

### Gaps
- No outdoor single-mic distance-estimation benchmark found.

---

## 8. Gunfire, artillery, explosions

### Takeaway
For a supersonic bullet passing near the listener, the delay between the ballistic "crack" (shockwave) and the muzzle "thump" grows with shooter range. This is used to range the shooter, with large errors from unknown bullet speed. For explosions, flash-to-bang (Δt × about 343 m/s) gives range if the flash is seen. These give distance to the *threat*, not the listener's map position. That only helps localisation if the threat position is known (e.g. a known friendly range or impact point), so value for Pothenot's localisation is weak. Safety value (reporting incoming fire and its approximate range) is real.

### Cited Findings
- VERA system (single recording device): shooter distance from the time difference between shockwave and muzzle-blast arrivals. Fails if the bullet is subsonic or the two sounds can't be separated (noise, poor audio). Bullet-speed uncertainty must be covered by a range of speeds, and localisation gets less certain as that range widens — [arXiv 1905.13313](https://arxiv.org/pdf/1905.13313) (findings via search summary; the PDF text could not be extracted)
- Patent: range from (muzzle time − shock time) combined with predicted calibre and miss distance — [USPTO 11693103](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/11693103)
- Small errors in shock/muzzle arrival times can cause large range errors. Iterative bullet-deceleration models refine range — [USPTO 7408840](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/7408840); [USPTO 8861311](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/8861311); [counter-sniper patent 6178141](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/6178141)
- Smartphone shooter localisation (Sallai et al., IPSN 2007): phones have the needed components, but phone GPS errors are too large (about 1 m sensor-position accuracy needed for networked localisation). Phones in pockets/bags make detection nearly impossible — [ipsn07-sallai](https://archive.isis.vanderbilt.edu/sites/default/files/ipsn07-sallai.pdf)
- Distributed low-cost MEMS array network: gunshot recognition MCC 0.70, average localisation error below 6.5 m over 25,000 m² (multi-node, not single phone) — [arXiv 2611.02591](https://arxiv.org/pdf/2611.02591)
- Low-cost Raspberry Pi gunshot detection: detection accuracy 0.986, F1 0.959 — [Manring & Hill, NSF PAR](https://par.nsf.gov//servlets/purl/10549609)
- Ad-hoc phone networks for gunshot detection need time sync within about 10 ms — [USPTO 9218728](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/9218728)

### Inferences
- Crack-thump approximation (standard physics, not from a fetched source): if the shooter fires roughly toward the listener with constant bullet speed V, Δt ≈ R·(1/c − 1/V). For V = 850 m/s and c = 343 m/s, Δt ≈ 1.74 ms per metre, i.e. about 0.17 s at 100 m and about 0.87 s at 500 m. Bullet deceleration and off-axis geometry change this a lot, so expect ±20–50 % error.
- Flash-to-bang: R = c·Δt, with c ≈ 331 + 0.6·T(°C) m/s. Error is dominated by the human timing of the flash (±0.2 s → ±70 m).
- For Pothenot: a spoken "explosion at my 2 o'clock, about 3 seconds after the flash" gives bearing + range to the explosion. That only fixes the speaker if the impact point is known, which is rare. Better used as a casualty-card/safety annotation than as a localisation term. Recommend **not** building this for the demo.

### Gaps
- No peer-reviewed single-phone crack-thump ranging accuracy found. No artillery ranging-by-ear figures.

---

## 9. Phone hardware realities and cheap calibration

### Takeaway
Uncalibrated phones differ by several dB, and up to about ±10 dB between models. Only a few apps on iOS met ±2 dB against a Type 1 meter in Kardous & Shaw (2014), and Android varies more. OS and browser processing (AGC, noise suppression) can wipe out absolute level and suppress steady background noise, which is exactly the traffic hum you want to measure. Mitigations: disable processing in `getUserMedia`, verify it with `getSettings()`, and rely on relative/ratio features (band ratios, L10−L90, event detection) rather than absolute dBA. Alternatively, calibrate once per phone at a known spot (e.g. next to the venue road) and keep the offset.

### Cited Findings
- Kardous & Shaw 2014 (JASA Express Letters): of 192 apps examined, 10 iOS apps were tested with pink noise at 65–95 dB against a Larson-Davis 831 Type 1 meter. Only 4 iOS apps had mean differences within ±2 dB (A-weighted). The NIOSH blog says 3 apps were within ±2 dB unweighted (NoiSee, SoundMeter, SPLnFFT). The counts conflict, likely A-weighted vs unweighted. Different models of the same platform performed differently. Phones are not designed to meet SLM standards — [PubMed 25236152](https://pubmed.ncbi.nlm.nih.gov/25236152/); [NIOSH Science Blog 2014](https://cdc.gov/niosh/blogs/2014/sound-app.html); [CDC stacks 199862](https://stacks.cdc.gov/view/cdc/199862)
- 2016 follow-up: apps with external calibrated microphones performed better — [PMC5102154](https://pmc.ncbi.nlm.nih.gov/articles/PMC5102154)
- Android: the VOICE_RECOGNITION source is meant by spec to exclude filtering/AGC, and UNPROCESSED exists, but manufacturers don't always comply. A Galaxy A52s showed a 2–3 dB(A) drop when white noise started (noise suppression). One user found a fixed −11.5 dB(A) offset against a city official's calibrated meter. These are anecdotal forum reports — [audiotool group, A52s](https://groups.google.com/g/audiotool-discussion-group/c/qYrxmtyGD08); [audiotool group, S23 Unprocessed vs Voice Recognition](https://groups.google.com/g/audiotool-Discussion-group/c/oJfrnBWwK2w)
- Lab free-field calibration methods for smartphone noise dosimetry (AGC disabled on test devices) significantly improved accuracy in diffuse and free fields — [Voix et al. 2013, ETS](https://espace2.etsmtl.ca/id/eprint/5759/1/Voix%20J.%202013%205759%20Calibration%20of%20smartphone-based%20devices%20for%20noise%20exposure%20monitoring.pdf); [Dumoulin thesis, ETS](https://espace.etsmtl.ca/1320/2/DUMOULIN_Romain.pdf)
- Browser: Chrome historically disabled all processing when `echoCancellation:false`. Firefox needs `noiseSuppression` and `autoGainControl` set false explicitly. The common pattern is all three false. Verify with `track.getSettings()`. WebKit/Safari has had bugs where constraints had no effect or a lowpass persisted — [Mozilla bug 1274392](https://bugzilla.mozilla.org/show_bug.cgi?id=1274392); [Mozilla bug 1367697](https://bugzilla.mozilla.org/show_bug.cgi?id=1367697); [WebKit bug 179411](https://bugs.webkit.org/show_bug.cgi?id=179411); [WebKit bug 192932](https://bugs.webkit.org/show_bug.cgi?id=192932); [Mozilla WebRTC blog, audio constraints](https://blog.mozilla.org/webrtc/fiddle-of-the-week-audio-constraints/)
- Newer browsers expose extra toggles (`voiceIsolation`, `goog*` constraints) — [Raw Mic Input userscript](https://greasyfork.org/fr/scripts/520484-raw-mic-input/code)

### Inferences
- **[1-DAY] recommended capture:** `getUserMedia({audio:{echoCancellation:false, noiseSuppression:false, autoGainControl:false, channelCount:1, sampleRate:48000}})`. Log `getSettings()` with each report. Record 10–20 s of ambience **separately from the voice report**, or use the non-speech gaps. Speech dominates the level otherwise.
- Treat the gain offset G as a nuisance parameter. Either (a) calibrate once at the venue against a free SLM app on a known phone, or at a cell with a known model level, or (b) marginalise G ~ N(0, 6 dB) in the likelihood. (b) is easy in a grid. Add G as one more dimension like heading, or analytically integrate a Gaussian.
- Prefer features that don't depend on calibration: band-energy ratios (low/high), level statistics (L10−L90, peak rate), and tagger class probabilities (traffic, train, bell, birds, water, siren). These remain usable even if AGC is on. Absolute dBA does not.
- Suggested per-cell likelihood product for the hackathon: L_audio(p) = N(Lmeas − Lpred_road(p) − G; 6 dB) · Π_classes f_c(dist_c(p))^[detected] · (1 − f_c(dist_c(p)))^[not detected and class would be clearly audible], where f_c is a logistic detection-vs-distance curve per class (placeholder ranges: rail 400 m, bell 500 m, fountain 40 m, park interior via signed distance). This fits CLAUDE.md §6.3's "can't see X" penalty pattern for audio. Keep "not heard" penalties soft, since detection recall is low (e.g. BirdNET 0.24–0.52).

### Gaps
- No systematic study found of WebRTC/browser capture level accuracy on phones.
- No quantified cross-model offset distribution for current (2024–26) phones.
