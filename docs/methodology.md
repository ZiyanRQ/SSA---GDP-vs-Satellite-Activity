# Methodology

How the sample, the window and the switches were decided, and the design choices behind them. Every figure here was checked against the data rather than carried over from the project brief; where the two disagree, [`verification.md`](verification.md) says why.

[← back to the README](../README.md)

---

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
