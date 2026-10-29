"""Step 4: turn daily COVID policy stringency into an annual country series.

Run from the project root:

    python -m src.load_oxcgrt

INPUT
    data/raw/OxCGRT_nat_latest.csv, from data/ in
    github.com/OxCGRT/covid-policy-tracker.
    202,819 daily national rows, 61 columns, 2020-01-01 to 2023-02-28.
    Column used: config.OXCGRT_STRINGENCY_COLUMN (StringencyIndex_Average,
    scale 0-100).

OUTPUT
    data/interim/oxcgrt_annual.csv, one row per (iso3c, year) over
    config.YEARS_GROWTH.

CONFIRMED BY READING THE FILE (not assumed)
    Every row is Jurisdiction == NAT_TOTAL, so there is no subnational data to
    filter out, but the filter is applied anyway: the file is regenerated
    upstream and a later version could add regions without warning.

    Coverage, in days with a stringency value:
        2020  366 days   2021  365 days   2022  365 days   2023  0
    2023 has 59 dated rows and NOT ONE stringency value, so there is nothing
    to average even partially.

    Of the 48 SSA countries, 44 appear. The four absent are COM, GNB, GNQ and
    STP. GNB and STP are why the balanced panel is 38 countries rather than
    40 (config.EXCLUDED_NO_COVID_DATA); COM and GNQ are already excluded for
    missing SPI data, so they cost nothing extra.

WHY ZERO AND NOT MISSING FOR 2016-2019
    There was no pandemic policy to measure, so zero is the true value.
    Leaving those years missing would drop them from the panel and destroy the
    balance, which would be an artefact of how the source is published rather
    than anything about the countries.
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from src import config

# Below this many days, a calendar-year mean is not comparable with a full
# year and should not be computed.
MIN_DAYS_FOR_ANNUAL_MEAN = 360


def load_oxcgrt(raw_dir: Path | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Read the daily file and return (annual means, coverage report)."""
    path = (raw_dir / config.OXCGRT_FILE.name) if raw_dir else config.OXCGRT_FILE
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Download OxCGRT_nat_latest.csv from "
            "https://github.com/OxCGRT/covid-policy-tracker (data/ folder) "
            "into data/raw/."
        )

    target = config.OXCGRT_STRINGENCY_COLUMN
    columns = ["CountryName", "CountryCode", "Jurisdiction", "Date", target]
    daily = pd.read_csv(path, usecols=columns, low_memory=False)
    print(f"read {len(daily):,} rows from {path.name}")

    if target not in daily.columns:
        raise ValueError(f"{path.name} has no column {target!r}")

    daily = daily[daily["Jurisdiction"] == "NAT_TOTAL"]
    print(f"  national rows: {len(daily):,}")

    # Date is an 8-digit integer (20200101). Casting to string first is
    # required: pandas now reads a bare integer with a format as an epoch.
    daily = daily.copy()
    daily["date"] = pd.to_datetime(daily["Date"].astype(str), format="%Y%m%d")
    daily["year"] = daily["date"].dt.year
    daily = daily.rename(columns={"CountryCode": "iso3c"})

    daily = daily[daily["iso3c"].isin(config.SSA_ALL)]
    print(f"  SSA rows: {len(daily):,} for "
          f"{daily['iso3c'].nunique()} countries")

    # Coverage first, so a short year is caught before it is averaged.
    coverage = (
        daily.groupby(["iso3c", "year"])
        .agg(days=("date", "nunique"),
             days_with_value=(target, lambda s: int(s.notna().sum())))
        .reset_index()
    )

    usable = coverage[coverage["days_with_value"] >= MIN_DAYS_FOR_ANNUAL_MEAN]
    short = coverage[coverage["days_with_value"] < MIN_DAYS_FOR_ANNUAL_MEAN]
    if len(short):
        by_year = short.groupby("year")["iso3c"].count()
        print(f"  country-years with fewer than {MIN_DAYS_FOR_ANNUAL_MEAN} "
              f"valued days, left missing rather than averaged:")
        for year, count in by_year.items():
            print(f"    {year}: {count} countries")

    annual = (
        daily.groupby(["iso3c", "year"])[target].mean()
        .reset_index()
        .rename(columns={target: "covid_stringency"})
    )
    # Keep only the country-years with enough days behind the mean.
    annual = annual.merge(
        usable[["iso3c", "year"]], on=["iso3c", "year"], how="inner"
    )

    return annual, coverage


def build_panel_series(annual: pd.DataFrame,
                       years: list[int] | None = None) -> pd.DataFrame:
    """Put the annual means onto the full country-year grid, zeroing pre-COVID.

    The grid is built explicitly so that a country-year with no stringency
    value is a row of missing data rather than an absent row, which is what
    lets build_panel.py see it.
    """
    target_years = years if years is not None else config.YEARS_GROWTH
    config.check_years(target_years, stage="growth")

    grid = pd.MultiIndex.from_product(
        [config.SSA_ALL, target_years], names=["iso3c", "year"]
    ).to_frame(index=False)

    panel = grid.merge(annual, on=["iso3c", "year"], how="left")

    # Pre-pandemic years are zero by construction, not missing. Only set them
    # where they are currently missing, so a real value is never overwritten.
    pre_covid = panel["year"].isin(config.OXCGRT_ZERO_YEARS)
    panel.loc[pre_covid & panel["covid_stringency"].isna(),
              "covid_stringency"] = 0.0
    print(f"\nset stringency to 0 for {int(pre_covid.sum())} pre-pandemic "
          f"country-years ({min(config.OXCGRT_ZERO_YEARS)}-"
          f"{max(config.OXCGRT_ZERO_YEARS)})")

    return panel.sort_values(["iso3c", "year"]).reset_index(drop=True)


def check_oxcgrt(panel: pd.DataFrame, coverage: pd.DataFrame) -> None:
    """Run the checks that have to pass before anything uses this table."""
    print("\n--- checks ---")

    missing_countries = sorted(
        panel.loc[panel["covid_stringency"].isna(), "iso3c"].unique()
    )
    print(f"countries with any missing stringency: {missing_countries}")

    # THE LOAD-BEARING CHECK: the 38-country sample exists because these two
    # have no data. If that ever stops being true, the sample should go back
    # to 40 and config.EXCLUDED_NO_COVID_DATA should be emptied.
    for code in config.COVID_MISSING_COUNTRIES:
        n_values = int(
            panel.loc[panel["iso3c"] == code, "covid_stringency"].notna().sum()
        )
        pre = len(config.OXCGRT_ZERO_YEARS)
        verdict = ("as expected: only the pre-pandemic zeros"
                   if n_values <= pre else
                   "UNEXPECTED: this country now has data, so the 38-country "
                   "sample should be revisited")
        print(f"  {code}: {n_values} non-missing values - {verdict}")

    in_sample = panel[panel["iso3c"].isin(config.EXPECTED_BALANCED_COUNTRIES)]
    n_missing = int(in_sample["covid_stringency"].isna().sum())
    print(f"\nmissing stringency inside the 38-country sample: {n_missing}")
    if n_missing:
        bad = in_sample[in_sample["covid_stringency"].isna()]
        print(bad.groupby("iso3c")["year"].apply(list).to_string())
    assert n_missing == 0, (
        "the estimation sample has missing stringency; it cannot enter the "
        "main model until this is resolved"
    )

    pre = panel[panel["year"].isin(config.OXCGRT_ZERO_YEARS)]
    assert (pre["covid_stringency"] == 0).all(), "a pre-COVID year is not zero"
    print(f"all {len(pre)} pre-pandemic country-years are exactly 0")

    print("\nspot-checks against the brief:")
    expected = {("GHA", 2020): 42.5, ("GHA", 2021): 42.8,
                ("KEN", 2020): 58.0, ("KEN", 2021): 56.1}
    for (code, year), value in expected.items():
        rows = panel[(panel["iso3c"] == code) & (panel["year"] == year)]
        got = float(rows["covid_stringency"].iloc[0]) if len(rows) else np.nan
        verdict = "MATCH" if abs(got - value) < 0.1 else "CHECK"
        print(f"  {code} {year}: {got:.1f} (brief says {value}) {verdict}")

    sample_mean = (
        panel[panel["iso3c"].isin(config.EXPECTED_BALANCED_COUNTRIES)
              & panel["year"].isin([2020, 2021])]
        .groupby("year")["covid_stringency"].mean().round(1)
    )
    print(f"  mean across the 38 (brief says 46.6 / 44.0 across its sample): "
          f"{sample_mean.to_dict()}")

    print("\ndays behind each annual mean, 2020-2022:")
    print(coverage[coverage["year"].isin([2020, 2021, 2022])]
          .groupby("year")["days_with_value"]
          .agg(["min", "median", "max", "count"]).to_string())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--raw-dir", type=Path, default=None)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()

    if args.raw_dir is not None and args.out_dir is None and not args.no_write:
        raise SystemExit(
            "--raw-dir was given without --out-dir or --no-write."
        )

    annual, coverage = load_oxcgrt(args.raw_dir)
    panel = build_panel_series(annual)
    check_oxcgrt(panel, coverage)

    if args.no_write:
        print("\n--no-write: every check ran, nothing was written.")
        return

    out_dir = args.out_dir if args.out_dir is not None else config.DATA_INTERIM
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / config.OXCGRT_INTERIM.name
    panel.to_csv(out_path, index=False)
    print(f"\nwritten to {out_path}")


if __name__ == "__main__":
    main()
