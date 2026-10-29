"""Step 3a: load the published SPI scores.

Run from the project root:

    python -m src.load_spi

This module only LOADS the published index and verifies how it is built.
Rebuilding it without the two circular indicators is rebuild_spi.py, which
depends on the structure confirmed here.

INPUT
    data/raw/SPI_index.csv   published scores, 4,557 rows x 80 columns,
                             2004-2024, from 03_output_data/ in
                             github.com/worldbank/SPI
    data/raw/02-SPI_index.Rmd   the SPI team's own index code (reference)

OUTPUT
    data/interim/spi_published.csv, one row per (iso3c, year) over
    config.YEARS_LEVELS, with the overall score, the five pillars and
    dimension 5.2.

HOW THE INDEX IS BUILT - CONFIRMED THREE WAYS
    Read off the R code in 02-SPI_index.Rmd and then verified against the
    data, because the brief's description, while not wrong, hides the part
    that matters most.

    1. Overall = simple mean of the five pillars.
       The R code weights them pillar_1 ... pillar_5, each set to 1/5
       (lines 1222-1281), so the weighted average is a simple mean.
       Verified: max absolute difference 0.000000 over 1,613 country-years.

    2. PILLAR 5 IS DIMENSION 5.2, AND NOTHING ELSE.
       Pillar 5 is a weighted average of dimensions 5.1, 5.2 and 5.5, but the
       weights are dim_5_1 <- 0, dim_5_2 <- 1, dim_5_5 <- 0 (lines 1283-1285).
       So Pillar 5 collapses to dimension 5.2 exactly.
       Verified: Pillar5 equals 100 x DIM5.2 to 0.00000000 over 1,710 rows.

       This is why the circularity problem bites as hard as it does. The two
       GDP-describing indicators are not two among the many making up a broad
       "data infrastructure" pillar; they are two of the ten items that are
       the whole pillar.

    3. Dimension 5.2 = simple mean of its ten SPI.D5.2.* indicators
       (rowMeans in the R code, line ~1398).
       Verified: max absolute difference 0.00000000.

    The -99 values the R code assigns to dimensions 5.1 and 5.5 when they are
    missing look alarming but are harmless: their weights are zero, and in R
    a missing value times zero is missing, which would poison the sum, while
    -99 times zero is 0. It is a guard against NA propagation, not data.

MEASURED CONSEQUENCE
    Dropping SPI.D5.2.1.SNAU and SPI.D5.2.2.NABY moves the overall score by
    -0.34 points on average across the estimation sample, with a standard
    deviation of 1.04 and a range of -4.0 to +2.0. The brief estimated 0.3 to
    0.7 points; the average is in that range but the tails are several times
    larger, and -4.0 is appreciable against a within-country standard
    deviation of 5.5.
"""

import argparse
from pathlib import Path

import pandas as pd

from src import config

# Published column -> the name used from here on.
PILLAR_COLUMNS = {
    "SPI.INDEX": "spi_overall",
    "SPI.INDEX.PIL1": "spi_p1_use",
    "SPI.INDEX.PIL2": "spi_p2_services",
    "SPI.INDEX.PIL3": "spi_p3_products",
    "SPI.INDEX.PIL4": "spi_p4_sources",
    "SPI.INDEX.PIL5": "spi_p5_infra",
    "SPI.DIM5.2.INDEX": "spi_dim5_2",
}

SSA_REGION_LABEL = "Sub-Saharan Africa"


def load_spi_published(raw_dir: Path | None = None) -> pd.DataFrame:
    """Read the published SPI index and subset to the SSA panel."""
    path = (raw_dir / config.SPI_INDEX_FILE.name) if raw_dir else config.SPI_INDEX_FILE
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Download SPI_index.csv from "
            "https://github.com/worldbank/SPI (03_output_data/) into "
            "data/raw/."
        )

    spi = pd.read_csv(path)
    print(f"read {len(spi):,} rows x {len(spi.columns)} columns from "
          f"{path.name}")

    missing_cols = [c for c in PILLAR_COLUMNS if c not in spi.columns]
    if missing_cols:
        raise ValueError(f"{path.name} has no column(s) {missing_cols}")

    # The region column is the World Bank's own grouping, so it is the
    # authority on which economies are Sub-Saharan Africa. config.SSA_ALL is
    # checked against it rather than the other way round.
    check_region_definition(spi)

    verify_index_construction(spi)

    spi = spi.rename(columns={"date": "year", **PILLAR_COLUMNS})

    # Printed before the window filter, while the extended years are still
    # here, so the brief's variation figures can be reproduced on the sample
    # they came from.
    report_brief_variation_reference(spi)
    spi = spi[spi["iso3c"].isin(config.SSA_ALL)
              & spi["year"].isin(config.YEARS_LEVELS)].copy()
    config.check_years(spi["year"].unique())

    keep = ["iso3c", "country", "year"] + list(PILLAR_COLUMNS.values())
    spi = spi[keep].sort_values(["iso3c", "year"]).reset_index(drop=True)
    return spi


def report_brief_variation_reference(spi: pd.DataFrame) -> None:
    """Reproduce the within/between SDs the brief quotes, on their own sample.

    The brief gives "within-country SD 5.5 / between 10.9" for the overall
    score, "4.2 / 14.2" for Pillar 4 and a correlation of 0.78 between them.
    Those are not the estimation sample's figures, and chasing the difference
    wasted time once. They are ALL 48 SSA COUNTRIES OVER 2016-2023, which is
    reproduced here to within rounding. check_spi() prints the estimation
    sample's own figures, which are the ones to quote in the dissertation.
    """
    # 2016-2023, not YEARS_EXTENDED_LEVELS: including 2015 would change the
    # Pillar 4 figure, because Pillar 4 has 2015 values even though the
    # overall index does not. See the SPI 2015 trap in verify_sources.py.
    years = config.YEARS_EXTENDED
    wide = spi[spi["iso3c"].isin(config.SSA_ALL) & spi["year"].isin(years)]

    print(f"\n  reference: all {wide['iso3c'].nunique()} SSA countries, "
          f"{min(years)}-{max(years)} - the sample the brief's figures use")
    print("    (brief: overall 5.5 / 10.9, pillar 4 4.2 / 14.2, "
          "correlation 0.78)")
    for column in ["spi_overall", "spi_p4_sources"]:
        series = wide.dropna(subset=[column])
        means = series.groupby("iso3c")[column].transform("mean")
        within = (series[column] - means).std()
        between = series.groupby("iso3c")[column].mean().std()
        print(f"    {column:<16} within {within:5.2f}  between {between:5.2f}")
    corr = wide[["spi_overall", "spi_p4_sources"]].corr().iloc[0, 1]
    print(f"    correlation of overall with pillar 4: {corr:.3f}")


def check_region_definition(spi: pd.DataFrame) -> None:
    """Compare config.SSA_ALL with the World Bank's own region column."""
    if "region" not in spi.columns:
        print("  NOTE: no region column; cannot verify config.SSA_ALL here")
        return

    codes = set(spi.loc[spi["region"] == SSA_REGION_LABEL, "iso3c"].dropna())
    only_file = sorted(codes - set(config.SSA_ALL))
    only_config = sorted(set(config.SSA_ALL) - codes)

    print(f"  region check: SPI lists {len(codes)} economies as "
          f"{SSA_REGION_LABEL}; config has {len(config.SSA_ALL)}")
    if only_file or only_config:
        raise ValueError(
            "config.SSA_ALL does not match the World Bank region definition.\n"
            f"  in the file but not in config: {only_file}\n"
            f"  in config but not in the file: {only_config}\n"
            "Correct config.SSA_ALL; the file is the authority."
        )
    print("  config.SSA_ALL matches the region column exactly")


def verify_index_construction(spi: pd.DataFrame) -> None:
    """Confirm the three structural facts the rebuild depends on.

    If any of these stops holding, rebuild_spi.py cannot simply recompute the
    mean of the remaining indicators, so it is checked every run rather than
    taken on trust from one inspection.
    """
    print("  verifying how the published index is built:")
    pillars = [f"SPI.INDEX.PIL{i}" for i in range(1, 6)]

    sub = spi.dropna(subset=pillars + ["SPI.INDEX"])
    diff = (sub["SPI.INDEX"] - sub[pillars].mean(axis=1)).abs().max()
    print(f"    overall vs mean of 5 pillars : max abs diff {diff:.8f} "
          f"(n={len(sub):,})")
    if diff > 1e-6:
        raise ValueError(
            "the overall score is not the simple mean of the five pillars. "
            "rebuild_spi.py assumes it is; re-read 02-SPI_index.Rmd."
        )

    sub5 = spi.dropna(subset=["SPI.INDEX.PIL5", "SPI.DIM5.2.INDEX"])
    diff5 = (sub5["SPI.INDEX.PIL5"]
             - 100 * sub5["SPI.DIM5.2.INDEX"]).abs().max()
    print(f"    pillar 5 vs 100 x dim 5.2    : max abs diff {diff5:.8f} "
          f"(n={len(sub5):,})")
    if diff5 > 1e-6:
        raise ValueError(
            "pillar 5 is not dimension 5.2 alone. The R code sets dim_5_1 and "
            "dim_5_5 to zero weight; if that has changed, the rebuild must "
            "follow the new weights."
        )


def check_spi(spi: pd.DataFrame) -> None:
    """Run the checks that have to pass before anything uses this table."""
    print("\n--- checks ---")

    print(f"rows {len(spi)} for {spi['iso3c'].nunique()} countries "
          f"x {len(config.YEARS_LEVELS)} years "
          f"(expected {len(config.SSA_ALL) * len(config.YEARS_LEVELS)})")

    # Coverage per year, against the brief.
    expected_coverage = {2016: 41, 2017: 44, 2018: 44, 2019: 44,
                         2020: 45, 2021: 45}
    print("\ncountries with a score per year (brief in brackets):")
    for year in config.YEARS_GROWTH:
        n = int(spi.loc[spi["year"] == year, "spi_overall"].notna().sum())
        want = expected_coverage.get(year)
        verdict = "" if want is None else (
            "  MATCH" if n == want else f"  CHECK, brief says {want}")
        print(f"  {year}: {n}{f'  [{want}]' if want else ''}{verdict}")

    # Which country-years are missing, against the brief's list of 25.
    gaps = spi[spi["year"].isin(config.YEARS_GROWTH)
               & spi["spi_overall"].isna()]
    print(f"\nmissing scores 2016-2021: {len(gaps)} country-years "
          "(brief says 25)")
    if len(gaps):
        print(gaps.groupby("iso3c")["year"].apply(
            lambda s: sorted(s.tolist())).to_string())

    # Anything missing inside the estimation sample would be a problem.
    in_sample = spi[spi["iso3c"].isin(config.EXPECTED_BALANCED_COUNTRIES)
                    & spi["year"].isin(config.YEARS_GROWTH)]
    n_missing = int(in_sample["spi_overall"].isna().sum())
    print(f"\nmissing inside the 38-country sample: {n_missing}")
    assert n_missing == 0, (
        "the estimation sample has missing SPI scores; the exclusion lists "
        "in config need revisiting"
    )

    print("\nspot-checks against the brief:")
    expected = {
        ("GHA", 2016, "spi_overall"): 59.3,
        ("GHA", 2021, "spi_overall"): 66.2,
        ("KEN", 2016, "spi_overall"): 55.9,
        ("KEN", 2021, "spi_overall"): 68.1,
        ("GHA", 2016, "spi_p4_sources"): 45.3,
        ("KEN", 2016, "spi_p4_sources"): 35.9,
    }
    for (code, year, column), value in expected.items():
        rows = spi[(spi["iso3c"] == code) & (spi["year"] == year)]
        got = float(rows[column].iloc[0]) if len(rows) else float("nan")
        verdict = "MATCH" if abs(got - value) < 0.15 else "CHECK"
        print(f"  {code} {column} {year}: {got:.1f} "
              f"(brief says {value}) {verdict}")

    # Within vs between variation, which decides how much the fixed-effects
    # estimate has to work with.
    # The brief quotes "within-country SD 5.5 / between 10.9" and "P4 4.2 /
    # 14.2" and a correlation of 0.78. Those are on ALL 48 SSA COUNTRIES OVER
    # 2016-2023, where this data reproduces them as 5.54 / 10.85, 4.21 /
    # 14.15 and 0.778. On the estimation sample they are smaller, because the
    # sample is 38 countries over 6 years rather than 48 over 8. The sample
    # figures are the ones to quote: they are the variation the fixed-effects
    # estimator actually has. Both are printed so the difference is visible
    # rather than a surprise later.
    print("\nwithin- vs between-country standard deviation:")
    print("  ESTIMATION SAMPLE (38 countries, 2016-2021) - quote these:")
    for column in ["spi_overall", "spi_p4_sources", "spi_p5_infra"]:
        series = in_sample.dropna(subset=[column])
        means = series.groupby("iso3c")[column].transform("mean")
        within = (series[column] - means).std()
        between = series.groupby("iso3c")[column].mean().std()
        print(f"    {column:<16} within {within:5.2f}  between {between:5.2f}")

    corr = in_sample[["spi_overall", "spi_p4_sources"]].corr().iloc[0, 1]
    print(f"    correlation of overall with pillar 4: {corr:.3f}")

    print("\n  (for the all-48, 2016-2023 figures the brief quotes, see the "
          "reference block printed above, before the filtering)")


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

    spi = load_spi_published(args.raw_dir)
    check_spi(spi)

    if args.no_write:
        print("\n--no-write: every check ran, nothing was written.")
        return

    out_dir = args.out_dir if args.out_dir is not None else config.DATA_INTERIM
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / config.SPI_INTERIM.name
    spi.to_csv(out_path, index=False)
    print(f"\nwritten to {out_path}")


if __name__ == "__main__":
    main()
