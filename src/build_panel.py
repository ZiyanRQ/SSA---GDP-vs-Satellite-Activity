"""Step 6: merge every source into the balanced country-year panel.

Run from the project root:

    python -m src.build_panel

This is where the sample is decided, so it is the step that most needs loud
logging: after every merge the row count, the country count and the merge
indicator are printed, and every dropped country is written to a table with
the reason and the variables responsible.

INPUT (all from data/interim/, all verified by src/verify_sources.py)
    wdi_long.csv                   load_wdi.py
    vdem_accountability.csv        load_vdem.py
    spi_rebuilt.csv                rebuild_spi.py (carries the published
                                   scores and the pillars as well)
    rebasing_dummy.csv             rebuild_spi.py
    oxcgrt_annual.csv              load_oxcgrt.py
    lights_country_year_raw.csv    process_lights.py, LEVELS 2015-2021
    lights_country_year.csv        process_lights.py, growth 2016-2021,
                                   used only to cross-check the growth rates
                                   recomputed here

OUTPUT
    data/processed/ssa_panel.csv          the estimation panel
    outputs/tables/dropped_countries.csv  one row per dropped country

TWO THINGS THAT DECIDE WHETHER THE MERGE IS RIGHT

    1. The grid comes first. The panel starts from an explicit
       config.SSA_ALL x config.YEARS_LEVELS grid rather than from whichever
       file merges first. On a grid a missing country-year is a row full of
       missing values, which is visible. Without one it is simply an absent
       row, which is not.

    2. SPI is merged AFTER the window is cut to 2016-2021, not before.
       The published SPI overall index starts in 2016, but Pillars 1, 3 and 4
       carry 2015 values. Merging SPI onto the 2015-2021 levels grid would put
       pillar values in a row whose overall index does not exist, and any
       later lag or difference would mix published with unpublished data
       silently. See the SPI 2015 trap in src/verify_sources.py.

WHY THE GROWTH RATES ARE RECOMPUTED HERE
    d_ln_lights already exists in lights_country_year.csv, and d_ln_gdp could
    be taken from WDI's published gdp_growth. Both are recomputed from the
    levels instead, inside this module, and then checked against the supplied
    versions. Recomputing costs nothing and makes the lag explicit; taking
    them on trust would hide the one error that matters most here, which is
    shifting across a country boundary rather than within a country.

ON SURVIVORSHIP BIAS
    Most dropped countries are fragile or conflict-affected with weak
    statistics, so the balanced sample leans towards stronger statistical
    capacity. That probably understates any capacity effect, and the results
    may not generalise to fragile states. The dropped-countries table is the
    evidence for saying so explicitly in the write-up.
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from src import config

# Sources merged on the 2015-2021 levels grid, because growth rates are
# differenced out of them and so need 2015 as a base year.
LEVEL_SOURCES = {
    "wdi": "wdi_long.csv",
    "vdem": "vdem_accountability.csv",
    "lights": "lights_country_year_raw.csv",
}

# Sources merged after the window is cut to 2016-2021. SPI is here for the
# reason in the docstring; the others are defined only on the growth years.
GROWTH_SOURCES = {
    "spi": "spi_rebuilt.csv",
    "oxcgrt": "oxcgrt_annual.csv",
    "rebasing": "rebasing_dummy.csv",
}

# Columns kept from each source. Listed rather than taken wholesale so that a
# new column appearing upstream does not silently enter the panel.
KEEP = {
    "wdi": ["gdp_real_lcu", "gdp_growth", "agri_share", "elec_access",
            "urban_share", "population", "oil_rents"],
    "vdem": ["v2x_accountability", "v2x_veracc", "v2x_horacc", "v2x_diagacc"],
    "lights": ["lights_sum", "lights_sum_bright", "area_cells"],
    "spi": ["spi_overall", "spi_rebuilt", "spi_rebuilt_no_cpiby",
            "spi_p1_use", "spi_p2_services", "spi_p3_products",
            "spi_p4_sources", "spi_p5_infra", "spi_rebuilt_p5"],
    "oxcgrt": ["covid_stringency"],
    "rebasing": ["base_year", "base_year_status", "rebased", "rebased_source",
                 "flag"],
}

# A country needs every one of these, in every year, to stay in the balanced
# panel. Built from config so the model and the sample cannot drift apart.
MODEL_VARIABLES = (
    ["d_ln_gdp", "d_ln_lights", config.OUTCOME_SIGNED]
    + config.CONTROLS
    + [config.CAPACITY_MAIN, config.ACCOUNTABILITY_MAIN]
    + ["covid_stringency"]
)


def load_source(name: str, filename: str, interim_dir: Path) -> pd.DataFrame:
    """Read one interim table and keep only the columns the panel uses."""
    path = interim_dir / filename
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Run the loader that produces it first; "
            "`python -m src.verify_sources` lists what is missing."
        )
    frame = pd.read_csv(path)

    wanted = ["iso3c", "year"] + KEEP[name]
    missing = [c for c in wanted if c not in frame.columns]
    if missing:
        raise ValueError(f"{filename} has no column(s) {missing}")

    print(f"  {name:<9} {len(frame):>5} rows x {len(frame.columns):>2} columns "
          f"-> keeping {len(KEEP[name])}")
    return frame[wanted].copy()


def merge_source(panel: pd.DataFrame, frame: pd.DataFrame,
                 name: str) -> pd.DataFrame:
    """Left-merge one source onto the panel, reporting what happened.

    The merge indicator is the point of this function. "left_only" means the
    source has no row for that country-year, which is different from having a
    row whose values are missing, and the two need telling apart: the first is
    a coverage gap in the source, the second is a gap in the data itself.
    """
    before = len(panel)
    merged = panel.merge(frame, on=["iso3c", "year"], how="left",
                         indicator="_merge", validate="one_to_one")

    counts = merged["_merge"].value_counts()
    both = int(counts.get("both", 0))
    left_only = int(counts.get("left_only", 0))

    print(f"\n  merged {name}")
    print(f"    rows {before} -> {len(merged)}  "
          f"({merged['iso3c'].nunique()} countries)")
    print(f"    matched {both}, no row in the source {left_only}")

    if left_only:
        gaps = merged[merged["_merge"] == "left_only"]
        by_country = gaps.groupby("iso3c")["year"].apply(
            lambda s: sorted(s.tolist()))
        print(f"    country-years with no row in {name}:")
        for iso, years in by_country.items():
            print(f"      {iso}: {years}")

    for column in KEEP[name]:
        n_missing = int(merged[column].isna().sum())
        if n_missing:
            who = sorted(merged.loc[merged[column].isna(), "iso3c"].unique())
            shown = who[:8]
            more = f" (+{len(who) - 8} more)" if len(who) > 8 else ""
            print(f"    {column:<22} {n_missing:>4} missing  {shown}{more}")

    if len(merged) != before:
        raise ValueError(
            f"merging {name} changed the row count from {before} to "
            f"{len(merged)}. A duplicate key in the source is the usual "
            "cause; src/verify_sources.py checks for them."
        )

    return merged.drop(columns="_merge")


def build_grid() -> pd.DataFrame:
    """The full country-year grid the panel is built on."""
    grid = pd.MultiIndex.from_product(
        [config.SSA_ALL, config.YEARS_LEVELS], names=["iso3c", "year"]
    ).to_frame(index=False)
    config.check_years(grid["year"].unique(), stage="levels")
    print(f"grid: {len(config.SSA_ALL)} countries x "
          f"{len(config.YEARS_LEVELS)} years = {len(grid)} rows "
          f"({min(config.YEARS_LEVELS)}-{max(config.YEARS_LEVELS)})")
    return grid


def add_derived_variables(panel: pd.DataFrame) -> pd.DataFrame:
    """Build the growth rates, the gap and the remaining model variables.

    EVERY lag is taken WITHIN COUNTRY: sort by (iso3c, year), group by iso3c,
    then shift. Shifting the whole sorted frame instead would give the first
    year of each country the last year of the country before it, which
    produces a wrong number rather than a missing one - the kind of error that
    survives every row-count check.
    """
    print("\n--- derived variables ---")
    panel = panel.sort_values(["iso3c", "year"]).reset_index(drop=True)
    grouped = panel.groupby("iso3c")

    panel["ln_gdp"] = np.log(panel["gdp_real_lcu"])
    panel["ln_lights"] = np.log(panel["lights_sum"])
    panel["ln_lights_bright"] = np.log(panel["lights_sum_bright"])

    panel["d_ln_gdp"] = grouped["ln_gdp"].diff()
    panel["d_ln_lights"] = grouped["ln_lights"].diff()
    panel["d_ln_lights_bright"] = grouped["ln_lights_bright"].diff()

    # The outcome: how much faster reported GDP grew than lights did. Negative
    # means lights grew faster than the official figures.
    panel[config.OUTCOME_SIGNED] = panel["d_ln_gdp"] - panel["d_ln_lights"]
    panel[config.OUTCOME_ABSOLUTE] = panel[config.OUTCOME_SIGNED].abs()

    # The same gap against the bright-cells measure, which is the robustness
    # check for the 2017 detection change.
    panel["gap_bright"] = panel["d_ln_gdp"] - panel["d_ln_lights_bright"]
    panel["abs_gap_bright"] = panel["gap_bright"].abs()

    # In percentage points, not a log change: elec_access is already a
    # percentage, and a log change in a percentage is hard to interpret.
    panel["elec_access_change"] = grouped["elec_access"].diff()

    panel["ln_population"] = np.log(panel["population"])

    for column in ["d_ln_gdp", "d_ln_lights", "elec_access_change"]:
        first_year = panel[panel["year"] == min(config.YEARS_LEVELS)]
        if first_year[column].notna().any():
            raise ValueError(
                f"{column} has a value in {min(config.YEARS_LEVELS)}, which "
                "is impossible: that year has no predecessor. The lag was "
                "probably taken across the whole frame instead of within "
                "each country."
            )
    print(f"  built {len(config.YEARS_LEVELS)}-year levels into growth rates; "
          f"every variable is missing in {min(config.YEARS_LEVELS)}, as it "
          "must be")
    return panel


def check_recomputed_growth(panel: pd.DataFrame, interim_dir: Path) -> None:
    """Check the recomputed growth rates against the ones already published.

    Two independent routes to the same number. If they disagree, the lag here
    is wrong, or the source changed, and either way nothing downstream should
    run.
    """
    print("\n--- recomputed growth vs the supplied versions ---")

    # WDI publishes its own growth rate as a percentage.
    comparable = panel.dropna(subset=["gdp_growth", "d_ln_gdp"])
    from_levels = 100 * (np.exp(comparable["d_ln_gdp"]) - 1)
    diff = (comparable["gdp_growth"] - from_levels).abs()
    print(f"  gdp_growth vs 100*(exp(d_ln_gdp)-1): max abs diff "
          f"{diff.max():.6f} pp over {len(comparable)} country-years")
    if diff.max() > 0.005:
        worst = comparable.loc[diff.idxmax(), ["iso3c", "year"]].tolist()
        raise ValueError(
            f"published WDI growth and growth computed from the constant-LCU "
            f"levels disagree by {diff.max():.4f} pp (worst: {worst}). A "
            "currency redenomination in the levels series is the usual cause."
        )

    # process_lights computed the same log differences independently.
    lights = pd.read_csv(interim_dir / "lights_country_year.csv")
    merged = panel.merge(lights[["iso3c", "year", "d_ln_lights",
                                 "d_ln_lights_bright"]],
                         on=["iso3c", "year"], how="inner",
                         suffixes=("", "_source"))
    for column in ["d_ln_lights", "d_ln_lights_bright"]:
        diff = (merged[column] - merged[f"{column}_source"]).abs()
        print(f"  {column} vs process_lights: max abs diff {diff.max():.3e} "
              f"over {len(merged)} country-years")
        if diff.max() > 1e-9:
            raise ValueError(
                f"{column} recomputed here differs from the one "
                "process_lights wrote. The lag is wrong in one of the two."
            )
    print("  both agree: the lags are taken within country")


def select_sample(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Apply the balanced or unbalanced rule and record every country lost."""
    balanced = not config.USE_UNBALANCED_PANEL
    print(f"\n--- selecting the sample "
          f"({'balanced' if balanced else 'unbalanced'}) ---")

    missing_any = panel[MODEL_VARIABLES].isna().any(axis=1)
    print(f"  country-years with a missing model variable: "
          f"{int(missing_any.sum())} of {len(panel)}")

    # One row per dropped country, naming the years and the variables, so the
    # write-up can say exactly what the balance requirement cost.
    records = []
    for iso in sorted(panel.loc[missing_any, "iso3c"].unique()):
        rows = panel[(panel["iso3c"] == iso) & missing_any]
        culprits = sorted(
            column for column in MODEL_VARIABLES
            if rows[column].isna().any()
        )
        records.append({
            "iso3c": iso,
            "years_missing": ", ".join(str(y) for y in sorted(rows["year"])),
            "n_years_missing": len(rows),
            "variables": ", ".join(culprits),
            "expected_reason": config.EXPECTED_DROPPED_REASONS.get(
                iso, "NOT EXPECTED TO DROP"),
        })
    dropped = pd.DataFrame(records)

    if balanced:
        bad_countries = set(panel.loc[missing_any, "iso3c"])
        kept = panel[~panel["iso3c"].isin(bad_countries)].copy()
        print(f"  balanced rule: dropping all {len(bad_countries)} countries "
              "with any gap, in every year")
    else:
        kept = panel[~missing_any].copy()
        print(f"  unbalanced rule: dropping {int(missing_any.sum())} "
              "individual country-years")

    print(f"  kept {kept['iso3c'].nunique()} countries, {len(kept)} rows")
    return kept.reset_index(drop=True), dropped


def check_panel(panel: pd.DataFrame, dropped: pd.DataFrame) -> None:
    """Every check that has to pass before anything is estimated."""
    print("\n=== checks ===")
    expected_countries, expected_rows = config.expected_sample()

    print(f"\nthe arithmetic this panel should satisfy:")
    print(f"  {len(config.SSA_ALL)} countries x {len(config.YEARS_GROWTH)} "
          f"years                     = "
          f"{len(config.SSA_ALL) * len(config.YEARS_GROWTH)} possible rows")
    print(f"  less {len(config.EXCLUDED_MISSING_DATA)} missing WDI/SPI data  "
          f"-> {len(config.SSA_ALL) - len(config.EXCLUDED_MISSING_DATA)} "
          f"countries, "
          f"{(len(config.SSA_ALL) - len(config.EXCLUDED_MISSING_DATA)) * len(config.YEARS_GROWTH)}"
          f" rows")
    print(f"  less {len(config.EXCLUDED_NO_COVID_DATA)} missing stringency  "
          f"-> {len(expected_countries)} countries, {expected_rows} rows")
    if config.EXCLUDED_LIGHTS:
        print(f"  less {len(config.EXCLUDED_LIGHTS)} lost to lights")
    else:
        print("  less 0 lost to lights    (no country lost a radiance total)")

    assert len(panel) == expected_rows, (
        f"the panel has {len(panel)} rows but the settings imply "
        f"{expected_rows}. If the lights step cost further countries, add "
        "them to config.EXCLUDED_LIGHTS and every count updates from there."
    )
    assert panel["iso3c"].nunique() == len(expected_countries), (
        f"{panel['iso3c'].nunique()} countries, expected "
        f"{len(expected_countries)}"
    )
    print(f"\n  rows {len(panel)} and countries {panel['iso3c'].nunique()} "
          "match config.expected_sample()")

    got = sorted(panel["iso3c"].unique())
    assert got == sorted(expected_countries), (
        "the kept countries are not the expected ones. Difference: "
        f"{sorted(set(got) ^ set(expected_countries))}"
    )
    print("  the kept countries are exactly the expected list")

    # Balance: not implied by the row count, which could be reached by one
    # country having seven years and another five.
    per_country = panel.groupby("iso3c").size()
    assert (per_country == len(config.YEARS_GROWTH)).all(), (
        "the panel is not balanced:\n"
        f"{per_country[per_country != len(config.YEARS_GROWTH)].to_string()}"
    )
    print(f"  every country has exactly {len(config.YEARS_GROWTH)} years")

    # 2015 is a base year for the 2016 growth rate, never an observation.
    config.check_years(panel["year"].unique(), stage="growth")
    assert min(config.YEARS_LEVELS) not in set(panel["year"]), (
        f"{min(config.YEARS_LEVELS)} survived into the panel; it is a base "
        "year, not an observation"
    )
    print(f"  {min(config.YEARS_LEVELS)} has gone, as it must")

    # No missing values anywhere in a model variable.
    for column in MODEL_VARIABLES:
        n_missing = int(panel[column].isna().sum())
        assert n_missing == 0, (
            f"{column} has {n_missing} missing values inside the final panel"
        )
    print(f"  all {len(MODEL_VARIABLES)} model variables are complete")

    # Every name config points the models at must exist here.
    referenced = set(
        config.CONTROLS + config.CAPACITY_ALTERNATIVES
        + config.ACCOUNTABILITY_ALTERNATIVES + config.CENTRE_VARIABLES
        + [config.OUTCOME_SIGNED, config.OUTCOME_ABSOLUTE,
           config.CAPACITY_MAIN, config.ACCOUNTABILITY_MAIN]
    )
    absent = sorted(referenced - set(panel.columns))
    assert not absent, (
        f"config names these columns but the panel has no {absent}. Either "
        "the panel is missing a variable or config has a stale name."
    )
    print(f"  all {len(referenced)} columns config references exist")

    # The dropped countries, against what the settings say should drop.
    print("\ndropped countries:")
    if len(dropped):
        print(dropped.to_string(index=False))
    actually_dropped = set(dropped["iso3c"]) if len(dropped) else set()
    expected_dropped = set(config.EXPECTED_DROPPED_REASONS)
    unexpected = sorted(actually_dropped - expected_dropped)
    not_dropped = sorted(expected_dropped - actually_dropped)
    assert not unexpected, (
        f"{unexpected} dropped but config does not expect them to. Something "
        "upstream has changed; do not estimate until this is understood."
    )
    assert not not_dropped, (
        f"config expects {not_dropped} to drop but they did not"
    )
    print(f"\n  the {len(actually_dropped)} dropped countries are exactly "
          "config.EXPECTED_DROPPED_REASONS")


def report_panel(panel: pd.DataFrame) -> None:
    """Describe the panel, and spot-check it against the brief."""
    print("\n=== the panel ===")
    print(f"{len(panel)} rows, {panel['iso3c'].nunique()} countries, "
          f"{len(panel.columns)} columns, "
          f"{panel['year'].min()}-{panel['year'].max()}")

    print("\nthe outcome and its two components:")
    summary = panel[["d_ln_gdp", "d_ln_lights", "d_ln_lights_bright",
                     config.OUTCOME_SIGNED, config.OUTCOME_ABSOLUTE,
                     "gap_bright"]].describe().T
    print(summary[["mean", "std", "min", "25%", "50%", "75%", "max"]]
          .to_string(float_format=lambda v: f"{v:8.3f}"))

    negative = int((panel[config.OUTCOME_SIGNED] < 0).sum())
    print(f"\n  the gap is negative in {negative} of {len(panel)} "
          f"country-years ({100 * negative / len(panel):.0f}%): lights grew "
          "faster than reported GDP")

    print("\nwithin- vs between-country variation, which is what fixed "
          "effects have to work with:")
    for column in [config.OUTCOME_SIGNED, "d_ln_gdp", "d_ln_lights",
                   config.CAPACITY_MAIN, config.ACCOUNTABILITY_MAIN,
                   "elec_access_change"]:
        means = panel.groupby("iso3c")[column].transform("mean")
        within = (panel[column] - means).std()
        between = panel.groupby("iso3c")[column].mean().std()
        ratio = between / within if within else float("nan")
        print(f"  {column:<20} within {within:7.3f}  between {between:7.3f}  "
              f"between/within {ratio:5.2f}x")
    print("  (a high ratio means a variable barely moves within a country, so "
          "fixed effects identify its coefficient weakly)")

    print("\ncorrelation of the capacity measures, to see how much the "
          "rebuild changed:")
    capacity = panel[["spi_overall", "spi_rebuilt", "spi_rebuilt_no_cpiby",
                      "spi_p4_sources"]].corr()
    print(capacity.to_string(float_format=lambda v: f"{v:6.3f}"))

    print(f"\nrebasing events in the panel: "
          f"{int(panel['rebased'].sum())} across "
          f"{panel.loc[panel['rebased'] == 1, 'iso3c'].nunique()} countries")

    print("\nthe case studies, assembled:")
    cases = panel[panel["iso3c"].isin(config.CASE_STUDIES)].sort_values(
        ["iso3c", "year"])
    columns = ["iso3c", "year", "gdp_growth", "d_ln_gdp", "d_ln_lights",
               config.OUTCOME_SIGNED, "spi_overall", "spi_rebuilt",
               "v2x_accountability", "elec_access", "covid_stringency",
               "rebased"]
    print(cases[columns].to_string(index=False,
                                   float_format=lambda v: f"{v:7.3f}"))

    print("\nspot-checks against the brief:")
    expected = {
        ("GHA", 2016, "gdp_growth"): 3.37,
        ("GHA", 2021, "gdp_growth"): 5.08,
        ("KEN", 2020, "gdp_growth"): -0.27,
        ("KEN", 2021, "gdp_growth"): 7.59,
        ("GHA", 2021, "elec_access"): 86.3,
        ("KEN", 2021, "elec_access"): 76.5,
        ("GHA", 2016, "v2x_accountability"): 1.36,
        ("KEN", 2016, "v2x_accountability"): 0.96,
        ("GHA", 2020, "covid_stringency"): 42.5,
        ("KEN", 2020, "covid_stringency"): 58.0,
    }
    for (iso, year, column), want in expected.items():
        rows = panel[(panel["iso3c"] == iso) & (panel["year"] == year)]
        got = float(rows[column].iloc[0]) if len(rows) else float("nan")
        verdict = "MATCH" if abs(got - want) < 0.05 else "CHECK"
        print(f"  {iso} {column} {year}: {got:.2f} (brief says {want}) "
              f"{verdict}")


def compare_with_draft(panel: pd.DataFrame) -> None:
    """Compare against the earlier draft panel, if it was ever uploaded.

    A cross-check only, never an input. A difference needs explaining, not
    overwriting.
    """
    print("\n--- cross-check against the earlier draft panel ---")
    if not config.DRAFT_PANEL_FILE.exists():
        print(f"  {config.DRAFT_PANEL_FILE.name} is not in data/raw/, so this "
              "cross-check did not run.")
        print("  Not a failure: the draft was never uploaded. Worth doing if "
              "it turns up, since it would be a fully independent check of "
              "the merge.")
        return

    draft = pd.read_csv(config.DRAFT_PANEL_FILE)
    print(f"  draft: {len(draft)} rows, {draft['iso3c'].nunique()} countries")
    shared = [c for c in draft.columns
              if c in panel.columns and c not in ("iso3c", "year")]
    merged = panel.merge(draft, on=["iso3c", "year"], how="inner",
                         suffixes=("", "_draft"))
    print(f"  {len(merged)} country-years in common, comparing "
          f"{len(shared)} columns")
    for column in shared:
        other = merged[f"{column}_draft"]
        if not pd.api.types.is_numeric_dtype(merged[column]):
            continue
        diff = (merged[column] - other).abs()
        worst = diff.max()
        verdict = "same" if worst < 1e-6 else f"DIFFERS by up to {worst:.4f}"
        print(f"    {column:<22} {verdict}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--interim-dir", type=Path, default=None)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()

    if args.interim_dir is not None and args.out_dir is None \
            and not args.no_write:
        raise SystemExit(
            "--interim-dir was given without --out-dir or --no-write."
        )

    interim_dir = (config.DATA_INTERIM if args.interim_dir is None
                   else args.interim_dir)

    print("--- reading the interim tables ---")
    sources = {
        name: load_source(name, filename, interim_dir)
        for name, filename in {**LEVEL_SOURCES, **GROWTH_SOURCES}.items()
    }

    print("\n--- merging on the levels grid (2015-2021) ---")
    panel = build_grid()
    for name in LEVEL_SOURCES:
        panel = merge_source(panel, sources[name], name)

    panel = add_derived_variables(panel)
    check_recomputed_growth(panel, interim_dir)

    print(f"\n--- cutting to the growth years "
          f"({min(config.YEARS_GROWTH)}-{max(config.YEARS_GROWTH)}) ---")
    before = len(panel)
    panel = panel[panel["year"].isin(config.YEARS_GROWTH)].copy()
    print(f"  {before} -> {len(panel)} rows "
          f"(dropped {min(config.YEARS_LEVELS)}, the base year)")

    print("\n--- merging the sources defined on the growth years ---")
    for name in GROWTH_SOURCES:
        panel = merge_source(panel, sources[name], name)

    panel, dropped = select_sample(panel)
    check_panel(panel, dropped)
    report_panel(panel)
    compare_with_draft(panel)

    if args.no_write:
        print("\n--no-write: every check ran, nothing was written.")
        return

    out_dir = args.out_dir if args.out_dir is not None else config.DATA_PROCESSED
    out_dir.mkdir(parents=True, exist_ok=True)
    panel_path = out_dir / config.PANEL_FILE.name
    panel.to_csv(panel_path, index=False)
    print(f"\nwritten to {panel_path}")

    tables_dir = (config.OUTPUTS_TABLES if args.out_dir is None
                  else args.out_dir)
    tables_dir.mkdir(parents=True, exist_ok=True)
    dropped_path = tables_dir / config.DROPPED_COUNTRIES_FILE.name
    dropped.to_csv(dropped_path, index=False)
    print(f"dropped-countries table written to {dropped_path}")


if __name__ == "__main__":
    main()
