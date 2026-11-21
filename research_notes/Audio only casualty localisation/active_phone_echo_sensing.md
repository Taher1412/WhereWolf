# Active acoustic sensing with a phone's own speaker and mic (sonar / echolocation), and its emission risk

Context: Pothenot already plays a 0.5 s exponential sweep 800 Hz–12 kHz, deconvolves it to an impulse response (IR), and reads echo delays (d = c·t/2), RT60 (Schroeder) and DRR, using one mic in a browser (Web Audio) on Android/iOS.

## Key systems and their measured accuracy

### Takeaway
Phone sonar is proven for **short-range distance (≤ ~4 m, cm-level in good conditions)** and for **coarse classification (indoor/outdoor, which room)**. Room *shape* needs either several mics, motion (IMU + moving the phone), or a strong prior (rectangular room). Nothing in the literature shows reliable phone-only ranging to facades tens of metres away outdoors.

### Cited Findings
- **BatMapper (Zhou, Elbadry, Gao, Ye — MobiSys 2017).** Phone speaker + both mics + gyro/accelerometer; the user walks with the phone pinging. Reported: 1–2 cm distance accuracy up to ~4 m; corridor shapes from a 2–3 min walk; doors at 92% precision with 1–2 m error at the 90th percentile; room geometry error < 0.3 m at the 80th percentile from "tens of seconds of measurement gestures". — [BatMapper paper PDF](https://zhoubinwy.github.io/pdf/batmapper.pdf)
- BatMapper wall-ranging test (plain wall, empty space, 0.5–4 m, 20 repeats per point): error within 1–2 cm at the 80th percentile and ≤ 4 cm maximum for 0.5–3.5 m; 5 cm at the 80th percentile and ≤ ~10 cm maximum out to 4 m. Usable range ≈ 3.5 m; "objects more than 6 meters away create very weak echoes, which can be ignored". — [BatMapper PDF](https://zhoubinwy.github.io/pdf/batmapper.pdf)
- BatMapper room gesture: about 50 chirps in 5 s with the phone held in front, then the arm moved right and left (10 chirps in 1 s each). Distances that change in line with the expected 0.3–0.5 m arm movement get more weight, and inconsistent echoes (front wall, clutter) get less. It converges "after a couple left/right movements". It does **not** work in irregular rooms or rooms larger than 8×8 m; there the user has to walk a loop along the walls. — [BatMapper PDF](https://zhoubinwy.github.io/pdf/batmapper.pdf)
- A competitor (Baig, Pradhan et al., 2018) measured BatMapper at 60 cm median and 2.5 m 90th-percentile error under its own test conditions, against 30 cm / 1 m for its own system. Treat this as a hostile comparison. — [search summary citing researchr / SUNY records](https://researchr.org/publication/ZhouEGY17)
- **EchoTag (Tung & Shin, MobiCom 2015).** Recognises fingerprinted spots from active echoes: 11 tags at 1 cm resolution with 98% accuracy, ~90% a week after training. In homes where objects moved, accuracy fell to 56%. — [MobiCom paper](https://old.sigmobile.org/mobicom/2015/papers/p525-tungA.pdf); [patent US9829577](https://patents.google.com/patent/US9829577); [UMD slides](https://www.cs.umd.edu/class/spring2019/cmsc818w/course_materials/slides/10_1_echotag_Josephine_Nick.pdf)
- **RoomRecognize / "Deep Room Recognition Using Inaudible Echos" (Song, Gu, Tan — IMWUT 2018).** A single 2 ms 20 kHz tone every 100 ms, a 0.1 s recording, and a CNN on the spectrogram. Accuracy: 99.7% (22 rooms), 97.7% (50 rooms), 99% (19 spots, quiet museum), 89% (15 spots, crowded museum). It needs prior training per room (fingerprinting). — [arXiv 1809.00531](https://arxiv.org/pdf/1809.00531)
- **Dokmanić et al., "Acoustic echoes reveal room shape", PNAS 110(30):12186–12191 (2013).** Recovers the 3D shape of a convex polyhedral room from first-order echoes using Euclidean distance matrices, with **several microphones** and one source. Demonstrated in a classroom and a cathedral portal. Not a single-mic method. — [PMC full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC3725052); [EPFL PDF](https://infoscience.epfl.ch/record/186657/files/DokmanicPWLV13.pdf?version=1)
- **Single co-located speaker + mic + motion sensors** (Krekovic, Dokmanić et al., arXiv 1612.05793, 2016): room shape and self-localisation from first-order echoes only, using the IMU for extra information. "Distance measures have reasonable accuracy, while direction measurement is often subject to large measurement error". With ungrouped echoes, a single distance measurement isn't enough even for parallelograms, and higher-order echoes are "often difficult to recover". — [arXiv 1612.05793](https://arxiv.org/pdf/1612.05793)
- **BeepBeep (Peng et al., Microsoft Research — SenSys 2007).** Phone-to-phone ranging, **two devices**, two-way sensing so that unknown system delays cancel. 0.8 cm claimed in the paper; the demo reported ~2 cm average at more than 10 m. — [BeepBeep paper](https://www.cs.purdue.edu/homes/chunyi/pubs/sensys106-beepbeep.pdf); [MSR demo](https://microsoft.com/en-us/research/wp-content/uploads/2007/11/demo_sensys07_beepbeep.pdf)
- **LLAP (MobiCom 2016)**: phase-based hand tracking, 3.5 mm (1D) and 4.6 mm (2D). **FingerIO (CHI 2016)**: OFDM, 8 mm 2D on a Galaxy S4. Both are close range and "not resilient to nearby interference". **CovertBand (2017)**: inaudible signals hidden in music track people to 18 cm (walking) and 8 cm (static), up to 6 m line-of-sight and 3 m through barriers. — [LLAP PDF](https://samsonsjarkal.github.io/KeSun/files/mobicom16_ultrasound.pdf); [FingerIO](https://fingerio.cs.washington.edu/fingerio.pdf); [acoustic sensing survey, arXiv 1901.03450](https://arxiv.org/pdf/1901.03450)
- **Indoor vs outdoor from the active probe:** a 2015 ICT Express paper classified environments from probe reverberation at about 95% accuracy over 46 indoor and outdoor locations. AudioIO (2018) uses the speaker probe, reverberation features and an SVM. Patents describe chirp-echo features (echo sum, peak count, variance) feeding an indoor/outdoor classifier. — [ICT Express 2015 (DOAJ)](https://doaj.org/article/df65077369db4eeb9a4b1cf610e59c22); [Springer chapter (AudioIO)](https://rd.springer.com/chapter/10.1007/978-3-030-28925-6_8); [patent 10506372](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/10506372)
- **Echo SLAM with a phone (2022):** a near-inaudible log chirp sweeping 15–20 kHz in 10 ms, used for learned echoic location features in indoor SLAM. — [arXiv 2210.08493](https://arxiv.org/pdf/2210.08493)

### Inferences
- What Pothenot can realistically get from one ping: (a) **indoor / enclosed vs open** (RT60, DRR, density of early echoes); (b) **distance to the nearest large flat surface within ~3–6 m**; (c) possibly "wall close on one side" if the user turns the phone. Getting *room shape* or *which facade* needs motion plus several pings (BatMapper-style), so it is not a single-shot feature.
- Fingerprinting (EchoTag, RoomRecognize) needs prior visits and is useless in a new combat area. Drop it.

### Gaps
- I found **no peer-reviewed measurement of phone-only ranging to outdoor facades** (10–50 m) with accuracy numbers. Outdoor results in the papers are about indoor/outdoor classification only.
- The full text of the 2020 smartphone rectangular-room paper wasn't retrieved, so I have no error number for it.

## Signal design (chirp vs MLS vs FMCW, band, duration, coupling, jitter, orientation)

### Takeaway
Use short (1–10 ms) windowed linear or log chirps. Cut out the speaker-to-mic direct path and the loudspeaker "ringing" (which in practice blinds the first ~0.3–2 m). Average many repetitions. A 0.5 s sweep is good for RT60 and DRR but long for ranging and for OPSEC.

### Cited Findings
- BatMapper's final signal: two Hanning-windowed linear chirps, **3 ms at 8–16 kHz** (top mic) and **1 ms at 8–10 kHz** (bottom mic), separated by 40 ms, giving ≈ 12 pings/s. The 8 kHz floor is there to stay above voice (< 1 kHz) and instruments (< 4 kHz), and the ceiling below the speaker limit (~20 kHz). Processing: Butterworth band-pass, cross-correlation with the pulse (matched filter), envelope, 35 ms windows; the **first and strongest peak is the direct speaker-to-mic sound and serves as the time zero**; the top 6 peaks are kept as echo candidates. — [BatMapper PDF](https://zhoubinwy.github.io/pdf/batmapper.pdf)
- The two mics behave differently: the bottom one is tuned for close-range voice, the top one for noise cancellation, which is why BatMapper uses a separate pulse per mic. — [BatMapper PDF](https://zhoubinwy.github.io/pdf/batmapper.pdf)
- **Loudspeaker ringing:** after a 2 ms 20 kHz chirp the signal "does not immediately stop… damped oscillation" from the speaker and mic diaphragms. RoomRecognize discards the first **13.8 ms** for analysis, and echoes are ~100× weaker than the direct and ringing part. A 2 ms chirp doesn't overlap echoes from objects more than 34 cm away. — [arXiv 1809.00531](https://arxiv.org/pdf/1809.00531)
- Earlier active systems used a sine sweep, MLS (RoomSense: a 0.68 s audible MLS with MFCC + SVM, "susceptible to ambient sounds") and multi-tone chirps. — [arXiv 1809.00531](https://arxiv.org/pdf/1809.00531)
- BeepBeep avoids unknown software and system delays by **self-recording** (each phone records its own beep), so time is counted in samples within one recording stream instead of trusting OS timestamps. "Performance… can be degraded by irregular and uncertain system delay" otherwise. — [BeepBeep](https://www.cs.purdue.edu/homes/chunyi/pubs/sensys106-beepbeep.pdf); [survey](https://arxiv.org/pdf/1901.03450)
- Web Audio latency: `outputLatency` is a platform *estimate*, and `baseLatency + outputLatency` may miss per-node latency. Android Chrome raises buffering if the device reports high latency (`latencyHint: 0.003` was suggested as a workaround). Firefox Android's `outputLatency` has been reported wrong. — [web.dev audio output latency](https://web.dev/articles/audio-output-latency); [WebAudio issue 2467](https://github.com/WebAudio/web-audio-api/issues/2467); [Construct forum](https://www.construct.net/en/forum/construct-3/general-discussion-7/big-sound-lag-android-148079/page-4); [Mozilla bug 1612093](https://bugzilla.mozilla.org/show_bug.cgi?id=1612093)
- Browser mic processing: Safari has historically ignored `noiseSuppression`/`autoGainControl: false` (only `echoCancellation` is honoured), throws `OverconstrainedError` on `{exact:false}`, and still has iOS-specific issues reported in 2025–26. On Chrome, one developer saw "no discernible difference" from disabling NS and AGC. — [WebKit bug 179411](https://bugs.webkit.org/show_bug.cgi?id=179411); [WebKit bug 192932 (cannot disable lowpass)](https://bugs.webkit.org/show_bug.cgi?id=192932); [addpipe constraints guide](https://blog.addpipe.com/getusermedia-audio-constraints.md); [discuss-webrtc thread](https://groups.google.com/g/discuss-webrtc/c/PDZYMzAI-_Y)

### Inferences (engineering advice for Pothenot, not from a single source)
- **Time zero:** take the direct-path peak in the deconvolved IR as t = 0 (as BatMapper does). Never use `AudioContext` timestamps, because the play/record offset in browsers is unknown and jittery. Since play and record share one capture stream, the direct peak cancels the latency, just as BeepBeep's self-recording does.
- **Blind zone:** speaker ringing and AEC/AGC transients hide echoes within roughly the first 2–14 ms, i.e. **0.3–2.4 m** (d = 343·t/2). Report "nearest surface > X m" rather than trusting the earliest peaks. Removing the direct path: subtract a reference IR recorded with the phone held in free air or at arm's length outdoors (a calibration ping), or gate it.
- **Sweep length:** the existing 0.5 s exponential sweep gives high SNR and, with Farina-style deconvolution, pushes harmonic distortion before t = 0. That's good for RT60. For ranging, 5–10 short chirps averaged (synchronous averaging adds 10·log10(N) dB of SNR against uncorrelated noise) are equivalent and quieter per event. *(Farina ESS and averaging gain are standard DSP knowledge; I didn't retrieve a source in this session.)*
- **Range resolution** ≈ c/(2B): 800 Hz–12 kHz (B ≈ 11 kHz) gives ~1.5 cm; a 17–20 kHz band (B = 3 kHz) gives ~6 cm. Both are far finer than the clutter and multipath errors, so bandwidth isn't the limit; SNR and echo association are.
- **Must set** `echoCancellation:false` (otherwise the AEC deletes the probe and its echoes, since it is literally designed to remove speaker output from the mic). Request `noiseSuppression:false, autoGainControl:false` but verify on the device by checking the direct-path amplitude from repeated pings.
- **Orientation:** the bottom mic sits next to the bottom speaker on most phones, which means a huge direct coupling. Holding the phone flat at chest height facing the wall or facade is the most repeatable posture. Body shadowing behind the user is real, so the echo set depends on which way the user faces.

### Gaps
- I found no published measurement of Web-Audio play-to-record jitter on mobile Chrome or Safari. It has to be measured on the demo phones (loopback ping, look at the spread of the direct-peak index).

## What one mic can and cannot do

### Takeaway
One mic gives **distances (ranges), not bearings**. Geometry only comes from adding known motion (IMU, arm sweeps, turning in place, walking) or priors. Two-mic phones help (BatMapper), but browsers usually expose one processed channel.

### Cited Findings
- BatMapper relies on the two mics and on movement to associate echoes with walls (the path-length difference between the top and bottom mics equals the mic spacing). — [BatMapper PDF](https://zhoubinwy.github.io/pdf/batmapper.pdf)
- A co-located speaker + mic with IMU motion can reconstruct room shape from first-order echoes; distances are reliable and directions aren't. — [arXiv 1612.05793](https://arxiv.org/pdf/1612.05793)
- Dokmanić's unique shape recovery needs several mics, and echo-to-wall labelling is the hard part. — [PMC3725052](https://pmc.ncbi.nlm.nih.gov/articles/PMC3725052)
- Safari 26 on macOS records stereo even with `channelCount:1` when AEC is off (so two-channel capture is possible on some browser builds, but it isn't a documented mobile feature). — [Apple developer forums](https://developer.apple.com/forums/thread/804765)

### Inferences
- A cheap way to add direction in a hackathon: **"ping, turn 90°, ping"** (4 pings, compass from the phone magnetometer or the sun heading). Point the phone (top edge or screen) at each quadrant and attribute the strongest near echo to that direction. The phone's directivity at 8–12 kHz plus body shadowing gives some front/back contrast. It's crude, and not validated in the literature retrieved.
- In the Pothenot likelihood grid, an echo range gives at most a constraint of the form "distance from p to the nearest building polygon ≈ d ± σ". Using OSM building footprints this is a usable soft term (σ ≈ 1–2 m if d < 5 m), but only when the user stands next to a facade.

### Gaps
- No browser API reliably exposes both raw phone mics. Native apps (Android AudioRecord with UNPROCESSED/stereo sources) can on some models, which I didn't verify in this session.

## Near-ultrasound (17–22 kHz) feasibility

### Takeaway
17–20 kHz works on many recent phones, but output is weak and uneven and falls off sharply above ~20 kHz. Air absorption at 20 kHz is about 0.4–0.5 dB/m, so near-ultrasound is only practical at **room scale (≤ ~5–10 m round trip)**, not for facades across a street.

### Cited Findings
- RoomRecognize: Galaxy S7/S8 and iPhone 6s/7/X "can well emit and receive the 20 kHz tone". At 21.4 kHz the received signal is "significantly distorted and becomes audible". Received power falls steadily with frequency. Android's AOSP "Near Ultrasound Tests" can check a given device. — [arXiv 1809.00531](https://arxiv.org/pdf/1809.00531)
- One measurement: a phone at max volume playing 18 kHz gave ~74 dB SPL on axis at 10 cm. Speaker response drops rapidly in this range; iPhone responses drop sharply above 20 kHz but pass 17–19 kHz. — [arXiv 2103.11261](https://ar5iv.labs.arxiv.org/html/2103.11261); [SonicPACT arXiv 2012.04770](https://arxiv.org/pdf/2012.04770)
- Consumer phone speakers and mics are generally designed to roll off above 19–20 kHz. — [patent 12033485](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/12033485)
- Safari 11 limited the AnalyserNode FFT to 2048 bins, and WebKit had a bug about being unable to disable an input lowpass, which would kill near-ultrasound capture on affected versions. — [WebKit 179411](https://bugs.webkit.org/show_bug.cgi?id=179411); [WebKit 192932](https://bugs.webkit.org/show_bug.cgi?id=192932)
- ISO 9613-1 tabulates air absorption for 50 Hz–10 kHz only. Its formula is reproduced by sengpielaudio. — [ISO 9613-1](https://www.iso.org/standard/17426.html); [sengpielaudio formula](https://sengpielaudio.com/AirdampingFormula.htm)

### Inferences
- **My own calculation** with the ISO 9613-1 formula (20 °C, 1 atm; above 10 kHz this is an extrapolation outside the standard's validated range), in dB/km:

  | RH | 1 kHz | 4 kHz | 8 kHz | 12 kHz | 16 kHz | 20 kHz |
  |---|---|---|---|---|---|---|
  | 20% | 7 | 75 | 217 | 342 | 435 | 506 |
  | 50% | 5 | 30 | 105 | 221 | 365 | 524 |
  | 80% | 5 | 21 | 69 | 147 | 252 | 380 |

  So a 20 m round trip (facade 10 m away) costs ~10 dB extra at 20 kHz against ~0.1 dB at 1 kHz, on top of spherical spreading and the weaker speaker. **Near-ultrasound is unsuited to outdoor facade ranging; the audible 1–8 kHz band is what reaches 10–30 m facades.**
- Browser sample rate is normally 48 kHz (Nyquist 24 kHz), so 17–20 kHz is representable. The risk lies in OS or browser low-pass and processing, not in the sample rate.

### Gaps
- No systematic dataset on which Android and iOS **browser** builds pass 18–20 kHz in both directions. It has to be tested per device (play a 19 kHz tone, check the spectrum of the recording).

## Military / OPSEC: detectability of emitted pings

### Takeaway
An audible 0.5 s sweep at phone volume is **audible to humans at tens to a few hundred metres in quiet conditions** and detectable by microphones further away. That's a real signature for a casualty position, so the ping should be opt-in, short, quiet, and preferably near-ultrasound indoors. Passive cues (ambient RT60, user speech reverberation) should come first.

### Cited Findings
- Phone loudspeaker loudness measured at 1 m is typically in the high 70s dB (e.g. Moto G 2015: 78.5 dB at 1 m). — [PhoneArena 2015](https://www.phonearena.com/news/Loud-louder-LOUDEST-Here-are-the-phones-with-the-loudest-speakers-so-far-in-2015_id74023); [GSMArena test method (1 m, soundproof room)](https://m.gsmarena.com/gsmarena_lab_tests-review-751p3.php)
- Human high-frequency hearing: everyone under 30 responded up to 16 kHz, but only 52.2% at 20 kHz. Responses were < 20% at 18–20 kHz in groups over 31. Children (6–10 y) responded 100% at 20 kHz. — [PMC9450601](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9450601/); [PMC8394048](https://pmc.ncbi.nlm.nih.gov/articles/PMC8394048)
- An 18 kHz phone tone at ~74 dB SPL (10 cm) is below the >86 dB SPL hearing threshold of most listeners at that frequency, per one paper. — [arXiv 2103.11261](https://ar5iv.labs.arxiv.org/html/2103.11261)
- Battlefield acoustic sensing is real and passive. A Quantum Systems Twister recon drone carries an acoustic sensor targeting artillery/mortar direction at 5° to 5 km. Fraunhofer IDMT acoustic drone detection works at 50–200 m depending on noise. A NATO JALLC Jan 2026 paper documents acoustic sensor networks in Ukraine for artillery and drones. Matchstick-size acoustic vector sensors give direction from a single unit. — [heise (Twister)](https://heise.de/-10279458); [heise (Fraunhofer)](https://heise.de/-11082679); [NATO JALLC 2026](https://nllp.jallc.nato.int/iks/sharing%20public/20260109_(nu)_%20uas_acoustic_sensor_systems_for_artillery_and_drone_threat_detection.pdf); [Scientific American](https://www.scientificamerican.com/article/acoustic-sensor-drone-surveillance-war/); [DSIAC primer](https://dsiac.dtic.mil/primers/what-is-an-acoustic-drone-detection-system/)

### Inferences
- **Rough audibility range (my calculation, not from a source):** source level L1 at 1 m, spherical spreading plus ISO absorption (50% RH), with no ground effect, barriers or wind, until the level hits the listener's in-band masking level:
  - 2 kHz component, L1 = 70–80 dB, quiet rural night (in-band ambient ~25 dB): **~150–370 m**; with 40 dB ambient (light activity, distant traffic): **~30–90 m**.
  - 19 kHz, L1 = 70–80 dB: drops to the 20 dB band floor within ~40–55 m. Since human thresholds at 19 kHz are ~70–90 dB SPL, **most adults won't hear it beyond about a metre**, but a sensitive microphone at a 0 dB floor could pick it up to **~70–90 m**.
  - These figures are optimistic for the listener (no barriers) and pessimistic in noise. Treat them as order of magnitude only.
- The sweep is a **coherent, known-form chirp**: any adversary sensor running a matched filter for chirps would gain well above human detection. Repeated identical pings at a fixed interval are especially distinctive. Drones' own rotor noise strongly masks ground sound for onboard mics, and I found no evidence of drones listening for small sounds from the ground. Ground acoustic sensors and humans nearby are the realistic threat.
- **Recommendations:** (1) passive-first: estimate RT60/DRR from the user's own speech (the report already contains speech) and from ambient sound before any ping; (2) ping only when the user confirms ("Ping to measure walls? say yes"); (3) indoors use 17–20 kHz with 2–10 ms chirps at reduced volume (room-scale range is all that's needed, and absorption limits leakage); (4) outdoors, if a facade range is wanted, use one short audible chirp burst at low-to-moderate volume, not a 0.5 s sweep, and not repeated; (5) a UI "silent mode" disables all emission. Also note that the TTS read-back through the phone speaker is a larger audible signature than the ping: recommend an earpiece/headset for the field user.

### Gaps
- No open-source data on the detection range of specific military acoustic sensors against small, short, high-frequency emitters. No authoritative source found on whether phone near-ultrasound gets flagged by fielded systems.

## Practical accuracy numbers, failure modes, and 1-day hackathon feasibility

### Takeaway
Expect cm–dm range accuracy to a **single clear wall within ~3.5–4 m in a quiet, uncluttered setting**, ~95% indoor/outdoor classification, and unreliable results in reverberant halls, noise, wind, or outdoors beyond ~10 m. In one day: indoor/outdoor plus nearest-surface distance is feasible; room shape and facade identification are not.

### Cited Findings
- Accuracy degrades past 3.5 m and gets "larger at 4 m" (5 cm at the 80th percentile, ≤ 10 cm maximum). Clutter and multi-surface reflections create spurious echoes; BatMapper needed probabilistic association and outlier removal plus a separate "cluttered area" classifier. — [BatMapper PDF](https://zhoubinwy.github.io/pdf/batmapper.pdf)
- Indoor/outdoor from probe reverberation: ~95% over 46 locations. — [ICT Express 2015](https://doaj.org/article/df65077369db4eeb9a4b1cf610e59c22)
- Crowd noise lowered room recognition from 99% to 89%; moved objects cut EchoTag from ~90% to 56%. — [arXiv 1809.00531](https://arxiv.org/pdf/1809.00531); [EchoTag slides](https://www.cs.umd.edu/class/spring2019/cmsc818w/course_materials/slides/10_1_echotag_Josephine_Nick.pdf)
- Higher-order echoes are hard to recover; single-distance data is ambiguous without echo grouping. — [arXiv 1612.05793](https://arxiv.org/pdf/1612.05793)

### Inferences
- **Failure modes to plan for:** reverberant rooms (late diffuse energy buries weak first echoes beyond the strongest wall); floor/ceiling echoes indoors (at ~1–1.5 m, often the strongest) get mistaken for walls; the body of the person holding the phone; wind noise on the mic (broadband low-frequency, mostly below the probe band but triggers AGC); AEC/NS left on; phone covers and fingers over the mic or speaker; outdoors, spherical spreading means an 18 m round trip loses ~25 dB against a 1 m wall (inverse square), so echoes sink into ambient noise.
- **Hackathon scope (1 day), best value for effort:**
  1. *Feasible (2–4 h):* indoor/enclosed vs outdoor/open from the existing IR (RT60 + DRR + echo count thresholds), fed to the localiser as a soft prior (inside a building footprint vs in open ground or a park). Keep the existing sweep but make it opt-in.
  2. *Feasible with care (half a day):* "nearest large surface at d m" from the first strong post-direct-path IR peak beyond the blind zone (> ~0.5–1 m), averaged over 3–5 pings, only trusted if d < ~6 m and the peak is consistent. Use it as a soft distance-to-nearest-building term in the grid.
  3. *Not feasible in a day:* room shape, multi-wall association, facade identification at street distances, two-mic capture in the browser, near-ultrasound ranging validated across iOS and Android.
- **Honest pitch framing:** phone sonar is a *supporting cue* ("inside a building / next to a wall"), not a localisation method. Present it as optional, with a silent default for OPSEC.

### Gaps
- No direct experimental data for outdoor phone echo ranging in a real urban street with traffic noise. Pothenot should measure its own numbers at the Château (known wall distances with a tape) before claiming any accuracy.
