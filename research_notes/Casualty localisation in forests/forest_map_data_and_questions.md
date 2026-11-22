# Casualty localisation in forests: map data, visibility models and discriminating questions (Bois de Vincennes)

Scope note: findings marked **[measured]** were computed in this session from live OpenStreetMap (Overpass, OSM base timestamp 2026-11-21T22:21Z) and the IGN Géoplateforme WMS, clipped to the OSM park relation "Bois de Vincennes" (relation 18047835, leisure=park, bbox lat 48.8171–48.8459, lon 2.3998–2.4697). Scripts and raw files sit in the session scratchpad (not in the repo). Everything else is cited. Uncertain items are flagged.

## 1. Open data for the Bois de Vincennes: what exists, licence, size, how fast to fetch

### Takeaway
Two sources are enough for a hackathon and both download in under 2 minutes. (1) OSM through Overpass gives a dense path network, forest polygons with leaf_type, about 11.8k individual tree nodes, 620 benches, water, fences and pitches. (2) The IGN LiDAR HD canopy height model (MNH) can be pulled for the whole park as one float32 GeoTIFF (about 5 m pixels, about 2.6 MB) in a single WMS GetMap call. BD Forêt v2, RGE ALTI and BD TOPO are all heavier and add little over these two.

### Cited Findings
**OpenStreetMap: feature counts inside the park relation [measured, Overpass `map_to_area` on rel 18047835]**
- Park area from a 25 m grid inside the relation: **973 ha**, consistent with the ~995 ha usually quoted. OSM forest/wood polygons cover **44%** of park cells. landuse=grass/meadow polygons cover 4%.
- Forest/wood features: 315 ways and 3 relations. leaf_type tags on forest ways: none 168, broadleaved 86, mixed 46+4, needleleaved 6. leaf_cycle is almost never tagged.
- Highways: 2,879 ways in total. path 779 ways (106.9 km), footway 1,057 (61.5 km), service 54.2 km, track 205 ways (32.1 km), bridleway 50 ways (20.9 km), cycleway 6.0 km, tertiary 8.6 km, primary 3.4 km, secondary 3.2 km, motorway 2.9 km (the A4 crosses the park).
- 1,628 highway ways carry a `surface` tag. Top values: asphalt 594, compacted 519, dirt 239, concrete 67, fine_gravel 44, sett 36, ground 32, gravel 18, sand 17. 1,251 ways have no surface tag.
- Point features: amenity=bench **620**, drinking_water 55, toilets 13, tourism=information 87, of which only **10** are information=guidepost. natural=tree **11,772 nodes** (11,259 with leaf_type: broadleaved 9,694, needleleaved 1,525). Top genera: Tilia 2,046, Quercus 1,387, Acer 1,336, Platanus 1,268, Pinus 982, Aesculus 761, Fagus 313.
- Other: barrier=fence/wall 186 ways; leisure pitch/sports_centre/stadium/track 184 features; playground 24; buildings 593; historic 43; parking 46; natural=water 75 ways and 12 relations; waterway 105 ways. **natural=peak/hill: 0**, so the Butte/Plateau de Gravelle has no OSM summit node and has to come from the DEM.
- OSM data licence is ODbL (stated in every Overpass response). The full geometry pull for the park (highways, forest, water, grass, fences, park relation, tree nodes) was **6.3 MB of JSON and took under about 1 minute**.
- Six FFRP walking routes named "Bois de Vincennes" (PR 1 to PR 6, relations 14941152, 14953763, 14953783, 14953810, 14953834, 14953847) are mapped with `osmc:symbol` "yellow::yellow_bar". These are the yellow paint blazes that walkers see on trees [measured, Overpass].

**IGN LiDAR HD canopy height model (MNH)**
- MNH = MNS (surface) minus MNT (terrain), both from the LiDAR HD point cloud (at least 10 pulses/m²). Delivered as 1 km × 1 km GeoTIFF tiles at **50 cm**; a 5 m version is announced. Licence: **Licence Ouverte 2.0**. Coverage targets all of metropolitan France plus DROM except Guyane in 2026. **ZICAD** (zones where aerial capture is banned) are distributed as nodata. Services: WMS, WMTS, WFS. Dataset last updated 30 Sep 2026 — [data.gouv.fr: MNH LiDAR HD](https://www.data.gouv.fr/datasets/mnh-lidar-hd)
- The Géoplateforme WMS (`https://data.geopf.fr/wms-r/wms`) exposes the layers `IGNF_LIDAR-HD_MNH_ELEVATION.ELEVATIONGRIDCOVERAGE.WGS84G` / `.LAMB93`, `IGNF_LIDAR-HD_MNT_...` and `IGNF_LIDAR-HD_MNS_...` [measured, GetCapabilities].
  - `FORMAT=image/png` is rejected for these float32 layers. `FORMAT=image/geotiff` works.
  - Working call: `...&REQUEST=GetMap&LAYERS=IGNF_LIDAR-HD_MNH_ELEVATION.ELEVATIONGRIDCOVERAGE.WGS84G&CRS=EPSG:4326&BBOX=48.8171,2.3998,48.8459,2.4697&WIDTH=1024&HEIGHT=640&FORMAT=image/geotiff`. It returns about 5 m × 5 m pixels for the whole park in seconds.
  - **No nodata over the park**: valid fraction 1.000, so the Bois de Vincennes is not a ZICAD hole [measured].
- Canopy height inside OSM forest polygons [measured, MNH at 5 m]: percentiles 10/25/50/75/90 = **3.9 / 7.8 / 11.5 / 14.9 / 18.0 m**. 87% of pixels are above 5 m, 61% above 10 m, 4% above 20 m. Outside OSM forest, 39% of pixels are still above 5 m (tree-lined avenues, groves and buildings that OSM doesn't tag as forest).
- Terrain (LiDAR MNT) inside forest [measured]: percentiles 5/50/95 = 47.7 / 54.4 / 62.8 m, max 73.2 m. The relief is gentle (about 25 m total), so slope questions carry little information here.
- IGN guidance on handling LiDAR HD products — [IGN workshop "LiDAR HD Manipulation" (PDF)](https://www.ign.fr/publications-de-l-ign/institut/evenements/ateliers_ign/241217_LiDAR_HD_Manipulation.pdf)

**BD Forêt v2 (IGN forest-type map)**
- Produced by photo-interpretation, department by department, between 2007 and 2018. It covers metropolitan France and is distributed as Shapefile through IGN's free-data download page — [IGN FAQ on forest data (PDF)](https://www.ign.fr/publications-de-l-ign/institut/Conferences-ligne/210119_donnees_forestieres/faq_juign_donnees_forestieres_ign.pdf); [IGN delivery descriptor DL_BDForet_2-0 (PDF)](https://geoservices.ign.fr/sites/default/files/2021-06/DL_BDForet_2-0.pdf)
- Listed on data.gouv.fr with shapefile, PDF and WMTS resources, linking out to the original source — [data.gouv.fr: BD FORET version 2](https://www.data.gouv.fr/datasets/bd-foret-version-2)
- A June 2026 data.gouv discussion reported an error when downloading the shapefile layer — [data.gouv.fr BD Forêt discussions](https://www.data.gouv.fr/datasets/bd-foret-r/discussions)
- The exact licence wording was not confirmed in the sources fetched. The IGN FAQ calls it open data.

**RGE ALTI 1 m and BD TOPO**
- RGE ALTI 1 m is downloaded per department as 7z archives (sometimes split into .001/.002) from data.geopf.fr — [geoservices.ign.fr/rgealti](https://geoservices.ign.fr/rgealti)
- Licence: Earth Engine lists it as etalab-2.0 — [Earth Engine catalog: IGN RGE ALTI 1m](https://developers.google.com/earth-engine/datasets/catalog/IGN_RGE_ALTI_1M_2_0). A harvested data.gouv record shows "License Not Specified", and a data.gouv record says updates stopped in 2024 pending a new LiDAR HD-based reference — [data.gouv.fr RGE ALTI](https://www.data.gouv.fr/datasets/rge-alti-r/informations)
- BD TOPO, BD ORTHO and RGE ALTI are under Licence Ouverte and are also available as Géoplateforme web services — [data.gouv.fr: Référentiel à grande échelle](https://www.data.gouv.fr/fr/datasets/referentiel-a-grande-echelle-rge/)

**Paris open data (trees, green spaces)**
- The City of Paris "Les arbres" inventory covers street, garden, school, cemetery and sports-ground trees, but **excludes trees planted as forest stands, for example in the bois**. One summary counts 219,360 managed trees. The City says the Bois de Boulogne and Bois de Vincennes together hold about 1,800 ha of forest and about 300,000 trees, and that the "arbres" layer is not updated in real time, with large lags in green spaces — [data.gouv.fr: Les arbres – Paris](https://www.data.gouv.fr/datasets/les-arbres-paris); [opendata Paris "arbres plantés hors peuplement forestier" (via fgeerolf summary)](https://fgeerolf.com/data/paris/arbres-plantes-hors-peuplement-forestier.html); [paris.fr: each tree has an ID card](https://www.paris.fr/pages/le-saviez-vous-chaque-arbre-de-paris-a-une-carte-d-identite-6597)
- A dataset of remarkable trees (arbres remarquables) exists — [data.gouv.fr: Les arbres remarquables](https://data.gouv.fr/es/datasets/les-arbres-remarquables-1)

### Inferences
- The 11,772 OSM tree nodes are very likely an import of the Paris "arbres" inventory (genus tags plus the Tilia/Platanus dominance typical of alignment trees). They therefore mark **avenues, alleys and lawns, not the forest interior**. Rows of plane or lime trees are a usable "am I on a tree-lined avenue?" cue. Not verified against the OSM changeset history.
- The WMS route for the MNH is far faster than downloading 50 cm tiles: the park needs about 3 × 6 km, so about 18 tiles. Uncompressed size would be about 16 MB per tile at 2000 × 2000 float32 (inferred; per-tile size is not stated on data.gouv). For a 25 m grid, the 5 m WMS extract is plenty.
- Skip BD Forêt v2 and RGE ALTI for the hackathon. OSM leaf_type plus tree genus give conifer vs broadleaf, and the LiDAR MNT from the same WMS gives terrain.

### Gaps
- No verified BD TOPO direct download URL or vegetation-layer detail for département 75/94 was retrieved.
- The exact BD Forêt v2 licence text was not confirmed.
- Water statistics below cover water *ways* only. The 12 water *relations* (likely including the Daumesnil, Minimes and Gravelle lakes as multipolygons) were not rasterised, so "water within X m" fractions are underestimates.

## 2. Viewshed and line of sight under canopy: models and a hackathon approximation

### Takeaway
Airborne LiDAR captures the canopy but not the understorey and trunks that actually block sightlines. The literature uses trunk-obstruction models or terrestrial scans and still has large errors. For a hackathon, model visibility as a probability that decays with the distance travelled through canopy (Beer–Lambert style), with the mean free path as a tunable constant. No source gave a validated metres-per-season figure for deciduous woodland.

### Cited Findings
- **Murgoitio et al. 2013** (IJGIS; lodgepole pine, Idaho) modelled tree trunks from aerial LiDAR as obstructions in a short-range visibility model. Mean error in target visibility:
  - trunk model: **8.8% underestimation**
  - mean-vegetation-height surface: **65.7% underestimation**
  - bare-earth model: **31.1% overestimation**

  — [Tecnalia portal: Improved visibility calculations with tree trunk obstruction modeling](https://scienceportal.tecnalia.com/en/publications/improved-visibility-calculations-with-tree-trunk-obstruction-mode/); [dblp](https://dblp.org/rec/journals/gis/MurgoitioSGS13)
- **Murgoitio et al. 2014** combined airborne LiDAR with terrestrial laser scanning (TLS). They found that obstruction shadowing in discrete LiDAR and TLS limits large-area visibility modelling, that TLS sub-canopy metrics could improve airborne models, and that canopy area or trunk counts from ALS were only weakly associated with measured visibility — [Tecnalia portal: Airborne LiDAR and TLS derived vegetation obstruction factors](https://scienceportal.tecnalia.com/en/publications/airborne-lidar-and-terrestrial-laser-scanning-derived-vegetation-/)
- **Gresham et al. 2023** (Ecology and Evolution) measured horizontal visibility at deer eye height in 71 woodland plots across 10 sites in North Wales using TLS. Plots with denser small stems had significantly lower viewshed coefficient 1 m above ground. There was **no difference between summer and winter scans**, but only 8 plots were rescanned in winter. Results are viewshed coefficients, not metres — [Gresham et al. 2023 (PDF, Reading CentAUR)](https://centaur.reading.ac.uk/114066/1/Ecology%20and%20Evolution%20-%202023%20-%20Gresham%20-%20Horizontal%20viewsheds%20of%20large%20herbivores%20as%20a%20function%20of%20woodland%20structure.pdf)
- Other work (abstract-level only): Lee et al. built a probabilistic estimator of below-canopy line of sight from airborne LiDAR, and a 2021 study estimated fine-scale understorey visibility from ALS + TLS with random forests — [search-result summaries; see core.ac.uk PDF](https://core.ac.uk/download/523307565.pdf); [NSF PAR](https://par.nsf.gov/servlets/purl/10450340)
- A US military report reviews forest visibility trials, measuring the distance at which a person using natural cover can be seen and identified. It notes that compiled forest-visibility data are "not strictly comparable" because methods differ — [DTIC AD0648230 (PDF)](https://apps.dtic.mil/sti/pdfs/AD0648230.pdf)

### Inferences
- **Hackathon visibility model** (assumption, not from a source). For an observer cell `p` and a landmark `c`, sample the straight segment p→c every 5–10 m on the MNH. Let `s` be the summed length of samples where canopy height is above about 5 m. Then `P_vis(p,c) = exp(−s/λ)`.
  - Start with λ ≈ 60 m for broadleaf leaf-on and 100–150 m leaf-off. Tune λ with one walk in the park.
  - Add a terrain term: the line is blocked if the MNT plus about 1.6 m eye height falls below the line to the landmark's top. Tall targets (keep, towers) can stay visible above the canopy if the observer is in a clearing. Use landmark height (OSM `height`, or MNS at the landmark minus MNT) against the canopy along the ray.
  - In the likelihood, multiply the bearing term by `P_vis` for "I see X" and by `1 − P_vis` for "I can't see X". This replaces the fixed 300 m radius in CLAUDE.md §6.3.
- The trunk results (Murgoitio) mean a mean-canopy-height surface badly underestimates visibility at eye level: you often see under the crowns. So λ should be calibrated in the field, not derived from canopy cover alone.
- The hackathon runs on 20–22 November, when leaves in Paris are falling or fallen. Expect longer sightlines than in summer. Gresham's "no seasonal difference" result came from deer-height scans in Welsh woods dominated by small stems, so it may not transfer to the mature oak and chestnut stands of Vincennes. This is uncertain.
- Precompute `P_vis` from all about 15.5k cells to the at most ~50 tall landmarks only. That is cheap: 15.5k × 50 rays × about 100 samples is about 78M lookups, a few seconds in numpy, and it can be cached to disk.

### Gaps
- I found no published metres-based visibility distance for deciduous forest leaf-on vs leaf-off. The full text of the DTIC report was not read.
- Sound propagation (traffic audible through woods) was not researched. A Bruitparif or Paris noise-map open dataset would be the obvious source, but it was not verified.

## 3. Forest observations a person can report reliably, whether they are in the data, and how discriminative they are

### Takeaway
In the Bois de Vincennes the path network is so dense that "are you on a path?" barely localises: 77% of the park lies within 25 m of a mapped way. The discriminating cues are **path type and surface** (asphalt road vs compacted alley vs dirt path vs sandy bridleway), **traffic noise from a main road or the A4**, **water visible**, **inside vs edge of trees**, **conifers nearby**, **fences** and **sports grounds**. Each is worth about 0.3–0.5 bits per yes/no answer once realistic answer error is included. Bearings to the keep and other tall landmarks stay the strongest cue whenever they are visible.

### Cited Findings (all [measured] on a 25 m grid over the park relation, 15,567 cells)
| Observation (what the speaker says) | Data source | Fraction of park cells where the answer is "yes" | Entropy of the yes/no answer, noiseless / 10% error / 20% error (bits) |
|---|---|---|---|
| On or right next to any path/road (any `highway`, <12.5 m) | OSM | 0.53 (0.77 within 25 m; median distance 11 m) | 1.00 / 0.53 / 0.28 |
| On a path/track/footway/bridleway (<12.5 m) | OSM | 0.43 (0.66 within 25 m) | ~0.99 / ~0.52 / ~0.27 |
| On asphalt or a road (service/residential/tertiary+, <12.5 m) | OSM | 0.17 (0.30 within 25 m) | 0.66 / 0.32 / 0.16 |
| On an unpaved surface (compacted/dirt/gravel/ground/sand, <12.5 m) | OSM surface tag | 0.24 | 0.80 / 0.40 / 0.21 |
| Main road within about 100 m (heavy traffic audible or visible: primary/secondary/tertiary/trunk) | OSM | 0.27 (0.15 within 50 m, 0.49 within 200 m) | 0.84 / 0.43 / 0.22 |
| Under trees (inside an OSM forest polygon) | OSM / MNH | 0.44 | 0.99 / 0.52 / 0.27 |
| Water (lake/pond) within 200 m / 300 m (water ways only, an underestimate) | OSM | 0.31 / 0.49 | 0.89 / 0.46 / 0.24 (200 m) |
| Pine/conifer trees around you (share of tree nodes that are needleleaved) | OSM tree nodes / forest leaf_type | ~0.14 (tree-node proxy, not a cell fraction) | 0.58 / 0.28 / 0.14 |
| Very tall canopy (>20 m) overhead | MNH | 0.04 of forest pixels | 0.24 / 0.09 / 0.05 |

- Distance from forest cells to the edge of the OSM forest mask: median **25 m**, 64% within 50 m, 95% within 100 m, max 168 m. Forest polygons are cut by the many paths and roads, so "deep forest" hardly exists here. "Can you see open sky or a lawn through the trees?" will usually be "yes" unless the visibility model (section 2) limits it.
- Terrain varies only from about 48 to 73 m (section 1). Slope or "am I on the hill?" is weak everywhere except around the Plateau/Butte de Gravelle.
- 620 benches, 55 drinking fountains, 10 guideposts, 186 fence/wall ways, 184 sports features and 24 playgrounds give point and area features for "can you see a bench / fence / sports field / playground?"
- Formula used for the noisy columns: IG = H(q) − H(ε), with q = p(1−ε) + (1−p)ε, for a symmetric answer error ε. These are **upper bounds on the first question under a uniform prior**. Once landmark bearings have narrowed the posterior, the selector in CLAUDE.md §6.5 should compute the gain on the current posterior.

### Inferences
- "Are you on a path?" should be used as a **prior and constraint** (see section 6), not as a question. Asking "what is under your feet: tarmac, gravel, packed earth or sand?" is a 4-way question and can carry more than 1 bit. The OSM surface tag is missing on 1,251 of 2,879 highway ways. Fill the missing values by class: service/tertiary → asphalt, track/bridleway → compacted/sand, path → dirt. Use a wider σ for these imputed values.
- **Junction structure** (dead end / straight / T / crossroads / roundabout, the latter typical of the star-shaped "carrefours" in the bois) can be computed from OSM node degree. It is probably more discriminative than any single surface cue, but it was not measured here.
- **Linear features with a direction** carry more information than presence alone: "the road runs from my 3 o'clock to my 9 o'clock". Bearing of the nearest way segment relative to the sun-derived heading constrains both position and heading. This is the "handrail" idea from section 5.
- Yellow PR blazes on trees (the PR1–PR6 relations above) give "Do you see yellow paint marks on trees?" as a cheap path-identity cue. Speakers may not notice blazes, though.
- Tall, named, far-visible features for clock bearings: the Château keep (about 50 m tall, a widely published figure not verified here), the Pagode/Buddhist temple, the zoo's Grand Rocher, the racecourse stands, the INSEP buildings and the A4. Their visibility from inside the wood should come from the section 2 ray model.

### Gaps
- No empirical study was found on how reliably laypeople or soldiers report surface, path width, tree type or distance to edge (the ε values above are assumptions). The 10% and 20% error columns are illustrative.
- Information gain of junction type, path width and "hear traffic" with a real acoustic model was not computed.

## 4. Search-and-rescue and spatial-language evidence: lost-person behaviour, interviewing callers, localising from verbal descriptions

### Takeaway
SAR doctrine (Koester/ISRID) holds that lost and injured people end up close to linear features such as trails, streams and roads, and is built on more than 50k incidents. Text-based localisation research (cross-view geo-localisation from descriptions, OSM scene-graph matching, Text2Loc) shows the problem is studied but uses learned retrieval, not interactive question-asking. Pothenot's information-gain dialogue is a distinct angle. I did not retrieve verified ISRID distance percentiles or dispatcher interview protocols.

### Cited Findings
- Koester compiled more than 50,000 lost-person cases into ISRID. A 2025 ICAR presentation reports ISRID 3.0 totals 532,816 incidents. The data give per-category distance quartiles from the Initial Planning Point and typical elevation change — [ICAR 2025 Koester Lost Person Behavior slides (PDF)](https://www.alpine-rescue.org/system/production/article/documents/file/005/312/a4507c99bbf7f6ade0b44cd1068b2354b42ae1dd3748ad1612445944f372f92c/20251009-1130-ICAR_2025_LPB_Koester.pdf) (figures from a search snippet; the PDF exceeded the fetch size limit); [Koester ISRID Iceland seminar, Linköping Univ. (PDF)](https://liu.se/dfsmedia/dd35e243dfb7406993c1815aaf88a675/67768-source/options/download/carer-semnarium-robert-koester-isridiceland-2023-01-19)
- Koester, as quoted in the press: most people lost in the wilderness, especially if injured, are found close to a "linear feature" such as a stream, trail or road — [Popular Science: The burgeoning science of search and rescue](https://www.popsci.com/environment/the-burgeoning-science-of-search-and-rescue/); [Undark 2024](https://undark.org/2024/01/22/science-search-rescue/)
- The ICAR 2025 deck reportedly lists "Lost" scenario values of 68% (hiker) and 49% (climber), rated "Highly likely". The column meaning could not be confirmed, so treat this as unverified — [ICAR 2025 slides](https://www.alpine-rescue.org/system/production/article/documents/file/005/312/a4507c99bbf7f6ade0b44cd1068b2354b42ae1dd3748ad1612445944f372f92c/20251009-1130-ICAR_2025_LPB_Koester.pdf)
- **"Where am I? Cross-View Geo-localization with Natural Language Descriptions"** (arXiv 2412.17007) frames the task for cases where GPS is interfered with: users describe their surroundings in natural language, and the system retrieves the matching OSM or satellite tile — [arXiv 2412.17007](https://arxiv.org/html/2412.17007v2)
- **GOTLoc** (arXiv 2501.08575) does outdoor localisation without GPS by matching text-derived scene graphs to OpenStreetMap, with no map preprocessing — [GOTLoc](https://ar5iv.labs.arxiv.org/html/2501.08575)
- **Text2Loc** (arXiv 2311.15977) localises a textual position description within a city-scale point cloud — [Text2Loc](https://ar5iv.labs.arxiv.org/html/2311.15977)
- Pate & Walter (2023) locate a user indoors from natural-language queries plus images. Their fine-tuned CLIP outperformed humans — [roman2023-location (PDF)](https://www.ccs.neu.edu/home/lsw/papers/roman2023-location.pdf)
- Walter, Hemachandra, Tellex et al. (IJRR 2014) learn semantic maps from natural-language descriptions, the robotics precursor in Tellex-style spatial language grounding — [IJRR 2014 (PDF)](https://people.csail.mit.edu/sachih/home/wp-content/uploads/2014/ijrr_2014.pdf); [TTIC walter14 (PDF)](https://ttic.edu/ripl/publications/walter14.pdf)

### Inferences
- None of the text-localisation papers found select questions by expected information gain. They retrieve once from a description. That supports Pothenot's originality claim ("asks the right question"), but the search here was not exhaustive (active and interactive geo-localisation from dialogue was not specifically searched).
- The "found near linear features" finding supports a path-proximity prior (section 6) and questions built on linear features (road, stream, lake shore, fence).

### Gaps
- Exact ISRID distance percentiles (for example hiker, temperate, flat) and "found on trail / road / drainage" percentages were **not retrieved**. They need the *Lost Person Behavior* book (Koester 2008) or the dbS Productions ISRID tables.
- No source was retrieved on how SAR dispatchers or French PGHM/CRS mountain units interview lost callers (for example structured "where am I" checklists, or AML/eCall handset location). I found no reliable source within budget.
- Kordjamshidi (spatial role labelling) and LLM geolocation-from-text papers were not retrieved.

## 5. Military land navigation in woods: terrain association, handrails, catching features → likelihood constraints

### Takeaway
Doctrinal land navigation (US FM 3-25.26, reportedly superseded by ATP 3-25.26 in 2019) uses terrain association. Handrails, catching features and attack points translate directly into likelihood terms on a grid: "on a north–south track next to a stream" means near a way whose bearing is about 0° or 180°, and near a waterway. I did not fetch the doctrine text itself this session.

### Cited Findings
- A US ROTC supplemental training document lists "Terrain Association" as a land navigation section (D-26) — [ATU ROTC LDAC supplemental training (PDF)](https://atu.edu/rotc/docs/19_LDAC10_Supplemental_Training_2_Jun.pdf)
- The search assistant stated (as background knowledge, not from a fetched source) that FM 3-25.26 *Map Reading and Land Navigation* was superseded by ATP 3-25.26 in 2019, and pointed to armypubs.army.mil as the authoritative copy. Not verified.

### Inferences (doctrine definitions from general knowledge; not verified against the manual this session)
- **Handrail** (a linear feature you travel along, such as a track, stream or fence): "I'm on a track running N–S" gives a distance term to the nearest highway=track segment, multiplied by a heading term. The segment bearing must match the stated direction (or its reverse) with σ about 20°, relative to the heading. If the heading is known from the sun, this is a strong absolute constraint. If not, it couples position and heading in the 72-heading grid, which handles it natively.
- **"Next to a stream / lake"**: distance to natural=water or waterway below about 30 m.
- **Catching feature** (a linear feature that stops you, such as a road, fence or lake shore across your path): "If I walk towards the sun I hit a road within 100 m" becomes a half-plane-limited distance term. It is useful as a follow-up instruction ("walk 50 m toward your 12 o'clock and tell me what you reach"). That is an active move, but costly for a casualty and buddy.
- **Attack point** (a distinctive feature near the target): in Pothenot terms, a named landmark close to the casualty. "50 m from the lake island bridge" becomes a log-normal distance term (already in CLAUDE.md §6.3).
- **Terrain association in general**: every reported feature is a likelihood factor, which is exactly the existing product-of-likelihoods design. The doctrine supports the approach rather than requiring new machinery.

### Gaps
- The text of FM 3-25.26 / ATP 3-25.26 was not retrieved. Definitions above are from general knowledge and should be checked before quoting them in the pitch.
- French doctrine (for example the "orientation" and "topographie" manuals of the Armée de Terre) was not searched.

## 6. Priors: where people (and casualties) are likely to be in a park forest

### Takeaway
No source was found for the fraction of time park-forest visitors spend on paths. Given SAR evidence that subjects concentrate near linear features, and that 77% of the Bois de Vincennes is within 25 m of a mapped way anyway, a mild path-proximity prior is defensible: a weight that decays with distance to the nearest way. In a military casualty scenario, being on a path may be *less* likely (tree-line cover), so the prior should be configurable or turned off.

### Cited Findings
- Lost or injured people are typically found close to linear features (trail, stream, road) — [Popular Science](https://www.popsci.com/environment/the-burgeoning-science-of-search-and-rescue/)
- [measured] Distance from park cells to the nearest OSM `highway` way: median 11 m. 53% within 12.5 m, 77% within 25 m, 94% within 50 m, 99% within 100 m. To the nearest path/track/footway/bridleway: median 16 m, 66% within 25 m. To an asphalt road: median 51 m.
- [measured] Bench (620) and drinking-water (55) nodes mark where civilians linger. Playgrounds (24) and sports grounds (184) are other attractors.

### Inferences
- Suggested prior: `prior(p) ∝ 0.3 + 0.7·exp(−d_way(p)/25 m)` for a civilian scenario, and a flat prior for a tactical one. Taking the log, the prior adds at most about 1.7 bits of concentration, so it nudges and does not dominate. The constants are assumptions.
- Because the path network is so dense, a path prior at 25 m cells changes little. Its main value is to break ties between blobs that fall in forest interior and blobs on a path.

### Gaps
- No visitor-tracking or GPS-trace study of the Bois de Vincennes (or of European urban forests) giving the share of time on and off paths was found. Strava-style heatmaps would be a proxy, but their licensing for this use was not checked.

## 7. Ranked list: forest features and question types to add to the grid in under a day (with expected information gain)

### Takeaway
Ranked by expected gain per question for the effort, from the measured Vincennes statistics above. The first four can be built in a few hours each from the OSM pull and one MNH WMS call.

### Cited Findings
Information-gain figures come from the [measured] table in section 3. First-question, uniform-prior, 10% answer-error gains are given in brackets. Data sources: OSM via Overpass (ODbL) and [IGN LiDAR HD MNH (Licence Ouverte 2.0)](https://www.data.gouv.fr/datasets/mnh-lidar-hd).

1. **Canopy-aware visibility for existing landmark questions** (MNH ray model, section 2). It doesn't add a question. It fixes the "can you see the church/keep?" likelihoods that drive every existing question inside the wood. Without it, "no, I can't see the keep" is wrongly read as "far from the keep". Highest value. About 2–3 h of work.
2. **"What's under your feet: tarmac, gravel/packed earth, or sand/dirt, or no path?"** (4-way). Built from OSM highway + surface, with class-based fill-in. Gain is above any single yes/no on surface (about 0.3–0.4 bits each). Expected about 0.6–1.0 bit noisy (inference from the per-class fractions 0.17 / 0.24 / 0.47 off-path). About 1–2 h.
3. **"Can you hear or see heavy traffic? Which clock direction?"** Uses distance to primary/secondary/tertiary/motorway. Presence alone is worth 0.43 bits (p = 0.27 within 100 m). Adding a clock bearing makes it a full bearing observation to a line feature, worth much more. About 2 h (sample road lines as points, as CLAUDE.md §6.1 already does).
4. **"Are you under trees or in the open?"** (OSM forest polygon or MNH > 5 m at the cell): 0.52 bits. **"Can you see a lake or pond? Which direction?"** (natural=water incl. relations): about 0.46 bits for presence, more with a bearing. About 1 h together.
5. **Path direction as a handrail**: "Does the path you're on run toward the sun or across it?" or "Is the road at your 3 and 9 o'clock?" This constrains heading plus position. The gain is posterior-dependent and likely high once the heading is known from the sun. About 2 h (segment bearings per cell).
6. **Junction type**: "Are you at a crossing of paths? How many directions?" From OSM node degree. Not measured; likely 0.3–0.6 bits. About 2 h.
7. **"Are there pine trees around you?"** (OSM forest leaf_type + needleleaved tree nodes; Pinus 982 nodes): about 0.28 bits overall, but high locally where conifer stands cluster. About 1 h.
8. **Point attractors and fences**: "Can you see a fence / sports field / playground / bench?" (186 fence ways, 184 sports, 24 playgrounds, 620 benches). Fences and sports fields are probably 0.2–0.4 bits each. Benches are too common inside the wood to discriminate much (not measured). About 1 h.
9. **Path-proximity prior** (section 6). It is not a question, and it is a small effect given the dense network. About 30 min.
10. **Slope or "are you on a hill?"** (LiDAR MNT): low value in Vincennes (about 25 m relief) except near Gravelle. Last.

### Inferences
- Items 2, 4, 7 and 8 are yes/no or multiple-choice questions that the current expected-entropy selector can score without changes, as long as each feature has a predicted answer per cell. They plug into §6.5 as new candidate generators.
- Bearing-carrying versions of items 3 and 4 ("which clock direction?") should outrank presence-only versions whenever the selector computes posterior gain, because they also constrain heading.
- Practical build order for the hackathon:
  1. Fetch `data/forest_layers.json` from Overpass (6 MB, under 1 min) and `data/mnh.tif` from the WMS (2.6 MB, seconds).
  2. Rasterise to the existing 25 m grid: `d_way`, `surface_class`, `d_mainroad`, `in_forest`, `d_water`, `conifer`, `canopy_h`.
  3. Precompute `P_vis` to the tall landmarks.
  4. Add candidate questions 2–4.

### Gaps
- All information-gain values are first-question figures under a uniform prior with assumed symmetric error. Real gains depend on the posterior after landmark observations and on answer reliability, which no source here quantified.
- Items 2, 6 and 8 have estimated (not measured) gains.
