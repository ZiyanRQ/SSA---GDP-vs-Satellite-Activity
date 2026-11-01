"""Step 6a: audit the built panel value by value, against the interim files.

Run from the project root, after build_panel.py:

    python -m src.verify_panel

Exits 0 if every check passes and 1 if any fails.

WHY THIS EXISTS WHEN build_panel.py ALREADY CHECKS ITSELF
    build_panel checks row counts, merge indicators and missing values. Those
    cannot catch the one failure that matters most here: a merge that lines up
    the RIGHT NUMBER of rows against the WRONG KEYS. Every count would be
    correct and every value would belong to another country or another year.

    So this module takes a different route to the same numbers. It looks each
    value up in its source file by (iso3c, year), one at a time, and compares.
    It checks every country-year rather than a sample, because there are only
    228 and a sample would leave the question half-answered.

    It also proves the lags were taken WITHIN country. Shifting a sorted frame
    without grouping gives each country's first year the last year of the
    country before it, which produces a plausible wrong number rather than a
    missing one - the kind of error that survives every count-based check. The
    output prints the boundary case explicitly: what the first year of a
    country reads, against what it would read if the shift had crossed over.
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from src import config

# Columns that should have been carried across from each source unchanged.
CARRIED = {
    "wdi_long.csv": ["gdp_real_lcu", "gdp_growth", "agri_share",
                     "elec_access", "urban_share", "population", "oil_rents"],
    "vdem_accountability.csv": ["v2x_accountability", "v2x_veracc",
                                "v2x_horacc", "v2x_diagacc"],
    "lights_country_year_raw.csv": ["lights_sum", "lights_sum_bright",
                                    "area_cells"],
    "spi_rebuilt.csv": ["spi_overall", "spi_rebuilt", "spi_rebuilt_no_cpiby",
                        "spi_p4_sources", "spi_p5_infra"],
    "oxcgrt_annual.csv": ["covid_stringency"],
    "rebasing_dummy.csv": ["rebased", "base_year"],
}

# Ranges a value must fall in to be believable. Not a statistical test: a
# percentage outside 0-100 or a negative population is a wiring mistake.
RANGES = {
    "spi_overall": (0, 100), "spi_rebuilt": (0, 100),
    "spi_rebuilt_no_cpiby": (0, 100), "spi_p4_sources": (0, 100),
    "spi_p5_infra": (0, 100), "covid_stringency": (0, 100),
    "elec_access": (0, 100), "urban_share": (0, 100),
    "agri_share": (0, 100), "oil_rents": (0, 100),
    "v2x_accountability": (-4, 4), "rebased": (0, 1),
}

failures = []


def check(label, condition, detail=""):
    if condition:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}")
        if detail:
            for line in str(detail).splitlines()[:10]:
                print(f"          {line}")
        failures.append(label)


def values_match(want, got) -> bool:
    """Compare one source value with one panel value, missing values included."""
    if pd.isna(want) and pd.isna(got):
        return True
    if pd.isna(want) != pd.isna(got):
        return False
    if isinstance(want, str) or isinstance(got, str):
        return want == got
    return abs(float(want) - float(got)) <= 1e-10


def check_carried_values(panel: pd.DataFrame, interim_dir: Path) -> None:
    """Every carried-across value, looked up in its source by key."""
    print("\n--- 1. carried-across values match their source, by key ---")
    for filename, columns in CARRIED.items():
        source = pd.read_csv(interim_dir / filename).set_index(
            ["iso3c", "year"])
        for column in columns:
            lookup = source[column]
            bad = []
            for _, row in panel.iterrows():
                want = lookup.get((row["iso3c"], row["year"]), np.nan)
                if not values_match(want, row[column]):
                    bad.append(f"{row['iso3c']} {row['year']}: source {want} "
                               f"vs panel {row[column]}")
            check(f"{filename}:{column} matches for all {len(panel)} rows",
                  not bad, "\n".join(bad[:6]))


def check_derived(panel: pd.DataFrame) -> None:
    """The derived variables must follow from the panel's own columns."""
    print("\n--- 2. derived variables follow from the columns beside them ---")
    identities = {
        "ln_population == log(population)":
            np.log(panel["population"]) - panel["ln_population"],
        "ln_lights == log(lights_sum)":
            np.log(panel["lights_sum"]) - panel["ln_lights"],
        f"{config.OUTCOME_SIGNED} == d_ln_gdp - d_ln_lights":
            panel["d_ln_gdp"] - panel["d_ln_lights"]
            - panel[config.OUTCOME_SIGNED],
        f"{config.OUTCOME_ABSOLUTE} == |{config.OUTCOME_SIGNED}|":
            panel[config.OUTCOME_SIGNED].abs() - panel[config.OUTCOME_ABSOLUTE],
        "gap_bright == d_ln_gdp - d_ln_lights_bright":
            panel["d_ln_gdp"] - panel["d_ln_lights_bright"]
            - panel["gap_bright"],
    }
    for label, difference in identities.items():
        check(label, bool(difference.abs().max() < 1e-12),
              f"max difference {difference.abs().max():.3e}")


def check_within_country_lags(panel: pd.DataFrame, interim_dir: Path) -> None:
    """Recompute every lag by explicit key lookup of the country's own year."""
    print("\n--- 3. lags were taken within country, not across the frame ---")
    wdi = pd.read_csv(interim_dir / "wdi_long.csv").set_index(
        ["iso3c", "year"])
    lights = pd.read_csv(
        interim_dir / "lights_country_year_raw.csv").set_index(
        ["iso3c", "year"])

    gdp, elec = wdi["gdp_real_lcu"], wdi["elec_access"]
    radiance = lights["lights_sum"]

    bad = {"d_ln_gdp": [], "d_ln_lights": [], "elec_access_change": []}
    for _, row in panel.iterrows():
        iso, year = row["iso3c"], row["year"]
        previous = (iso, year - 1)

        want = np.log(gdp[(iso, year)]) - np.log(gdp[previous])
        if abs(want - row["d_ln_gdp"]) > 1e-12:
            bad["d_ln_gdp"].append(f"{iso} {year}: {want} vs {row['d_ln_gdp']}")

        want = np.log(radiance[(iso, year)]) - np.log(radiance[previous])
        if abs(want - row["d_ln_lights"]) > 1e-12:
            bad["d_ln_lights"].append(
                f"{iso} {year}: {want} vs {row['d_ln_lights']}")

        want = elec[(iso, year)] - elec[previous]
        if abs(want - row["elec_access_change"]) > 1e-10:
            bad["elec_access_change"].append(
                f"{iso} {year}: {want} vs {row['elec_access_change']}")

    for column, problems in bad.items():
        check(f"{column} uses each country's own previous year", not problems,
              "\n".join(problems[:6]))

    # The boundary case, shown rather than asserted: what the first year of a
    # country reads, against what it would read if the shift had crossed into
    # the country listed before it.
    print("\n  the boundary case, for the first three countries' first year:")
    ordered = sorted(panel["iso3c"].unique())
    first_year = min(config.YEARS_GROWTH)
    for iso in ordered[:3]:
        position = ordered.index(iso)
        own = (np.log(gdp[(iso, first_year)])
               - np.log(gdp[(iso, first_year - 1)]))
        shown = panel.loc[(panel["iso3c"] == iso)
                          & (panel["year"] == first_year), "d_ln_gdp"].iloc[0]
        line = (f"    {iso} {first_year}: panel {shown:+.6f}, "
                f"own base {own:+.6f}")
        if position:
            neighbour = ordered[position - 1]
            crossed = (np.log(gdp[(iso, first_year)])
                       - np.log(gdp[(neighbour, max(config.YEARS_GROWTH))]))
            line += (f", would be {crossed:+.6f} using {neighbour} "
                     f"{max(config.YEARS_GROWTH)}")
        else:
            line += "  (first country, nothing before it)"
        print(line)


def check_shape_and_ranges(panel: pd.DataFrame) -> None:
    """Keys are unique, and every value is in a believable range."""
    print("\n--- 4. keys and ranges ---")
    check("no duplicate (iso3c, year)",
          not panel.duplicated(subset=["iso3c", "year"]).any())
    countries, n_rows = config.expected_sample()
    check(f"{n_rows} rows and {len(countries)} countries",
          len(panel) == n_rows
          and panel["iso3c"].nunique() == len(countries),
          f"got {len(panel)} rows, {panel['iso3c'].nunique()} countries")

    for column, (low, high) in RANGES.items():
        series = panel[column].dropna()
        check(f"{column} within [{low}, {high}]",
              bool(((series >= low) & (series <= high)).all()),
              f"min {series.min()}, max {series.max()}")
    check("lights_sum strictly positive", bool((panel["lights_sum"] > 0).all()))
    check("population strictly positive", bool((panel["population"] > 0).all()))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--panel", type=Path, default=None)
    parser.add_argument("--interim-dir", type=Path, default=None)
    args = parser.parse_args()

    panel_path = config.PANEL_FILE if args.panel is None else args.panel
    interim_dir = (config.DATA_INTERIM if args.interim_dir is None
                   else args.interim_dir)

    if not panel_path.exists():
        raise SystemExit(
            f"{panel_path} not found. Run `python -m src.build_panel` first."
        )

    panel = pd.read_csv(panel_path)
    print(f"auditing {panel_path.name}: {len(panel)} rows, "
          f"{panel['iso3c'].nunique()} countries, {len(panel.columns)} columns")

    check_carried_values(panel, interim_dir)
    check_derived(panel)
    check_within_country_lags(panel, interim_dir)
    check_shape_and_ranges(panel)

    print("\n" + "=" * 70)
    if failures:
        print(f"RESULT: {len(failures)} check(s) FAILED")
        for failure in failures:
            print(f"  - {failure}")
        print("Do not estimate on this panel until these are resolved.")
        sys.exit(1)
    print("RESULT: every value in the panel traces back to its source.")
    print("=" * 70)


if __name__ == "__main__":
    main()
