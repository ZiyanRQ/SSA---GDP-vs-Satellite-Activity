# Verification

"It runs" is not "it is correct". This is the record of what was checked, how, and what the checks caught — including four reconciliations against the project brief and three bugs that would have changed a result.

[← back to the README](../README.md)

---

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
