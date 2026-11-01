# GDP vs Night Lights in Sub-Saharan Africa

BSc dissertation project (SP32038, University of Bath). Student: Ziyan Rafiq.
Supervisor: Ricky Kanabar. Deadline 22 April 2027.

**Research question.** What explains divergence between officially reported GDP
growth and satellite-observed night-time economic activity in Ghana and Kenya?
Evidence from a Sub-Saharan African panel.

**Design.** A balanced panel of **38** Sub-Saharan African countries,
**2016–2021 strictly** (228 country-years). The outcome is the *gap* between log
GDP growth and log night-lights growth, estimated with country and year fixed
effects and standard errors clustered by country. It tests whether the gap is
larger where statistical capacity (World Bank SPI, rebuilt to remove indicators
that describe the GDP series itself) and political accountability (V-Dem) are
lower. Ghana and Kenya are case studies: they contrast on capacity and
accountability, and each has a distinct measurement problem (Kenya the fastest
electrification in the region, Ghana offshore oil and a 2019 rebasing).

Full background, decisions and supervisor feedback:
[`docs/Dissertation_Project_Brief.pdf`](docs/Dissertation_Project_Brief.pdf).

## Status

All six data sources are loaded and verified. Nothing has been estimated yet.

The environment is built and tested: Python 3.12.10 in `.venv`, with GDAL 3.12.2
and PROJ 9.8.1 loading, zonal statistics verified against a hand-computed sum,
and `PanelOLS` verified to recover a known slope exactly.

| Step | Module | Status |
| --- | --- | --- |
| 1 | `src/load_wdi.py` | done, run on the real data |
| 2 | `src/load_vdem.py` | done, run on the real data |
| 3a | `src/load_spi.py` | done, run on the real data |
| 3b | `src/rebuild_spi.py` | done, run on the real data |
| 4 | `src/load_oxcgrt.py` | done, run on the real data |
| 5 | `src/process_lights.py` | done, all 7 years processed |
| 5a | `src/verify_sources.py` | done, all checks pass |
| 6 | `src/build_panel.py` | done, 38 countries / 228 rows |
| 6a | `src/verify_panel.py` | done, all checks pass |
| 7 | `src/models.py` | done, estimated; headline results null |
| 8 | `src/dashboard.py` | done, `outputs/dashboard.html` |

Each of the seven interim tables re-runs **byte-identically** from the raw
files, so the pipeline is reproducible and not merely runnable.

## Layout

```
data/raw/         original downloads (gitignored, never edited by code)
data/interim/     one tidy file per source (gitignored, rebuildable)
data/processed/   the merged estimation panel (committed: small and useful)
src/              one module per pipeline step, plus config.py
notebooks/        exploration
outputs/tables/   regression tables, the dropped-countries table
outputs/figures/  case-study figures
docs/             the project brief
```

`src/config.py` holds everything more than one script must agree on: folder
paths, the 48-country candidate list, the year ranges, variable codes, and the
sample switches. It reads no data, so importing it is always safe. Run it on
its own to print the settings and check they are consistent:

```bash
python -m src.config
```

### The sample: 38 countries, 228 rows

Because the panel is balanced, it must hold the **same countries in every
specification** — otherwise coefficients from one model cannot be compared with
another. So a country missing any model variable leaves the sample outright
rather than appearing in some regressions and not others. Exclusions are listed
in `config.py` in three groups:

| Group | Countries | Running total |
| --- | --- | --- |
| All Sub-Saharan Africa | 48 | 48 countries, 288 rows |
| `EXCLUDED_MISSING_DATA` — missing WDI or SPI data | 8: CAF, COD, COM, ERI, GNQ, SOM, SSD, SYC | 40 countries, 240 rows |
| `EXCLUDED_NO_COVID_DATA` — no OxCGRT stringency | 2: GNB, STP | **38 countries, 228 rows** |
| `EXCLUDED_LIGHTS` — lost in the lights step | none yet | to be determined |

COVID stringency is a main-model regressor, which is why GNB and STP are out.
Note that 240 is **not** 252 − 48: the unbalanced panel's 252 rows already
exclude 36 of those 48.

**The sample will probably shrink again** when the night-lights rasters are
processed: a country with missing or near-zero radiance has no log change and
would break the balance. When that happens, add each country to
`config.EXCLUDED_LIGHTS` with its reason. That is the **single edit point** —
every expected count in the project is derived from the exclusion lists, so the
panel check and the dropped-countries table follow automatically. (Verified: a
simulated two-country lights exclusion correctly produced 36 countries / 216
rows throughout.)

### The timeline

| Window | Years | Use |
| --- | --- | --- |
| Levels loaded | 2015–2021 | 2015 exists **only** to form the 2016 growth rate |
| Estimation sample | 2016–2021 | the main results, 6 years per country |
| Pre-COVID | 2016–2019 | robustness; a subset, so no extra data needed |
| Extended | 2016–2023 | robustness; needs VIIRS v2.2, reported separately |

**2015 is not part of the sample.** A 2016 growth rate is
`ln(GDP 2016) − ln(GDP 2015)`, so the 2015 *level* has to be loaded — but there
is no 2015 growth rate (that would need 2014), so no 2015 row appears in any
regression. The levels range is one year longer than the sample range purely as
arithmetic.

The **extended 2016–2023 check will be run**, but it is reported separately and
never merged into the main results, because VIIRS v2.2 composites the imagery
differently from v2.1: the 2021→2022 growth rate straddles the version change,
so part of any change there is method rather than growth. Two further gaps to
state when reporting it: oil rents end in 2021, and OxCGRT stops on 2023-02-28,
so 2023 has no comparable annual stringency figure (it is left missing rather
than averaged from two months).

### The switches

- `STRICT_TIMELINE` — `True`. The main period cannot be widened by accident.
  This does not forbid the extended check; it forces it to be asked for, by
  passing `extended=True` to `config.check_years()`. Enforced, not just
  documented: every loader calls `check_years()` on what it has read, and the
  config self-check tests eight cases of what it should accept and reject.
- `USE_COVID_IN_MAIN` — `True` (default). Whether stringency is a regressor.
  This **no longer changes the sample**: setting it to `False` drops the
  stringency term but keeps the same 38 countries. Recovering the 40-country
  panel would mean dropping stringency from the project entirely, which is a
  design change rather than a flag.
- `USE_UNBALANCED_PANEL` — `False` (default) drops any country with any
  missing value. `True` drops individual country-years only, for the
  unbalanced robustness check.

## Reproducing

```bash
# 1. environment (Python 3.12 — see the note in requirements.txt)
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt     # or requirements-lock.txt for exact versions

# 2. check the settings
python -m src.config

# 3. put the raw downloads in data/raw/ (see Data sources below)

# 4. run the pipeline in order, from the project root
python -m src.load_wdi
python -m src.load_vdem
python -m src.load_spi
python -m src.rebuild_spi
python -m src.load_oxcgrt
python -m src.process_lights

# 5. gate: check the six sources fit together before merging them
python -m src.verify_sources

python -m src.build_panel

# 6. gate: audit the built panel value by value against its sources
python -m src.verify_panel

python -m src.models          # main, estimators, check model, robustness

# 7. the interactive dashboard (writes one self-contained HTML file)
python -m src.dashboard --open
```

`verify_sources` exits non-zero if anything would make the merge silently
wrong, so it can be run as a gate. It is the step that caught the SPI 2015
trap described below. `verify_panel` is the matching gate on the other side of
the merge: it re-derives every value in the built panel from the interim files
by key lookup, which is the only way to catch a merge that lines up the right
number of rows against the wrong keys.

Run every command from the project root, using `python -m src.<module>` rather
than `python src/<module>.py`. The `-m` form runs `src` as a package, which is
what makes `from src import config` work.

Each step reads from `data/raw/` or `data/interim/` and writes to
`data/interim/` or `data/processed/`. Nothing writes back to `data/raw/`, so
the originals stay untouched and any step can be re-run from scratch.

## Data sources

Sizes and "last updated" dates are what the brief records. Download dates
marked *to confirm* were not noted at the time and should be filled in when
each file is next fetched.

The dashboard renders this list too, with the "on disk" status read from the
filesystem at build time rather than from this table, so the two cannot
silently disagree.

| Variable | Source | Code / file | Vintage | Download date |
| --- | --- | --- | --- | --- |
| GDP, constant LCU | World Bank WDI | `NY.GDP.MKTP.KN` | last updated 2026-10-08 | Oct 2026 *(to confirm)* |
| GDP growth, annual % | World Bank WDI | `NY.GDP.MKTP.KD.ZG` | last updated 2026-10-08 | Oct 2026 *(to confirm)* |
| Agriculture, % of GDP | World Bank WDI | `NV.AGR.TOTL.ZS` | last updated 2026-10-08 | Oct 2026 *(to confirm)* |
| Electricity access, % | World Bank WDI | `EG.ELC.ACCS.ZS` | last updated 2026-10-08 | Oct 2026 *(to confirm)* |
| Urban population, % | World Bank WDI | `SP.URB.TOTL.IN.ZS` | last updated 2026-10-08 | Oct 2026 *(to confirm)* |
| Population | World Bank WDI | `SP.POP.TOTL` | last updated 2026-10-08 | Oct 2026 *(to confirm)* |
| Oil rents, % of GDP | World Bank WDI | `NY.GDP.PETR.RT.ZS` | last updated 2026-10-08; series ends 2021 | Oct 2026 *(to confirm)* |
| Accountability | [V-Dem v16](https://v-dem.net/data/the-v-dem-dataset/) | `V-Dem-CY-Full+Others-v16.csv` (~400 MB) | published March 2026, covers 1789–2025 | Oct 2026 *(to confirm)* |
| Statistical capacity, indicator level | [worldbank/SPI](https://github.com/worldbank/SPI) | `SPI_data.csv` | 2004–2024 | Oct 2026 *(to confirm)* |
| Statistical capacity, published scores | [worldbank/SPI](https://github.com/worldbank/SPI), `03_output_data/` | `SPI_index.csv` | 2016–2024 | downloaded, 1.8 MB |
| SPI scoring rules | [worldbank/SPI](https://github.com/worldbank/SPI) | `SPI_full_metadata.csv` | — | **not yet downloaded** |
| SPI weighting logic | [worldbank/SPI](https://github.com/worldbank/SPI), `02_programs/` | `02-SPI_index.Rmd` (reference; weights at lines 1283–1285) | — | downloaded |
| COVID stringency | [OxCGRT](https://github.com/OxCGRT/covid-policy-tracker), `data/` | `OxCGRT_nat_latest.csv` | daily 2020-01-01 to 2023-02-28; 2020–2022 are full years, 2023 is 2 months so no annual mean is computed | downloaded, 48.6 MB |
| Night lights, main | [EOG VIIRS annual VNL](https://eogdata.mines.edu/products/vnl/) (also on Google Earth Engine as `NOAA/VIIRS/DNB/ANNUAL_V21`) | v2.1 annual composites 2015–2021, `average_masked` band | v2.1 covers 2012–2021 | downloaded, 7 rasters, ~2.1 GB gzipped |
| Night lights, extended check | same, `ANNUAL_V22` | v2.2 composites 2022–2023 | different compositing method from v2.1 | **not yet downloaded** |
| Country boundaries | [Natural Earth](https://www.naturalearthdata.com/) 1:10m Admin 0 | `ne_10m_admin_0_countries.shp`, ISO3 from `ISO_A3` | version 5.1.1, public domain | downloaded 2026-10-28, 8.8 MB |

`data/raw/ssa_balanced_panel_2016_2021.csv` is an earlier draft panel kept for
cross-checking only. It is never an input to the pipeline.

## Key design decisions

| Decision | Reason |
| --- | --- |
| SSA panel, Ghana and Kenya as cases | 2 countries × 6 years = 12 observations is far too few; supervisor agreed |
| Balanced panel, 38 countries, 228 rows | Supervisor's recommendation; a balanced panel must hold the same countries in every specification, so the two countries without stringency data leave the sample outright; unbalanced panel as a robustness check |
| Main period 2016–2021 | SPI's overall score starts in 2016; VIIRS v2.1 ends in 2021; oil rents end in 2021 |
| Levels from 2015 | A 2016 growth rate needs a 2015 level. 2015 is never an observation |
| 2016–2023 as a separate robustness check | Worth running, but VIIRS v2.2 composites differently from v2.1, so the 2021→2022 growth rate mixes method change with real growth — it cannot be merged into the main results |
| Outcome is the gap, signed and absolute | Answers the research question directly; both terms are log changes so they can be subtracted; separates overstatement from noise |
| Fixed effects as the main estimator | Short panel; pooled OLS, random effects with a Hausman test, and first differences as comparisons |
| SPI rebuilt without SNAU and NABY | Those two indicators describe the GDP series itself, so SPI falls as a base year ages and jumps back at rebasing — circular with the outcome |
| Standard errors clustered by country | A country's errors are correlated across years |
| VIIRS v2.1 for the main analysis, v2.2 only in the extended check | v2.2 changes the compositing method, so a 2021→2022 jump could be an artefact. v2 is never used: v2.1 fixed an averaging bug and removed a detection filter, so the two are not comparable |
| COVID stringency in the main model | Year fixed effects absorb only the common part of the 2020–21 shock; lockdowns differed by country. Cost: two countries |
| Python 3.12 | geopandas, rasterio and exactextract are compiled packages whose wheels lag new Python releases; 3.13 and 3.14 are installed on this machine but 3.12 is the safe choice for this stack |
| Python | Existing skills; could be replicated in R later |

## Verification practice

"It runs" is not "it is correct". Every step prints row and country counts,
missing-value counts, and a spot-check of Ghana and Kenya against the figures
in the brief, before anything downstream uses its output. `src/config.py`
carries the expected sample as `EXPECTED_BALANCED_COUNTRIES` and
`EXPECTED_DROPPED_REASONS`, so `build_panel.py` can compare what it actually
built against what the design says and fail loudly on a difference rather than
quietly estimating on a different sample.

`python -m src.config` checks the settings are internally consistent (the
exclusion groups do not overlap, the arithmetic reaches 48, the case studies
survive, `check_years` really rejects out-of-range years) before any data is
touched.

`python -m src.verify_sources` then checks that the six sources fit *together*,
which no individual loader can see: clean merge keys, no duplicate
`(iso3c, year)`, year stored as an integer rather than text, identical country
coverage, no missing values anywhere in the 38-country sample, and a dry-run
merge that lands on 38 × 6 = 228 rows. All checks currently pass.

### Reconciled against the brief

Four figures in the brief did not match what the data gives. All four are now
explained, and in each case the explanation was found rather than assumed.

| Brief says | This repo gets | Why |
| --- | --- | --- |
| 23 base-year changes 2016–21 among the 40; 28 events / 24 countries 2016–22; 24 countries across all 48 | 27 / 32 / 28 countries | The brief counted **before** doing its own listed fixes. Treating the text base years as unreadable and dropping the Kenya release-date override reproduces **all three figures exactly**. The four extra events are ETH 2018, SDN 2018, UGA 2020 and KEN 2021 — precisely the fixes the brief asked for. |
| SPI within-country SD 5.5, between 10.9; Pillar 4 4.2 / 14.2; overall–P4 correlation 0.78 | 4.80 / 8.93, 3.75 / 11.60, 0.74 | The brief's figures are on **all 48 SSA countries over 2016–2023**, where this repo reproduces them as 5.54 / 10.85, 4.21 / 14.15 and 0.778. The estimation sample is 38 countries over 2016–2021, so its own figures are the ones to quote. |
| Kenya Pillar 5 rises 45 → 70 | 45 → 65 | The 70 is Kenya's **2022** value, confirmed from the index file (2021 = 65.0, 2022 = 70.0, 2023 = 70.0). Kenya's base year only appears in SPI from 2022, which is what the brief's own NABY path says. |
| Ghana SPI overall 2021 = 66.2 | 66.15 | Rounding: 66.1479 to one decimal is 66.1. Ghana's 2023 value is 66.245, which does round to 66.2. |

One figure is **not** fully reconciled: the brief's V-Dem accountability
within/between SDs of 0.141 / 0.667. The closest reading includes Somaliland
and Zanzibar as separate units (0.136 / 0.670), which `load_vdem.py`
deliberately drops because they are not states in the WDI or SPI panels.
Across every plausible country set and window the within SD lands between
0.128 and 0.163, so the substantive point — between-country variation is
roughly 4–5× within — holds under all of them.

### The SPI 2015 trap

The published SPI **overall** index starts in 2016, but Pillars 1, 3 and 4
carry 2015 values. So `spi_published.csv` has a 2015 row that is *partly*
filled. Merging SPI onto the 2015–2021 levels grid would hand the panel pillar
values with no published overall index behind them, and nothing would complain.

SPI is therefore merged on **2016–2021 only**, which is all the model needs:
SPI enters as a level on the growth years and is never lagged or differenced.
`verify_sources.py` asserts the 2015 overall column is still empty, so that if
a future SPI vintage fills it in, the merge window gets reconsidered rather
than a stale comment left behind.

### The night-lights totals, cross-checked against a second method

Every other variable is a published number that this repo only reads and
reshapes. The lights totals are the one variable *computed* here, so a
zonal-statistics error would not announce itself — the numbers would still be
plausible, still the right shape, and still produce a regression.

Checked on ten countries (both case studies, the largest and smallest by area,
two islands) for 2015 and 2021, against `rasterstats` with whole-cell
assignment instead of `exactextract`'s area weighting:

- radiance totals agree to a **median 0.030%**, worst case 0.46%
- the log growth rates agree to at most **0.0016 log points**, 0.25% of the
  growth itself
- the disagreement is unsystematic (mean −0.031%) and is largest exactly where
  theory says it should be: Cape Verde 0.46% and Mauritius 0.19%, islands
  where border cells are a large share of the total, against under 0.08% for
  DR Congo, Nigeria, South Africa and Chad

Border-cell differences are nearly constant over time, so they difference out
of the growth rate, which is what the model uses.

### Night-lights decisions, fixed before any results were seen

- **Negative radiance is clamped to zero** (`config.LIGHTS_CLAMP_NEGATIVES`),
  decided 2026-10-28 before any country total was computed. Negative radiance
  is residual noise from VIIRS's background subtraction and is not physically
  meaningful. Measured on the 2015 crop: 8,523 negative cells out of 389
  million (0.0022%), minimum −1.5 nW/cm²/sr, so the effect either way is
  negligible against country totals in the millions. The counter-argument —
  that keeping them is more faithful, and clamping adds a small upward bias if
  the noise is symmetric — is recorded in `config.py`. `process_lights.py`
  reports the exact magnitude removed per year so the claim can be checked.
- **Sum, not mean, radiance within borders.** A sum scales with country area,
  which country fixed effects absorb in levels; in log changes it is the
  growth of total luminosity.

- **Near-zero rule set at 1.0 nW/cm²/sr** (`config.LIGHTS_NEAR_ZERO_THRESHOLD`).
  It **binds on nothing**: of 336 country-years, none is below 100, the
  smallest anywhere is Comoros at 214, and the dimmest country in the
  estimation sample (Burundi) sits ~1,800× above the threshold. It exists for
  reproducibility and to protect the extended-period and unbalanced runs.
- **The lights step cost no countries.** The sample stays at 38 / 228.

### Night-lights results and three things to watch

The series is in `data/interim/lights_country_year.csv`; see
`outputs/figures/lights_series.png`.

#### 1. The 2017 jump is a detection change, confirmed

Median growth across the 38 is **+17.8% in 2017**, against +1.0%, +7.2%,
+2.4%, +5.2% and +10.4% in the other years. Thirty-eight separate economies do
not accelerate together like that.

`python -m src.process_lights --stage diagnose` tests it directly, by building
a **stable mask** of cells at or above 5 nW/cm²/sr in *every* year and
comparing the total over that fixed set of cells with the total over
everything. Holding the cells fixed removes any change in *which* cells are
counted, leaving only changes in how bright the same cells are.

| 2016→2017 | Δln |
| --- | --- |
| All cells | **+0.060** |
| Fixed set of reliably-lit cells | **+0.005** |
| Number of lit cells | +0.050 |

The same physically bright cells did **not** brighten in 2017. The extra light
arrives in cells that previously read zero. The brightness bands confirm it,
with a clean monotonic gradient — cell counts, 2017 ÷ 2016:

| 0.25–0.5 | 0.5–1 | 1–2 | 2–5 | 5–10 | 10–50 | >50 |
| --- | --- | --- | --- | --- | --- | --- |
| ×1.31 | ×1.47 | ×1.32 | ×1.20 | ×1.11 | ×1.06 | ×1.04 |

The dimmer the band, the larger the jump. That is the signature of a detection
threshold moving, not of economic growth.

**Why this is worse than it first looks.** Year fixed effects absorb a shift
that is *common to all countries*, but this one is not: it lands on marginal,
near-threshold cells, so countries with proportionally more of them gain most.
That is why the median country sees +17.8% while the SSA aggregate sees only
+6.0% — the aggregate is dominated by bright cells that barely moved. The
artefact is therefore **correlated with how dim a country is**, which year
effects cannot remove.

**The robustness measure this produced.** `lights_sum_bright` is the sum of
radiance over cells at or above **5.0 nW/cm²/sr in that year**
(`config.LIGHTS_BRIGHT_FLOOR`). It is an **extra column, never a
replacement**: `lights_sum` remains the main measure and the main results are
estimated on it. Supporting evidence that the restricted series is also the
more economically meaningful one: the fixed-mask total **falls 4.3% in 2020**,
picking up COVID, while the all-cells total falls only 1.6%.

*Why a per-year floor, not the diagnostic's fixed mask.* The diagnostic uses
cells bright in **every** year, which is immune by construction but picks
cells using information from the whole period — including its end. That is
fine for measuring the instrument, which is all a diagnostic does, but it must
not be used for estimation: conditioning on cells that stayed bright through
2021 discards genuine new development and selects on the outcome. The floor is
applied to each year separately by the same rule, so a newly developed area
enters as soon as it becomes bright.

The floor removes most, not all, of the artefact — the 2016→2017 jump in cell
counts is ×1.47 at 0.5–1 nW but ×1.11 at 5–10 and ×1.04 above 50.

**It worked.** The 2017 excess over the median of the other years falls from
**+0.109 to +0.025**, so roughly three quarters of the artefact is gone. See
`outputs/figures/lights_measure_comparison.png`.

**It is not free, and the costs should be stated with the result:**

- The series is **noisier**: standard deviation 0.178 against 0.122. Fewer
  cells means more sampling noise, and under fixed effects extra measurement
  error means more attenuation towards zero.
- It is **unstable for the dimmest countries**, where little survives the
  floor. Burundi goes from ×3.00 to ×7.52, Liberia ×2.21 to ×3.97 — those are
  small, volatile bases, not findings.
- The two measures correlate 0.848, and **several countries change sign**
  (Eswatini +0.12 → −0.26, Malawi +0.20 → −0.14, Zimbabwe, Sudan). The
  robustness check is therefore a real test, not a formality.

**The case studies behave exactly as the decomposition predicted**, which is
useful independent corroboration:

| | All cells | Bright cells | Reading |
| --- | --- | --- | --- |
| **Ghana** | ×3.21 | **×3.57** | Grows *more* under the floor — already-lit areas intensifying, so not a detection artefact |
| **Kenya** | ×1.90 | **×1.45** | Shrinks under the floor — expansion into newly lit, dim areas, i.e. electrification |

Ghana's tripling survives the measure built specifically to remove the
artefact, which is strong evidence it is real. Kenya's rise is substantially
grid expansion. Those were derived from completely separate evidence (the
cell-level decomposition) and agree.

### What has been done to the data

Only one step changes any value, and it is the clamp:

| Step | Alters values? |
| --- | --- |
| Crop to the SSA box | No — subsetting only |
| **Clamp negatives to zero** | **Yes — 20,680 cells, 0.00065% of radiance** |
| Sum within borders | No — aggregation |
| `ln`, then first difference | No — standard transformation |
| Near-zero threshold (1.0) | No — binds on zero observations |
| Brightness floor (5.0) | Builds a **separate** column, leaves `lights_sum` untouched |

The downloaded `.gz` rasters are never written to; the crop is a faithful copy
and the clamp is a separate file beside it. The previews (max-pooling, fixed
colour scale) and the diagnostics are display-only and read-only respectively.

The brightness floor is a researcher choice, so: it was fixed at 5.0 **before
any model was estimated**, it is the same value the diagnostic used, and it
adds a column rather than altering the main series.

#### 2. Ghana's tripling is mostly real, and not what Kenya's is

Ghana rose **3.21×** over 2015–2021 (Δln = 1.17) while real GDP grew about
1.3×. Three checks:

- **Not a flare.** The brightest cell inside the border stays modest
  (138 → 248). A flare would read in the thousands, as Nigeria's does.
- **Not a dim-baseline artefact.** Growth across the 38 is essentially
  unrelated to starting brightness (r = −0.165, r² = 0.027, and the brightest
  quartile grew as fast as the dimmest). Ghana is in the **brightest**
  quartile and still tripled.
- **Mostly existing areas getting brighter**, which is what separates it from
  its neighbours. Decomposing the rise by comparing the same cells in both
  years:

| Source of the rise | Ghana | Kenya | Côte d'Ivoire |
| --- | --- | --- | --- |
| Cells lit in **both** years, brighter | **66.3%** | 37.8% | 41.6% |
| **Newly lit** cells | 29.5% | 57.8% | 48.3% |

Kenya's rise is grid expansion, as its +23pp of electricity access implies.
Ghana's is predominantly **intensification of places that were already lit**.

**Leading hypothesis, still to verify:** Ghana's *dumsor* power crisis, with
years of load shedding, ran to around 2016. That would make 2015 an
artificially dark baseline, and much of the subsequent rise a recovery rather
than growth. Since 2015 is the base year for the 2016 growth rate, this
matters directly. Check against Ghana Grid Company / Energy Commission load
shedding records before interpreting Ghana's gap.

Note also that the lit-cell count roughly tripled in all three countries
(3.27, 3.26, 3.21) — that part is the detection artefact from finding 1, not
three identical electrification programmes.

#### 3. Nigeria's series is flare-driven

Lights fell 0.90× over the period, and the brightest cell inside the border
dropped from 9,961 (2015) to 3,606 (2016) — the signature of Niger Delta
flaring, coinciding with the 2016 oil-price collapse and attacks on oil
infrastructure. Unlike Ghana's offshore fields, this flaring is *inside* the
land border and cannot be excluded by the boundary.

Two more things are deliberately left unset so that a decision has to be made
rather than defaulted:

- `config.LIGHTS_NEAR_ZERO_THRESHOLD` is `None`. `ln(0)` is undefined, so a
  rule is needed for near-zero radiance totals — and it must be fixed *before*
  any results are seen. `process_lights.py` refuses to run until it is set.
- `config.SPI_BASE_YEAR_TEXT_FIXES` is empty. Some countries store their base
  year as text ("2015/2016", "2010/11", "chained"). `rebuild_spi.py` must print
  every non-numeric value it finds and stop if one is not in the mapping, so
  nothing is silently guessed.

Assumptions still to verify against the actual data are marked
`ASSUMPTION TO VERIFY` in `src/config.py`.

## The estimation panel

`data/processed/ssa_panel.csv` — **38 countries × 6 years = 228 rows**, 43
columns, 2016–2021, balanced. Every dropped country is listed with its reason
and the variables responsible in `outputs/tables/dropped_countries.csv`.

The arithmetic the build asserts against `config.expected_sample()`:

```
48 countries × 6 years                        = 288 possible rows
less 8 missing WDI or SPI data   → 40 countries, 240 rows
less 2 missing COVID stringency  → 38 countries, 228 rows
less 0 lost to night lights      → 38 countries, 228 rows
```

### What the panel looks like before any model is fitted

| | mean | sd | min | median | max |
| --- | --- | --- | --- | --- | --- |
| Δln GDP | 0.027 | 0.043 | −0.233 | 0.037 | 0.113 |
| Δln lights | 0.083 | 0.122 | −0.281 | 0.072 | 0.667 |
| **gap** (Δln GDP − Δln lights) | **−0.057** | 0.121 | −0.615 | −0.048 | 0.264 |
| abs_gap | 0.099 | 0.089 | 0.000 | 0.081 | 0.615 |

**The gap is negative in 157 of 228 country-years (69%)**: lights grew faster
than reported GDP across most of the region, most of the time. That is a
description of the data, not a result — how much of it is under-reported
growth, how much is electrification, and how much is the 2017 detection drift
documented above is exactly what the models are for.

### Within- versus between-country variation

This decides what fixed effects can actually identify, so it is worth reading
before the first regression rather than after a disappointing one:

| Variable | within | between | between / within |
| --- | --- | --- | --- |
| gap | 0.109 | 0.051 | 0.47× |
| Δln GDP | 0.035 | 0.026 | 0.74× |
| Δln lights | 0.108 | 0.057 | 0.53× |
| elec_access_change | 2.815 | 1.293 | 0.46× |
| spi_rebuilt | 4.83 | 8.90 | 1.84× |
| **v2x_accountability** | **0.131** | **0.597** | **4.56×** |

The outcome and the growth variables vary mostly *within* countries, which is
what fixed effects need. **Accountability does not**: it is 4.6 times more
variable across countries than within them, so its coefficient is identified
off very little and will be imprecise. The brief anticipated this; the panel
confirms it, and it belongs in the limitations rather than as a surprise in
the results.

### How the merge is protected

Two failures would survive every row count, so both are checked directly:

- **Wrong keys, right counts.** `verify_panel.py` looks every carried-across
  value up in its source file by `(iso3c, year)` and compares — all 228 rows,
  not a sample. A merge that aligned the right number of rows against the
  wrong keys would pass a count check and fail this one.
- **A lag crossing a country boundary.** Shifting a sorted frame without
  grouping gives each country's first year the *previous country's* last year:
  a plausible wrong number, not a missing one. Every lag is recomputed by
  explicit key lookup, and the gate prints the boundary case — Burundi's 2016
  growth reads **+0.032**, where a frame-wide shift would have given it
  **−2.087** from Angola's 2021.

### One bug this step found, upstream

`rebuild_spi.py` computed the rebuilt SPI score with pandas' default
`skipna=True`, so a country-year missing a pillar still received a score — the
mean of whichever pillars happened to be present. The rebuilt index therefore
existed for **CAF, COD and SYC**, which the SPI team does not score at all,
and for 2015, where no published index exists.

Left alone, the balanced panel would have kept 41 countries instead of 38, with
three of them carried on a capacity measure this project invented. The fix is
`skipna=False` in both row means, plus a check each run that the rebuilt index
is available on exactly the same country-years as the published one. It costs
nothing in reproduction: in this data the published score exists if and only if
all five pillars do, which is now asserted rather than assumed.

## Results

**Nothing here is a finished result.** The models run, the estimator is
verified, and the headline coefficients are null. What follows is what the
data currently says, not a conclusion.

### The two coefficients the design predicts a sign for

Country and year fixed effects, standard errors clustered by country,
228 observations, 38 countries.

| Outcome | Coefficient | Estimate | SE | p |
| --- | --- | --- | --- | --- |
| abs_gap | spi_rebuilt (capacity) | −0.0000109 | 0.0018 | 0.995 |
| gap | v2x_accountability | −0.0048 | 0.0332 | 0.886 |

Both are **indistinguishable from zero**, and both survive every robustness
check as null: published SPI instead of rebuilt, Pillar 4, the no-CPIBY
variant, the rebasing dummy, dropping COVID, pre-COVID years only, excluding
Ghana, excluding Kenya, excluding oil producers, excluding the biggest
accountability movers, and the bright-cells lights measure.

The estimator itself is not in doubt: the fixed-effects coefficients were
reproduced to **3.5 × 10⁻¹⁴** against a hand-coded two-way within
transformation followed by plain OLS, and the clustered standard errors agree
with `statsmodels` up to a small-sample correction that makes
`linearmodels`' the more conservative of the two.

### A null needs a power statement, or it says nothing

"We found nothing" and "we could not have found anything smaller than a very
large effect" look identical in a regression table. The minimum detectable
effect at 80% power and a 5% two-sided test is about 2.8 standard errors,
reported per one **within**-country SD of the regressor as a share of the
outcome's own within-country SD:

| Effect of a 1-within-SD move in… | …on | smallest detectable | observed |
| --- | --- | --- | --- |
| spi_rebuilt (4.83 points) | abs_gap | **0.32 SD** | 0.001 SD |
| v2x_accountability (0.131) | gap | **0.11 SD** | 0.006 SD |

So the accountability null is reasonably informative — it rules out anything
above about a tenth of a within-country standard deviation. The capacity null
is weaker: effects below a third of a standard deviation were never
detectable here. Both should be written up as *bounds*, not as "no
relationship".

### The check model rejects the gap's central assumption

The gap assumes GDP and lights move one-for-one. Estimating that elasticity
instead of assuming it:

> **β̂ = 0.056** (SE 0.025) — against H₀: β = 1,
> **t = −37.3** on 37 df, **p < 0.000001. Rejected.**

Within country and year, a 1% rise in night lights is associated with roughly
a **0.06%** rise in reported GDP, not 1%. That is well below even the ~0.3
that Henderson, Storeygard and Weil report on older DMSP data.

This has a direct consequence for how the whole project is written up: the
gap is a **difference in two growth rates**, not a structural elasticity, and
it should be described that way. Some of the attenuation is real measurement
error in both series, which fixed effects amplify — that is a limitation, not
a correction to apply.

### What the model does explain

Very little. On the main two-way specification, R² on the demeaned data is
**0.042** for the signed gap and **0.079** for the absolute gap. (The
estimator comparison reaches 0.21 only because it drops year effects, so the
year-to-year common movement is left in the outcome for the regressors to
explain.)

COVID stringency is the one consistently significant regressor (p ≈ 0.001 on
both outcomes, opposite signs), and the case-study predictions correlate
**0.597** with the actual gaps. Ghana's largest positive residual is
**2019 — its rebasing year** — and Kenya's is 2020. Suggestive, and only
suggestive: with two countries and six years each it cannot be more than that,
which is the reason the 38-country panel exists.

> **A reporting note.** `linearmodels`' `rsquared_within` is **not** the number
> above and is routinely negative here. With time effects absorbed it is
> computed against entity-demeaned data using parameters never chosen to fit
> it. The figure to quote is `rsquared`, the fit on the two-way demeaned data
> the model is actually estimated on.

### The Hausman test does not decide anything here

V_FE − V_RE is **not positive definite** (smallest eigenvalue −6.2 × 10⁻⁷), so
the statistic is not interpretable in the usual way and is reported rather
than relied on. Fixed effects remain the main estimator on the design
argument — unobserved country characteristics are certain to be correlated
with statistical capacity — not on a test that did not run cleanly.

## The dashboard

`python -m src.dashboard` writes **`outputs/dashboard.html`** — one
self-contained file, about 135 KB, that opens straight from disk with no
server and no internet connection.

Countries are ranked by **divergence**, which can be read four ways, so the
ranking is sortable rather than fixed:

| Sort | Question it answers |
| --- | --- |
| Mean gap (signed) | Did lights consistently outgrow reported GDP? |
| Mean \|gap\| | How big is the disagreement, ignoring direction? |
| Volatility | Is a small average gap hiding large swings both ways? |
| Worst year | Where would a case study start? |

Selecting a country loads its growth trace (Δln GDP against both lights
measures, with the gap drawn as the vertical distance it literally is), its
gap against the model's prediction with rebasing years flagged, its position
in the panel-wide distribution, and a cross-section scatter against capacity,
accountability, electrification or agriculture share.

**Python does every calculation; the page only draws.** Nothing is computed in
JavaScript that could disagree with the pipeline, every figure is read from
the committed tables rather than hard-coded, and `dashboard.py` re-checks in
the payload itself that `gap = Δln GDP − Δln lights` and
`gap = prediction + residual` for all 228 observations before writing the file.
Re-run `models.py` and the dashboard changes with it.

The charts are hand-written SVG rather than a plotting library: it keeps the
project to its existing dependencies and gives exact control over the layout.

It opens with **Why this question** — the case for the project, built on live
figures rather than prose alone. The one that makes it: the median yearly
disagreement between reported GDP growth and lights growth is **0.081 log
points against median GDP growth of 0.037**, so *the typical gap is more than
twice the size of the thing being measured*. An expandable panel sets out what
the data says so far, what the project explicitly is **not** claiming, and why
the nulls are bounds rather than absences.

**Compare countries** puts up to eight countries on one shared axis — gap,
bright-cells gap, GDP growth, lights growth, capacity or electrification — with
rebasing years ringed, and a sortable summary table underneath. Quick picks for
the case studies and the five widest gaps. Unlike the single-country trace,
these lines are always on a common scale, so they are directly comparable.

It also carries three reference sections:

- **A Sub-Saharan Africa locator**, generated from the *same* Natural Earth
  file the night lights were summed inside — so the shape on screen is the
  shape the data was measured in, not a decorative outline from elsewhere.
  All 48 countries are drawn; the 10 outside the balanced panel are dimmed
  rather than hidden, and the selected country is lit. Clicking a country
  selects it.
- **The models, symbol by symbol.** All three equations — the gap definition,
  the main specification and the check model — with every symbol explained in
  three parts: what it is, what it means in this data, and *where it shows up
  on the charts*. The estimated values of θ, φ and β are read from the
  results tables, so they cannot go stale.
- **The processed datasets**, all ten of them, each with its row × column
  shape, the module that built it, its full column list and a **Download CSV**
  button. The CSVs are embedded in the page, so the dashboard is a portable
  copy of the processed data: one file that can be sent to a supervisor who
  can then read the numbers behind any chart without the repository.
  `--no-embed` drops them (586 KB → 205 KB).

> The page carries the same warning this README does: **a large divergence is
> not evidence of misreporting.** Lights miss agriculture, the informal economy
> and off-grid activity, they pick up flaring and electrification, and the 2017
> detection change inflates growth for dim countries specifically. The ranking
> is for choosing where to look.

## Open tasks

Done since the brief was written: VIIRS 2015–2021 processed (no countries lost,
so `config.EXCLUDED_LIGHTS` stays empty), SPI rebuilt against the published
index, the rebasing dummy built with all four text conversions, OxCGRT
stringency added, and every count in the brief reconciled.

Still open:

1. Interpret and write up the null results: they are bounds, not absences
   (see the minimum detectable effects above), and the rejection of beta = 1
   changes how the gap itself should be described throughout.
2. Decide the accountability scale (raw, standardised, or V-Dem's `osp` 0–1),
   and whether to centre SPI and accountability.
3. Add oil rents to the panel (already loaded in `wdi_long.csv`) and get GSS
   oil/non-oil GDP for the Ghana case study.
4. Verify the Ghana *dumsor* load-shedding timeline against Ghana Grid Company
   or Energy Commission records. If load shedding ran into 2016, the 2015
   lights baseline is artificially dark and Ghana's tripling is partly a
   recovery from it — this is the one open question that could change a
   headline number.
5. Download VIIRS v2.2 for 2022–2023 for the extended robustness check.
6. Read Martinez (2022) for his exact specification; verify every citation.
