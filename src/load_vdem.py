"""Step 2: load the four V-Dem accountability measures.

Run from the project root:

    python -m src.load_vdem

INPUT
    data/raw/V-Dem-CY-Full+Others-v16.csv

    V-Dem v16 (published March 2026), Country-Year Full+Others. About 400 MB
    and roughly 4,000 columns covering 1789-2025. Only seven columns are
    needed, so the file must never be read in full.

    Identifiers (config.VDEM_ID_COLUMNS):
        country_name, country_text_id, year
    Indicators (config.VDEM_INDICATORS):
        v2x_accountability  overall, roughly -2 to +2
        v2x_veracc          vertical: elections, parties
        v2x_horacc          horizontal: courts, legislature, oversight bodies
        v2x_diagacc         diagonal: media, civil society, free expression

OUTPUT
    data/interim/vdem_accountability.csv, one row per (iso3c, year) for
    config.SSA_ALL over config.YEARS_LEVELS.

THE POINT OF THIS STEP IS usecols
    pandas.read_csv(..., usecols=[...]) parses only the named columns, so the
    400 MB file costs a few MB of memory instead of several GB. Reading it
    whole is the obvious way to do this and the one that will not work.

    The column names are checked against the file's header BEFORE the read,
    because usecols fails with an unhelpful error if a name is absent, and
    V-Dem does rename indicators between versions.

WHY country_text_id
    It already holds ISO3 codes, so it joins directly to the WDI table. The
    numeric country_id is V-Dem's own and would need a crosswalk.

EXCLUSIONS
    config.VDEM_EXCLUDE_CODES removes ZZB (Zanzibar) and SML (Somaliland).
    Both are in V-Dem's coverage of the region but are not WDI economies, so
    leaving them in would add rows that can never merge and would quietly
    inflate the country count.
"""

import argparse
import glob
from pathlib import Path

import pandas as pd

from src import config


def find_vdem_file(raw_dir: Path | None = None) -> Path:
    """Find the V-Dem country-year file, tolerating small naming differences."""
    directory = raw_dir if raw_dir is not None else config.DATA_RAW

    if config.VDEM_FILE.exists() and raw_dir is None:
        return config.VDEM_FILE

    # The exact name varies a little between downloads: "+Others" is
    # sometimes written "_Others", and the version may be capitalised.
    patterns = ["V-Dem-CY-Full*Others*.csv", "V-Dem-CY*.csv", "*V-Dem*CY*.csv"]
    for pattern in patterns:
        matches = sorted(glob.glob(str(directory / pattern)))
        if len(matches) == 1:
            return Path(matches[0])
        if len(matches) > 1:
            names = "\n  ".join(Path(m).name for m in matches)
            raise ValueError(
                f"{len(matches)} files match {pattern}; expected one:\n  {names}"
            )

    raise FileNotFoundError(
        f"no V-Dem country-year CSV in {directory}.\n"
        "Download 'Country-Year: V-Dem Full+Others' (CSV) v16 from "
        "https://v-dem.net/data/the-v-dem-dataset/ and unzip it into "
        "data/raw/."
    )


def check_columns_present(path: Path, wanted: list[str]) -> None:
    """Confirm every column we intend to read exists, before reading.

    usecols raises a bare "Usecols do not match columns" if a name is absent,
    which says nothing about which one. V-Dem does rename and retire
    indicators between versions, so this checks first and names the culprit.

    Reading with nrows=0 parses the header and no data, which is instant even
    on a 400 MB file.
    """
    header = pd.read_csv(path, nrows=0)
    available = set(header.columns)
    missing = [c for c in wanted if c not in available]
    if missing:
        raise ValueError(
            f"{path.name} has no column(s) {missing}. The file has "
            f"{len(available)} columns. Check the V-Dem codebook for this "
            "version: indicator names do change between releases."
        )
    print(f"  file has {len(available):,} columns; reading {len(wanted)}")


def load_vdem(raw_dir: Path | None = None) -> pd.DataFrame:
    """Read the accountability columns and subset to the SSA panel."""
    path = find_vdem_file(raw_dir)
    size_mb = path.stat().st_size / 1e6
    print(f"reading {path.name} ({size_mb:,.0f} MB)")

    wanted = config.VDEM_ID_COLUMNS + config.VDEM_INDICATORS
    check_columns_present(path, wanted)

    # usecols is what makes this feasible: only these columns are parsed.
    vdem = pd.read_csv(path, usecols=wanted)
    print(f"  read {len(vdem):,} rows x {len(vdem.columns)} columns "
          f"({vdem.memory_usage(deep=True).sum() / 1e6:.1f} MB in memory)")

    vdem = vdem.rename(columns={"country_text_id": "iso3c"})

    # Drop V-Dem's extra polities before anything counts countries.
    before = vdem["iso3c"].nunique()
    excluded = vdem[vdem["iso3c"].isin(config.VDEM_EXCLUDE_CODES)]
    if len(excluded):
        print(f"  dropping {sorted(excluded['iso3c'].unique())}: "
              f"{len(excluded)} rows "
              f"({', '.join(sorted(excluded['country_name'].unique()))})")
    vdem = vdem[~vdem["iso3c"].isin(config.VDEM_EXCLUDE_CODES)]
    print(f"  countries {before} -> {vdem['iso3c'].nunique()}")

    vdem = vdem[
        vdem["iso3c"].isin(config.SSA_ALL)
        & vdem["year"].isin(config.YEARS_LEVELS)
    ].copy()

    config.check_years(vdem["year"].unique())

    vdem = vdem[["iso3c", "country_name", "year"] + config.VDEM_INDICATORS]
    return vdem.sort_values(["iso3c", "year"]).reset_index(drop=True)


def check_vdem(vdem: pd.DataFrame) -> None:
    """Run the checks that have to pass before anything uses this table."""
    print("\n--- checks ---")

    expected_rows = len(config.SSA_ALL) * len(config.YEARS_LEVELS)
    print(f"rows {len(vdem)} for {vdem['iso3c'].nunique()} countries "
          f"x {len(config.YEARS_LEVELS)} years (expected {expected_rows})")

    found = set(vdem["iso3c"])
    missing = sorted(set(config.SSA_ALL) - found)
    if missing:
        print(f"WARNING: no V-Dem rows for {missing}. If these are in the "
              "estimation sample they must be resolved, not ignored.")
    else:
        print("every SSA country is present")

    for code in config.VDEM_EXCLUDE_CODES:
        assert code not in found, f"{code} should have been excluded"
    print(f"excluded codes absent: {config.VDEM_EXCLUDE_CODES}")

    print("\nmissing values by indicator:")
    for column in config.VDEM_INDICATORS:
        n_missing = int(vdem[column].isna().sum())
        countries = sorted(vdem.loc[vdem[column].isna(), "iso3c"].unique())
        shown = ", ".join(countries) if 0 < len(countries) <= 6 else (
            f"{len(countries)} countries" if countries else ""
        )
        print(f"  {column:<20} {n_missing:>4}  {shown}")

    # Spot-checks against the brief. These catch a wrong column or a wrong
    # country code in one go.
    print("\nspot-checks against the brief:")
    expected = [
        ("GHA", 2016, "v2x_accountability", 1.36),
        ("KEN", 2016, "v2x_accountability", 0.96),
    ]
    for code, year, column, value in expected:
        rows = vdem[(vdem["iso3c"] == code) & (vdem["year"] == year)]
        if not len(rows):
            print(f"  {code} {year}: no row")
            continue
        got = float(rows[column].iloc[0])
        verdict = "MATCH" if abs(got - value) < 0.02 else "CHECK"
        print(f"  {code} {column} {year}: {got:+.3f} "
              f"(brief says {value:+.2f}) {verdict}")

    # Within vs between variation. This matters for the write-up: with
    # between-variation several times larger, the fixed-effects estimate of
    # the accountability effect comes from a handful of large movers rather
    # than from the panel as a whole.
    print("\nwithin- vs between-country standard deviation "
          "(brief: overall 0.141 within, 0.667 between):")
    for column in config.VDEM_INDICATORS:
        country_means = vdem.groupby("iso3c")[column].transform("mean")
        within = (vdem[column] - country_means).std()
        between = vdem.groupby("iso3c")[column].mean().std()
        ratio = between / within if within else float("nan")
        print(f"  {column:<20} within {within:.3f}  between {between:.3f}  "
              f"ratio {ratio:.1f}x")

    # The largest movers, which the write-up has to name because they are
    # what identifies the coefficient under fixed effects.
    print("\nlargest changes in v2x_accountability over the period:")
    first, last = config.YEAR_LEVELS_START, config.YEAR_LEVELS_END
    wide = vdem.pivot(index="iso3c", columns="year",
                      values="v2x_accountability")
    if first in wide.columns and last in wide.columns:
        change = (wide[last] - wide[first]).dropna().sort_values()
        # Take the four largest falls and the four largest rises, but drop
        # duplicates: with fewer than eight countries the two ends overlap and
        # a country would otherwise be listed twice.
        movers = pd.concat([change.head(4), change.tail(4)])
        movers = movers[~movers.index.duplicated()]
        for code, delta in movers.items():
            print(f"  {code}: {delta:+.3f}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--raw-dir", type=Path, default=None,
        help="where the V-Dem CSV lives (default: data/raw)",
    )
    parser.add_argument(
        "--out-dir", type=Path, default=None,
        help="where to write the output (default: data/interim)",
    )
    parser.add_argument(
        "--no-write", action="store_true",
        help="run every check but write nothing",
    )
    args = parser.parse_args()

    # Same guard as load_wdi: reading from elsewhere almost always means a
    # test, and test output must not land where the real table belongs.
    if args.raw_dir is not None and args.out_dir is None and not args.no_write:
        raise SystemExit(
            "--raw-dir was given without --out-dir or --no-write.\n"
            "Refusing to write output read from a non-default directory into "
            f"{config.DATA_INTERIM}."
        )

    vdem = load_vdem(args.raw_dir)
    check_vdem(vdem)

    if args.no_write:
        print("\n--no-write: every check ran, nothing was written.")
        return

    out_dir = args.out_dir if args.out_dir is not None else config.DATA_INTERIM
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / config.VDEM_INTERIM.name
    vdem.to_csv(out_path, index=False)
    print(f"\nwritten to {out_path}")


if __name__ == "__main__":
    main()
