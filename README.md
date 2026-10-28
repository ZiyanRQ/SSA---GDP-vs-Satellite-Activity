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

Step 1 (repository scaffolding and environment) is done. Every module in `src/`
is a **documented stub**: each docstring states the inputs, outputs, planned
steps and the checks to run, and `main()` raises `NotImplementedError`. No data
has been processed yet.

The environment is built and tested: Python 3.12.10 in `.venv`, with GDAL 3.12.2
and PROJ 9.8.1 loading, zonal statistics verified against a hand-computed sum,
and `PanelOLS` verified to recover a known slope exactly.

| Step | Module | Status |
| --- | --- | --- |
| 1 | `src/load_wdi.py` | not started |
| 2 | `src/load_vdem.py` | not started |
| 3a | `src/load_spi.py` | not started |
| 3b | `src/rebuild_spi.py` | not started |
| 4 | `src/load_oxcgrt.py` | not started |
| 5 | `src/process_lights.py` | not started |
| 6 | `src/build_panel.py` | not started |
| 7 | `src/models.py` | not started |

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
python -m src.build_panel
python -m src.models
```

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
| Statistical capacity, published scores | [worldbank/SPI](https://github.com/worldbank/SPI), `03_output_data/` | `SPI_index.csv` | 2016–2024 | **not yet downloaded** |
| SPI scoring rules | [worldbank/SPI](https://github.com/worldbank/SPI) | `SPI_full_metadata.csv` | — | **not yet downloaded** |
| SPI weighting logic | [worldbank/SPI](https://github.com/worldbank/SPI), `02_programs/` | `02-SPI_index.Rmd` (reference, around lines 1398 and 1434) | — | **not yet downloaded** |
| COVID stringency | [OxCGRT](https://github.com/OxCGRT/covid-policy-tracker), `data/` | `OxCGRT_nat_latest.csv` | daily 2020-01-01 to 2023-02-28; 2020–2022 are full years, 2023 is 2 months so no annual mean is computed | **not yet downloaded** |
| Night lights, main | [EOG VIIRS annual VNL](https://eogdata.mines.edu/products/vnl/) (also on Google Earth Engine as `NOAA/VIIRS/DNB/ANNUAL_V21`) | v2.1 annual composites 2015–2021, `average_masked` band | v2.1 covers 2012–2021 | **not yet downloaded** (free EOG account required) |
| Night lights, extended check | same, `ANNUAL_V22` | v2.2 composites 2022–2023 | different compositing method from v2.1 | **not yet downloaded** |
| Country boundaries | not yet chosen; must carry ISO3 codes | — | — | **not yet downloaded** |

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

Two things are deliberately left unset so that a decision has to be made rather
than defaulted:

- `config.LIGHTS_NEAR_ZERO_THRESHOLD` is `None`. `ln(0)` is undefined, so a
  rule is needed for near-zero radiance totals — and it must be fixed *before*
  any results are seen. `process_lights.py` refuses to run until it is set.
- `config.SPI_BASE_YEAR_TEXT_FIXES` is empty. Some countries store their base
  year as text ("2015/2016", "2010/11", "chained"). `rebuild_spi.py` must print
  every non-numeric value it finds and stop if one is not in the mapping, so
  nothing is silently guessed.

Assumptions still to verify against the actual data are marked
`ASSUMPTION TO VERIFY` in `src/config.py`.

## Open tasks

1. Download VIIRS v2.1 annual composites 2015–2021 (and v2.2 for 2022–2023 for
   the extended check), choose a boundary file, compute lights growth, handle
   gas flares and near-zero totals, and record any further countries lost in
   `config.EXCLUDED_LIGHTS`.
2. Rebuild SPI with the official weights, validating against the published
   `SPI.INDEX` first; also build the Pillar 4 and no-CPIBY variants.
3. Build the rebasing dummy: convert the text base years (ETH, UGA, GIN, SDN),
   check Liberia's backwards base year in 2019, use the KNBS September 2021
   date for Kenya.
4. Add OxCGRT annual stringency (0 for 2016–2019) and oil rents; get GSS
   oil/non-oil GDP for the Ghana case study.
5. Decide the accountability scale (raw, standardised, or V-Dem's `osp` 0–1).
6. Read Martinez (2022) for his exact specification; verify every citation.
