# Room acoustics and environment inference from a single smartphone microphone

Scope: what can be inferred blindly from a few seconds of single-channel phone audio (indoor/outdoor, room volume, RT60/DRR/C50, wall distance, street canyon vs open field), with measured accuracy, hardware limits, and what is feasible in ~1 day for Near.

## Blind RT60 / DRR / C50 estimation from speech or ambient sound

### Takeaway
Fullband blind T60 from 4 s of *distant-talker* speech is mature: the best single-channel CNNs reach MSE ~0.026-0.038 s^2 (RMSE ~0.16-0.20 s), Pearson rho ~0.84-0.92 on the real ACE corpus. Blind DRR is much worse (MSE ~9-15 dB^2, i.e. RMSE ~3-4 dB, rho ~0.56-0.71). All of these were trained and tested on talkers 1-3+ m from the mic; none were validated on close-talk phone speech, so applying them to the operator's own voice at ~10 cm is out of distribution.

### Cited Findings
- ACE Challenge (Eaton et al., WASPAA 2015 / IEEE-ACM TASLP 2016, vol. 24 no. 10, pp. 1681-1693): tasks were single- and multi-mic fullband and 1/3-octave T60 and DRR estimation from speech in ambient, babble and fan noise. Its conclusion: T60 estimation is mature and dominated by analytical (signal-processing) methods; DRR estimation is less mature and ML methods did best. — [ACE Challenge page](https://www.imperial.ac.uk/a-z-research/speech-audio-processing/projects/ace-challenge/); [ACE results report, arXiv 1606.03365](https://arxiv.org/pdf/1606.03365)
- NIRA (Peso Parada et al., ACE 2015) on the ACE eval set: DRR RMSD ~3.84-3.87 dB and T60 RMSD ~43-45% (relative), with fan noise worse than babble for DRR. — [arXiv 1510.04616](https://arxiv.org/pdf/1510.04616)
- Gamper & Tashev 2018 (IWAENC, Microsoft Research): CNN on 4 s single-channel reverberant speech in noise; features = 21-band gammatone (400 Hz-6 kHz) log-energy, 21x1996 input; only 2,541 parameters; trained on 1,325 synthetic+measured RIRs (T60 0.1-1.5 s), noise SNR 0/10/20 dB. ACE eval-set results: CNN bias 0.0304 s, MSE 0.0384 s^2, rho 0.836, vs. best ACE overall method QA Reverb (Prego et al.) bias -0.068, MSE 0.0648, rho 0.778 and best ML ACE method (MLP, Xiong et al.) bias -0.0967, MSE 0.104, rho 0.48. Real-time factor ~0.05 (CPU, mostly Matlab preprocessing), ~0.002 on GPU. Error grows at higher T60 because a long decay needs a long input with sparse speech. SNR did not have a major effect for tested levels. Train-set (in-distribution) MSE was 0.0125, showing a large generalisation gap. — [Gamper & Tashev, IWAENC 2018 PDF](https://microsoft.com/en-us/research/uploads/prod/2018/09/Blind_reverberation_time_estimation_Gamper_IWAENC_2018.pdf)
- Bryan 2019/2020 (Adobe, ICASSP 2020, arXiv 1909.03642): RIR augmentation (AIRA) that re-scales DRR (-6 to 18 dB) and T60 (0.1-1.5 s) of 16 real ACE dev RIRs into 8,000 RIRs; speech from DAPS, SNR uniform -5 to 20 dB, 4 s inputs, 32-band mel at 16 kHz; 8,737-param CNN. ACE results: T60 bias -0.0264, MSE 0.0261 s^2, rho 0.9197 (GT-CNN+AIRA: MSE 0.0265, rho 0.909). DRR: bias 0.81 dB, MSE 8.98 dB^2, rho 0.708 (NIRAv2: bias -1.85, MSE 14.8, rho 0.558; multi-channel PSD beamspace MSE 8.14, rho 0.577). RTF 0.0088 (>110x real time) on a 2018 MacBook Pro CPU. For recordings shorter than 4 s, the example is repeated to 4 s; for longer, slide every 0.5 s and take the median. — [Bryan, arXiv 1909.03642](https://arxiv.org/pdf/1909.03642.pdf)
- Gamper 2020 (MMSP) extended the same CNN idea to blind C50 estimation from speech. — [Blind C50 estimation, MMSP 2020 PDF](https://www.microsoft.com/en-us/research/uploads/prod/2020/10/Blind_C50_estimation_Gamper_MMSP_2020.pdf) (numbers not extracted)
- "A Universal Deep Room Acoustics Estimator" (arXiv 2109.14436, 2021): CRNN on 8 s, 16 kHz MFCC input estimating several parameters jointly; MAE on (simulated-convolution) speech test set: T60 0.21 s, DRR 2.91 (dB), C50 5.95 dB, C80 6.60 dB, SNR 1.98 dB, STI 0.033 (CNN baseline: T60 0.24 s, DRR 2.98, C50 6.28, C80 7.20). Not evaluated on real recordings. Code released as a Code Ocean capsule (Python/TensorFlow); 369K params. — [arXiv 2109.14436](https://ar5iv.labs.arxiv.org/html/2109.14436)
- Götz et al. (arXiv 2202.11790) note Gamper & Tashev gives one estimate per 4 s, and propose a CRNN for short-time T60 estimates in dynamic conditions. — [arXiv 2202.11790](https://arxiv.org/pdf/2202.11790)
- Löllmann et al. (IWAENC 2010, ACE 2015 entry) maximum-likelihood subband T60 estimation is one of the classic analytical baselines; Ratnam et al. 2003 ML method is implemented in Python as `blind_rt60`. — [Bryan 2019 references](https://arxiv.org/pdf/1909.03642.pdf); [nuniz/blind_rt60](https://github.com/nuniz/blind_rt60)

### Inferences
- Rule of thumb from the numbers: blind T60 RMSE ~0.16-0.2 s on unseen real rooms. That is enough to separate "dry/outdoor-like" (<0.2 s), "furnished room" (0.3-0.6 s) and "large hard hall/stairwell/tunnel" (>1 s), but not to resolve fine differences.
- Close talk: using Genovese et al.'s critical-distance formula d_c ~ 0.1*sqrt(Q*V/(pi*T60)) (see next section), a 50 m^3 room with T60 0.5 s and Q=2 gives d_c ~0.8 m, so a mouth at 10 cm yields DRR ~ +18 dB, at the top edge of (or above) the -6 to 18 dB range the DRR models were trained on. Expect DRR to saturate and T60 to be underestimated from close-talk speech, which matches the bias the team already observed.
- Workarounds ranked by expected payoff: (1) estimate the decay from impulsive sounds or the phone's own chirp (a measured impulse response gives Schroeder-integration T60, the standard non-blind method); (2) run blind estimation on the *ambient* segments and on speech captured with the phone at arm's length / buddy talking from >1 m; (3) use the speech-offset decay (free-decay segments right after word endings) rather than the whole utterance.

### Gaps
- Could not retrieve the ACE per-method full tables (arXiv 1606.03365) or Löllmann/Eaton SDD numbers directly; only those quoted inside Gamper and Bryan.
- No paper found that evaluates blind T60/DRR on close-talk (<20 cm) smartphone speech. Srivastava et al. joint estimation numbers not retrieved.
- No clearly packaged pretrained neural blind-RT60 model on GitHub/PyPI was found (Code Ocean capsule for 2109.14436 is the closest).

## Room volume / geometry from single-channel audio

### Takeaway
Blind room volume from 4 s of single-channel noisy speech is possible only to within about a factor of 2 (MeanMult 1.75-2.3 on unseen real rooms; ~3.3 on the noisy ACE corpus). Room *shape* from echoes (Dokmanic) needs multiple mics and a known emission; there is no robust single-mic blind geometry method. Wall distance from a phone's own chirp is plausible but published smartphone numbers are sparse.

### Cited Findings
- Genovese, Gamper, Pulkki, Raghuvanshi, Tashev, "Blind Room Volume Estimation from Single-channel Noisy Speech", ICASSP 2019: CNN (12,556 params) on 4 s chunks, features = 20-band gammatone 50 Hz-2 kHz + low-frequency DFT, cepstrum, etc. Data: 83 real rooms from 11 RIR sets plus 47 simulated rooms (59-2,715 m^3), SNR inf/20/10/0 dB. Results on log10 volume: unseen test rooms MSE 0.19, rho 0.90, MeanMult 2.27; ACE rooms only MSE 0.16, rho 0.41, MeanMult 2.16; full ACE corpus (real recorded noise) MSE 0.43, rho 0.28, MeanMult 3.31; ACE high-SNR (>=18 dB) MSE 0.19, MeanMult 2.28. Distinguishing small rooms (<400 m^3) was hard. Paper states critical distance d_c ~ 0.1*sqrt(Q*V/(pi*T60)). — [Genovese et al. ICASSP 2019 preprint](https://microsoft.com/en-us/research/uploads/prod/2019/04/preprint_ICASSP2019_VolumeEstimation.pdf)
- Earlier volume work cited there: MFCC room identification from closed sets ~84-85% accuracy (Moore et al.; Peters et al. 7 rooms), not evaluated on unseen rooms or noise. — [Genovese et al. 2019](https://microsoft.com/en-us/research/uploads/prod/2019/04/preprint_ICASSP2019_VolumeEstimation.pdf)
- Wang et al. "Attention Is All You Need For Blind Room Volume Estimation" (arXiv 2309.13504, 2023/ICASSP 2024): attention-only model, 4 s speech, 20 gammatone bands (50-2000 Hz) + phase features <500 Hz; test = 6,400 samples from 21 real rooms; SNR 0-30 dB white/babble. Best (ImageNet-pretrained, SpecAugment): log10 MSE 0.154, MAE 0.242, rho 0.893, MeanMult 1.75, median absolute error 155 m^3 (mean 1,219 m^3) over volumes ~12-21,000 m^3. CNN baseline: MeanMult 2.59, median AE 353 m^3. — [arXiv 2309.13504](https://arxiv.org/html/2309.13504v3)
- Ick, Mehrabi, Jin, "Blind Acoustic Room Parameter Estimation Using Phase Features" (arXiv 2303.07449): CNN on single-channel noisy speech, adds phase features. — [arXiv 2303.07449](https://arxiv.org/pdf/2303.07449)
- Dokmanic, Parhizkar, Walther, Lu, Vetterli, "Acoustic Echoes Reveal Room Shape", PNAS 2013: reconstructs 3D convex polyhedral room from one known emission recorded by several (4 in demos) arbitrarily placed mics, using first-order echo times and Euclidean distance matrices; explicitly uses more than one mic because higher-order echoes are hard to label. — [EPFL PDF](https://infoscience.epfl.ch/record/186657/files/DokmanicPWLV13.pdf?version=1); [Physics World](https://physicsworld.com/a/how-to-hear-the-shape-of-a-room/)
- Phone speaker+mic room recognition (RoomRecognize, Song et al., arXiv 1809.00531): 2 ms 20 kHz tone every 100 ms, 44.1 kHz, analysis band 19.5-20.5 kHz; echo is ~100x (40 dB) weaker in amplitude than the self-heard chirp; first 13.8 ms of ringing discarded. *Fingerprinting* (needs training per room): 22 rooms 99.7%, 50 rooms 97.7%, crowded museum 89%, with music 81%; drops to 64% for unseen phone orientation and <80% for unseen spot. — [arXiv 1809.00531](https://ar5iv.arxiv.org/html/1809.00531)
- Smartphone wall sensing with FMCW 15-21 kHz (Frontiers in Computer Science 2026): uses phone speaker+mic, 20 ms pulses at 40 Hz; detects doors/parallel walls at ~0.25-1.0 m; precision often >90% but recall ~55% for unseen users and <20% when phone faces the user or swings; no cm-level distance error reported. — [Frontiers 2026](https://www.frontiersin.org/journals/computer-science/articles/10.3389/fcomp.2026.1834280/full)
- Narrow 18-22 kHz inaudible bandwidth on most phones significantly limits distance accuracy of echo ranging. — [search summary of related ranging literature, e.g. LEAD SenSys 2024](https://aboutzack.github.io/files/SenSys24_LEAD.pdf)

### Inferences
- Range resolution of a matched-filtered chirp is c/(2B): the team's 800 Hz-12 kHz sweep (B ~11 kHz) gives ~1.5 cm theoretical resolution, much better than an 18-22 kHz chirp (~4 cm), at the cost of being audible. The practical limits are the direct speaker-to-mic blast (~40 dB above the echo) and its ringing (~14 ms, i.e. first ~2.4 m masked unless the direct path is subtracted with a reference measurement in free space), not bandwidth.
- Achievable in 1 day: compute the impulse response by deconvolving the recorded sweep (Farina method), subtract/skip the direct path, then (a) T60/EDT via Schroeder backward integration, (b) the first strong reflection delay -> nearest-surface distance, (c) "reflection richness" (energy 5-50 ms after direct vs. later) as an indoor/canyon/open cue. Volume regression and shape reconstruction are research-grade.
- Street canyon vs open field: expect discrete strong reflections at 2*d/c (e.g. 15 m street half-width -> ~90 ms flutter between facades) and little diffuse tail; open field: only ground reflection and nothing after. This is an inference from geometry, not a measured result.

### Gaps
- No single-mic, blind room-dimension (LxWxH) estimation paper with real-room accuracy was found.
- No published accuracy for "street canyon vs open field" classification from audio was found.
- No cm/m wall-distance error numbers for a single phone chirp were retrieved (EchoSpot IMWUT 2021, SAMS 2018 likely have them).

## Indoor/outdoor and environment classification

### Takeaway
Passive acoustic scene classification into indoor / outdoor / transportation reaches 96.5% (DCASE 2020 Task 1B winner, <500 KB model) and 89.5% baseline, but "indoor" is the weakest class (92.7% best, 84.5% baseline) and the classes are urban (airport, mall, metro, street, park). Active probing on phones reports >90-95% indoor/outdoor accuracy with small test sets.

### Cited Findings
- DCASE 2020 Task 1B (3 classes: indoor = airport, shopping mall, metro station; outdoor = pedestrian street, public square, street with traffic, urban park; transportation = bus, tram, metro; model size <500 KB): top system Koutini_CPJKU 96.5% (95% CI 96.2-96.8) with per-class indoor 92.7%, outdoor 97.4%, transportation 99.2%; baseline 89.5% (indoor 84.5%, outdoor 89.1%, transportation 94.9%). — [DCASE 2020 Task 1B results](https://dcase.community/challenge2020/task-acoustic-scene-classification-results-b); [DCASE 2020 task description](https://dcase.community/challenge2020/task-acoustic-scene-classification)
- DCASE 2018 Task 1 (10 scenes): baseline 70.4% on matched device (1A), 59.6% on mismatched devices (1B), showing device mismatch costs ~10 points. — [DCASE 2018 Task 1 results](https://dcase.community/challenge2018/task-acoustic-scene-classification)
- Sung et al., ICT Express 2015: smartphone sound probe, classify by reverberation pattern, ~95% indoor/outdoor accuracy over 46 locations. — [ICT Express 2015 (DOAJ)](https://doaj.org/article/df65077369db4eeb9a4b1cf610e59c22)
- AudioIO (Urb-IoT 2018): active probing with MLS and chirp signals, >90% indoor/outdoor accuracy across tested noise levels and device types. — [Springer chapter](https://rd.springer.com/chapter/10.1007/978-3-030-28925-6_8)
- Patents (U. Michigan / T-Mobile): chirp + echo features + classifier with confidence for indoor/outdoor, used when the camera is unavailable (pocket); another uses the built-in echo canceller's estimated impulse response as an indoor/outdoor signature. No accuracy given. — [US10506372B2](https://patents.google.com/patent/US10506372); [US9326104 ambient signals](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/9326104)

### Inferences
- Near already has YAMNet+AST tagging; a cheap indoor/outdoor prior can come from AudioSet labels (traffic, wind, birds -> outdoor; reverberant speech, HVAC, footsteps on hard floor -> indoor) combined with the chirp-IR features. Expected accuracy is "~90% on urban scenes" but unverified for military/rural scenes (tree lines, ruins), which are out of DCASE distribution.
- Indoor is hardest passively; the active chirp is exactly the cue that fixes this (a real room produces a tail; outdoors produces none).

### Gaps
- No DCASE-style results for rural/forest/battlefield scenes; no accuracy for YAMNet-based indoor/outdoor mapping found.
- AudioIO full paper (signal parameters, per-device accuracy) not retrieved.

## Close-talking effects and workarounds

### Takeaway
At ~10 cm the direct path dominates (DRR roughly +15-20 dB in normal rooms by the critical-distance formula), so the reverberant tail of the operator's voice is buried; blind estimators trained on distant talkers will read "dry". Use excitation that is not close-talk: the phone's own chirp, a hand clap / door slam, or ambient segments, and/or hold the phone at arm's length.

### Cited Findings
- Critical distance d_c ~ 0.1*sqrt(Q*V/(pi*T60)) where DRR = 0 dB. — [Genovese et al. 2019](https://microsoft.com/en-us/research/uploads/prod/2019/04/preprint_ICASSP2019_VolumeEstimation.pdf)
- DRR training ranges in the best blind estimators were -6 to 18 dB (Bryan AIRA), with T60 0.1-1.5 s. — [Bryan 2019](https://arxiv.org/pdf/1909.03642.pdf)
- Gamper & Tashev noted that estimating a long T60 needs long input with sparse speech (pauses expose free decay). — [Gamper & Tashev 2018](https://microsoft.com/en-us/research/uploads/prod/2018/09/Blind_reverberation_time_estimation_Gamper_IWAENC_2018.pdf)
- Phone self-chirp echoes are ~100x weaker than the direct speaker-to-mic signal; ringing lasts ~14 ms. — [arXiv 1809.00531](https://ar5iv.arxiv.org/html/1809.00531)

### Inferences
- A clap or the chirp at arm's length gives a near-impulsive excitation: T60 from Schroeder integration of the measured IR is the textbook method and needs only ~20-35 dB of decay above the noise floor (T20/T30). This is feasible in a day with numpy/pyroomacoustics.
- Average several chirps (e.g. 5-10 sweeps) to gain ~7-10 dB SNR; noise floor outdoors (wind/traffic) will limit the measurable decay.
- Keep a "free-field" reference of the direct path (phone held up in the open, or the first ~3 ms of each IR) to subtract coupling.

### Gaps
- No measured study of how close-talk distance biases blind T60/DRR on phones was found.

## Smartphone microphone / hardware limits

### Takeaway
To get usable raw audio: on Android use `AudioSource.UNPROCESSED` (API 24+, if supported) or `VOICE_RECOGNITION`; in browsers set `echoCancellation:false, noiseSuppression:false, autoGainControl:false` but expect device-dependent leftovers. Unprocessed mic response is only guaranteed within +/-10 dB at 100 Hz-7 kHz and +/-30 dB at 7-22 kHz; speaker-to-mic round-trip latency is up to 300 ms and jitters, so time echoes relative to the direct path recorded in the same buffer, never relative to the play() call.

### Cited Findings
- Android CDD section 5.11 (Capture for Unprocessed): if UNPROCESSED is claimed, response flat within about +/-10 dB from 100 Hz to 7 kHz, +/-20 dB 5-100 Hz, +/-30 dB 7-22 kHz (relative to mid band); only a no-delay level multiplier allowed (no AGC, high-pass filter, or echo cancellation); SNR >60 dB; THD <1% at 1 kHz at 90 dB SPL. — [Android 9 CDD 5.11](https://android.googlesource.com/platform/compatibility/cdd/+/refs/tags/android-9.0.0_r9/5_multimedia/5_11_unprocessed-audio.md); [Android 7.1.2 CDD 5.11](https://android.googlesource.com/platform/compatibility/cdd/+/refs/tags/android-7.1.2_r1/5_multimedia/5_11_unprocessed-audio.md)
- Android `MediaRecorder.AudioSource`: UNPROCESSED (API 24) = "tuned for unprocessed (raw) sound if available, behaves like DEFAULT otherwise"; VOICE_COMMUNICATION uses echo cancellation/AGC if available; VOICE_PERFORMANCE (API 29) minimizes latency and coupling with playback path. — [Android developer docs](https://developer.android.com/reference/android/media/MediaRecorder.AudioSource)
- CTS Verifier tests the unprocessed preset at 94 dB SPL and voice-recognition frequency response at 90 dB SPL. — [Audio framework CTS Verifier](https://source.android.com/docs/compatibility/cts/audio-framework?hl=en)
- Android 15 CDD 5.6 (handheld): mean continuous round-trip latency (speaker-to-mic among paths) <=300 ms with mean absolute deviation <30 ms; stricter media-performance tier <=80 ms round-trip. — [Android 15 CDD](https://source.android.com/docs/compatibility/15/android-15-cdd)
- Chrome: `echoCancellation:false` historically acts as a master switch disabling all WebRTC audio processing (since M37); Chrome will not touch hardware noise suppression unless echoCancellation is enabled, so device DSP may still apply processing. Android Chrome did not default to filters off like desktop; some users report noiseSuppression/autoGainControl false made no audible difference on certain devices. — [Chrome blog: hardware noise suppression](https://developer.chrome.com/blog/disabling-hardware-noise-suppression/); [discuss-webrtc: disable processing](https://groups.google.com/g/discuss-webrtc/c/a1DsB_NKfUg); [discuss-webrtc: Android constraints](https://groups.google.com/g/discuss-webrtc/c/wTUknxGXRyY); [Mozilla bug 1882846 (Firefox Android noise)](https://bugzilla.mozilla.org/show_bug.cgi?id=1882846)
- Safari/WebKit: long-standing bugs where getUserMedia constraints have no effect or processing (low-pass) cannot be disabled; Safari 26 macOS records stereo despite channelCount:1 when echoCancellation is false. — [WebKit bug 179411](https://bugs.webkit.org/show_bug.cgi?id=179411); [WebKit bug 192932](https://bugs.webkit.org/show_bug.cgi?id=192932); [Apple forum thread](https://developer.apple.com/forums/thread/804765)
- Phone high-frequency behaviour: Galaxy S7/S8 and iPhone 6s/7/X handled 20 kHz well; above ~20 kHz performance falls, and at 21.4 kHz the signal was distorted and audible. — [arXiv 1809.00531](https://ar5iv.arxiv.org/html/1809.00531)

### Inferences
- The team's 800 Hz-12 kHz sweep sits inside the band where phone speakers and mics are reasonably usable; no need to go ultrasonic. Avoid <300-500 Hz (tiny speakers produce little output).
- Record at 48 kHz, start recording before playback, and locate the direct-path peak by cross-correlation in the recording; all echo delays are measured from that peak (immune to the 80-300 ms output latency and its jitter).
- Check for clipping of the direct blast (peak near full scale) and lower playback volume if so; AGC, if still active, will pump the tail and corrupt T60, so verify with a test sweep in a known room.

### Gaps
- iOS-specific: did not retrieve Apple docs on AVAudioSession `.measurement` mode (which disables system processing); recommend checking.
- No exact Chromium mapping of Android getUserMedia constraints to `VOICE_RECOGNITION`/`UNPROCESSED` sources was found.

## Open-source tools / models

### Takeaway
No turnkey pretrained "blind room analyser" exists. Practical 1-day toolkit: numpy/scipy for sweep deconvolution and Schroeder T60; pyroomacoustics for simulation and its RT60 measurement helper; `blind_rt60` for a classic statistical blind estimate; train a tiny Gamper-style CNN only if time allows.

### Cited Findings
- `blind_rt60` (PyPI / GitHub nuniz): Python implementation of Ratnam et al. 2003 ML blind RT60, tested on decaying chirps and speech; statistical, no training. — [GitHub](https://github.com/nuniz/blind_rt60); [PyPI](https://pypi.org/project/blind-rt60/)
- JASA-Reverberation (saeidsafavi): Python port of a Laplacian-model blind RT60 approach. — [GitHub](https://github.com/saeidsafavi/JASA-Reverberation-)
- Universal Deep Room Acoustics Estimator: Code Ocean capsule (TensorFlow), CRNN estimating T60, DRR, C50, C80, SNR, STI from 8 s speech. — [arXiv 2109.14436](https://ar5iv.labs.arxiv.org/html/2109.14436)
- Gamper & Tashev CNN is tiny (2,541 params) and Bryan's CNN 8,737 params; both trainable on a laptop from synthetic RIRs + speech; Bryan reports RIR augmentation was key. — [Gamper & Tashev 2018](https://microsoft.com/en-us/research/uploads/prod/2018/09/Blind_reverberation_time_estimation_Gamper_IWAENC_2018.pdf); [Bryan 2019](https://arxiv.org/pdf/1909.03642.pdf)
- RIR datasets used in the literature: ACE, AIR, BUT ReverbDB, OpenAIR, C4DM, dechorate, MIT IR Survey, EchoThief, RWCP. — [arXiv 2309.13504](https://arxiv.org/html/2309.13504v3); [arXiv 2109.14436](https://ar5iv.labs.arxiv.org/html/2109.14436)
- pyroomacoustics image-source simulation was used to generate training RIRs in the attention volume paper. — [arXiv 2309.13504](https://arxiv.org/html/2309.13504v3)

### Inferences
- Feasible in ~1 day: (1) sweep -> IR via inverse-filter deconvolution; (2) Schroeder EDC -> EDT/T20/T30; (3) first-reflection delay -> nearest surface distance; (4) early/late energy ratio (C50-like) from the measured IR; (5) simple rule or logistic classifier for open / street-canyon / room / large hall using T60, first-reflection delay, number of discrete reflections, plus YAMNet tags. Report as a soft prior to the localisation grid (e.g. "indoors, room ~3-6 m") rather than a hard decision.
- Research-grade (skip): blind volume regression (factor-of-2 error, needs training data), room-shape reconstruction (multi-mic), accurate blind DRR from close talk.

### Gaps
- pyroomacoustics RT60 measurement API and pyrirgen links were not verified in this session (pyroomacoustics: https://github.com/LCAV/pyroomacoustics is the known repo; confirm function names before relying on them).
