"""Step 5a: verify every interim table before build_panel.py merges them.

Run from the project root:

    python -m src.verify_sources

Exits 0 if every check passes and 1 if any fails, so it can be used as a gate
before building the panel.

WHY THIS MODULE EXISTS
    A merge is the step where mistakes stop looking like mistakes. A country
    code that differs by one character, a year stored as text, a duplicated
    key, a column that is missing for one country - the output still has the
    right number of columns and a plausible number of rows, and nothing
    complains. Every loader checks its own data, but nothing until now
    checked that the six tables fit TOGETHER.

WHAT IT CHECKS
    1. Every interim file exists and loads.
    2. The merge keys: iso3c is three capitals, year is an integer dtype, and
       no (iso3c, year) pair repeats.
    3. Country coverage is exactly config.SSA_ALL, both directions.
    4. Year coverage matches the strict timeline for each source.
    5. Every variable the main specification needs is non-missing across the
       38-country sample, over the window that source is defined on.
    6. Each excluded country still has the missing data it was excluded for,
       and none of the 38 has a problem that should have excluded it.
    7. WDI published growth equals growth recomputed from the levels.
    8. The lights growth rates equal the log differences of the levels they
       came from, and country area is constant across years.
    9. The rebasing dummy is 0/1 with no gaps.
   10. A dry-run merge produces exactly 38 countries x 6 years = 228 rows.

THE ONE TRAP THIS FOUND
    The published SPI overall index starts in 2016, but Pillars 1, 3 and 4
    carry 2015 values. So spi_published.csv has a 2015 row that is PARTLY
    filled. Merging SPI onto the 2015-2021 levels grid would hand the panel
    pillar values with no published overall index behind them. SPI is
    therefore merged on 2016-2021 only, which is also all the model needs:
    SPI enters as a level on the growth years and is never lagged or
    differenced.
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from src import config

# Sources, with the window each one is defined on. None means the file keeps
# its full source range and is filtered downstream.
SOURCES = {
    "wdi": ("wdi_long.csv", config.YEARS_LEVELS),
    "vdem": ("vdem_accountability.csv", config.YEARS_LEVELS),
    "spi_published": ("spi_published.csv", config.YEARS_LEVELS),
    "spi_rebuilt": ("spi_rebuilt.csv", config.YEARS_LEVELS),
    "oxcgrt": ("oxcgrt_annual.csv", config.YEARS_GROWTH),
    "lights_levels": ("lights_country_year_raw.csv", config.YEARS_LEVELS),
    "lights_growth": ("lights_country_year.csv", config.YEARS_GROWTH),
    "rebasing": ("rebasing_dummy.csv", None),
}

# Variables needed over 2015-2021, because growth rates are differenced out
# of them and so need 2015 as a base year.
NEEDED_LEVELS = {
    "wdi": ["gdp_real_lcu", "elec_access", "urban_share", "population",
            "agri_share"],
    "vdem": ["v2x_accountability"],
    "lights_levels": ["lights_sum", "lights_sum_bright"],
}

# Variables needed over 2016-2021 only. SPI is here, not above: see the
# docstring.
NEEDED_GROWTH = {
    "oxcgrt": ["covid_stringency"],
    "lights_growth": ["d_ln_lights", "d_ln_lights_bright"],
    "spi_published": ["spi_overall", "spi_p4_sources"],
    "spi_rebuilt": ["spi_rebuilt"],
}

# The order build_panel.py should merge in: levels on the full grid, then
# restrict to the growth years, then the rest.
MERGE_ON_LEVELS = ["wdi", "vdem", "lights_levels"]
MERGE_ON_GROWTH = ["spi_published", "spi_rebuilt", "oxcgrt", "lights_growth",
                   "rebasing"]


class Checker:
    """Collects pass/fail results so the run can exit non-zero at the end."""

    def __init__(self):
        self.failures = []

    def check(self, label, condition, detail=""):
        if condition:
            print(f"  PASS  {label}")
            return True
        print(f"  FAIL  {label}")
        if detail:
            for line in str(detail).splitlines():
                print(f"          {line}")
        self.failures.append(label)
        return False

    def note(self, text):
        print(f"  NOTE  {text}")


def load_frames(checker, interim_dir):
    """Read every interim table, failing loudly on a missing file."""
    print("\n--- 1. every interim file exists and loads ---")
    frames = {}
    for name, (filename, _) in SOURCES.items():
        path = interim_dir / filename
        if checker.check(f"{name}: {filename} exists", path.exists()):
            frames[name] = pd.read_csv(path)
    return frames


def check_keys(checker, frames):
    """The merge keys have to be clean or the merge is meaningless."""
    print("\n--- 2. merge keys ---")
    for name, frame in frames.items():
        if not checker.check(f"{name}: has iso3c and year",
                             {"iso3c", "year"}.issubset(frame.columns),
                             f"columns: {list(frame.columns)[:8]}"):
            continue

        # A year read as text merges against nothing and leaves an
        # all-missing column that looks like missing data.
        checker.check(f"{name}: year is an integer dtype",
                      pd.api.types.is_integer_dtype(frame["year"]),
                      f"dtype is {frame['year'].dtype}")

        codes = frame["iso3c"].astype(str)
        clean = codes.str.fullmatch(r"[A-Z]{3}")
        checker.check(f"{name}: every iso3c is three capitals",
                      bool(clean.all()),
                      f"bad: {sorted(codes[~clean].unique())[:10]}")

        # A duplicate key multiplies rows on the merge.
        dups = frame.duplicated(subset=["iso3c", "year"])
        checker.check(f"{name}: no duplicate (iso3c, year)", not dups.any(),
                      frame[dups][["iso3c", "year"]].to_string(index=False))


def check_coverage(checker, frames):
    """Country and year coverage, both directions."""
    print("\n--- 3. country coverage against config.SSA_ALL ---")
    expected = set(config.SSA_ALL)
    for name, frame in frames.items():
        if "iso3c" not in frame.columns:
            continue
        present = set(frame["iso3c"])
        extra = sorted(present - expected)
        absent = sorted(expected - present)
        checker.check(f"{name}: no country outside SSA_ALL", not extra,
                      f"extra: {extra}")
        checker.check(f"{name}: all {len(expected)} SSA countries present",
                      not absent, f"absent: {absent}")

    print("\n--- 4. year coverage and the strict timeline ---")
    for name, (_, years) in SOURCES.items():
        if name not in frames or "year" not in frames[name].columns:
            continue
        frame = frames[name]
        got = sorted(frame["year"].unique())
        if years is None:
            checker.note(f"{name}: years {min(got)}-{max(got)} "
                         "(full source range, filtered downstream)")
            continue
        checker.check(f"{name}: years are exactly {min(years)}-{max(years)}",
                      got == sorted(years), f"got {got}")
        n_expected = len(config.SSA_ALL) * len(years)
        checker.check(f"{name}: {n_expected} rows "
                      f"({len(config.SSA_ALL)} x {len(years)})",
                      len(frame) == n_expected, f"got {len(frame)} rows")


def check_sample_completeness(checker, frames):
    """Every variable the main model needs, present for all 38 countries."""
    print("\n--- 5. the 38-country balanced sample has no gaps ---")
    sample = sorted(config.EXPECTED_BALANCED_COUNTRIES)
    checker.check("config.EXPECTED_BALANCED_COUNTRIES has 38 countries",
                  len(sample) == 38, f"got {len(sample)}")

    for needed, years, label in [(NEEDED_LEVELS, config.YEARS_LEVELS,
                                  "2015-2021"),
                                 (NEEDED_GROWTH, config.YEARS_GROWTH,
                                  "2016-2021")]:
        for name, columns in needed.items():
            frame = frames[name]
            sub = frame[frame["iso3c"].isin(sample) & frame["year"].isin(years)]
            checker.check(f"{name}: {len(sample) * len(years)} rows for the 38 "
                          f"over {label}",
                          len(sub) == len(sample) * len(years),
                          f"got {len(sub)}")
            for column in columns:
                if column not in sub.columns:
                    checker.check(f"{name}: has column {column}", False)
                    continue
                n_missing = int(sub[column].isna().sum())
                who = sorted(sub.loc[sub[column].isna(), "iso3c"].unique())
                checker.check(f"{name}.{column}: no missing in the sample",
                              n_missing == 0,
                              f"{n_missing} missing, countries {who}")


def check_spi_2015_trap(checker, frames):
    """Confirm the SPI 2015 row is partly filled, so the trap stays visible.

    This is checked rather than just commented, because if a future SPI
    vintage fills in 2015 properly the right response is to reconsider
    merging SPI on the levels grid, not to leave a stale comment behind.
    """
    print("\n--- 5b. the SPI 2015 trap ---")
    spi = frames["spi_published"]
    sample = config.EXPECTED_BALANCED_COUNTRIES
    row_2015 = spi[spi["iso3c"].isin(sample) & (spi["year"] == 2015)]
    spi_columns = [c for c in spi.columns if c.startswith("spi_")]

    for column in spi_columns:
        n = int(row_2015[column].notna().sum())
        flag = "  <-- filled, and must not be used" if n else ""
        print(f"        {column:<18} {n:>3} of {len(sample)} filled in 2015"
              f"{flag}")

    checker.check("spi_overall is empty in 2015, so the index starts in 2016",
                  int(row_2015["spi_overall"].notna().sum()) == 0,
                  f"{int(row_2015['spi_overall'].notna().sum())} values found - "
                  "if a new vintage fills 2015, revisit the merge window")
    partly_filled = [c for c in spi_columns if c != "spi_overall"
                     and int(row_2015[c].notna().sum()) > 0]
    checker.check("some pillars ARE filled in 2015 (the trap is real)",
                  bool(partly_filled), f"filled: {partly_filled}")
    checker.note("SPI is therefore merged on 2016-2021 only "
                 "(see MERGE_ON_GROWTH)")


def check_exclusions(checker, frames):
    """Each dropped country still has the data problem it was dropped for."""
    print("\n--- 6. the exclusions still hold in the data ---")
    wdi, spi, ox = frames["wdi"], frames["spi_published"], frames["oxcgrt"]

    for code, reason in config.EXPECTED_DROPPED_REASONS.items():
        evidence = []
        w = wdi[(wdi["iso3c"] == code) & wdi["year"].isin(config.YEARS_LEVELS)]
        n = int(w["gdp_real_lcu"].isna().sum())
        if n:
            evidence.append(f"GDP missing x{n}")
        n = int(w["agri_share"].isna().sum())
        if n:
            evidence.append(f"agri_share missing x{n}")
        s = spi[(spi["iso3c"] == code) & spi["year"].isin(config.YEARS_GROWTH)]
        n = int(s["spi_overall"].isna().sum())
        if n:
            evidence.append(f"SPI missing x{n}")
        o = ox[(ox["iso3c"] == code) & ox["year"].isin(config.YEARS_GROWTH)]
        n = int(o["covid_stringency"].isna().sum())
        if n:
            evidence.append(f"stringency missing x{n}")

        checker.check(f"{code} excluded ({reason[:38]}) - evidence present",
                      bool(evidence),
                      "; ".join(evidence) or "NO MISSING DATA FOUND: this "
                      "country may no longer need excluding")

    print("\n   and the reverse: does any of the 38 have a disqualifying gap?")
    clean = True
    for code in config.EXPECTED_BALANCED_COUNTRIES:
        problems = []
        w = wdi[(wdi["iso3c"] == code) & wdi["year"].isin(config.YEARS_LEVELS)]
        for column in ["gdp_real_lcu", "elec_access", "population",
                       "urban_share", "agri_share"]:
            if w[column].isna().any():
                problems.append(f"{column} missing")
        s = spi[(spi["iso3c"] == code) & spi["year"].isin(config.YEARS_GROWTH)]
        if s["spi_overall"].isna().any():
            problems.append("SPI missing")
        o = ox[(ox["iso3c"] == code) & ox["year"].isin(config.YEARS_GROWTH)]
        if o["covid_stringency"].isna().any():
            problems.append("stringency missing")
        if problems:
            clean = False
            checker.check(f"{code} is in the sample but has {problems}", False)
    if clean:
        print("        none: all 38 are complete on the main variables")


def check_gdp(checker, frames):
    """Published growth must equal growth recomputed from the levels."""
    print("\n--- 7. GDP growth from levels, which is what the panel uses ---")
    wdi = frames["wdi"]
    sample = config.EXPECTED_BALANCED_COUNTRIES
    w = wdi[wdi["iso3c"].isin(sample)].sort_values(["iso3c", "year"]).copy()
    w["d_ln_gdp"] = (np.log(w["gdp_real_lcu"])
                     - np.log(w.groupby("iso3c")["gdp_real_lcu"].shift(1)))
    w["from_levels"] = 100 * (np.exp(w["d_ln_gdp"]) - 1)

    cmp = w[w["year"].isin(config.YEARS_GROWTH)].dropna(
        subset=["gdp_growth", "from_levels"])
    diff = (cmp["gdp_growth"] - cmp["from_levels"]).abs()
    checker.check(f"published growth equals growth from levels (n={len(cmp)})",
                  diff.max() < 0.005,
                  f"max abs diff {diff.max():.6f} pp")

    n_expected = len(sample) * len(config.YEARS_GROWTH)
    n_got = int(w.loc[w["year"].isin(config.YEARS_GROWTH),
                      "d_ln_gdp"].notna().sum())
    checker.check(f"d_ln_gdp exists for all {n_expected} sample country-years",
                  n_got == n_expected, f"got {n_got}")


def check_lights(checker, frames):
    """Lights growth must match the levels, and area must not move."""
    print("\n--- 8. lights: growth against the levels it came from ---")
    levels = frames["lights_levels"].sort_values(["iso3c", "year"]).copy()
    growth = frames["lights_growth"]

    for level_column, growth_column in [("lights_sum", "d_ln_lights"),
                                        ("lights_sum_bright",
                                         "d_ln_lights_bright")]:
        checker.check(f"no {level_column} is zero or negative "
                      "(a log would be undefined)",
                      bool((levels[level_column] > 0).all()),
                      levels.loc[levels[level_column] <= 0,
                                 ["iso3c", "year"]].to_string(index=False))
        levels["recomputed"] = levels.groupby("iso3c")[level_column].transform(
            lambda s: np.log(s).diff())
        merged = growth.merge(levels[["iso3c", "year", "recomputed"]],
                              on=["iso3c", "year"], how="left")
        diff = (merged[growth_column] - merged["recomputed"]).abs()
        checker.check(f"{growth_column} equals the log difference of "
                      f"{level_column} (n={len(merged)})",
                      diff.max() < 1e-9, f"max abs diff {diff.max():.3e}")

    # area_cells is the country's area, not a measurement. If it moves
    # between years, the boundary or the grid changed.
    spread = levels.groupby("iso3c")["area_cells"].agg(["min", "max"])
    spread["spread"] = spread["max"] - spread["min"]
    checker.check("area_cells is identical across years for every country",
                  bool((spread["spread"].abs() < 1e-6).all()),
                  spread[spread["spread"].abs() >= 1e-6].to_string())


def check_rebasing(checker, frames):
    """The rebasing dummy is a clean 0/1 over the sample."""
    print("\n--- 9. the rebasing dummy ---")
    reb = frames["rebasing"]
    sub = reb[reb["iso3c"].isin(config.EXPECTED_BALANCED_COUNTRIES)
              & reb["year"].isin(config.YEARS_GROWTH)]
    n_expected = len(config.EXPECTED_BALANCED_COUNTRIES) * len(
        config.YEARS_GROWTH)
    checker.check(f"rebasing: {n_expected} rows for the 38 over 2016-2021",
                  len(sub) == n_expected, f"got {len(sub)}")
    checker.check("rebasing: rebased is only 0 or 1",
                  set(sub["rebased"].dropna().unique()).issubset({0, 1}),
                  f"values {sorted(sub['rebased'].dropna().unique())}")
    checker.check("rebasing: no missing values in rebased",
                  int(sub["rebased"].isna().sum()) == 0)
    checker.note(f"{int(sub['rebased'].sum())} events in the sample across "
                 f"{sub.loc[sub['rebased'] == 1, 'iso3c'].nunique()} countries")
    for code in config.CASE_STUDIES:
        years = sorted(sub.loc[(sub["iso3c"] == code) & (sub["rebased"] == 1),
                               "year"].tolist())
        checker.note(f"{code} rebasing years in the sample: {years}")


def check_dry_run_merge(checker, frames):
    """Merge everything the way build_panel.py will, and count the rows."""
    print("\n--- 10. dry-run merge: does it give 38 x 6 = 228 rows? ---")
    panel = pd.MultiIndex.from_product(
        [config.SSA_ALL, config.YEARS_LEVELS], names=["iso3c", "year"]
    ).to_frame(index=False)

    for name in MERGE_ON_LEVELS:
        frame = frames[name].drop(columns=["country"], errors="ignore")
        before = len(panel)
        panel = panel.merge(frame, on=["iso3c", "year"], how="left",
                            suffixes=("", f"_{name}"))
        checker.check(f"merging {name} did not change the row count",
                      len(panel) == before, f"{before} -> {len(panel)}")

    growth = panel[panel["year"].isin(config.YEARS_GROWTH)].copy()
    for name in MERGE_ON_GROWTH:
        frame = frames[name].drop(columns=["country"], errors="ignore")
        before = len(growth)
        growth = growth.merge(frame, on=["iso3c", "year"], how="left",
                              suffixes=("", f"_{name}"))
        checker.check(f"merging {name} did not change the row count",
                      len(growth) == before, f"{before} -> {len(growth)}")

    balanced = growth[growth["iso3c"].isin(
        config.EXPECTED_BALANCED_COUNTRIES)]
    countries, n_rows = config.expected_sample()
    checker.check(f"the balanced sample is {n_rows} rows",
                  len(balanced) == n_rows, f"got {len(balanced)}")
    checker.check(f"the balanced sample is {len(countries)} countries",
                  balanced["iso3c"].nunique() == len(countries),
                  f"got {balanced['iso3c'].nunique()}")
    checker.check("the balanced sample is exactly the expected country list",
                  sorted(balanced["iso3c"].unique()) == sorted(countries),
                  f"unexpected: "
                  f"{sorted(set(balanced['iso3c']) ^ set(countries))}")
    per_country = balanced.groupby("iso3c").size()
    checker.check(f"every country has exactly {len(config.YEARS_GROWTH)} years",
                  bool((per_country == len(config.YEARS_GROWTH)).all()),
                  per_country[per_country != len(config.YEARS_GROWTH)
                              ].to_string())
    return balanced, panel


def show_case_studies(frames, balanced, panel):
    """Print the case studies end to end, as a human-readable sanity check.

    Not a pass/fail test: a check that the assembled numbers are the ones
    expected from the earlier stages, read by eye.
    """
    print("\n--- 11. case studies, assembled end to end ---")
    rows = balanced[balanced["iso3c"].isin(config.CASE_STUDIES)].copy()
    rows = rows.sort_values(["iso3c", "year"])

    rows["d_ln_gdp"] = np.nan
    for code in config.CASE_STUDIES:
        series = panel[panel["iso3c"] == code].sort_values("year")
        mapping = dict(zip(series["year"],
                           np.log(series["gdp_real_lcu"]).diff()))
        mask = rows["iso3c"] == code
        rows.loc[mask, "d_ln_gdp"] = rows.loc[mask, "year"].map(mapping)

    rows["gap"] = rows["d_ln_gdp"] - rows["d_ln_lights"]
    columns = ["iso3c", "year", "d_ln_gdp", "d_ln_lights", "gap",
               "spi_overall", "spi_rebuilt", "covid_stringency", "rebased"]
    print(rows[columns].to_string(index=False,
                                  float_format=lambda v: f"{v:8.3f}"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--interim-dir", type=Path, default=None,
                        help="read the interim tables from here instead")
    args = parser.parse_args()

    interim_dir = (config.DATA_INTERIM if args.interim_dir is None
                   else args.interim_dir)
    print(f"verifying the interim tables in {interim_dir}")

    checker = Checker()
    frames = load_frames(checker, interim_dir)
    if checker.failures:
        print("\nsome interim files are missing; run the loaders first.")
        sys.exit(1)

    check_keys(checker, frames)
    check_coverage(checker, frames)
    check_sample_completeness(checker, frames)
    check_spi_2015_trap(checker, frames)
    check_exclusions(checker, frames)
    check_gdp(checker, frames)
    check_lights(checker, frames)
    check_rebasing(checker, frames)
    balanced, panel = check_dry_run_merge(checker, frames)
    show_case_studies(frames, balanced, panel)

    print("\n" + "=" * 70)
    if checker.failures:
        print(f"RESULT: {len(checker.failures)} check(s) FAILED")
        for failure in checker.failures:
            print(f"  - {failure}")
        print("Do not build the panel until these are resolved.")
        sys.exit(1)
    print("RESULT: every check passed. The sources are ready to merge.")
    print("=" * 70)


if __name__ == "__main__":
    main()
