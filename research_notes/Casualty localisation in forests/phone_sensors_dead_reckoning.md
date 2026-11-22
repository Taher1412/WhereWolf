# Phone sensors and dead reckoning for casualty localisation in forests (non-GNSS, non-acoustic)

Scope: what a standard smartphone, driven from a plain HTML/JS page in Chrome Android or Safari iOS plus a Python backend, can add to Near's likelihood grid (25 m cells, 72 headings) in a mostly flat, wooded area such as the Bois de Vincennes. Each section ends with how the cue fuses into the grid. Numbers come from the cited sources. Where a number is my own calculation or an uncited fact, it is marked as an inference.

---

## 1. Magnetometer compass: accuracy, interference, browser access, pointing at landmarks

### Takeaway
A phone compass held still outdoors, away from metal, is usually good to about 5–25° (median RMSE about 22–24° in the one controlled study I found, with a few degrees under the best conditions). The error grows to 40–90° when the phone is moving or near magnetic disturbances such as steel, electronics or vehicles. Both target browsers can read it, but each has its own API and a permission step. Use it as a wide prior on heading (σ ≈ 20–30°), or as an absolute bearing when the user points the phone at a landmark. It must never be trusted as tightly as the sun.

### Cited Findings
- **Controlled test (Elias & Maas, TU Dresden, ISPRS Annals V-1-2020, 2020).** Three phones (LG Nexus 5, Samsung Galaxy S8 and S10+), 216 measurement series, compared against a reference IMU. Pitch and roll were accurate to under 2°. For azimuth, the median RMSE was **24.0° static and 41.9° dynamic**. It was **45.6° with magnetic perturbation** (simulated soft iron of 10–15 µT) versus **22.0° without**, and **23.7° outdoors versus 51.2° indoors**. Maximum azimuth error was **50.8° outdoors** and **90.9° indoors**. Across conditions, azimuth accuracy "varies between 1° and 90°". With the best sensor fusion (IRS2), 25% of measurements were within 15° and 50% within 30°. The authors recommend treating the phone azimuth as a rough estimate and refining it with landmark-based resection. — [Elias & Maas 2020, ISPRS Annals](https://isprs-annals.copernicus.org/articles/V-1-2020/181/2020/isprs-annals-V-1-2020-181-2020.pdf) (DOI 10.5194/isprs-annals-V-1-2020-181-2020)
- **Literature cited in that paper.** Blum et al. (2013) found about 30° azimuth deviations, with significant drift after a few minutes, in a static AR app. Novakova & Pavlis (2017) found azimuth errors of up to 90° when using a phone as a geological compass. — [Elias & Maas 2020](https://isprs-annals.copernicus.org/articles/V-1-2020/181/2020/isprs-annals-V-1-2020-181-2020.pdf)
- **Structural geology comparisons with survey compasses.** Allmendinger, Siron & Scott (2017, J. Structural Geology 102:96–112) conclude that iOS devices are suitable "for all but the most demanding applications" if care is taken with metal and electronic objects. The magnetometer is the least reliable sensor, and small metal objects within several centimetres disturb it. — [Allmendinger et al. 2017 (record)](https://asu.elsevierpure.com/en/publications/structural-data-collection-with-mobile-devices-accuracy-redundanc/); [copy of the text](https://www.scribd.com/document/372939199/traducir-pdf)
- **Smart Compass-Clinometer (Lee et al. 2013).** Outdoors, the mean difference from a conventional compass-clinometer was 2.63° for dip direction (an azimuth) and 1.70° for dip. In an underground mine it was 4.57° and 2.57°. — [AGRIS record](https://agris.fao.org/search/en/records/65dfd6cd0f3e94b9e5dcab44)
- **Brunton comparison (Vanderlip & Mitchell, GSA 2016 abstract).** A correctly used Brunton pocket transit was more precise than the smartphone apps. — [GSA 2016 handout](https://gsa.confex.com/gsa/2016AM/webprogram/Handout/Paper283596/There%20Is%20An%20App%20For%20That%20Testing%20Geologic%20Smartphone%20Apps%20Against%20The%20Brunton%20Pocket%20Transit.pdf)
- **Best case after custom calibration.** A student study reached 1.37° heading accuracy for one phone with a custom calibration algorithm. The built-in calibration did worse. This is a low-tier venue. — [Emerging Investigators 2023](https://emerginginvestigators.org/articles/23-153)
- **Indoor walking heading.** RMSE was 17.4° with a method designed to suppress magnetic anomalies. — [NAVIGATION, Feb 2024 (DOAJ)](https://doaj.org/article/2e69ad6dd0ba4100ab3b333fb77a7a3d)
- **Heading bias in an outdoor PDR study.** Most heading biases (Android rotation-vector sensor) stayed within ±15°. There was one transient of about 30° attributed to magnetic interference. The researchers modelled heading bias as a Gauss–Markov process with σ = 15° and τ = 60 s. — [Broyles et al. 2018, Sensors 18(7):2232](https://pmc.ncbi.nlm.nih.gov/articles/PMC6068906/)
- **iOS browser access.** `DeviceOrientationEvent.requestPermission()` must be called from a user gesture such as a button tap, on HTTPS. Safari does not fire `deviceorientationabsolute`. Instead, listen to `deviceorientation` and read the non-standard `webkitCompassHeading` (0–360°, clockwise from north) and `webkitCompassAccuracy`. — [MDN requestPermission](https://developer.mozilla.org/en-US/docs/Web/API/DeviceOrientationEvent/requestPermission_static); [W3C public-geolocation thread, Jan 2024](https://lists.w3.org/Archives/Public/public-geolocation/2024Jan/0035.html); [W3C thread, May 2024](https://lists.w3.org/Archives/Public/public-geolocation/2024May/0082.html); [WebKit IDL](https://webkit.googlesource.com/WebKit/+/master/Source/WebCore/dom/DeviceOrientationEvent.idl)
- **Chrome and spec access.** Listen to `deviceorientationabsolute`, where `absolute === true`, and derive heading from `alpha`. A common recipe is heading = 360 − alpha, valid when the phone is held flat. The W3C Device Orientation and Motion spec is still a Working Draft (Oct 2024). — [W3C WD 2024-10-24](https://www.w3.org/TR/2024/WD-orientation-event-20241024/); [MDN DeviceOrientationEvent](https://developer.mozilla.org/docs/Web/API/DeviceOrientationEvent); [DEV article (secondary)](https://dev.to/toolswebs1/building-a-compass-in-the-browser-how-the-deviceorientation-api-actually-works-3f37)
- **Generic Sensor API.** In Chrome, `AbsoluteOrientationSensor` is a standard motion-sensor class, but the raw `Magnetometer` sits behind the `#enable-generic-sensor-extra-classes` flag. Secure context only, and readings only arrive while the page is visible. — [Chrome Developers: Sensors for the web](https://developer.chrome.com/docs/capabilities/web-apis/generic-sensor)

### Inferences
- **Grid fusion, option A (heading prior).** Multiply `L(p,θ)` by `N(wrap(θ − h_compass); σ_c)`, with σ_c = 25° by default. Use 35° if iOS `webkitCompassAccuracy` is large or negative, or the user is in a vehicle or next to one. This is the same mechanism as the sun term (§6.4 of the brief) but with a looser σ. It cuts the effective number of headings from 72 to about 10–15. When sun and compass are both present, the sun should dominate because its σ is about 15°.
- **Grid fusion, option B (absolute bearing, the stronger use).** "Point the top of the phone at the church and tap." The observation then becomes an absolute bearing `b_i`, and the term is `max_c N(wrap(bearing(p→c) − b_i); σ_c)`, independent of θ. Each pointed landmark is then a full line of position. Two pointed landmarks give a fix without the sun. Clock directions should still be kept as relative bearings, and the compass then acts only as a prior on θ.
- **Trail direction.** "Point the phone along the path." This gives the trail azimuth modulo 180°. It can be scored against the orientation of nearby OSM path segments (see §4).
- **Interference rules of thumb** (from the "metal within cm" findings): ask the user to hold the phone at arm's length, away from a rifle, steel plates, radios or a vehicle, and to wave it in a figure-8 once. Body armour with steel plates and a weapon right next to the phone are exactly the 10–15 µT soft-iron case where error doubled in Elias & Maas.
- **Magnetic declination.** I believe declination in Paris is currently about +1 to +2° east. This is not verified in my sources. It is negligible compared with σ_c, so it can be ignored for the hackathon.
- The 1–3° results from geology and survey compasses come from phones held carefully against a surface. A soldier pointing a phone by hand at a half-visible church will do worse. 20–25° is the honest planning number.

### Gaps
- I found no peer-reviewed study that measures phone compass error in forests specifically, or near military kit (rifle, plate carrier, vehicle). The interference figures are from simulated soft-iron tests.
- I did not verify exactly what `webkitCompassAccuracy` means (Apple documents it as an accuracy in degrees, with negative meaning invalid), nor whether Chrome's `deviceorientationabsolute` reference is magnetic or true north. Both should be tested on the demo phones.

---

## 2. Barometer altitude and DEM matching

### Takeaway
The best paper found (Broyles et al. 2018, AFIT) shows that a particle filter fusing phone PDR with barometric elevation matched against a fine DEM brings walked-route error from about 175 m RMS (PDR only) down to about 46 m RMS. The gain comes from walked traces over hilly ground. On flat routes (under 10 m relief) it still helped, but less. **No browser exposes the barometer**, so for a web app this is a native-app idea only. The browser substitute is a spoken terrain-class question checked against a DEM (see §5).

### Cited Findings
- **Broyles, Kauffman, Raquet, Smagowski (Sensors 18(7):2232, 2018), "Non-GNSS Smartphone Pedestrian Navigation Using Barometric Elevation and Digital Map-Matching".**
  - Method: a SIR particle filter (500 particles). The state is east/north position, heading bias and barometric bias. Steps come from Android's step detector. Step length = height × 0.415 (male) or 0.413 (female), ± 0.15 m.
  - Barometer: resolution 0.16 Pa, which is under 10 cm. Bias was modelled as Gauss–Markov with σ = 5 m and τ = 3600 s (σ = 20 m, τ = 1200 s for SRTM). The largest observed drift was about 10 m over one walk.
  - Results: summary RMS was **174.8 m for PDR alone**, **45.8 m with the USGS 10 m DEM**, 46.2 m with 2 m lidar, 47.8 m with a 0.5 m DEM, 60.5 m with the USGS 30 m DEM and **165.7 m with SRTM30** (no better than PDR alone). Routes were 1.2–5.6 km long.
  - Flat routes (under 10 m total change) gave, for example, 3.2 km: PDR 105.7 m → 25.6–34.4 m. 4.8 km: PDR 245.3 m → 45.1–83.7 m. On a flat leg the particles spread out and the predicted uncertainty grew.
  - Limits: map-matching is on elevation only, not trails. The original work was post-processed on a desktop. Fine DEMs are needed, and SRTM30 is not good enough.
  - [Broyles et al. 2018](https://pmc.ncbi.nlm.nih.gov/articles/PMC6068906/)
- **Follow-on work.** Weir (Auburn thesis, 2024) adds LEO-satellite aiding for heading to barometric map-matching PDR and evaluates lighter filters with open-source DEMs. The full text is embargoed until 2029. — [Auburn ETD 10415/9610](https://etd.auburn.edu/handle/10415/9610)
- **Drift and absolute altitude.** Phone barometer readings drift over tens of minutes, so using differences between consecutive readings is preferred. — [Inertial odometry on handheld smartphones, arXiv 1703.00154](https://arxiv.org/pdf/1703.00154). Floor changes can be distinguished because they happen faster than typical drift. — [Microsoft Research, HotMobile 2014](https://microsoft.com/en-us/research/wp-content/uploads/2016/02/hotmobile14b.pdf). Industry patents say that absolute altitude from the standard formula "rarely" matches truth because of sensor drift, weather and poor factory calibration, so a reference pressure is needed. — [US patent 10655961](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/10655961)
- **Browser availability.** Chrome's Generic Sensor documentation lists accelerometer, gyroscope, linear acceleration, gravity, absolute and relative orientation, and (behind a flag) magnetometer and ambient light. There is no pressure or barometer class. — [Chrome Developers](https://developer.chrome.com/docs/capabilities/web-apis/generic-sensor). In Chromium's generic_sensor platform table, the PRESSURE row is empty on every platform (an old version, r61). — [Chromium source README](https://chromium.googlesource.com/chromium/src/+/1eb995ae863d08fbdb7fda170d678129bdcfff2a/services/device/generic_sensor/README.md)
- **Relief in the Bois de Vincennes.** Hiking and mapping sources (not geodetic) give about 71 m for the Butte aux Canons, 68–70 m near the Lac de Gravelle / Butte Gravelle, a mean of 53 m and a low point of about 48 m. That is about **20–25 m of total relief**, mostly gentle, and the Butte aux Canons rises about 15 m above its surroundings. — [visorando route](https://www.visorando.com/randonnee-petit-tour-au-bois-de-vincennes/); [areq.net](https://areq.net/lang/fr/Bois_de_Vincennes.html); [cirkwi: Rivière de Gravelle](https://www.cirkwi.com/fr/point-interet/3766845-riviere-de-gravelle). The sources disagree by a few metres.

### Inferences
- In a browser, the barometer simply isn't available, so drop it for the hackathon. A Capacitor or Kotlin wrapper could read `TYPE_PRESSURE`, but that is not a one-day job alongside everything else.
- A single static barometer reading, without a reference station, has bias of tens of metres. That is comparable to the whole relief of the Bois de Vincennes, so it carries almost no information. A *relative* reading over a walked trace ("we climbed about 10 m") would carry information, but only together with PDR.
- **Grid fusion, if ever available:** `L(p) *= N(h_baro − DEM(p) − b; σ)`, with the bias b either marginalised (σ_b ≈ 5 m with a reference, 20+ m without) or estimated from a known start point. In nearly flat ground expect only a little help. It can tell the hilltop or butte cells from lake level, and little else.
- A suitable French DEM exists: IGN RGE ALTI at 1 m / 5 m, which is open data as far as I know (not verified here). By the Broyles results, a 30 m global DEM (SRTM) is not good enough.

### Gaps
- I found no study of barometric DEM matching in terrain as flat as the Bois de Vincennes (about 20 m of relief) for a *static* user. The Broyles flat routes were walked traces of 2–5 km.
- I did not confirm the current Chromium status of a pressure sensor (only an old table). No Web API is known to me in Safari.

---

## 3. Pedestrian dead reckoning (PDR), last GPS fix and spoken dead reckoning

### Takeaway
Phone PDR typically loses 1–5% of distance travelled *in step length*. Heading error dominates the position drift, and real outdoor PDR alone ran to about 175 m RMS over 1–5 km routes. For Near the high-value, cheap version is **spoken dead reckoning from an anchor** ("10 minutes north from the car park", "last GPS fix before jamming") turned into a likelihood sector or annulus. Live JS step counting is possible but fragile, because the page must stay open and visible.

### Cited Findings
- **Step length from a handheld phone (Renaudin, Susi, Lachapelle, Sensors 12(7):8507, 2012).** Step detection was 97–100% per subject (mean 99.2%). The step length model is s = h·(a·f_step + b) + c. Distance error was **2.5–5%** of distance travelled (universal model mostly 4–6%, worst 8–9%; calibrated model at most 5%). Tested in swinging-hand and texting-hand modes. — [Renaudin et al. 2012](https://pmc.ncbi.nlm.nih.gov/articles/PMC3444061)
- **Step detection.** Windowed peak detection gave the best results, with a median error of 1.3% regardless of where the phone was carried. — [search snippet, Sensors comparison study (PMC6603536)](https://pmc.ncbi.nlm.nih.gov/articles/PMC6603536). Distance-estimation error was about 0.66–1.14% across texting, calling and swinging modes. — [PMC9782146](https://pmc.ncbi.nlm.nih.gov/articles/PMC9782146). Particle-filter PDR stayed under 5% of distance travelled indoors and outdoors. — [IPIN 2016 postprint, Tampere](https://trepo.tuni.fi/bitstream/10024/129025/1/IPIN_Racko_PostPrint.pdf). These figures are from search snippets of short controlled walks, so treat them as optimistic.
- **Real outdoor PDR position error.** PDR alone (Android step detector plus rotation-vector heading) gave per-route final DRMS of 39–389 m over 1.2–5.6 km, with an overall RMS of 174.8 m. Heading bias was within ±15° most of the time. — [Broyles et al. 2018](https://pmc.ncbi.nlm.nih.gov/articles/PMC6068906/)
- **Doctrine.** Army land navigation treats dead reckoning (azimuth plus pace count) as one method and says that moving by terrain association is "more forgiving of mistakes and far less time-consuming than dead reckoning". TC 3-25.26 (Nov 2013) supersedes FM 3-25.26 (2005). — [TC 3-25.26 (Missouri S&T ROTC copy)](https://armyrotc.mst.edu/media/academic/armyrotc/documents/manualsadpadrpfmetc/TC%203-25.26.pdf); [FM 3-25.26 (archive.org)](https://archive.org/download/MManuals/Fm3-25.26MapReadingAndLandNavigation.pdf)
- **Browser limits.** Generic Sensor readings are delivered only while the page is visible. — [Chrome Developers](https://developer.chrome.com/docs/capabilities/web-apis/generic-sensor). Motion and orientation events on iOS need `requestPermission()` from a user gesture. — [MDN](https://developer.mozilla.org/en-US/docs/Web/API/DeviceOrientationEvent/requestPermission_static)

### Inferences
- **Spoken DR → grid (implementable in hours).** From an anchor A (a named OSM feature, or a stored last GPS fix), distance `d = minutes × v`, with v ≈ 1.2–1.4 m/s on paths (a typical walking speed, not cited here; slower off-path or carrying a casualty). Use a log-normal on range with σ ≈ 40–50% (a spoken duration is a rough guess) and a von Mises/normal on bearing with σ ≈ 30–45° for "roughly north". `L(p) *= LN(|p − A|; d, 0.45) · N(wrap(bearing(A→p) − φ); 35°)`. If no direction is given, use the range term alone, which gives an annulus.
- **Last GPS fix before jamming.** Store `navigator.geolocation` fixes continuously while they are good, keeping the last one with its timestamp and accuracy. When jamming starts, the prior is a disk of radius `v_max × Δt + accuracy`. That alone bounds the search area. 12 min at 1.4 m/s is about 1 km, or roughly 3 km² of grid, which is much smaller than "the whole Bois" (995 ha).
- **Live PDR in JS.** DeviceMotion peak detection plus compass heading gives about 5% distance error from step counting, plus heading error × distance (sin 15° ≈ 26% cross-track). In practice expect about 10–20% of distance walked. It is only worth doing if the field page is open during the walk, which is unlikely for a medic.
- **Pace count as a spoken question.** "How many paces / minutes since you left X?" fits the doctrine. Soldiers trained in pace count give better distances than "about 10 minutes".

### Gaps
- I found no study of PDR specifically under forest canopy or on forest trails with a phone, and none of soldiers carrying phones in pouches or plate carriers.
- I found no source for how accurately people estimate walking time or distance from memory, which is needed to set σ for spoken DR. 40–50% is my guess.

---

## 4. Map matching to OSM paths and trails

### Takeaway
Constraining position to mapped paths is a strong, cheap cue. In a park-forest with a dense path network it turns 2D blobs into narrow ribbons along paths. The literature is mostly indoor (corridors) or constraint-only particle filters. I found no forest-trail accuracy numbers, so the expected gain is an engineering estimate.

### Cited Findings
- **Constraint-only dead reckoning.** IMU-only dead reckoning has been formulated as a constraint-only particle filter using only a map and human physiology, with no external observations. — [Russell & Bergmann, Oxford ORA](https://ora.ox.ac.uk/objects/uuid:a6c17ad5-063d-4dd2-8e2d-92ae1d6c509a/files/r1831cn776)
- **Backtracking particle filter with geospatial analysis.** Real-time map matching that corrects inertial odometry (building maps). — [Sensors, Apr 2022 (PMC9105771)](https://pmc.ncbi.nlm.nih.gov/articles/PMC9105771)
- **Map-matching PDR.** Map matching that uses corridor orientation to calibrate step direction, with a particle filter that removes impossible positions. — [MDPI JSAN 3(1):44](https://mdpi.com/2224-2708/3/1/44)
- **GNSS/INS particle filter with map priors.** "Impassable buildings and unlikely walking areas" used as probabilistic map matching. — [arXiv 2601.22406 (2026)](https://arxiv.org/pdf/2601.22406)
- **Doctrine.** A "handrail" is a linear feature (trail, road, power line, river) followed towards an "attack point". Handrail, catching feature and attack point are standard navigation aids. — [ROTC land-nav study guide](https://open-exam-prep.com/study-guides/army-promotion-board/weapons-land-nav-readiness/land-navigation-terrain-azimuths); [ATU ROTC supplemental training](https://atu.edu/rotc/docs/19_LDAC10_Supplemental_Training_2_Jun.pdf)

### Inferences
- **Grid fusion ("I'm on a path or track").** Precompute the distance from each cell to the nearest OSM `highway=path|track|footway|bridleway|cycleway`. Then `L(p) *= ε + (1−ε)·exp(−d(p)²/2σ²)`, with σ ≈ 15 m (half a cell plus OSM error) and ε ≈ 0.05 so that a missing or unmapped path doesn't zero out the truth. Use typed variants for "wide gravel track" (`highway=track`, or `service` in Vincennes) versus "narrow footpath" (`path`/`footway`), and "paved road" (`highway=tertiary` and up, e.g. Route de la Pyramide).
- **Trail direction from the compass** ("point along the path"): for cells near a path, multiply by `N(wrap180(seg_azimuth(p) − b); σ_c)`. This removes paths running the wrong way.
- **Junctions and shores** make good yes/no questions for the selector: "Are you at a path junction?" (cells within 20 m of a path node with degree ≥ 3). "Can you see water / a lake shore?" (Lac Daumesnil, Lac des Minimes, Lac de Gravelle, Lac de Saint-Mandé). "Is there a fence or wall beside you?" These fit the existing expected-entropy selector directly: predict the answer per cell from the OSM layers.
- With 25 m cells, a single path constraint keeps about 10–30% of the cells in the Bois (an estimate that depends on path density; compute it from the cache). Combined with one bearing it often leaves a few path segments, which is exactly the multi-blob case the question selector handles well.

### Gaps
- I found no published accuracy numbers for map matching to forest trails, or to OSM paths outdoors, with phone PDR. Nor did I find any on how complete OSM trail coverage is in wooded parks. Bois de Vincennes OSM coverage should be checked directly from the local cache.

---

## 5. Terrain-aided cues: slope and aspect from the phone or by voice

### Takeaway
The phone's accelerometer measures tilt very well (pitch and roll under 2°), so a phone laid on the ground measures the ground slope. Downhill direction (aspect) also needs the compass. In the Bois de Vincennes most ground is nearly flat, so slope only identifies the few sloped places (the buttes, lake banks, the ravine-like Gravelle stream). That is still a useful binary question.

### Cited Findings
- Pitch and roll from phone sensors are accurate to under 2° (median 0.6–2.8° RMSE across conditions) and are barely affected by magnetic disturbance (less than 1° loss). — [Elias & Maas 2020](https://isprs-annals.copernicus.org/articles/V-1-2020/181/2020/isprs-annals-V-1-2020-181-2020.pdf)
- Geology apps measure dip (slope) from gravity alone, so slope doesn't need the magnetometer. Lee et al. found a mean outdoor dip difference of 1.70° from a conventional clinometer. — [Allmendinger et al. 2017 (copy of the text)](https://www.scribd.com/document/372939199/traducir-pdf); [Lee et al. 2013](https://agris.fao.org/search/en/records/65dfd6cd0f3e94b9e5dcab44)
- Terrain in Vincennes: about 48–71 m, with the Butte aux Canons about 15 m high, and the high point near the Lac de Gravelle. — [visorando](https://www.visorando.com/randonnee-petit-tour-au-bois-de-vincennes/); [cirkwi](https://www.cirkwi.com/fr/point-interet/3766845-riviere-de-gravelle)
- Terrain association (matching visible relief to the map) is the primary doctrinal method. — [TC 3-25.26](https://armyrotc.mst.edu/media/academic/armyrotc/documents/manualsadpadrpfmetc/TC%203-25.26.pdf)

### Inferences
- **Browser implementation.** The `DeviceOrientationEvent` beta and gamma angles (or the `GravitySensor` in Chrome) give the phone's tilt. Ask "lay the phone flat on the ground and tap". Slope = acos(g_z/|g|). Downhill azimuth = compass heading + atan2 of the gravity x and y components.
- **Spoken alternative (no sensor):** "Is the ground sloping where you are? Which way is downhill (clock direction)?", or "Are you on top of a hill, on a slope or on flat ground?"
- **Grid fusion.** From a DEM (for example IGN RGE ALTI at 5 m, resampled to 25 m), compute slope s(p) and aspect a(p). Then:
  - `L(p) *= N(s_meas − s(p); 2–3°)` if measured, or a 3-class likelihood for voice (flat < 2°, gentle 2–6°, steep > 6°: thresholds are my guesses);
  - when the measured slope is above about 3°, multiply by `N(wrap(a_meas − a(p) [relative to θ if a clock direction was given]); 30°)`.
- A 25 m cell can hide micro-relief such as ditches, mounds and old fortification earthworks, so keep σ wide and ε > 0.

### Gaps
- I found no paper on pedestrian terrain-aided navigation from phone tilt. The approach is borrowed from geology compass-clinometer work and aircraft TERCOM-style ideas.
- I did not verify the resolution or licence of the IGN RGE ALTI DEM in this research.

---

## 6. Celestial cues under canopy: sun, shadows, polarization, moon

### Takeaway
On 21 November in Paris the sun peaks at only about 21° elevation (around 12:37 CET), and it sets around 17:00 CET. Low sun comes in sideways under the canopy and casts long shadows (about 2.5 × object height at noon). With deciduous trees mostly bare in late November, "which way do shadows point?" is often answerable even when the sun itself is hidden. Phone-camera polarization compasses are unproven. Dedicated polarization sensors reach under 0.5°.

### Cited Findings
- **Sun position for the demo** (computed with the project's `backend/sun.py` at 48.84 N, 2.44 E, 21 Nov 2026):

  | Local time (CET) | Azimuth | Elevation |
  |---|---|---|
  | 09:30 | 136° | 9.9° |
  | 10:30 | 149° | 15.9° |
  | 11:30 | 163° | 19.8° |
  | ~12:40 | ~180° | 21.4° (maximum) |
  | 13:30 | 193° | 20.4° |
  | 14:30 | 208° | 16.9° |
  | 15:30 | 221° | 11.3° |
  | 16:30 | 233° | 4.0° |
  | ~17:00 | 239° | below 0° |

  The azimuth moves about 13–15° per hour, so the time of the report must be stamped. (Own computation, NOAA-style formula in the repo.)
- **Sunflecks.** Under intact canopies, sunflecks may supply 37–68% of seasonal understorey PAR. Individual sunflecks last only 4–6 min. Even in large gaps (1000 m²) direct sun usually lasts under 4 h a day. Gap light depends mainly on canopy height and latitude. — [Canham et al., "Light regimes beneath closed canopies and tree-fall gaps in temperate and tropical forests" (Andrews Forest PDF)](https://andrewsforest.oregonstate.edu/sites/default/files/lter/pubs/pdf/pub1134.pdf); [LSU record](https://digitalcommons.lsu.edu/biosci_pubs/3047)
- **Low sun.** In ray-tracing models, low sun elevation makes the light under the canopy more diffuse and more uniform. Low solar angles together with canopy heterogeneity shape transmission. — [Musselman et al. 2015](https://research-groups.usask.ca/hydrology/documents/pubs/marmot/musselman_et_al_2015_2.pdf); [Int J Biometeorol, doi 10.1007/s00484-009-0222-7](https://link.springer.com/article/10.1007/s00484-009-0222-7)
- **Polarization compasses.** Bio-inspired dedicated sensors reach a solar-meridian error under 0.5°, even on cloudy days. — [Bionic polarization navigation sensor (PMC5017388)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5017388/); [Photonics, Nov 2024 (MDPI 2304-6732/11/12/1099)](https://mdpi.com/2304-6732/11/12/1099). Performance depends strongly on weather and air quality, and tilt away from the zenith adds error. — same sources. For phones, only a demo page claims that phone cameras are partly polarization-sensitive, with no measured accuracy. — [invisible-layer demo](https://rfi-irfos.github.io/invisible-layer/docs/experiments/sky-polarization/). A 2026 arXiv paper on calibrating fisheye cameras with skylight is preliminary. — [arXiv 2611.08911](https://arxiv.org/pdf/2611.08911)

### Inferences
- **Shadow direction question.** "Which way do shadows point (clock direction)?" gives θ = (sun_az + 180°) − k·30°. This is the same term as "sun at my k o'clock" with a 180° offset, and σ ≈ 20° (shadows are fuzzy and the ground is uneven). The selector can offer it when the user says the sun is not visible but it is daytime and not overcast.
- **"Which side of the trees is bright?"** gives a coarse sun bearing even when the disc is hidden (σ ≈ 45°). It is cheap to add as a relative-direction observation.
- **Low November sun.** At under 21° elevation the sun is often at horizon level, framed by trunks rather than by canopy. In late November the leaves are mostly down (a general phenology fact, not sourced here), so a direct sun bearing is more available than in summer. Sunflecks still flicker: a "sun at my k o'clock" answer is momentary but usable.
- **Moon.** The same code path works with lunar azimuth (e.g. `astral.moon` or `ephem`) at night. This is only relevant for night evacuation and is not a priority.
- **Polarization:** don't build it. There is no verified phone accuracy and it needs a camera pipeline.

### Gaps
- I found no study quantifying the probability of seeing the sun disc or shadows under temperate deciduous canopy in late autumn at low sun elevation.
- I found no peer-reviewed smartphone skylight-polarization heading accuracy.

---

## 7. RF signals of opportunity (brief) and OPSEC

### Takeaway
Cellular signals of opportunity (LTE/5G timing) can give metre-level fixes on vehicles and UAVs, even inside jammed areas. They need a software-defined-radio receiver, though, not a phone browser. A web page can only get whatever the OS geolocation API returns. Emitting is itself an OPSEC risk.

### Cited Findings
- Kassas group research: real LTE signals gave "meter-level accuracy" on ground vehicles and sub-metre on UAVs. Urban multipath degrades this to tens of metres in deep urban canyons. Tests have included LTE towers *inside* a GPS-jammed region. — [Kassas et al., "I am not afraid of the GPS jammer" (OSU)](https://ece.osu.edu/sites/default/files/2022-09/I_am_not_afraid_of_the_GPS_jammer_resilient_navigation_via_signals_of_opportunity_in_GPS_denied_environments.pdf); [NSF PAR 10225276](https://par.nsf.gov/servlets/purl/10225276); [OSU, LTE positioning performance](https://ece.osu.edu/sites/default/files/2022-09/Performance_Characterization_of_Positioning_in_LTE_Systems.pdf)

### Inferences
- Browsers expose no cell-ID, Wi-Fi scan, FM or DAB data. The only route is `navigator.geolocation`. On Android and iOS this may return a network (Wi-Fi/cell) fix when GNSS is jammed, if the OS location service can reach its servers (not verified in my sources). Near could accept such a fix with its stated `accuracy` as one more Gaussian term, gated for plausibility, as the brief already allows for GPS.
- OPSEC: any phone that transmits (including the voice report itself) is detectable. Near's compact-packet idea (§6.9 of the brief) is the right framing: minimise airtime, and never scan or emit beyond the report. Spoofing is also a risk, so treat any network fix as low-trust.

### Gaps
- I found no pedestrian or phone-grade signal-of-opportunity accuracy numbers, and no sources on Ukrainian practice regarding phone emissions (out of scope for this sweep).

---

## 8. Land-navigation and SAR self-location practice → spoken questions

### Takeaway
Doctrine (TC 3-25.26, which supersedes FM 3-25.26) prefers terrain association over dead reckoning. Its tools (resection on two known points, handrails, catching features, attack points, pace count) map almost one-to-one onto Near question templates, which the existing expected-entropy selector can score.

### Cited Findings
- TC 3-25.26 (Nov 2013) supersedes FM 3-25.26 (Jan 2005). — [TC 3-25.26](https://armyrotc.mst.edu/media/academic/armyrotc/documents/manualsadpadrpfmetc/TC%203-25.26.pdf)
- Terrain association is "more forgiving of mistakes and far less time-consuming than dead reckoning". — [FM 3-25.26 / TC 3-25.26](https://archive.org/download/MManuals/Fm3-25.26MapReadingAndLandNavigation.pdf)
- Resection means determining your location from two (or more) known points visible on the ground and on the map. — [land-nav study guide (secondary)](https://open-exam-prep.com/study-guides/army-promotion-board/weapons-land-nav-readiness/land-navigation-terrain-azimuths)
- Handrail: follow a linear feature (trail, road, power line, river) to an attack point. Handrail, catching feature and attack point are listed together as navigation aids. — [study guide](https://open-exam-prep.com/study-guides/army-promotion-board/weapons-land-nav-readiness/land-navigation-terrain-azimuths); [ATU ROTC](https://atu.edu/rotc/docs/19_LDAC10_Supplemental_Training_2_Jun.pdf)
- Pace count: one secondary guide says "typically 100 meters per 100 paces, adjusted for your stride". This figure is questionable, because doctrine defines a pace as about one natural step and soldiers calibrate their own count on a 100 m course. Verify against the TC before quoting it. — [cadettrails land nav practical](https://cadettrails.pages.dev/docs/warriortasks/landnavpractical/)

### Inferences: question templates, each with its grid likelihood
| Doctrine idea | Spoken question | Per-cell predicted answer (for expected entropy) |
|---|---|---|
| Handrail | "Are you on or beside a path, road, fence, lake shore or stream?" | distance to the OSM linear feature < 20 m |
| Catching feature | "If you keep walking ahead, do you soon hit a road, lake or the ring road?" | ray from p along θ hits the feature within 200 m |
| Attack point / last known point | "What was the last thing you clearly passed, and how many minutes ago?" | annulus around that feature (spoken DR, §3) |
| Resection | (already core) clock directions or pointed bearings to two landmarks | existing term |
| Pace count | "How many paces since the junction?" | range from the junction node, σ ≈ 20% |
| Terrain association | "Ground flat, sloping or on a hilltop? Which way is downhill?" | DEM slope/aspect class (§5) |
| Sun/shadow | "Which way do shadows point?" | sun-azimuth heading term (§6) |
| Collecting features | "Can you see open grass, a lawn or a sports field?" | distance to `leisure=pitch`/`landuse=grass` |

---

## 9. Ranked list: implementable in under a day (browser + Python) and expected effect

### Takeaway
The biggest, cheapest wins are not new sensors but new *likelihood terms*. In order: a path constraint, compass bearings (pointing the phone), spoken dead reckoning from a last fix or named anchor, and shadow/slope questions. Barometer, live PDR, polarization and RF are not worth a hackathon day.

### Cited Findings
- Compass σ, PDR %, DEM-matching gains and browser API limits are as cited in §§1–7 ([Elias & Maas 2020](https://isprs-annals.copernicus.org/articles/V-1-2020/181/2020/isprs-annals-V-1-2020-181-2020.pdf); [Broyles et al. 2018](https://pmc.ncbi.nlm.nih.gov/articles/PMC6068906/); [Renaudin et al. 2012](https://pmc.ncbi.nlm.nih.gov/articles/PMC3444061); [Chrome Generic Sensor](https://developer.chrome.com/docs/capabilities/web-apis/generic-sensor); [MDN requestPermission](https://developer.mozilla.org/en-US/docs/Web/API/DeviceOrientationEvent/requestPermission_static)).

### Inferences: ranked (effort / expected effect, my engineering estimates)
1. **"On a path / track / road / shore" constraint plus path-junction and lake questions** (OSM layers already cached). About 2–3 h: a distance transform over the grid in numpy, plus new question templates. Effect: it collapses 2D blobs to path ribbons, likely shrinking the posterior area several-fold in the Bois. It works under full canopy with no sensor at all. **Highest value.**
2. **Compass: "point the phone at X and tap" absolute bearings, plus a compass heading prior.** About 2–3 h: iOS `requestPermission()` on the push-to-talk tap, `webkitCompassHeading` on iOS, `deviceorientationabsolute` alpha on Chrome, sent with the report. Effect: it replaces the sun when the sun is hidden (σ ≈ 20–25° compared with the sun's 15°), and turns two landmarks into a fix. Inflate σ if the accuracy reading is poor. Risk: interference from kit, so tell the user to hold the phone away from the rifle and plates.
3. **Spoken dead reckoning from an anchor or last GPS fix.** About 2 h: the extraction schema gets `{"from": "car park|last_fix|<landmark>", "minutes": 10, "paces": null, "direction": "north|clock"}`, and the front end caches the last good `navigator.geolocation` fix with its timestamp. Effect: it bounds the search area to roughly a 1 km disk or sector instead of the whole 995 ha. A large effect on the first report, and it makes the other cues' ambiguity resolvable.
4. **Shadow-direction and "bright side" questions** reuse `sun.py`. About 1 h. Effect: they bring back the sun heading constraint under canopy whenever shadows exist. In November the low sun makes long, readable shadows.
5. **Slope/aspect: "lay the phone flat" plus a spoken slope class against a DEM.** About 3–4 h including the DEM download and resampling. Effect: small in the flat Bois, but it can confirm or reject the buttes and lake-bank blobs. Do it only if time allows.
6. **Live JS PDR (step counting plus heading).** 4+ h and fragile (the page must stay open, iOS needs a permission). Effect: about 5% step-length error plus heading error, so roughly 10–20% of distance walked. Low value, because the medic won't keep the page open while moving.
7. **Do not attempt:** barometer (no browser API, and about 20 m of relief); polarization compass (unproven on phones); RF signals of opportunity (needs an SDR; OPSEC).

### Gaps
- None of the effect sizes in this ranked list are measured. They should be checked with the project's synthetic test (`tests/test_localise.py`-style) by adding each term and measuring the 2-σ radius and the error at Bois de Vincennes test points.
