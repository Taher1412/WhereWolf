# Active acoustic sensing in forests: what one phone chirp can tell you in woodland

Scope: the phone plays a 0.5 s sweep after each report, records it, deconvolves the impulse response (IR), and measures RT60, direct-to-reverberant ratio (DRR) and echo delays. This note covers what that IR looks like in woodland (Bois de Vincennes-type mixed deciduous forest) and what can honestly be inferred from it.

Conventions used in the inferences: c = 343 m/s. Echo delay for a reflector at distance d from a phone that holds both the speaker and the mic is t = 2d/c, which is 5.83 ms per metre. Wavelength is 34 cm at 1 kHz and 8.6 cm at 4 kHz.

---

## 1. Measured forest impulse responses: RT, decay shape, frequency dependence, first trunk echo

### Takeaway
Forests are reverberant but "dry". Mid-band T30 runs from about 0.3 to 1.7 s and peaks around the 1 kHz octave, because trunk diameters (10–60 cm) are comparable to the wavelength. Low frequencies (63–125 Hz) and high frequencies (4–8 kHz) decay faster. The decay is not a single exponential: a fast early drop is followed by a long, low tail. Echo density is roughly constant (diffuse) from the first few tens of ms. That is unlike a room, where echo density builds up over time, and unlike a street, which gives a few discrete specular spikes. Discrete trunk echoes exist, but they are buried in a dense scattered field.

### Cited Findings
- **Koli National Park, Finland (Shelley, Murphy & Chadwick, DAFx-13, 2013).** Mixed birch and spruce, trees up to about 21 m tall with trunks up to about 60 cm in diameter, 50–70 cm of snow on the ground. They used a 30 s log sweep (22 Hz–22 kHz) through a Genelec 8130A with the source and mic 1.5 m above the ground, 7.2–11 m apart, analysed per ISO 3382. Results:
  - T30 is highest in the 1 kHz octave band at **1.3–1.7 s**, which they describe as "comparable with that of a small church or concert hall".
  - T30 is about **0.1–0.3 s at 63–125 Hz** and about **0.4–0.5 s at 4 kHz**, falling to about 0.3–0.4 s at 8 kHz. Values are read off their Fig. 4a.
  - C50 (early/late energy ratio) is **about 15–40 dB**: highest at 125 Hz (about 41 dB at one site) and lowest at 1 kHz (about 8 dB at one site). Overall they call it "a relatively dry reverberant space".
  - The authors attribute the 1 kHz peak to trunk widths of 10–60 cm being comparable to the wavelength.
  - In the IR envelopes (Fig. 3a), the direct sound arrives at about 27 ms (9 m path). Dense reflections follow at about −20 to −40 dB within the next 20–60 ms, and the envelope falls toward −80 dB by about 100–140 ms in the directional-source IR. Values are read off the figure.
  - The intensity-vector analysis (Fig. 5) shows "a strongly directional direct sound" and a tail that is "very scattered", with "occasional clusters" of vectors pointing in the same direction. The authors interpret those clusters as "distinct reflections ... from nearby tree trunks" at frequencies of 3 kHz and above, and as terrain gradients at lower frequencies.
  - They expected summer conditions (no snow, foliage, warmer air) to reduce RT.
  - IRs are downloadable from OpenAIR.
  - [Shelley et al. 2013, DAFx-13 pp. 351–355](https://eprints.whiterose.ac.uk/78001/1/56.dafx2013_submission_26.pdf)
- **Kaneko & Gamper (IEEE MMSP 2021, Microsoft Research).** They compared real forest IRs (Koli winter and summer from OpenAIR; Volunteer Park, Seattle, at several distances) with a single-scattering-cylinder model. Findings:
  - "Real forest IRs have nearly constant echo density profiles". Normalised echo density is about 0.9–1.0 from t = 0 to 0.5 s (their Fig. 3).
  - Energy decay curves (EDCs, band-passed 500 Hz–8 kHz) drop about 10–15 dB almost immediately. They then decay slowly to about −45 dB at 1 s (Fig. 4, read off the figure).
  - "The energy decays more slowly with increasing D", the source–receiver distance, in both real and synthetic IRs (Volunteer Park measured at about 5.5, 9.3, 30.3 and 48.8 m).
  - C50 decreases with distance: Volunteer Park drops from about 20 dB at 5 m to about 10 dB at 30–40 m (Fig. 5).
  - Koli T60 falls from about 0.7–0.9 s in the 500 Hz–1 kHz bands to about 0.35–0.4 s at 4–8 kHz (Fig. 5, read off the figure).
  - Single-cylinder scattering amplitude drops about 30 dB relative to the incident wave for scattering angles above about 20°.
  - Plausible IRs needed about 200k–500k scatterers per km², which they note is 5–10× typical real tree density. They attribute the gap to unmodelled leaves, branches and multiple scattering.
  - [Kaneko & Gamper 2021, MMSP](https://microsoft.com/en-us/research/uploads/prod/2021/10/A-fast-forest-reverberator-using-single-scattering-cylinders-MMSP-2021.pdf)
- **Padgham (JASA 103(4):2154–2166, 1998; often cited as 2004).** Two Australian forests:
  - "The structurally denser of the forests exhibits much slower reverberative decay."
  - The frequency dependence of reverberation is qualitatively similar in both forests.
  - "There exists a central range of frequencies between 1 and 3 kHz within which reverberation varies relatively little with distance."
  - Attenuation is much greater in the denser forest.
  - Source height mainly affects reverberation; receiver height mainly affects attenuation.
  - I found the abstract only, not the dB/s values. The citation year is inconsistent across sources (1998 vs 2004; JASA 115:402–410 also appears).
  - [abstract mirror](https://data.zhenzhi.com/details/1/876875671)
- **Huisman & Attenborough (JASA 90(5):2664–2677, 1991).** Reverberation and attenuation in a pine forest at 10–100 m range:
  - Below 1 kHz, excess attenuation fits a two-parameter ground-impedance model.
  - At high frequencies, loss and reverberation are attributed to multiple scattering by trunks.
  - Measured attenuation was well above the Dutch-Scandinavian noise prediction scheme.
  - The measurements show a strong height dependence that the model fails to reproduce.
  - I found the abstract only.
  - [abstract mirror](https://data.zhenzhi.com/details/1/993718255)
- **Richards & Wiley.** Reverberation is "potentially the most severe problem for song recognition and localization in a forest" and is strongly frequency dependent. Forest sound is degraded more by reverberation off leaves and trunks; open-habitat sound is degraded more by turbulent amplitude fluctuation. [Richards 1981, Studies in Avian Biology 6:297–300](https://sora.unm.edu/sites/default/files/SAB_006_1981_P297-300%20Part%206%20Environmental%20Acoustics%20and%20Censuses%20of%20Singing%20Birds%20Douglas%20G.%20Richards.pdf)
- **Swearingen et al. (ASA 2007).** At low frequencies, wavelengths are much longer than trunk diameters, so sound is "largely unaffected" by trunks. [Swearingen et al., ASA 153rd meeting](https://acoustics.org/pressroom/httpdocs/153rd/swearingen.html)

### Inferences
- **The phone geometry differs from every published forest IR.** All the measured forest IRs above use a separate source and receiver 5–50 m apart, so the direct sound plus forward scatter dominates. On a phone the speaker and mic are about 10–15 cm apart. The "direct sound" is the internal speaker-to-mic coupling, tens of dB above any echo, and everything the phone records afterwards is **backscatter** (scattering angle about 180°). Kaneko & Gamper's −30 dB drop beyond 20° means backscatter from a single trunk is weak.
  - Expect a phone forest IR to look like this: a huge coupling spike at 0–1 ms, then a ground echo, then a smooth, noise-like tail that decays steadily. A few discrete trunk peaks will show only from trunks within a few metres.
  - Published RT/C50 values are therefore an upper bound on what a collocated phone will measure, not a direct prediction.
- **The ground reflection is a fixed marker.** With the phone at 1.2–1.5 m height, the ground echo arrives at 2h/c ≈ **7–9 ms** in every outdoor IR: open field, street or forest. It can serve as a calibration and sanity check. Over leaf litter it should be weaker than over asphalt, which absorbs very little.
- **Distance to the first trunk echo.** For trunks scattered at random with density n stems/m², the mean distance from a random point to the nearest trunk is 0.5/√n. Some examples:
  - 400 stems/ha (n = 0.04 m⁻²): about 2.5 m, giving a first trunk echo at about **15 ms**.
  - 100 stems/ha: about 5 m, giving about 29 ms.
  - Large old-growth stands of about 200 stems/ha: about 3.5 m, giving about 21 ms.

  This is geometry for a random (Poisson) layout, not a measured value. Real stands are more regular, and the observer usually stands on a path, which pushes the first trunk out to roughly the path half-width plus 1–2 m.
- **A sound model of the tail.** This is a physics derivation of my own, not validated against data. With collocated source and receiver, single scattering from vertical cylinders (radius a, density n) and no air absorption, the backscattered power envelope should follow approximately:

  P(t) ∝ n·a·t⁻²·exp(−2a·n·c·t)

  The t⁻² factor combines two effects. A trunk at range d returns intensity proportional to a/d³ (spherical spreading going out, cylindrical spreading after reflection). The number of trunks in an annulus grows as 2πn·d·dd. The exponential term is shadowing: the mean free path between trunks is ℓ = 1/(2a·n), for example about 83 m for 400 stems/ha with 30 cm trunks.

  So **level × t² should decay exponentially, with a rate that encodes the stem density times the diameter (2a·n)**. It is the acoustic analogue of basal area. This is the same model family (single scattering cylinders) that Kaneko & Gamper found produces realistic forest IRs.
- **Season matters.** Snow raised RT at Koli, and leaves add high-frequency scattering. In late November the Bois de Vincennes is mostly leafless (deciduous oak, chestnut, hornbeam etc.), so trunk and branch scattering will dominate. That is close to the Koli birch condition.

### Gaps
- I found no published IR measured with a **collocated** source and receiver (monostatic) in a forest at audible frequencies, and none from a smartphone in a forest.
- Exact Padgham and Huisman decay rates in dB/s: abstracts only.
- Sakai, Sato & Ando (JASA 104:1491–1497, 1998), forest vs concert hall: I found the citation only, no values.
- Wiley & Richards 1978/1982 tail durations: not found.
- Naguib and Slabbekoorn forest reverberation numbers: not retrieved.
- Unread potentially relevant sources:
  - The York MSc thesis on Wheldrake Wood IRs: [Feng thesis](https://webfiles.york.ac.uk/OPENAIR/IRs/wheldrake-wood/Sinuo_Feng_Thesis.pdf). The search snippet says T30 is 1.3–1.7 s at 1 kHz, but that may be conflated with Koli.
  - A 2026 arXiv paper: [ForestIR (arXiv 2607.06299)](https://arxiv.org/pdf/2607.06299)

---

## 2. Can tree density, trunk diameter, or distance to the edge or a clearing be estimated from echoes?

### Takeaway
In the bat and biosonar literature, yes for coarse vegetation parameters: leaf density, leaf size, needle vs broad-leaf. That work uses ultrasound at 1–2 m range, often needs about 10 echoes, and can recover one parameter only if the others are known. At audible frequencies from a phone, the realistic outputs are (a) an "inside dense vegetation vs open" indicator, (b) a coarse scattering-density index from the tail decay, and (c) possibly the onset delay of backscatter from a nearby forest edge. Individual trunk diameters are not realistically recoverable from one phone chirp.

### Cited Findings
- **Yovel, Stilz, Franz, Boonman & Schnitzler (2009), *PLoS Comput Biol* 5(7):e1000429.**
  - Setup: a 4 ms 140→25 kHz FM sweep from 1.5 m, 4 species × 50 plants × 25 aspect angles.
  - Needles (spruce) act as high-pass filters; broad leaves (about 8 cm, apple and beech) filter less.
  - About 10 echoes from one plant were enough to show the characteristic spectral shape.
  - In a *Ficus* leaf-removal experiment (11 density steps × 36 angles), normalised spectral energy correlated almost perfectly and linearly (negatively) with leaf density at 27 cm wavelength scale. Removing leaves noticeably reduced absolute echo energy, so leaves dominate echo strength.
  - Twig spacing of 15 cm produced envelope peaks about 0.9 ms apart.
  - The authors warn that variability makes "characteristic spectral notches" futile as cues.
  - [Yovel et al. 2009](https://pmc.ncbi.nlm.nih.gov/articles/PMC2699101/)
- **Yovel et al. (2008/2009).** An SVM on spectrogram time and frequency cues classified plant species, with classification possible from a single echo. [search snippet, PMC2267002](https://pmc.ncbi.nlm.nih.gov/articles/PMC2267002)
- **Computational foliage-echo model (PLoS ONE 2017, Virginia Tech group).** Foliage is described by leaf density, leaf size and leaf orientation. "A single foliage parameter can be estimated with high accuracy if the other two parameters are known a priori"; Lasso regression "did not support simultaneous estimation of all three parameters". [PMC5560571](https://pmc.ncbi.nlm.nih.gov/articles/PMC5560571)
- **UAV forest flight simulation (bat-inspired sonar).** Simple batch processing estimates sparse leaf locations well; wavelet scattering plus SVM handles dense leaves. [search snippets, NSF PAR / PMC9858711](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9858711/)
- **Stilz & Schnitzler (2012), JASA 132(3):1765–1775.**
  - They ensonified trees, meadows and water at 1–20 m with a mobile ultrasonic sonar and derived reflection-loss and spreading laws.
  - Atmospheric attenuation is the main range limiter. Energy loss at the reflecting surface varies more than geometric spreading and accounts for most differences between targets.
  - Maximum detection range for "extended backgrounds such as a forest edge" can be **as short as 2.4 m** at bat ultrasonic frequencies.
  - I could not retrieve the target-strength values themselves.
  - [USF digital commons abstract](https://digitalcommons.usf.edu/kip_articles/9842)

### Inferences
- **Stem density × diameter index.** Fit the t⁻²-compensated tail decay (Section 1) between about 20 and 150 ms to get 2a·n. This is the only density-type estimate that seems physically grounded for one audible chirp.
  - Expected precision: poor. Probably factor-of-2 level, because ground reflection, branches, foliage and multiple scattering all bias it, and Kaneko & Gamper needed 5–10× the real tree count to match real IRs.
  - It is useful as a relative "dense stand vs open stand vs clearing" indicator, not as an absolute stems/ha value.
- **Trunk diameter.** It is set by the frequency of the scattering transition (ka ≈ 1, so a ≈ λ/2π: 5.5 cm at 1 kHz, 1.4 cm at 4 kHz). Koli's 1 kHz RT peak is consistent with 10–60 cm trunks. With everything blended in one omnidirectional chirp, I would not expect a usable per-tree diameter. At most you get a spectral-shape feature of the tail.
- **Distance to a forest edge or clearing boundary from inside a clearing.** The edge acts as a rough volume reflector, not a specular wall. Expect a quiet gap after the ground echo, then a **rise in diffuse energy starting at t = 2D/c**, not a sharp peak.
  - Example: an edge 20 m away gives onset at about 117 ms; 40 m gives about 233 ms.
  - Because the phone speaker is roughly omnidirectional below about 2 kHz, this measures the distance to the *nearest* edge segment (plus returns from farther segments), not its direction.
  - This maps neatly onto the existing pipeline. Treat OSM `landuse=forest` / `natural=wood` polygon boundaries as "soft walls". The onset delay then gives a likelihood on distance-to-nearest-edge for each grid cell.
  - Whether the onset clears the noise floor at 20–40 m is unverified (see Section 3).
- **From inside the forest**, the edge is not separable from the volume backscatter. The trunks between you and the edge shadow it (mean free path ℓ is tens of metres) and dominate the return.

### Gaps
- I found no paper estimating stem density, basal area or trunk diameter from audible-band backscatter in real forests.
- I found no robotic sonar field results in forests with quantitative density estimates; I searched but did not retrieve Kuc or Müller robot-in-forest papers.
- The "acoustic flow" literature (Müller) was not retrieved.
- Stilz & Schnitzler target strengths, and anything at audible frequencies: not obtained.

---

## 3. Is a forest edge a measurable reflector from a field or clearing? Strength vs a building facade

### Takeaway
A forest edge does return organised backscatter, measured with an impulsive source (a propane cannon) at 60–800 Hz. Tree groups can reflect energy of the same order as the direct sound in roadside noise-barrier work. But it is a diffuse, extended, lossy return. Expect it to be clearly weaker and much less peaky than a flat facade, which returns a sharp specular spike. No paper gives a direct facade-vs-forest-edge echo comparison.

### Cited Findings
- **Swearingen, White, Guertin, Mifflin, Onder, Albert, Decato & Tunick (ASA 153rd meeting, 2007; Camp Ripley, red pine edge).** Microphones were placed in the open field, at the edge, and inside the forest, with a propane-cannon source.
  - Peak levels: 141 dB (A1, open field), 127 dB (A2), 120 dB (A3, 25 m into the forest). That is about 14 dB then 7 dB of drop. The text gives no distances, so no dB/m figure.
  - Backscatter "is not organized" below 60 Hz. Incident and backscattered signals "behave similarly" from 60 to 800 Hz. Above 800 Hz they separate, for reasons not yet known.
  - "After passing 25 m into the forest, the sound level is insensitive to direction of arrival": the field is fully diffuse.
  - [Swearingen et al. 2007](https://acoustics.org/pressroom/httpdocs/153rd/swearingen.html)
- **Swearingen et al. (JASA 133(5):2566–2575, 2013), "Influence of a forest edge on acoustical propagation".** Attenuation is lower in the open field and higher in the forest, and stronger in the 1–2 kHz range when sound propagates into the forest. This is from the search snippet of the abstract. [record](https://bvbvf1.bib-bvb.de/vufind/PrimoRecord/cdi_proquest_miscellaneous_1350151276); the full data report is DTIC ADA470913 [DTIC](https://apps.dtic.mil/sti/pdfs/ADA470913.pdf)
- **Roadside tree groups (Institute of Acoustics proceedings, about 2010, noise barriers and plants).** "Reflection intensities were significantly higher than those of the direct noise from the reflecting tree group, in the same order of magnitude as the direct sound."
  - This is a search snippet only; the PDF returned 404, so the context and geometry are unverified.
  - [IOA proceedings link](https://www.ioa.org.uk/system/files/proceedings/m_weber_p_angst_impact_of_plants_on_the_protection_effect_of_noise_barriers.pdf)
- **Rogers, Shen & Lee (IOA), forest backscatter.** They made an early backscatter measurement from a grassy field next to a wood, with the source and meter 60 m and 140 m from the edge. The paper calls itself preliminary, with ground effects not fully accounted for. It is a snippet only; the PDF returned 404. [IOA link](https://www.ioa.org.uk/system/files/publications/JC%20ROGERS%20W%20SHEN%20SM%20LEE%20ACOUSTIC%20SCATTERING%20MEASUREMENTS%20ON%20MODEL%20TREES%20AND%20THEIR%20EXTENSION%20TO%20NATURAL%20FORESTS.pdf)
- **RWTH Aachen forest reflection model.** The earlier version treated the forest edge as the reflector. The newer version spreads representative trees across the forested area, validated on 66 source–receiver pairs at 4 sites. This is a snippet only. [RWTH](https://publications.rwth-aachen.de/record/769227/files/769227.pdf?version=1)
- **Stilz & Schnitzler (2012).** For bat ultrasound, a forest edge as an extended background can be detectable only out to about 2.4 m in poor conditions, because of air absorption plus surface loss. [abstract](https://digitalcommons.usf.edu/kip_articles/9842)

### Inferences
- **Rough strength estimate.** This is geometric acoustics of my own, flagged as an estimate.
  - A single rigid trunk of radius a at range r, compared with a flat wall at the same range, returns roughly an amplitude factor √(a/(2r)) in the specular plane. For a = 0.15 m and r = 5 m that is about **−18 dB below a facade at the same distance**; at r = 20 m it is about −24 dB.
  - A forest edge is many such trunks spread over a range of depths. Its total energy can approach a facade's, but it is spread over tens of ms instead of one spike.
  - Peak-picking (the current street algorithm) will therefore underperform. Use an **energy-envelope onset** detector instead.
- **Use 0.5–2 kHz for edge detection.** Swearingen's organised-backscatter band (60–800 Hz) plus the trunk-scattering resonance near 1 kHz point to 0.5–2 kHz. Phone speakers roll off below about 300–500 Hz (general knowledge, not sourced here), so **about 500 Hz to 2 kHz** is the practical band.
- **The current 0.3 m street precision will not carry over.** An edge is a statistical surface whose depth varies by several metres. Expect edge-distance uncertainty of a few metres at best. That is still useful against a 20–40 m grid.

### Gaps
- I found no measured echo level from a forest edge back to a collocated source and receiver at audible frequencies.
- I found no direct facade-vs-tree-line comparison.
- Both IOA PDFs were unavailable (404).

---

## 4. Smartphone active acoustic sensing: outdoor and vegetation performance, ultrasound vs audible, range limits

### Takeaway
Smartphone echo sensing is mature indoors at short range: about 1–2 cm ranging up to about 4 m, and room geometry within 0.3 m at the 80th percentile. I found no peer-reviewed smartphone echo-sensing results outdoors or in vegetation. Near-ultrasound (17–22 kHz) would be stealthier but suffers much higher air absorption and weak backscatter from extended vegetation (the bat "2.4 m" result). For forest-scale (5–50 m) returns, audible 0.5–4 kHz is the only band with a chance.

### Cited Findings
- **BatMapper (Zhou et al., ACM MobiSys 2017).** Uses the phone speaker plus two mics.
  - "1–2 cm distance accuracy in ranges up to around 4 m". Door detection reached 92% precision, and room geometry errors were under 0.3 m at the 80th percentile.
  - A later system reports BatMapper at 60 cm median and 2.5 m 90th-percentile error, versus its own 30 cm and 1 m.
  - BatMapper-Plus notes that BatMapper "is unable to generate a satisfactory complete floor plan in a wide area".
  - [BatMapper PDF](https://zhoubinwy.github.io/pdf/batmapper.pdf); [MDPI Machines 2023 follow-up](https://mdpi.com/2075-1702/11/2/205)
- **Deep Room Recognition Using Inaudible Echos (arXiv 1809.00531, 2018).** A 2 ms single-tone inaudible chirp from the phone speaker; a CNN classifies rooms from the echoes. I did not verify the accuracy figure. [arXiv](https://ar5iv.arxiv.org/html/1809.00531)
- **Indoor smartphone SLAM with learned echoic location features (arXiv 2210.08493, 2022).** Chirp excitation gives "more individually-compact and mutually-separated" feature clusters than single-tone excitation. [arXiv](https://arxiv.org/pdf/2210.08493)
- **Stilz & Schnitzler (2012).** Air absorption is the dominant range limit for ultrasonic sonar on natural extended targets; forest edge range is as short as 2.4 m. [abstract](https://digitalcommons.usf.edu/kip_articles/9842)
- **Phone loudness.** There is no standard rating. GSMArena measured maximum loudness at exactly 1 m in a soundproof studio (now discontinued); DXOMARK measures SPL across volume steps in an anechoic box. I did not retrieve per-model SPL numbers. [GSMArena method](https://m.gsmarena.com/gsmarena_lab_tests-review-751p3.php); [DXOMARK method](https://www.dxomark.com/how-we-test-smartphone-speaker-playback/)
- **Not retrieved:** EchoTag, SAMS and BeepBeep. BeepBeep is two-phone ranging, not echo sensing. I did not retrieve their outdoor numbers in this session.

### Inferences
- **Sweep processing gain.** A 0.5 s sweep over about 10 kHz bandwidth gives a time-bandwidth product of about 5000, about **37 dB of processing gain** over an impulse of the same peak level. Over 0.5–4 kHz (B = 3.5 kHz) it is about 32 dB. This is why weak forest backscatter may still be measurable.
- **Rough link budget for a trunk echo.** All assumptions are flagged:
  - Source: 80–90 dB SPL at 1 m (typical loud phone; not sourced here).
  - Two-way spreading to a 5 m trunk: −20 dB (1 m → 5 m → back, referenced to the flat-wall image).
  - Trunk factor: −18 dB.
  - That gives an echo of about **42–52 dB SPL** at the phone, against a quiet woodland background of perhaps 30–45 dB (not sourced here). Add about 32 dB of processing gain: a clean trunk echo at 5 m is plausible.
  - At 20 m: −32 dB spreading and −24 dB trunk factor give about 24–34 dB plus gain. That is marginal for single trunks, but aggregated edge energy may still be visible.
  - Wind and handling noise (low frequency) and the speaker-mic coupling ringing in the first 1–3 ms are the practical killers.
- **Near-ultrasound (18–22 kHz).** Air absorption is much higher than at 1–4 kHz (order of several tenths of a dB/m near 20 kHz, per ISO 9613-1; humidity-dependent; exact values not verified here). Phone speakers and mics are also inconsistent above about 18 kHz. Vegetation reflection loss dominates too (Stilz & Schnitzler). Expect usable range of only a few metres in a forest. It is good for "something within 2 m", useless for edges at 20–40 m.

### Gaps
- I found no peer-reviewed smartphone active acoustic sensing results outdoors or in vegetation.
- EchoTag, SAMS and BeepBeep outdoor numbers: not retrieved.
- Measured SPL of specific phone models: not retrieved.

---

## 5. Telling forest from open field, urban canyon and indoors from a chirp IR

### Takeaway
I found no published classifier that separates *forest* from other outdoor scenes using a phone chirp. Indoor/outdoor and room recognition from chirp echoes exist (papers and patents). From the measured physics, the four scenes should separate well on a handful of hand-made features. This is probably the single most useful thing the chirp can do in woodland: it acts as a land-cover likelihood that can be matched to OSM polygons.

### Cited Findings
- **Forest IRs** have a near-constant, high echo density from the start of the tail [Kaneko & Gamper 2021](https://microsoft.com/en-us/research/uploads/prod/2021/10/A-fast-forest-reverberator-using-single-scattering-cylinders-MMSP-2021.pdf). Their T30 peaks at 1 kHz (1.3–1.7 s) with high-frequency roll-off (about 0.4 s at 4 kHz) and a C50 of 15–40 dB [Shelley et al. 2013](https://eprints.whiterose.ac.uk/78001/1/56.dafx2013_submission_26.pdf).
- **Forest vs open sound.** Forest sound is dominated by reverberation; open-habitat sound by turbulent amplitude fluctuation [Richards 1981](https://sora.unm.edu/sites/default/files/SAB_006_1981_P297-300%20Part%206%20Environmental%20Acoustics%20and%20Censuses%20of%20Singing%20Birds%20Douglas%20G.%20Richards.pdf).
- **Indoor/outdoor patent.** It plays a chirp, extracts echo features "such as echo energy and peak counts", and predicts indoor vs outdoor. A related patent uses the device's echo-canceller room impulse response as a signature, since "indoor spaces typically exhibit different impulse responses than outdoor spaces". These are patents, with no accuracy given. [USPTO 10506372](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/10506372); [US 2021/0360425](https://patents.justia.com/patent/20210360425)
- **Rooms** can be classified from 2 ms inaudible phone chirps with a CNN [arXiv 1809.00531](https://ar5iv.arxiv.org/html/1809.00531), and chirps beat tones for echo-feature separability [arXiv 2210.08493](https://arxiv.org/pdf/2210.08493).

### Inferences
Expected signatures for a phone held at about 1.3 m are derived from Sections 1–4. These are my predictions, not measurements.

| Scene | 0–10 ms after coupling | 10–200 ms | Late tail | Spectral tilt of tail |
|---|---|---|---|---|
| Open field | ground echo at about 7–9 ms only | essentially noise floor | none | n/a |
| Urban canyon (current case) | ground echo | a few **sparse, strong, specular spikes** at 2d/c (facades); periodic flutter at street-width spacing | short; RT is low unless the canyon is narrow | flat-ish (hard surfaces) |
| Forest / woodland | ground echo (weaker over litter); first trunk at about 15–30 ms | **dense, noise-like, smoothly decaying** envelope; few distinct peaks; echo density about 1 | long, low tail; RT 0.3–1.7 s in published bistatic data, shorter for a phone | energy concentrated around 0.5–2 kHz; fast high-frequency loss |
| Indoors | strong reflections under 5 ms (walls, ceiling, nearby objects) | echo density builds up quickly to diffuse | RT about 0.3–1 s, exponential | room modes at low frequency |

Discriminative features, cheap to compute on the existing deconvolved IR:
1. **Tail energy ratio, E(20–200 ms) / E(ground echo).** Near 0 in an open field, moderate in forest and streets, high indoors.
2. **Peakiness of the 10–200 ms envelope.** Use kurtosis, or the fraction of energy in the top 5 peaks. High for streets (specular), low for forest (diffuse). This is the key **forest vs street** separator.
3. **Normalised echo density profile** (Abel–Huang: the fraction of samples beyond 1σ in a sliding 20 ms window, divided by erfc(1/√2)). Forest is about 1 early; a street stays below 1 because it is sparse; indoors rises from low to 1.
4. **EDT and T20 per octave (500 Hz, 1 kHz, 2 kHz, 4 kHz)**, plus the ratio T(1 kHz)/T(4 kHz). Forest shows a mid-band peak and a high-frequency drop.
5. **Earliest reflection delay after the ground echo.** Under 5 ms suggests indoors or next to a wall. 15–30 ms with no strong spike suggests a trunk. Strong isolated spikes at 20–120 ms suggest facades.
6. **t²-compensated tail decay rate** (Section 1). Gives a scattering-density index 2a·n.

A rule-based classifier on features 1–5 with hand-set thresholds should get forest vs street vs open vs indoor right most of the time. That is a guess; there is no published accuracy for this exact task. To calibrate the thresholds, record 5–10 IRs in each of: a Vincennes street, the Château courtyard, an open lawn, and inside the Bois.

### Gaps
- I found no published accuracy for classifying forest vs open vs urban vs indoor from a smartphone chirp.
- The cited patents give no performance numbers.
- The accuracy figure for arXiv 1809.00531 was not verified.

---

## 6. Military and OPSEC: how far away a phone chirp can be heard in a forest, and alternatives

### Takeaway
An audible sweep is a distinctive, unnatural sound. A rough estimate puts it detectable by ear at **roughly 50–100 m in a forest and a few hundred metres in the open**, depending on phone loudness and background noise. That is comparable to or worse than the spoken report itself. Ultrasonic (above 18 kHz) is far less detectable by humans, but it only senses a few metres and may still be picked up by microphones or detectors. In a real deployment, the voice-only path (landmarks, sun, ask-back) should be primary, with the chirp off or at low level by default.

### Cited Findings
- **Excess attenuation in forests** spans "a few tenths dB/100 m (e.g. Embleton, 1963) up to a few 10 dB/100 m", depending on vegetation, geometry and frequency, and "results cannot be generalized simply". A secondary summary attributed to Martens gives about **20 dB/100 m roughly flat up to 2 kHz, higher above**. These are search snippets of reviews and secondary summaries, not primary tables. [IOA, Martens, "Sound propagation in forests"](https://www.ioa.org.uk/system/files/publications/MJM%20MARTENS%20SOUND%20PROPAGATION%20IN%20FORESTS.pdf); [core.ac.uk review](https://core.ac.uk/download/77228637.pdf)
- **Lower frequencies carry better through forest** at all source heights (Dutchess County, NY, 100 m paths; snippet). [IOA, excess attenuation through densely planted forest](https://www.ioa.org.uk/node/10122)
- **Haupert, Sèbe & Sueur (2022), *Methods in Ecology and Evolution*.** Habitat attenuation in an Alpine and a Neotropical forest follows an exponential law, linear in frequency and distance. Detection distance "mostly depends on the ambient sound" and "may vary by a factor of up to 5 over the diel cycle and across seasons". [arXiv 2211.16077](https://arxiv.org/abs/2211.16077)
- **Swearingen 2013.** Attenuation is stronger at 1–2 kHz going into a forest. [record](https://bvbvf1.bib-bvb.de/vufind/PrimoRecord/cdi_proquest_miscellaneous_1350151276)

### Inferences
- **Back-of-envelope detection distance.** Assumptions, none verified here:
  - The phone emits 85 dB SPL at 1 m.
  - In-band forest background is about 35 dB.
  - Excess attenuation is about 0.2 dB/m (the Martens-type value).
  - The level drops to the background where 20·log₁₀(r) + 0.2·r ≈ 50 dB, at about **65–70 m**.
  - In the open (no excess attenuation): 20·log₁₀(r) = 50, giving about **300 m**.
  - A human listener can detect a structured sweep somewhat below broadband background, so real detection distance could be larger. Night or windless conditions with low background push it up, possibly by Haupert's factor of 5.
- **The voice report is audible too.** A normal speaking voice is about 60 dB at 1 m (general acoustics, not verified here), which is roughly 25 dB quieter than a loud phone sweep. So the chirp extends the audible footprint well beyond the report itself. The CLAUDE.md pitch says "no screen needed"; an audible chirp works against the "covert" framing.
- **Mitigations, in order of preference:**
  1. Make the chirp **opt-in** (off by default in "tactical" mode).
  2. Use a lower-level, **longer** sweep: processing gain rises 3 dB per doubling of duration, so a 1 s sweep at −10 dB keeps most of the SNR. Band-limit it to 0.5–2 kHz, where forest scattering is strongest.
  3. Near-ultrasound (18–21 kHz) for "very close obstacle / indoors vs outdoors" only.
  4. **Passive alternative:** analyse the reverberation of the speaker's *own voice* in the push-to-talk recording. It is a blind estimate of the decay of speech offsets: T60 from the decay of syllable offsets, plus a DRR proxy. It is noisier, but adds zero emission.

### Gaps
- I found no primary measurement of how far away a phone loudspeaker sweep can be detected in a forest, by humans or sensors.
- The Embleton (1963) and Fricke (1984) per-frequency tables were not retrieved.
- I found no source on acoustic detection doctrine (e.g. military acoustic sensors vs smartphone emissions).

---

## Implementation plan: features and algorithms for under a day, with expected value

(This plan and the verdict are inferences built on the findings above.)

1. **Scene classifier (forest / street / open / indoor).** About 2–3 h. Discriminative value is **high**.
   - Features: tail energy ratio, envelope peakiness (kurtosis of the 10–200 ms Hilbert envelope), normalised echo density, T(1 kHz)/T(4 kHz), earliest reflection delay.
   - Use rule thresholds calibrated on about 20 recordings around the venue.
   - Output a soft label. In `localise.py`, multiply the grid by a land-cover likelihood from OSM polygons, for example P(forest-label | cell inside `landuse=forest`/`natural=wood`) = 0.8. In the Bois de Vincennes this alone removes the streets, lawns and lake from the hypotheses.
2. **Forest-edge / clearing-boundary onset distance.** About 2–3 h. Value is **medium and speculative**.
   - Only when the classifier says "open" or "clearing".
   - Band-pass 0.5–2 kHz, smooth the envelope (10 ms), and find the first sustained rise of 6 dB or more above the noise floor after the ground echo. Then D = c·t/2.
   - Add a likelihood term N(dist_to_nearest_forest_edge(cell) − D; σ = 3–5 m), using the same "wall" machinery with edge points sampled from the forest polygons (CLAUDE.md 6.1 already samples line features into points).
   - Must be validated on site before it goes in the demo.
3. **Scattering-density index.** About 1 h. Value for localisation is **low**.
   - Fit log(P(t)·t²) between 20 and 150 ms and use the slope to estimate 2a·n.
   - OSM has no stem density, so this cannot be matched to the map. It can feed a "dense / sparse woodland" descriptor on the coordinator card, and gives a little more confidence in "inside forest".
4. **Discrete trunk echoes.** Value is **low**. Peak-pick 10–60 ms only to report "nearest obstacle about X m". Don't match it to the map. OSM `natural=tree` nodes exist in Paris, but I have not verified coverage inside the Bois and would not rely on it.
5. **Passive voice-reverberation fallback.** About 2 h. Value is **low to medium**. A blind T60 from speech offsets in the push-to-talk audio, used as a coarse forest/street/indoor cue with zero emission.

## Verdict

- **Keep the chirp in forests, but change what it is for.** It cannot reproduce the 0.3 m wall matching from streets: there are no specular walls, the returns are diffuse, and no individual trees are mapped. Its realistic value in woodland is (a) a reliable "you are inside woodland / in a clearing / on a street" land-cover cue, which is cheap and strongly constrains the grid, and (b) possibly the distance to a nearby forest edge when standing in a clearing.
- **The doubts are honest ones.** None of this has been measured with a phone in a forest. Published forest IRs are all source-and-receiver-apart measurements, and edge-echo strength at audible frequencies for a monostatic phone is unknown.
- **Field test.** Do a 15-minute test in the Bois de Vincennes: 5 IRs inside the trees, 5 in a clearing at known distances from the edge, and 5 on a street. That decides whether feature 2 is real.
- **OPSEC.** An audible sweep is detectable at an estimated 50–100 m in woodland and much further in the open. Present it as optional, low-level and band-limited. Keep the voice landmark, sun and ask-back loop as the primary localiser.
