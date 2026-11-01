# Findings

What the data shows, in the order it was found: three things about the night-lights series that had to be understood before any model could be trusted, then the panel, then the estimates.

[← back to the README](../README.md)

---

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
