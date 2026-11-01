"""Step 7: estimate the models.

Run from the project root:

    python -m src.models                 # main models, estimators, robustness
    python -m src.models --quick         # main models only, nothing written

INPUT
    data/processed/ssa_panel.csv (from build_panel.py, audited by
    verify_panel.py)

OUTPUT
    outputs/tables/main_results.csv         signed and absolute gap, FE
    outputs/tables/estimator_comparison.csv pooled / FE / RE / FD + Hausman
    outputs/tables/check_model.csv          lights on the right-hand side
    outputs/tables/robustness.csv           every robustness check, one row
                                            per specification and coefficient
    outputs/figures/case_study_gaps.png     Ghana and Kenya, actual vs fitted

THE TWO QUESTIONS, AND WHY THEY NEED TWO OUTCOMES
    gap     = d_ln_gdp - d_ln_lights   how much faster reported GDP grew
    abs_gap = |gap|                    how far apart the two series are

    The signed gap asks about OVERSTATEMENT and has a direction, so the
    accountability coefficient is the one to read: phi < 0 would mean GDP
    grows faster than lights where accountability is weaker.

    The absolute gap asks about NOISE in either direction, which is what
    statistical capacity should affect: theta < 0 would mean smaller gaps,
    either way, where capacity is higher. A country could have a large
    absolute gap with no overstatement at all.

    They answer different questions, so they are reported side by side and
    neither is called "the" result.

WHAT FIXED EFFECTS CAN AND CANNOT DO HERE
    Country effects absorb each country's average gap and everything
    unchanging about it; year effects absorb shocks common to all countries,
    including the common part of COVID.

    Three limitations, stated before the results rather than after:
    - Accountability varies 4.6x more between countries than within them
      (measured on this panel, not assumed), so its coefficient is identified
      off very little within-country movement and will be imprecise. A null
      result on phi is close to uninformative.
    - Fixed effects amplify measurement error, and BOTH sides of the gap are
      measured with error. Attenuation towards zero is expected.
    - The 2017 detection change is not common across countries: it lands on
      cells near the detection limit, so it hits dim countries hardest. Year
      effects CANNOT absorb it. That is why robustness check 12, which swaps
      in the bright-cells lights measure, is a necessary check and not a
      nicety.

THE DECISION RULE FOR THE CHECK MODEL, FIXED BEFORE ESTIMATING
    The gap assumes GDP and lights move one-for-one. The check model puts
    lights on the right-hand side and estimates that elasticity:
        H0: beta = config.BETA_NULL (= 1)
        not rejected -> the simple gap is justified
        beta well below 1 -> give the check model more weight, and treat the
            gap results as describing a difference in growth rates rather
            than a structural elasticity
    The literature expects beta below 1 (Henderson, Storeygard and Weil 2012
    find around 0.3 on older DMSP data), so rejecting H0 is the likely
    outcome and is reported either way.

THE DECISION RULE FOR THE BRIGHT-CELLS CHECK, ALSO FIXED BEFORE ESTIMATING
    If the main coefficients keep their sign and rough size with
    d_ln_lights_bright in place of d_ln_lights, the detection artefact is not
    driving them. If they do not, THAT IS THE FINDING and it goes in the
    write-up. Whichever measure reads better is not a criterion.
"""

import argparse
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from linearmodels.panel import (FirstDifferenceOLS, PanelOLS, PooledOLS,
                                RandomEffects)
from scipy import stats

from src import config

# Columns centred before any interaction is built, so the lights elasticity
# in the check model is read at average capacity and accountability rather
# than at zero, which is outside the data entirely.
CENTRED_SUFFIX = "_c"

# The main specification's right-hand side, after centring.
MAIN_REGRESSORS = (
    [config.CAPACITY_MAIN + CENTRED_SUFFIX,
     config.ACCOUNTABILITY_MAIN + CENTRED_SUFFIX]
    + config.CONTROLS
    + ["covid_stringency"]
)


# ===========================================================================
# loading and preparation
# ===========================================================================

def load_panel(path: Path | None = None) -> pd.DataFrame:
    """Read the panel, centre the key variables and build the interactions."""
    panel_path = config.PANEL_FILE if path is None else path
    if not panel_path.exists():
        raise FileNotFoundError(
            f"{panel_path} not found. Run `python -m src.build_panel` first."
        )
    panel = pd.read_csv(panel_path)
    print(f"read {len(panel)} rows, {panel['iso3c'].nunique()} countries, "
          f"{panel['year'].min()}-{panel['year'].max()}")

    countries, n_rows = config.expected_sample()
    if len(panel) != n_rows or panel["iso3c"].nunique() != len(countries):
        raise ValueError(
            f"the panel is {len(panel)} rows / {panel['iso3c'].nunique()} "
            f"countries but config.expected_sample() says {n_rows} / "
            f"{len(countries)}. Rebuild it before estimating."
        )

    for column in config.CENTRE_VARIABLES:
        centred = column + CENTRED_SUFFIX
        panel[centred] = panel[column] - panel[column].mean()
        print(f"  centred {column}: mean {panel[column].mean():.3f} "
              f"subtracted, so 0 now means the sample average")

    # Alternative capacity measures get centred too, so swapping one in for a
    # robustness check does not silently change what the intercept means.
    for column in config.CAPACITY_ALTERNATIVES + \
            config.ACCOUNTABILITY_ALTERNATIVES + ["spi_rebuilt_no_cpiby"]:
        if column in panel.columns:
            panel[column + CENTRED_SUFFIX] = panel[column] - panel[column].mean()

    # Interactions, as explicit columns rather than formula syntax, so the
    # names in the output tables are predictable and readable.
    for lights in ["d_ln_lights", "d_ln_lights_bright"]:
        panel[f"{lights}_x_spi"] = (
            panel[lights] * panel[config.CAPACITY_MAIN + CENTRED_SUFFIX])
        panel[f"{lights}_x_acc"] = (
            panel[lights] * panel[config.ACCOUNTABILITY_MAIN + CENTRED_SUFFIX])
        panel[f"{lights}_x_elec"] = panel[lights] * panel["elec_access_change"]

    return panel


def as_panel(data: pd.DataFrame) -> pd.DataFrame:
    """Index on (entity, time), which is what linearmodels needs."""
    indexed = data.set_index(config.PANEL_INDEX)
    indexed = indexed.sort_index()
    return indexed


# ===========================================================================
# estimation
# ===========================================================================

def fit(data: pd.DataFrame, outcome: str, regressors: list[str],
        *, entity_effects: bool = True, time_effects: bool = True,
        estimator: str = "fe"):
    """Fit one specification and return the linearmodels results object.

    Standard errors are clustered by country throughout: a country's errors
    are correlated across years, and ignoring that understates them. With 38
    clusters this is above the usual rule-of-thumb minimum of about 30, but
    close enough to it to belong in the limitations.
    """
    indexed = as_panel(data)
    y = indexed[outcome]
    X = indexed[regressors]

    # Drop any regressor with no variation left: with both sets of effects a
    # constant-within-everything column is collinear with the effects, and
    # linearmodels would otherwise fail with a less readable message.
    constant = [c for c in X.columns if X[c].nunique() <= 1]
    if constant:
        print(f"      dropping {constant}: no variation in this sample")
        X = X.drop(columns=constant)

    if estimator == "fe":
        model = PanelOLS(y, X, entity_effects=entity_effects,
                         time_effects=time_effects, drop_absorbed=True)
    elif estimator == "pooled":
        model = PooledOLS(y, X.assign(const=1.0))
    elif estimator == "re":
        model = RandomEffects(y, X.assign(const=1.0))
    elif estimator == "fd":
        # First differences cannot carry a constant: it differences away.
        model = FirstDifferenceOLS(y, X)
    else:
        raise ValueError(f"unknown estimator {estimator!r}")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return model.fit(cov_type="clustered", cluster_entity=True)


def summarise(label: str, result, outcome: str,
              keep: list[str] | None = None) -> pd.DataFrame:
    """Turn a results object into tidy rows, one per coefficient."""
    rows = []
    for name in result.params.index:
        if keep is not None and name not in keep:
            continue
        rows.append({
            "specification": label,
            "outcome": outcome,
            "term": name,
            "coefficient": result.params[name],
            "std_error": result.std_errors[name],
            "t_stat": result.tstats[name],
            "p_value": result.pvalues[name],
            "ci_low": result.conf_int().loc[name, "lower"],
            "ci_high": result.conf_int().loc[name, "upper"],
            "n_obs": int(result.nobs),
            "n_entities": int(result.entity_info["total"]),
            "r2": getattr(result, "rsquared", np.nan),
            "r2_inclusive": getattr(result, "rsquared_inclusive", np.nan),
        })
    return pd.DataFrame(rows)


def stars(p: float) -> str:
    """Conventional significance marks, so the tables read at a glance."""
    if p < 0.01:
        return "***"
    if p < 0.05:
        return "**"
    if p < 0.10:
        return "*"
    return ""


def print_table(result, label: str, terms: list[str] | None = None) -> None:
    """Print one fitted model in a compact, readable form."""
    print(f"\n  {label}")
    print(f"    {'term':<34}{'coef':>10}{'se':>9}{'t':>7}{'p':>8}")
    names = terms if terms is not None else list(result.params.index)
    for name in names:
        if name not in result.params.index:
            continue
        p = result.pvalues[name]
        print(f"    {name:<34}{result.params[name]:>10.4f}"
              f"{result.std_errors[name]:>9.4f}{result.tstats[name]:>7.2f}"
              f"{p:>8.3f} {stars(p)}")
    # result.rsquared is the fit on the two-way demeaned data, which is what
    # this model is actually estimated on. NOT result.rsquared_within: with
    # time effects absorbed, linearmodels computes that against
    # entity-demeaned data only, using parameters that were never chosen to
    # fit it, so it is routinely negative here and means nothing.
    print(f"    n = {int(result.nobs)}, countries = "
          f"{int(result.entity_info['total'])}, "
          f"R2 (two-way within) = {getattr(result, 'rsquared', float('nan')):.3f}")


# ===========================================================================
# the main models
# ===========================================================================

def run_main_models(panel: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """The headline specification, on the signed gap and the absolute gap."""
    print("\n" + "=" * 74)
    print("MAIN SPECIFICATION: country and year fixed effects, "
          "SEs clustered by country")
    print("=" * 74)
    print("  Read theta (capacity) on the ABSOLUTE gap and phi "
          "(accountability) on the SIGNED gap:")
    print("  those are the two the design predicts a sign for.")

    results, frames = {}, []
    for outcome in [config.OUTCOME_SIGNED, config.OUTCOME_ABSOLUTE]:
        result = fit(panel, outcome, MAIN_REGRESSORS)
        results[outcome] = result
        print_table(result, f"outcome: {outcome}")
        frames.append(summarise("main FE", result, outcome))

    print("\n  the two coefficients the design makes a prediction about:")
    capacity = config.CAPACITY_MAIN + CENTRED_SUFFIX
    accountability = config.ACCOUNTABILITY_MAIN + CENTRED_SUFFIX
    for outcome, term, expected in [
        (config.OUTCOME_ABSOLUTE, capacity,
         "negative: higher capacity, smaller gaps either way"),
        (config.OUTCOME_SIGNED, accountability,
         "negative: weaker accountability, GDP grows faster than lights"),
    ]:
        result = results[outcome]
        coefficient = result.params[term]
        p = result.pvalues[term]
        sign = "negative" if coefficient < 0 else "positive"
        verdict = ("as predicted" if (coefficient < 0 and p < 0.10)
                   else "NOT significant at 10%" if coefficient < 0
                   else "WRONG SIGN")
        print(f"    {outcome:<9} {term:<28} {coefficient:+.4f} "
              f"(p = {p:.3f}) -> {sign}, {verdict}")
        print(f"              expected {expected}")

    return pd.concat(frames, ignore_index=True), results


def report_power(panel: pd.DataFrame, results: dict) -> pd.DataFrame:
    """How large an effect could this design actually have detected?

    A null result is only informative alongside this. "We found nothing" and
    "we could not have found anything smaller than a very large effect" look
    identical in a regression table and mean completely different things.

    The minimum detectable effect at 80% power and a 5% two-sided test is
    about 2.8 standard errors. It is reported per one WITHIN-country standard
    deviation of the regressor, because that is the variation fixed effects
    actually use, and expressed as a fraction of the within-country standard
    deviation of the outcome, so it can be read as an effect size.
    """
    print("\n" + "=" * 74)
    print("HOW LARGE AN EFFECT COULD THIS DESIGN HAVE DETECTED?")
    print("=" * 74)
    print("  Minimum detectable effect at 80% power, 5% two-sided: 2.8 x SE.")
    print("  Reported for a one-within-SD move in the regressor, as a share")
    print("  of the outcome's own within-SD.")

    def within_sd(column):
        means = panel.groupby("iso3c")[column].transform("mean")
        return float((panel[column] - means).std())

    rows = []
    targets = [(config.OUTCOME_ABSOLUTE, config.CAPACITY_MAIN + CENTRED_SUFFIX,
                config.CAPACITY_MAIN),
               (config.OUTCOME_SIGNED,
                config.ACCOUNTABILITY_MAIN + CENTRED_SUFFIX,
                config.ACCOUNTABILITY_MAIN)]
    print(f"\n    {'outcome':<9}{'regressor':<22}{'coef':>9}{'MDE':>9}"
          f"{'MDE in SD':>11}")
    for outcome, term, raw in targets:
        result = results[outcome]
        se = float(result.std_errors[term])
        coefficient = float(result.params[term])
        mde = 2.8 * se
        x_sd, y_sd = within_sd(raw), within_sd(outcome)
        mde_in_sd = mde * x_sd / y_sd
        observed_in_sd = abs(coefficient) * x_sd / y_sd
        print(f"    {outcome:<9}{raw:<22}{coefficient:>9.4f}{mde:>9.4f}"
              f"{mde_in_sd:>11.3f}")
        rows.append({
            "specification": "power", "outcome": outcome, "term": raw,
            "coefficient": coefficient, "std_error": se,
            "t_stat": np.nan, "p_value": float(result.pvalues[term]),
            "ci_low": np.nan, "ci_high": np.nan,
            "n_obs": int(result.nobs),
            "n_entities": int(result.entity_info["total"]),
            "r2": np.nan, "r2_inclusive": np.nan,
            "mde": mde, "mde_in_outcome_sd": mde_in_sd,
            "observed_in_outcome_sd": observed_in_sd,
        })
        print(f"              a one-within-SD move in {raw} "
              f"({x_sd:.3f}) could only have been")
        print(f"              detected if it shifted {outcome} by at least "
              f"{mde_in_sd:.2f} of its within-SD; observed "
              f"{observed_in_sd:.3f}")
    print("\n  So the nulls rule out large effects, not small ones. Say that")
    print("  in the write-up rather than 'no relationship was found'.")
    return pd.DataFrame(rows)


def run_estimator_comparison(panel: pd.DataFrame) -> pd.DataFrame:
    """Pooled OLS, FE, RE and FD on the same specification, plus Hausman."""
    print("\n" + "=" * 74)
    print("ESTIMATOR COMPARISON (outcome: " + config.OUTCOME_SIGNED + ")")
    print("=" * 74)

    outcome = config.OUTCOME_SIGNED
    frames = []

    # Year dummies are added explicitly so that FE and RE have the SAME
    # specification and the Hausman test compares like with like. PanelOLS's
    # time_effects would be absorbed and invisible to RandomEffects.
    with_dummies = panel.copy()
    year_dummies = pd.get_dummies(with_dummies["year"], prefix="y",
                                  drop_first=True, dtype=float)
    with_dummies = pd.concat([with_dummies, year_dummies], axis=1)
    dummy_names = list(year_dummies.columns)
    regressors = MAIN_REGRESSORS + dummy_names

    fitted = {}
    for label, estimator, kwargs in [
        ("pooled OLS", "pooled", {}),
        ("fixed effects", "fe", dict(entity_effects=True, time_effects=False)),
        ("random effects", "re", {}),
    ]:
        result = fit(with_dummies, outcome, regressors, estimator=estimator,
                     **kwargs)
        fitted[label] = result
        print_table(result, label, terms=MAIN_REGRESSORS)
        frames.append(summarise(label, result, outcome, keep=MAIN_REGRESSORS))

    # First differences: differencing removes the country effect the same way
    # FE does, but handles serially correlated errors differently.
    fd = fit(with_dummies, outcome, regressors, estimator="fd")
    fitted["first differences"] = fd
    print_table(fd, "first differences", terms=MAIN_REGRESSORS)
    frames.append(summarise("first differences", fd, outcome,
                            keep=MAIN_REGRESSORS))

    hausman_row = hausman(fitted["fixed effects"], fitted["random effects"],
                          MAIN_REGRESSORS)
    frames.append(hausman_row)
    return pd.concat(frames, ignore_index=True)


def hausman(fe_result, re_result, terms: list[str]) -> pd.DataFrame:
    """Hand-coded Hausman test: linearmodels does not provide one.

        H = (b_FE - b_RE)' [V_FE - V_RE]^-1 (b_FE - b_RE)

    compared with chi-squared on the number of coefficients compared.

    Two honest caveats, printed rather than buried:
    - V_FE - V_RE should be positive definite. In finite samples it often is
      not, and then the statistic is not interpretable in the usual way.
    - The classical test assumes RE is efficient under the null, which
      clustered standard errors undercut. So this is reported as evidence,
      not as a decision procedure. FE is the main estimator either way, on
      the design argument rather than on this test.
    """
    print("\n  Hausman test, FE against RE")
    common = [t for t in terms
              if t in fe_result.params.index and t in re_result.params.index]
    difference = fe_result.params[common] - re_result.params[common]
    variance = (fe_result.cov.loc[common, common]
                - re_result.cov.loc[common, common])

    eigenvalues = np.linalg.eigvalsh(variance.values)
    positive_definite = bool((eigenvalues > 0).all())
    print(f"    comparing {len(common)} coefficients")
    print(f"    V_FE - V_RE positive definite: {positive_definite} "
          f"(smallest eigenvalue {eigenvalues.min():.3e})")

    statistic = float(difference.values @ np.linalg.pinv(variance.values)
                      @ difference.values)
    p_value = float(stats.chi2.sf(statistic, len(common)))
    print(f"    H = {statistic:.3f} on {len(common)} df, p = {p_value:.4f}")
    if not positive_definite:
        print("    The variance difference is not positive definite, so this "
              "statistic")
        print("    is not interpretable in the usual way. Reported, not "
              "relied on.")
    elif p_value < 0.05:
        print("    RE is rejected: the country effects are correlated with "
              "the regressors, so FE it is.")
    else:
        print("    RE is not rejected on this test. FE remains the main "
              "estimator on the design argument.")

    return pd.DataFrame([{
        "specification": "Hausman FE vs RE",
        "outcome": config.OUTCOME_SIGNED,
        "term": f"chi2({len(common)})",
        "coefficient": statistic,
        "p_value": p_value,
        "std_error": np.nan, "t_stat": np.nan,
        "ci_low": np.nan, "ci_high": np.nan,
        "n_obs": int(fe_result.nobs),
        "n_entities": int(fe_result.entity_info["total"]),
        "r2": np.nan, "r2_inclusive": np.nan,
    }])


def run_check_model(panel: pd.DataFrame,
                    lights: str = "d_ln_lights") -> pd.DataFrame:
    """Lights on the right-hand side, and the test of beta = 1."""
    print("\n" + "=" * 74)
    print(f"CHECK MODEL: d_ln_gdp on {lights}, and the test of beta = "
          f"{config.BETA_NULL}")
    print("=" * 74)
    print("  The gap assumes GDP and lights move one-for-one. This estimates")
    print("  that elasticity instead of assuming it.")

    regressors = ([lights, f"{lights}_x_spi", f"{lights}_x_acc"]
                  + MAIN_REGRESSORS)
    result = fit(panel, "d_ln_gdp", regressors)
    print_table(result, f"d_ln_gdp on {lights} and interactions")

    beta = result.params[lights]
    se = result.std_errors[lights]
    t = (beta - config.BETA_NULL) / se
    df = int(result.entity_info["total"]) - 1          # clusters - 1
    p = float(2 * stats.t.sf(abs(t), df))

    print(f"\n  H0: beta = {config.BETA_NULL}")
    print(f"    beta_hat = {beta:.4f} (se {se:.4f})")
    print(f"    t = ({beta:.4f} - {config.BETA_NULL}) / {se:.4f} = {t:.3f} "
          f"on {df} df (clusters - 1)")
    print(f"    p = {p:.6f}")
    if p < 0.05:
        print(f"    REJECTED. GDP and lights do not move one-for-one, so the")
        print(f"    simple gap is a difference in growth rates, not a")
        print(f"    structural elasticity. Say so when reporting it.")
    else:
        print("    Not rejected: the simple gap is justified on this test.")

    rows = summarise(f"check model ({lights})", result, "d_ln_gdp")
    rows = pd.concat([rows, pd.DataFrame([{
        "specification": f"check model ({lights})",
        "outcome": "d_ln_gdp",
        "term": f"test beta = {config.BETA_NULL}",
        "coefficient": beta, "std_error": se, "t_stat": t, "p_value": p,
        "ci_low": np.nan, "ci_high": np.nan,
        "n_obs": int(result.nobs),
        "n_entities": int(result.entity_info["total"]),
        "r2": np.nan, "r2_inclusive": np.nan,
    }])], ignore_index=True)
    return rows


# ===========================================================================
# robustness
# ===========================================================================

def biggest_accountability_movers(panel: pd.DataFrame, n: int = 6) -> list[str]:
    """The countries whose accountability moved most, found in the data.

    Named rather than hard-coded, because a hard-coded list quietly stops
    matching the data when the V-Dem vintage changes.
    """
    span = panel.groupby("iso3c")[config.ACCOUNTABILITY_MAIN].agg(
        lambda s: s.max() - s.min())
    movers = span.sort_values(ascending=False).head(n)
    print(f"  biggest accountability movers in the panel: "
          f"{', '.join(f'{k} ({v:.2f})' for k, v in movers.items())}")
    return list(movers.index)


def run_robustness(panel: pd.DataFrame, main: dict) -> pd.DataFrame:
    """Every robustness check that the data currently supports."""
    print("\n" + "=" * 74)
    print("ROBUSTNESS CHECKS")
    print("=" * 74)

    capacity = config.CAPACITY_MAIN + CENTRED_SUFFIX
    accountability = config.ACCOUNTABILITY_MAIN + CENTRED_SUFFIX
    movers = biggest_accountability_movers(panel)

    def swap(regressors, old, new):
        return [new if r == old else r for r in regressors]

    checks = []

    # 1-3: alternative capacity measures.
    for name, column in [
        ("1. published SPI instead of rebuilt", "spi_overall"),
        ("2. SPI pillar 4 as capacity", "spi_p4_sources"),
        ("3. rebuilt SPI also dropping CPIBY", "spi_rebuilt_no_cpiby"),
    ]:
        checks.append((name, panel,
                       swap(MAIN_REGRESSORS, capacity,
                            column + CENTRED_SUFFIX)))

    # 5: the rebasing dummy.
    checks.append(("5. plus rebasing dummy", panel,
                   MAIN_REGRESSORS + ["rebased"]))

    # 6: lights interacted with electrification.
    checks.append(("6. plus lights x elec change", panel,
                   MAIN_REGRESSORS + ["d_ln_lights_x_elec"]))

    # 7: COVID handled two other ways.
    checks.append(("7a. drop COVID stringency", panel,
                   [r for r in MAIN_REGRESSORS if r != "covid_stringency"]))
    pre_covid = panel[panel["year"].isin(config.YEARS_PRE_COVID)]
    checks.append(("7b. pre-COVID 2016-2019 only", pre_covid,
                   [r for r in MAIN_REGRESSORS if r != "covid_stringency"]))

    # 8-10: leave-one-out and sample variations.
    for code in config.CASE_STUDIES:
        checks.append((f"8. excluding {code}",
                       panel[panel["iso3c"] != code], MAIN_REGRESSORS))
    checks.append(("9a. excluding oil producers",
                   panel[~panel["iso3c"].isin(config.OIL_PRODUCERS)],
                   MAIN_REGRESSORS))
    checks.append(("9b. plus oil rents", panel,
                   MAIN_REGRESSORS + ["oil_rents"]))
    checks.append(("10. excluding biggest accountability movers",
                   panel[~panel["iso3c"].isin(movers)], MAIN_REGRESSORS))

    # 4 and 12 are handled separately: the check model has a different
    # outcome, and the bright-cells check changes the outcome variable.

    frames = []
    for label, data, regressors in checks:
        print(f"\n  {label}  (n={len(data)}, "
              f"{data['iso3c'].nunique()} countries)")
        for outcome in [config.OUTCOME_SIGNED, config.OUTCOME_ABSOLUTE]:
            result = fit(data, outcome, regressors)
            frames.append(summarise(label, result, outcome))
            term = (accountability if outcome == config.OUTCOME_SIGNED
                    else capacity)
            # The swapped-in capacity measures have different names.
            if term not in result.params.index:
                term = next((r for r in regressors if r.startswith("spi")),
                            None)
            if term and term in result.params.index:
                p = result.pvalues[term]
                print(f"      {outcome:<9} {term:<28} "
                      f"{result.params[term]:+.4f} (p={p:.3f}) {stars(p)}")

    frames.append(run_bright_cells_check(panel, main))
    return pd.concat(frames, ignore_index=True)


def run_bright_cells_check(panel: pd.DataFrame, main: dict) -> pd.DataFrame:
    """Check 12: rerun the main models on the bright-cells lights measure.

    The decision rule was fixed before running this, and is in the module
    docstring: if the coefficients keep their sign and rough size, the 2017
    detection artefact is not driving the results; if they do not, that is
    the finding.
    """
    print("\n" + "=" * 74)
    print("12. BRIGHT-CELLS LIGHTS (the detection-artefact check)")
    print("=" * 74)
    print("  Identical specification; the only change is that the gap is")
    print("  built from lights above a fixed 5 nW/cm2/sr floor, which the")
    print("  2017 compositing change barely touches.")

    capacity = config.CAPACITY_MAIN + CENTRED_SUFFIX
    accountability = config.ACCOUNTABILITY_MAIN + CENTRED_SUFFIX

    frames = []
    comparison = []
    pairs = [(config.OUTCOME_SIGNED, "gap_bright", accountability),
             (config.OUTCOME_ABSOLUTE, "abs_gap_bright", capacity)]
    for original, bright, term in pairs:
        result = fit(panel, bright, MAIN_REGRESSORS)
        frames.append(summarise("12. bright-cells lights", result, bright))
        print_table(result, f"outcome: {bright}")
        comparison.append({
            "outcome": original,
            "term": term,
            "main": main[original].params[term],
            "main_p": main[original].pvalues[term],
            "bright": result.params[term],
            "bright_p": result.pvalues[term],
        })

    print("\n  side by side, the two coefficients the design predicts:")
    print(f"    {'outcome':<10}{'term':<24}{'main':>10}{'p':>7}"
          f"{'bright':>10}{'p':>7}  verdict")
    for row in comparison:
        # A sign comparison only means something if there is a sign to
        # compare. Both of these coefficients are indistinguishable from
        # zero, and reporting "the sign flipped" when a coefficient moves
        # from -0.00003 to +0.0015 would dress up noise as a reversal.
        either_significant = min(row["main_p"], row["bright_p"]) < 0.10
        if not either_significant:
            verdict = "both null, sign not meaningful"
        elif np.sign(row["main"]) == np.sign(row["bright"]):
            verdict = "same sign, holds"
        else:
            verdict = "SIGN FLIPS, and one is significant"
        row["verdict"] = verdict
        print(f"    {row['outcome']:<10}{row['term']:<24}"
              f"{row['main']:>10.4f}{row['main_p']:>7.3f}"
              f"{row['bright']:>10.4f}{row['bright_p']:>7.3f}  {verdict}")

    meaningful = [r for r in comparison if min(r["main_p"], r["bright_p"]) < 0.10]
    if not meaningful:
        print("\n  Neither coefficient is distinguishable from zero under")
        print("  either lights measure. On the rule fixed in advance this")
        print("  check cannot overturn a result, because there is no result")
        print("  to overturn: it says the null finding is not an artefact of")
        print("  the lights measure either. It is NOT evidence that the")
        print("  detection change is harmless - only that it is not what is")
        print("  producing these particular nulls.")
    elif all(np.sign(r["main"]) == np.sign(r["bright"]) for r in meaningful):
        print("\n  The coefficients that are distinguishable from zero keep")
        print("  their sign. On the rule fixed in advance, the detection")
        print("  artefact is not what is driving the results.")
    else:
        print("\n  A sign flips on a coefficient that is significant under at")
        print("  least one measure. On the rule fixed in advance THIS IS THE")
        print("  FINDING: the result is not robust to the lights measure, and")
        print("  the write-up says so rather than choosing the measure that")
        print("  reads better.")
    return pd.concat(frames, ignore_index=True)


# ===========================================================================
# case studies
# ===========================================================================

def write_case_study_figure(panel: pd.DataFrame, result) -> None:
    """Plot each case study's gap against the model's fitted value."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # linearmodels splits the outcome three ways:
    #     y = fitted_values + estimated_effects + resids
    # fitted_values is X @ params ONLY: it excludes the absorbed country and
    # year effects, so on its own it runs around -2.7 for an outcome that
    # lives between -0.6 and +0.3. The model's actual prediction for a
    # country-year is fitted_values PLUS the estimated effects, and the
    # residual to read is resids. Checked against the identity above rather
    # than taken from the attribute name.
    prediction = (result.fitted_values.iloc[:, 0]
                  + result.estimated_effects.iloc[:, 0])
    parts = pd.DataFrame({
        "prediction": prediction,
        "residual": result.resids,
    }).reset_index()
    merged = panel.merge(parts, on=config.PANEL_INDEX, how="left")

    actual = as_panel(panel)[config.OUTCOME_SIGNED]
    identity = (actual - prediction - result.resids).abs().max()
    if identity > 1e-10:
        raise ValueError(
            "y does not equal fitted_values + estimated_effects + resids "
            f"(max difference {identity:.3e}); the decomposition assumed here "
            "no longer holds."
        )
    # Written out per country-year, because the dashboard and the case-study
    # write-up both need the prediction and the residual for every row, not
    # only for the two case studies.
    config.OUTPUTS_TABLES.mkdir(parents=True, exist_ok=True)
    fitted_path = config.OUTPUTS_TABLES / "panel_fitted.csv"
    merged[["iso3c", "year", config.OUTCOME_SIGNED, "prediction",
            "residual"]].to_csv(fitted_path, index=False)
    print(f"\n  per-observation fits written to {fitted_path}")

    print(f"  prediction = fitted_values + estimated_effects, checked "
          f"against the identity (max difference {identity:.1e})")
    print(f"  correlation of actual gap with prediction: "
          f"{np.corrcoef(actual, prediction)[0, 1]:.3f}")

    events = {
        ("GHA", 2019): "rebasing\n2006->2013",
        ("KEN", 2021): "rebasing\n(KNBS Sept)",
        ("GHA", 2020): "COVID",
        ("KEN", 2020): "COVID",
    }

    fig, axes = plt.subplots(1, len(config.CASE_STUDIES),
                             figsize=(11, 4.2), sharey=True)
    for axis, code in zip(np.atleast_1d(axes), config.CASE_STUDIES):
        rows = merged[merged["iso3c"] == code].sort_values("year")
        axis.axhline(0, color="#999999", linewidth=0.8, zorder=1)
        axis.plot(rows["year"], rows[config.OUTCOME_SIGNED], "o-",
                  color="#1f4e79", label="actual gap", zorder=3)
        axis.plot(rows["year"], rows["prediction"], "s--", color="#c0504d",
                  label="model prediction", zorder=2)
        for _, row in rows.iterrows():
            key = (code, int(row["year"]))
            if key in events:
                axis.annotate(events[key],
                              (row["year"], row[config.OUTCOME_SIGNED]),
                              textcoords="offset points", xytext=(0, 14),
                              ha="center", fontsize=7, color="#555555")
        axis.set_title(code)
        axis.set_xlabel("year")
        axis.grid(alpha=0.25, linewidth=0.6)
    np.atleast_1d(axes)[0].set_ylabel(
        "gap  (ln GDP growth - ln lights growth)")
    np.atleast_1d(axes)[0].legend(frameon=False, fontsize=8)
    fig.suptitle("Case studies: actual gap against the fixed-effects "
                 "prediction", fontsize=11)
    fig.tight_layout()

    config.OUTPUTS_FIGURES.mkdir(parents=True, exist_ok=True)
    path = config.OUTPUTS_FIGURES / "case_study_gaps.png"
    fig.savefig(path, dpi=150, facecolor="white")
    plt.close(fig)
    print(f"\ncase-study figure written to {path}")

    print("\nresiduals for the case studies (actual minus predicted):")
    cases = merged[merged["iso3c"].isin(config.CASE_STUDIES)].copy()
    print(cases[["iso3c", "year", config.OUTCOME_SIGNED, "prediction",
                 "residual", "rebased"]].to_string(
        index=False, float_format=lambda v: f"{v:8.3f}"))
    print("  A large positive residual means the gap was less negative than "
          "the model expects:")
    print("  reported GDP grew faster relative to lights than the country's "
          "own average and")
    print("  that year's regional shock would predict.")


# ===========================================================================
# checks on the estimation itself
# ===========================================================================

def check_samples(tables: pd.DataFrame) -> None:
    """Confirm every specification ran on the sample it should have.

    linearmodels drops rows with any missing value silently, so the number of
    observations has to be READ from the output, not assumed. A table whose
    sample size moves for no stated reason is a bug, not a result.
    """
    print("\n" + "=" * 74)
    print("CHECKS ON THE ESTIMATION")
    print("=" * 74)

    countries, n_rows = config.expected_sample()
    full = tables[tables["specification"].isin(
        ["main FE", "fixed effects", "pooled OLS", "random effects"])]
    bad = full[(full["n_obs"] != n_rows) | (full["n_entities"] != len(countries))]
    if len(bad):
        print("  FAIL  a full-sample specification did not use all "
              f"{n_rows} rows / {len(countries)} countries:")
        print(bad[["specification", "outcome", "n_obs",
                   "n_entities"]].drop_duplicates().to_string(index=False))
        raise ValueError("a full-sample model ran on the wrong sample")
    print(f"  PASS  every full-sample model used {n_rows} rows and "
          f"{len(countries)} countries")

    # The specifications that SHOULD have a different sample, and why.
    expected_smaller = {
        "7b. pre-COVID 2016-2019 only": "fewer years",
        "8. excluding GHA": "one country out",
        "8. excluding KEN": "one country out",
        "9a. excluding oil producers": "six countries out",
        "10. excluding biggest accountability movers": "six countries out",
        "first differences": "one year lost to differencing",
    }
    print("\n  specifications that deliberately use a different sample:")
    for label, reason in expected_smaller.items():
        rows = tables[tables["specification"] == label]
        if not len(rows):
            continue
        n_obs = int(rows["n_obs"].iloc[0])
        n_entities = int(rows["n_entities"].iloc[0])
        print(f"    {label:<46} n={n_obs:>4}, countries={n_entities:>3}  "
              f"({reason})")

    others = tables[~tables["specification"].isin(
        list(expected_smaller) + ["Hausman FE vs RE"])]
    unexplained = others[others["n_obs"] != n_rows]
    if len(unexplained):
        print("\n  FAIL  these specifications changed sample without a "
              "stated reason:")
        print(unexplained[["specification", "n_obs"]].drop_duplicates()
              .to_string(index=False))
        raise ValueError("an unexplained sample-size change")
    print(f"\n  PASS  every other specification used all {n_rows} rows")


# ===========================================================================

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--panel", type=Path, default=None)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--quick", action="store_true",
                        help="main models only, write nothing")
    args = parser.parse_args()

    panel = load_panel(args.panel)
    main_table, main_results = run_main_models(panel)
    power = report_power(panel, main_results)

    if args.quick:
        print("\n--quick: main models only, nothing written.")
        return

    estimators = run_estimator_comparison(panel)
    check = run_check_model(panel)
    robustness = run_robustness(panel, main_results)

    everything = pd.concat([main_table, estimators, check, robustness],
                           ignore_index=True)
    check_samples(everything)

    write_case_study_figure(panel, main_results[config.OUTCOME_SIGNED])

    out_dir = args.out_dir if args.out_dir is not None else config.OUTPUTS_TABLES
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, frame in [("main_results", main_table),
                        ("minimum_detectable_effects", power),
                        ("estimator_comparison", estimators),
                        ("check_model", check),
                        ("robustness", robustness)]:
        path = out_dir / f"{name}.csv"
        frame.to_csv(path, index=False)
        print(f"written to {path}")


if __name__ == "__main__":
    main()
