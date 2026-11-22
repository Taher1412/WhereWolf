# Passive acoustic cues for locating a person inside a forest / wooded park (single phone mic, 5-20 s clip)

Scope: how road/traffic noise and other sounds propagate in woodland, and which cues a single smartphone microphone can use to tell (a) forest vs open field vs street and (b) roughly where in a forest the speaker is. Target site: Bois de Vincennes (Paris). Research done 2026-11-21. Many primary papers (JASA, Applied Acoustics) are paywalled; where only abstracts or secondary citations were available this is flagged.

---

## Q1. Excess attenuation of road/traffic noise through forest belts and woodland

### Takeaway
Inside real woodland, expect roughly **5-10 dB extra attenuation per 100 m** beyond what open grass gives, mostly from the **soft forest floor (ground effect, low-mid frequencies)** and **multiple scattering off trunks (mid-high frequencies)**. Foliage adds little to A-weighted traffic noise. Narrow belts (<20-30 m) give only 0-4 dB. Leaf-off costs up to about 3 dB(A) for deciduous stands. The Nordic and ISO engineering models are known to **underpredict** forest attenuation.

### Cited Findings
**Magnitudes**
- Huisman & Attenborough (1991, JASA 90(5):2664-2677, DOI 10.1121/1.401861) measured reverberation and attenuation vs frequency in a pine forest at 10-100 m. Below 1 kHz, a point-source calculation with a two-parameter ground impedance model fits the excess attenuation. Day-to-day weather did **not** significantly change the 100 m attenuation at any frequency. High-frequency attenuation and reverberation for paths below the canopy are dominated by **multiple scattering off tree trunks**. The measured attenuation is "considerably underpredicted" by the Dutch-Scandinavian (Nordic) prediction scheme. There is a strong receiver-height dependence that their model can't reproduce. — [Abstract mirror](https://data.zhenzhi.com/details/1/993718255)
- Secondary sources give conflicting headline numbers for that study: a **maximum 13.2 dB over 100 m** in coniferous forest, vs. **about 10 dB(A) extra attenuation of road traffic noise through 100 m of pine forest**. The original wasn't read, so check it before using either. — [Review (ResearchGate)](https://www.researchgate.net/publication/258499942_Outdoor_noise_control_by_naturalsustainable_materials_in_urban_areas); [Academia.edu: Sound propagation through forests and tree belts](https://www.academia.edu/112538310/Sound_propagation_through_forests_and_tree_belts)
- Bucur ("Urban forest acoustics"), citing measurements:
  - beech and ash stands: excess attenuation **≥10 dB/100 m** for receivers at 1.2 m;
  - spruce stands: **10 dB/100 m** at 1.2 m receiver height and **7 dB/100 m** at 3.9 m.
  
  — [Bucur, Urban Forest Acoustics (PDF)](https://cdn.homeownershub.com/media/73165/60a02322623617.28914949.pdf)
- Beranek & Vér (1976), as cited by Van Renterghem: at least **30 m of "heavily wooded" area** is needed for about **5 dB(A)** reduction. — [Van Renterghem 2014, Ecol. Eng. 69:276-286](https://users.ugent.be/~tvrenter/publicaties/guidelinestreebelts.pdf)
- Kragh (1981), as cited by Van Renterghem: belts of trees and bushes **10-25 m deep** add only insignificant attenuation of road traffic noise compared with propagation over grass or other porous ground. Reynolds (1981): buffers should be **at least 20 m wide**, with trees, ground foliage and bushes. — [Van Renterghem 2014](https://users.ugent.be/~tvrenter/publicaties/guidelinestreebelts.pdf)
- Fang & Ling (2003, Landscape & Urban Planning 63:187-195) studied **35 evergreen tree belts** in Taipei. At 20 m depth, the belts fell into three groups: **<3, 3-6 and 6-9 dB(A)** relative attenuation.
  - Relative attenuation falls logarithmically with visibility through the belt (it is higher where you can see less far).
  - It rises logarithmically with belt width, length and height.
  
  — [Van Renterghem 2014](https://users.ugent.be/~tvrenter/publicaties/guidelinestreebelts.pdf); [urbanforestrysouth citation](https://urbanforestrysouth.org/resources/library/citations/Citation.2004-11-03.P178)
- Tanaka et al. (1979), as summarised by Van Renterghem: basal areas up to about **70 m²/ha** gave **0-4 dB** attenuation at **10 m and 20 m** into the forest from its edge. — [Van Renterghem 2014](https://users.ugent.be/~tvrenter/publicaties/guidelinestreebelts.pdf)
- FDTD simulations of a 15 m deep belt next to a 4-lane road, receiver at 1.5 m, 40 m behind the belt:
  - closely packed low-diameter trunks: **8.1 dB(A)** reduction relative to grassland;
  - 22 cm trunks at the same basal area: at most **6.0 dB(A)**;
  - a 1 m × 2 m spacing with 22 cm trunks and 25% randomness: **5.8 dB(A)**.
  
  Insertion loss grows linearly-to-quadratically with stem diameter and basal area. If the belt is wide enough along the road, moving the receiver further away does not reduce the shielding. — [Van Renterghem 2014](https://users.ugent.be/~tvrenter/publicaties/guidelinestreebelts.pdf)

**Mechanisms and parameters you can plug into a model**
- Noise shielding in a belt comes from **multiple scattering in the trunk layer plus the acoustically soft soil**. Foliage absorbs and scatters only at high frequencies, so it is "not useful" against road traffic noise, whose energy is mostly at low frequencies (Martens 1980; Kotzen & English 2009). — [Van Renterghem 2014](https://users.ugent.be/~tvrenter/publicaties/guidelinestreebelts.pdf); [HOSANNA project, CORDIS](https://cordis.europa.eu/project/id/234306/reporting)
- **Ground parameters used, from Attenborough et al. 2011 meta-analysis:**

  | Surface | Flow resistivity | Porosity |
  |---|---|---|
  | Grass | **300 kPa·s·m⁻²** | **0.75** |
  | Forest floor | **20 kPa·s·m⁻²** | **0.5** |

  — [Van Renterghem 2014](https://users.ugent.be/~tvrenter/publicaties/guidelinestreebelts.pdf)
- Bark absorption coefficient (normal incidence), conservative value: **0.075** (Reethof et al. 1977). — [Van Renterghem 2014](https://users.ugent.be/~tvrenter/publicaties/guidelinestreebelts.pdf)
- **Crown scattering when both source and receiver are below the canopy is slightly negative**: canopies scatter sound down towards the ground.
  - Behind a highway noise wall, one row of tall trees added **+6 dB at 10 kHz**, and **<1 dB below 2 kHz** (Van Renterghem & Botteldooren 2002).
  - Net effect on A-weighted traffic noise is about **−0.5 dB(A)** of the predicted benefit.
  
  — [Van Renterghem 2014](https://users.ugent.be/~tvrenter/publicaties/guidelinestreebelts.pdf)
- The ISO 9613-2 foliage term is "very conservative". Its limited effects came from low measured attenuation at some belts, and ISO 9613-2 underlies most noise-mapping software. — [Van Renterghem 2014](https://users.ugent.be/~tvrenter/publicaties/guidelinestreebelts.pdf). ISO 9613-2 is now in its 2024 edition, which still uses octave bands from 63 Hz to 8 kHz. The foliage data are in Annex A. — [ISO 9613-2:2024](https://www.iso.org/standard/74047.html)

**Forest edge and in-forest impulse measurements (US Army ERDC)**
- Swearingen et al. (2007 ASA meeting): propane cannon in an open field, propagating into a planted red-pine monoculture with no understory at the edge.
  - Peak levels were **141 → 127 dB** across the open field and **120 dB at 25 m inside the forest**.
  - Below 600 Hz, the oblique line (25°) was 2-3 dB lower than the main line. **After 25 m into the forest, the level no longer depended on the direction of arrival.**
  
  — [ASA pressroom, Swearingen et al. 2007](https://acoustics.org/pressroom/httpdocs/153rd/swearingen.html)
- Swearingen, White, Guertin, Albert & Tunick (2013, JASA 133(5):2566-2575, DOI 10.1121/1.4799011):
  - Open-field waveforms are close to simple impulses; edge and in-forest waveforms show strong reverberation after the direct arrival.
  - Transmission *into* the forest shows a steeper SEL decay, about **4 dB per tenfold distance** more than outbound, plus stronger attenuation in the **1-2 kHz band**.
  - Meteorology alone does not explain the non-reciprocity.
  
  This is from search summaries, so verify against the paper. — [Search record](https://bvbvf1.bib-bvb.de/vufind/PrimoRecord/cdi_proquest_miscellaneous_1350151276)

**Seasonal (leaf-on vs leaf-off)**
- UK Forest Research guidance: a deciduous buffer (beech, lime) in winter could give **up to about 3 dB(A) less** reduction than in full leaf. Evergreens keep their effect all year. This is a guidance estimate, not a controlled measurement. — [Forest Research TDAG "First steps: urban noise"](https://cdn.forestresearch.gov.uk/2025/05/TDAG_FirstStepsUrbanNoise.AW_.pdf)
- Salford study: an evergreen hedge gave **3-6 dB** more attenuation than a deciduous beech hedge in the 1/3-octave bands **1.6-6.3 kHz**. — [Salford repository](https://salford-repository.worktribe.com/OutputFile/2478399)
- Virginia DOT (1973): twigs and small branches of deciduous trees reduce visibility but do little to attenuate noise. — [VTRC 73-R30](https://vtrc.virginia.gov/media/vtrc/vtrc-pdf/vtrc-pdf/73-r30.pdf)

### Inferences
- For a Pothenot road-noise model inside the Bois de Vincennes, use free-field line-source decay (−3 dB per doubling of distance from a long road), plus:
  - an **in-forest excess attenuation of about 5 dB(A) per 100 m of woodland path**, with a plausible range of 3-10;
  - **0-2 dB for the first 20-30 m** of woodland;
  - **ground ≈ forest floor (σ ≈ 20 kPa·s·m⁻²)**, versus grass (300) or asphalt (hard) in open areas.
  
  This replaces the −15 dB building screening used in town.
- In November, the Bois de Vincennes is leaf-off for its deciduous trees (assumption: mostly broadleaf; not verified here), so use the lower end of the attenuation range and add +0-3 dB compared with summer.
- Because weather did not significantly change 100 m forest attenuation (Huisman & Attenborough), the forest term is more stable than open-field propagation, which is very sensitive to wind and temperature gradients over hundreds of metres. Over long distances (Périphérique, A4 at 500 m to 1.5 km), meteorological refraction will dominate the uncertainty. Use σ ≈ 5-6 dB for those predictions.
- Receiver height matters (7 vs 10 dB/100 m at 3.9 vs 1.2 m). Low positions (casualty lying down, phone near the ground) will hear **less** traffic than a standing buddy at the same spot.

### Gaps
- **ISO 9613-2 Annex A foliage table values were not verified.** The sample PDF is a scanned image. The values commonly reproduced (from memory, *unverified*) are:
  - propagation through foliage of **10-20 m**: 0, 0, 1, 1, 1, 1, 2, 3 dB at 63 Hz-8 kHz;
  - **20-200 m**: 0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.09, 0.12 dB/m;
  - capped at 200 m.
  
  Check against a licensed copy before quoting.
- No Nord2000 or Harmonoise forest-specific coefficients were found in accessible sources.
- No Bruitparif dB values specific to the interior of the Bois de Vincennes were found. Airparif/Bruitparif's 2024 combined air-noise map names the Bois de Vincennes as a combined-exposure zone. The live map is at carto.airparif.bruitparif.fr. — [Airparif/Bruitparif 2024 press release](https://airparif.fr/sites/default/files/document_publication/2024-05%20-%20CP%20-%20Premi%C3%A8re%20cartographie%20crois%C3%A9e%20de%20la%20qualit%C3%A9%20de%20l%E2%80%99air%20et%20de%20l%E2%80%99environnement%20sonore%20au%20sein%20de%20la%20r%C3%A9gion%20%C3%8Ele-de-France.pdf). A Vincennes PPBE exists. — [PPBE Vincennes](https://www.vincennes.fr/sites/default/files/2025-02/ppbevincennes2013.pdf). These PDFs and the open-data Lden rasters should be checked directly. They could replace our own road model with official Lden grids.
- A study result of "about 4-8 dB(A) per 30 m of forest depth" for Japanese forest stands appeared in a search summary. Its source URL is uncertain (possibly the JIRCAS JARQ paper, [jircas.go.jp](https://www.jircas.go.jp/sites/default/files/publication/jarq/15-3-202-204_0.pdf)). Don't use it without checking.

---

## Q2. Can distance to a road be estimated from spectral shape rather than absolute level?

### Takeaway
Physically yes, but it's weak for a single clip. High frequencies are lost faster than low ones, through air absorption (about 3-4 dB/100 m at 4 kHz), the forest ground effect and trunk scattering. A **low/high band ratio of the traffic noise** therefore gets steeper with distance. But the source spectrum varies (speed, tyres, trucks), and listeners only use spectral cues reliably beyond about 15 m and relative to a reference. No paper was found that ranges traffic noise from its spectrum. Treat it as a soft secondary likelihood, not a ranging method.

### Cited Findings
- Air absorption at **4 kHz is about 3-4 dB per 100 m** (Ingård 1953). It depends on temperature and humidity. — [DTIC, Auditory perception in open field: distance estimation](https://apps.dtic.mil/sti/pdfs/ADA588823.pdf)
- Psychoacoustics: sounds with less high-frequency content relative to low-frequency content are heard as further away.
  - Spectral cues matter for sources **beyond about 15 m**.
  - Between 1 and 15 m they carry no distance information.
  
  — [DTIC ADA588823](https://apps.dtic.mil/sti/pdfs/ADA588823.pdf)
- High-frequency attenuation increases perceived distance **only when compared with a less-filtered reference**. Level and direct-to-reverberant ratio also matter. — [Acta Acustica 2026, "Sound spectrum influences auditory distance perception in highly reverberant environments"](https://acta-acustica.edpsciences.org/articles/aacus/full_html/2026/01/aacus250191/aacus250191.html)
- Outdoor sensor-network localisation work models propagation as spherical spreading plus ISO 9613 frequency-dependent air absorption, so that high frequencies decay faster with range. — [arXiv 2403.20130](https://arxiv.org/html/2403.20130)
- In forest, attenuation is "generally greater at higher frequencies and greater distances" in both forests Padgham studied (JASA 2004, 115(1)). — [Padgham 2004 abstract](https://data.zhenzhi.com/details/1/876875671)
- Huisman & Attenborough: below 1 kHz, forest excess attenuation is ground-effect dominated. Above that, trunk scattering dominates. — [Abstract](https://data.zhenzhi.com/details/1/993718255)
- In-forest transmission shows extra attenuation in the 1-2 kHz band. — [Swearingen et al. 2013 record](https://bvbvf1.bib-bvb.de/vufind/PrimoRecord/cdi_proquest_miscellaneous_1350151276)
- Soundscape CCA in Thetford Forest: the **0-2 kHz** band associated with open habitat, **4-7 kHz** with broadleaf woodland, and **7-10 kHz** with older conifer woodland. — [Turner et al. 2018, PLoS ONE](https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0189843)

### Inferences
- A usable cue is the traffic-band spectral tilt, for example **L(125-500 Hz) − L(1-4 kHz)**, measured only in frames where YAMNet says "traffic / vehicle" and no voice is present. Close to a road (<50 m), tyre noise gives a relatively flat spectrum up to about 1-2 kHz. Far away (>300 m, through forest), the spectrum becomes a low-frequency rumble.
- Expected extra loss at ~2-4 kHz relative to 250 Hz, per 100 m of forest: roughly 3-4 dB from air absorption, plus several dB from trunk scattering. This is an inference from the cited numbers, not a measured traffic-specific value.
- Combine tilt with absolute level (already estimated using the voice as a reference). The level says "how much road", and the tilt helps separate **near small road** from **far big road (Périphérique/A4)**, which can give the same dB(A).
- The ground effect of soft forest floor can make a dip at a few hundred Hz rather than a monotonic tilt (inference from ground-impedance physics; not quantified here). Use broad bands to avoid fitting dips.

### Gaps
- No peer-reviewed study was found that estimates distance to a road from the traffic noise spectrum. Calibration would need our own recordings (e.g. walk transects from the Route de la Pyramide or the Périphérique edge into the woods).
- Phone mic frequency response and AGC may distort tilt (see Q7). This hasn't been quantified for the specific devices.

---

## Q3. Soundscape ecology / acoustic indices: forest interior vs edge vs urban park; distance-to-road gradients; habitat classification from short clips

### Takeaway
**NDSI** (ratio of 1-2 kHz "anthrophony" to 2-11 kHz "biophony") tracks **distance to the nearest road**, explaining about 37-40% of variance in a forest, with road noise detectable to about **1 km**. **ACI** tracks **openness / distance to the forest edge**. Indices are noisy on short clips and are usually computed on minutes to hours. Generic scene classifiers confuse "park" with "residential area". For a 5-20 s clip, NDSI-style band ratios are worth computing as a cheap feature. Don't expect a reliable forest-interior vs edge decision from indices alone.

### Cited Findings
**Turner, Fischer & Tzanopoulos (2018), "Sound-mapping a coniferous forest", PLoS ONE 13(1):e0189843** — [PLoS ONE](https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0189843)
- Study design:
  - Site: Thetford Forest, UK; 320 ha mosaic of conifer stands aged 0-85 years.
  - 73 points on a 250 m grid.
  - Summers 2014 and 2015, 06:00-11:00.
  - 3-min recordings, of which 2 min (12 × 10 s segments) were analysed; 889 samples, 29.6 h total.
  - Recorder: Roland R-05 with EM-172 capsules, at 1.5 m height.
- Indices (R soundecology): ADI, AEI, NDSI, ACI, BAI.
  - NDSI: anthrophony 1-2 kHz, biophony 2-11 kHz.
  - BAI: 2-8 kHz.
  - ADI/AEI: share of each of ten 1 kHz bands above −50 dBFS.
- **NDSI rose with distance from the nearest road** and was its strongest predictor:
  - 2014: r² = 0.373, p < 0.001;
  - 2015: r² = 0.397, p < 0.001.
- **NDSI reached 0 (anthrophony = biophony) at about 1 km from the nearest busy road** (A1065/A134; traffic volumes not reported).
- ADI and AEI were also correlated with road distance, more weakly.
- **ACI was the only index related to distance to the stand edge**, and was higher in more open areas.
- Between-year site correlation was highest for NDSI (r = 0.81), so it is the most stable index.
- Effect of time and wind:
  - NDSI was higher at 08:30-11:00 than at dawn.
  - ADI and BAI were higher at dawn.
  - Wind degraded ADI (rs up to −0.475) and inflated ACI (rs = 0.493).

**Other studies**
- Urban national parks (Washington DC): **distance to road had the strongest effect on NDSI**, followed by species richness. Rudge, Holland, Schmit & Shriver, SSRN preprint. — [SSRN 5616279](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5616279)
- A natural area exposed to road and rail noise: eco-acoustic indices "clearly reveal a spatial gradient in relation to distance from the motorway". — [Sustainability 2020, 12(24):10455](https://doi.org/10.3390/su122410455)
- An urban-park eco-acoustic assessment: clusters showed low NDSI and DSC scores dominated by road traffic. — [Sustainability 2021, 13(14):7857](http://dx.doi.org/10.3390/su13147857). A recommendation to record **at least 120 h continuously per site** and to combine several indices appeared in the same search. Which of these two papers it came from wasn't verified.
- Forest-edge ecoacoustics using explainable metrics along a distance-to-edge gradient: tropical bioRxiv preprint (2025), not peer-reviewed. — [bioRxiv 2025.09.28.679116](https://www.biorxiv.org/content/10.1101/2025.09.28.679116.full.pdf)
- DCASE acoustic scene classification:
  - "park" is easily confused with "residential area" and vice versa (DCASE 2016, 15 classes). — [arXiv 1607.03682](https://arxiv.org/pdf/1607.03682); [arXiv 1807.04970](https://arxiv.org/pdf/1807.04970)
  - street_traffic is among the scenes hardest to tell apart between cities. — [arXiv 1905.00979](https://arxiv.org/pdf/1905.00979)
  - Class-wise accuracy tables are on the DCASE results pages. — [DCASE 2018 results](https://dcase.community/challenge2018/task-acoustic-scene-classification-results-c); [DCASE 2016 results](https://dcase.community/challenge2016/task-acoustic-scene-classification-results)

### Inferences
- From a 10-20 s clip, compute an **NDSI-like ratio** as (E[2-8 kHz] − E[1-2 kHz]) / (sum), after removing voice frames. Map it to a soft "distance-to-busy-road" likelihood: NDSI ≈ −1 near a road, ≈ 0 at about 1 km. Use a wide σ, because single short clips are noisy and the published fits explain only about 40% of variance.
- **In November, biophony is low** (no dawn chorus), so NDSI will skew negative everywhere near Paris. The ratio will mainly measure traffic. Calibrate locally rather than using the Thetford mapping.
- Forest vs open field vs street can be decided better from combined cues:
  - YAMNet class mix: "Vehicle/Traffic/Car passing" vs "Bird/Wind/Rustling leaves";
  - presence of *discrete* car passes (near road) vs continuous rumble (far);
  - reverberation tail (Q6).
  
  Indices alone are not enough.

### Gaps
- No study was found that reports classification accuracy of forest vs edge vs urban park from **5-20 s phone clips** with YAMNet/PANNs/AudioSet classes.
- No AudioSet-class-based habitat classifier with published accuracy was found within this search budget.

---

## Q4. Bird species as habitat indicators (BirdNET); November in Paris

### Takeaway
BirdNET can match experts at the species-list level in European cities. Precision per species varies widely (0.29 to >0.7), and single detections are unreliable. The principle is sound: woodpeckers, nuthatch and treecreeper suggest mature woodland; gulls, coots and ducks suggest water; pigeons and sparrows suggest buildings. But **November is a low-song season**, and a 5-20 s clip often contains no bird song. Treat bird species as an occasional bonus cue.

### Cited Findings
- European city study: BirdNET found **90% / 65%** of the species a human detected, at a low / high confidence threshold respectively.
  - Precision was **>0.70 for 9 of 13 species**; the lowest was **0.29**.
  - Occupancy estimates, including **habitat associations, were similar** whether from BirdNET or experts.
  
  — [BirdNET can be as good as experts for acoustic bird monitoring in a European city (ResearchGate)](https://www.researchgate.net/publication/395419520_BirdNET_can_be_as_good_as_experts_for_acoustic_bird_monitoring_in_a_European_city)
- Gothenburg urban dataset: per-species correctness depends on the confidence threshold. Expert validation and a well-chosen threshold are essential, and isolated detections raise false positives. — [Scientific Data 2025](https://www.nature.com/articles/s41597-025-05481-z)
- Review of BirdNET applications and pitfalls: performance is context- and species-dependent. — [BirdNET: applications, performance, pitfalls (ResearchGate)](https://www.researchgate.net/publication/368849592_BirdNET_applications_performance_pitfalls_and_future_opportunities)
- Soundscape frequency bands relate to habitat: **4-7 kHz with broadleaf woodland**, 7-10 kHz with older conifer. — [Turner et al. 2018](https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0189843)

### Inferences
- Useful rule-based indicator mapping (expert knowledge, not validated here):
  - great spotted woodpecker drumming/calls, Eurasian nuthatch, short-toed treecreeper, jay: woodland;
  - mallard, coot, moorhen, grey heron, black-headed gull: near the Bois de Vincennes lakes (Lac Daumesnil, Lac des Minimes, Lac de Gravelle);
  - feral pigeon, house sparrow: built-up edges.
  
  Use BirdNET with confidence ≥0.7 and require ≥2 detections. Location (Paris) and week (November) filters should be enabled in BirdNET.
- Calls (contact and alarm calls of tits, jay, crows, ring-necked parakeet, which is common in Paris parks) persist in winter. Song is reduced.

### Gaps
- No peer-reviewed study was found quantifying BirdNET-detected species as indicators of **forest interior vs edge vs water** in short clips, or of winter detection rates in Paris woods.
- The time-of-day and season effects on detection rates were not sourced for November. The Thetford data are summer mornings only.

---

## Q5. Water, wind in leaves, aircraft, trains, bells as location cues in woodland

### Takeaway
No quantitative detectability distances for these sources in woodland were found in peer-reviewed literature within the search budget. Of the modelling work found, a physics-based detection-distance model for recorders in forests is the closest.

### Cited Findings
- Haupert et al. (arXiv 2211.16077) give a physics-based model of acoustic detection distance for autonomous recorders in an Alpine and a Neotropical forest, across the day-night cycle and seasons. Detection distance depends on background noise level and on frequency-dependent attenuation (geometric spreading, air absorption, habitat excess attenuation). The specific numbers weren't extracted. — [arXiv 2211.16077](https://arxiv.org/pdf/2211.16077)
- Wind confounds acoustic indices. In Thetford, the proportion of wind-affected recordings correlated with Met Office wind speed (rs = 0.28-0.48), and wind changed ADI, AEI and ACI significantly. — [Turner et al. 2018](https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0189843)
- Bruitparif measured rail noise from the **RER A** at building facades in Vincennes (2017 report). This gives a local rail source reference. — [Bruitparif 2017 RER A Vincennes report](https://www.bruitparif.fr/pages/En-tete/400%20Nos%20publications/700%20Rapports%20d'%C3%A9tude/2017-10-09%20-%20Rapport%20-%20Mesures%20de%20bruit%20d'origine%20ferroviaire%20en%20fa%C3%A7ade%20de%20logements%20de%20la%20ligne%20RER%20A%20%C3%A0%20Vincennes.pdf)

### Inferences
- **Aircraft** are heard at about the same level across a 1-2 km area, because propagation is from above and less affected by trunks and ground. They say almost nothing about position at our scale. Use them only if ATC/approach-path geometry places a known track overhead.
- **Water**: a still lake is silent. Waterfowl calls are the real "near water" cue (Q4). Fountains and weirs are point sources, plausibly audible only within tens of metres in the presence of traffic noise. This is unverified, so don't model it without measurement.
- **Bells** (Vincennes church, Château chapel) are only intermittent at hours. They are useful only if the clip captures them, and they are low-frequency enough to cross a forest with little loss.
- **Zoo** (Parc zoologique de Paris) and **racecourse** (Hippodrome de Vincennes) are events, not continuous sources. YAMNet "animal" or "crowd/PA" classes can act as binary "near X" cues, again as soft evidence.
- **Wind in leaves**: in leaf-off November, the rustling-leaves signature is weak. Wind on the microphone dominates instead (Q7).

### Gaps
- Detectability distances for fountains, streams, bells and aircraft in woodland: not found.
- Orly approach-path geometry over the Bois de Vincennes: not researched here.

---

## Q6. Reverberation in forests as a cue; blind RT estimation from voice

### Takeaway
Forests have a **measurable reverberant tail from trunk and canopy scattering**, which open fields lack. Impulse waveforms in a forest are clearly reverberant, while in an open field they are near-clean impulses. Densities that attenuate more also reverberate longer. The mid-band of about **1-3 kHz** shows the most stable reverberation with distance. This makes a "forest vs open field" decision plausible from a speech-decay estimate. Exact RT values by forest type were not obtained from primary texts.

### Cited Findings
- Padgham (2004, JASA 115(1), DOI 10.1121/1.1629304), two Australian forests:
  - the **denser forest showed much slower reverberative decay** and much greater attenuation;
  - reverberation changed relatively little with distance in a **central band of about 1-3 kHz**;
  - raising the source reduced reverberation; raising the receiver reduced attenuation.
  
  — [Abstract](https://data.zhenzhi.com/details/1/876875671)
- Huisman & Attenborough (1991): high-frequency attenuation and reverberation below the canopy are dominated by trunk multiple scattering. — [Abstract](https://data.zhenzhi.com/details/1/993718255)
- Single tree in an open field (JASA 2013, 134(1):264; authorship believed to be Yang, Kang & Cheal, unverified):
  - **RT20 is proportional to crown size**, the most important factor;
  - leaves added about **+0.08 s RT20 at 4 kHz**.
  
  — [JASA abstract](https://pubs.aip.org/asa/jasa/article-abstract/134/1/264/614411/Quantifying-scattered-sound-energy-from-a-single?redirectedFrom=fulltext); [ResearchGate](https://www.researchgate.net/publication/249996347_Quantifying_scattered_sound_energy_from_a_single_tree_by_means_of_reverberation_time)
- Richards & Wiley (1980, American Naturalist) is the classic reference on reverberation and amplitude fluctuations of sound in forests. Dense forests reverberate more than sparse forests or open areas. — [Studies in Avian Biology chapter](https://digitalcommons.usf.edu/cgi/viewcontent.cgi?article=1149&context=sab); [Environmental acoustics and the evolution of bird song](https://www.researchgate.net/publication/239844473_Chapter_1_Environmental_Acoustics_and_the_Evolution_of_Bird_Song)
- Forest edge and interior impulses (red pine, US): open-field waveforms are close to simple impulses, while edge and in-forest waveforms show strong reverberation after the direct arrival. — [Swearingen et al. 2013 record](https://bvbvf1.bib-bvb.de/vufind/PrimoRecord/cdi_proquest_miscellaneous_1350151276)
- A forest RT figure of "**about 2 s, range about 1.2-3 s**" depending on stand and ground came up in search results. It was not traced to a specific primary paper; possibly the Forum Acusticum 2025 in-situ vs scale-model comparison. Flag as uncertain. — [Forum Acusticum 2025 paper](https://dael.euracoustics.org/confs/fa2025/data/articles/000147.pdf)
- Forest reverberation is now modelled for audio rendering, using single-scattering cylinders as trunks. — [Microsoft Research MMSP 2021 forest reverberator](https://microsoft.com/en-us/research/uploads/prod/2021/10/A-fast-forest-reverberator-using-single-scattering-cylinders-MMSP-2021.pdf)

### Inferences
- Forest reverberation is **diffuse and low-level** (scattered energy), unlike a street canyon's strong discrete reflections from façades. A blind decay estimate on the speaker's own voice can be compared across cases:
  - open field: very short tail;
  - forest: a long, weak, high-frequency-rich tail, around 1-3 kHz;
  - street canyon: a strong early tail with flutter.
  
  A simple method is the slope of the energy decay after speech offsets in the 1-4 kHz band.
- The talker is close to the phone (high direct-to-reverberant ratio), so tail energy will be 20-40 dB below the direct voice. Background noise of 45-55 dB(A) in a wood may mask it. Expect only a coarse three-way decision (open / forest / built-up) with low confidence. This needs testing on our recordings.
- Leaf-off in November reduces the canopy contribution, but trunk scattering remains.

### Gaps
- No numeric RT60 values by frequency for deciduous European forests were obtained (Padgham's tables are paywalled).
- No study was found validating **blind RT estimation from speech on smartphones outdoors** to classify forest vs open vs street.

---

## Q7. Smartphone microphone limits outdoors

### Takeaway
The best iOS sound-meter apps reach about ±2 dB(A) of a reference, and within ±1 dB with a calibrated external mic. Android is much less consistent. **No sourced data were found on AGC, wind noise or high-frequency limits.** Those must be handled empirically, for example by recording raw audio with processing disabled and rejecting windy frames.

### Cited Findings
- Kardous & Shaw (2014, NIOSH, JASA-EL):
  - 10 iOS apps tested (from 130+) over 65-95 dB.
  - The best had mean differences of **0.07 dB (unweighted)** and **−0.52 dB(A)** from reference; two others were within ±2 dB.
  - Only **4 of 62 Android apps** partially met the criteria.
  - Type-2 meter tolerance is ±2 dB(A).
  
  — [NIOSH blog 2014](https://cdc.gov/niosh/blogs/2014/sound-app.html); [CDC stacks](https://stacks.cdc.gov/view/cdc/36704/cdc_36704_DS1.pdf)
- With calibrated external microphones, accuracy improved to about **±1 dB** (Kardous & Shaw 2016 follow-up). — [CDC stacks](https://stacks.cdc.gov/view/cdc/44791/cdc_44791_DS1.pdf); [PMC4659422](https://pmc.ncbi.nlm.nih.gov/articles/PMC4659422)
- Wind degrades soundscape indices even with dedicated recorders. — [Turner et al. 2018](https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0189843)

### Inferences
- The browser `getUserMedia` path applies `echoCancellation`, `noiseSuppression` and `autoGainControl` by default. Set them to `false` for any level or spectral-tilt cue; otherwise the background level is suppressed. This is a known Web API behaviour, not sourced here.
- Our "voice as loudness reference" approach partly cancels unknown mic gain, but AGC changes gain *during* the clip. Measure background in the gaps right next to speech.
- Wind on the mic shows up as high, uncorrelated energy below about 200 Hz. Reject frames where the <200 Hz energy jumps without a matching broadband traffic signature. This is a heuristic; YAMNet's "Wind noise (microphone)" class is also usable.
- The ADI/AEI −50 dBFS thresholds from dedicated recorders won't transfer to phones directly. Normalise to the voice level.

### Gaps
- No sourced data on phone mic frequency response above about 10 kHz outdoors, AGC time constants, or wind-noise levels vs wind speed.

---

## Q8. Concrete model parameters and algorithms implementable in under a day

### Takeaway
Extend the existing road-noise map with a **forest excess-attenuation term** and a **ground-type switch**, and add two cheap clip features (**traffic spectral tilt**, **NDSI-like ratio**), plus YAMNet/BirdNET binary cues. Fuse them all as soft likelihood terms with wide σ in `localise.py`. All values below come from Q1-Q7; numbers marked [assumed] are engineering choices to be validated with recordings.

### Cited Findings
- Forest floor flow resistivity **20 kPa·s·m⁻²**, porosity 0.5; grass **300 kPa·s·m⁻²**, porosity 0.75; bark absorption 0.075. — [Van Renterghem 2014](https://users.ugent.be/~tvrenter/publicaties/guidelinestreebelts.pdf)
- Forest excess attenuation about **7-10 dB/100 m** (spruce, beech, ash; receiver 1.2-3.9 m). — [Bucur](https://cdn.homeownershub.com/media/73165/60a02322623617.28914949.pdf). About 10 dB(A) per 100 m of pine for road traffic (secondary, conflicting). — [Academia.edu](https://www.academia.edu/112538310/Sound_propagation_through_forests_and_tree_belts)
- First 10-25 m of trees gives only 0-4 dB. About 5 dB(A) needs ≥30 m of dense wood. — [Van Renterghem 2014](https://users.ugent.be/~tvrenter/publicaties/guidelinestreebelts.pdf)
- Leaf-off penalty up to about 3 dB(A). — [Forest Research](https://cdn.forestresearch.gov.uk/2025/05/TDAG_FirstStepsUrbanNoise.AW_.pdf)
- NDSI bands 1-2 kHz vs 2-11 kHz. NDSI ≈ 0 at about 1 km from a busy road; r² ≈ 0.37-0.40 vs road distance. — [Turner et al. 2018](https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0189843)
- Air absorption about 3-4 dB/100 m at 4 kHz. — [DTIC ADA588823](https://apps.dtic.mil/sti/pdfs/ADA588823.pdf)
- Phone level accuracy about ±2 dB at best on iOS. — [NIOSH](https://cdc.gov/niosh/blogs/2014/sound-app.html)

### Inferences
Implementation plan, about one day:

1. **Forest attenuation in the road-noise map.** Add `data/forest.geojson` from OSM: `landuse=forest`, `natural=wood`, `leisure=park` polygons with trees. For each grid cell and each road segment, compute the length `d_f` of the straight path that lies inside wood polygons (use a raster mask and sample about every 10 m).
   - Predicted level: `L = L_road(r) − A_forest(d_f)`.
   - `A_forest = 0` for `d_f < 20 m`. Otherwise `A_forest = min(k·(d_f − 20), A_max)`, with `k = 0.05 dB/m` (leaf-off, conservative), `0.07` for evergreen or leaf-on [assumed from the 5-10 dB/100 m range], and `A_max = 15 dB` [assumed].
   - Keep the −15 dB building screening for built-up paths.
2. **Ground switch.** Open grass/water paths use the existing model. Forest paths are already covered by `A_forest`, which includes the soft-floor effect. Hard surfaces (lakes, plazas) get +1-3 dB vs grass [assumed].
3. **Likelihood σ.** Level residual σ = **6 dB** inside forest and for sources >500 m away (motorway, Périphérique), and 4 dB in town [assumed; reflects ±2 dB phone error plus meteorology plus traffic variability].
4. **Traffic spectral tilt feature.** From non-voice frames (YAMNet speech prob < 0.2), compute `T = L(125-500 Hz) − L(1-4 kHz)` in dB.
   - Predict `T(cell)` as `T0 + a·d_air/100 + b·d_f/100`, with `T0 ≈ 5 dB` near a road, `a ≈ 3 dB` per 100 m of air path (from the 4 kHz air absorption), and `b ≈ 3-5 dB` per 100 m of forest [assumed].
   - Use σ = 6 dB. Calibrate `T0`, `a` and `b` with 3-4 transect recordings in the Bois de Vincennes on Saturday.
5. **NDSI-like feature.** `N = (E2-8k − E1-2k)/(E2-8k + E1-2k)` on non-voice frames. Use it only as a weak monotone "distance to nearest busy road" term, logistic from N = −0.8 (<100 m) to N = 0 (about 1 km), σ = 0.4 [assumed]. Downweight in November, when biophony is low.
6. **Binary cue terms** (YAMNet/BirdNET, confidence ≥0.7 and ≥2 detections):
   - waterfowl or gulls: ×3 likelihood within 150 m of OSM `natural=water` [assumed];
   - woodpecker, nuthatch or treecreeper: ×2 within wood polygons >50 m from the edge [assumed];
   - discrete car passes (YAMNet "Car passing by" with a rise-fall envelope): ×3 within 60 m of a road [assumed];
   - train/RER: ×2 within 300 m of `railway=rail` [assumed].
   
   Absence of a cue is weak evidence (×0.8) because of low detection rates in short clips.
7. **Reverb feature (optional, last).** Fit the decay slope of 1-4 kHz energy in the 300 ms after each speech offset.
   - Slow decay → forest likely: ×1.5 in wood cells.
   - Near-zero tail → open field or lake shore.
   - Strong, quick early tail → street canyon.
   
   Low confidence, so cap its likelihood ratio at 1.5 [assumed].
8. **Capture settings.** `getUserMedia({audio: {echoCancellation: false, noiseSuppression: false, autoGainControl: false}})`. Reject windy frames (high <200 Hz energy plus YAMNet "Wind noise"). Report "acoustic evidence weak" if fewer than 3 s of clean non-voice audio remain.
9. **Ask-back synergy.** Acoustics give broad blobs, so use them to seed the question selector:
   - "Can you hear the motorway?" separates near-Périphérique from interior;
   - "Can you see water / the lake?" and "Are you under trees or in an open lawn?"
   
   These yes/no questions are cheaper and more reliable than acoustic inference, and fit 6.5 of the brief.

### Gaps
- All [assumed] coefficients need field calibration. No published traffic-tilt-vs-distance curve or forest-specific phone dataset was found.
- Verify the ISO 9613-2 Annex A foliage table (see Q1 Gaps) if we want to cite a standard in the pitch.
