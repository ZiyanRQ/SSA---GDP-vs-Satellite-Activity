"""Step 1: load the seven World Development Indicators series.

Run from the project root:

    python -m src.load_wdi

INPUT
    data/raw/API_<CODE>_DS2_en_csv_v2_*.csv, one file per indicator.

    These are the World Bank's bulk CSV downloads. They are WIDE: one row per
    country, one column per year, with a few lines of preamble before the real
    header row, roughly:

        "Data Source","World Development Indicators",
        [possibly blank]
        "Last Updated Date","2026-10-08",
        [possibly blank]
        "Country Name","Country Code","Indicator Name","Indicator Code","1960",...

    The trailing number in the filename changes with every download, so files
    are found by pattern (config.WDI_FILE_PATTERN), never by an exact name.

    Indicators (config.WDI_INDICATORS):
        NY.GDP.MKTP.KN       GDP, constant local currency (levels)
        NY.GDP.MKTP.KD.ZG    GDP growth, annual %
        NV.AGR.TOTL.ZS       Agriculture, value added, % of GDP
        EG.ELC.ACCS.ZS       Access to electricity, % of population
        SP.URB.TOTL.IN.ZS    Urban population, % of total
        SP.POP.TOTL          Total population
        NY.GDP.PETR.RT.ZS    Oil rents, % of GDP

OUTPUT
    data/interim/wdi_long.csv      one row per (iso3c, year), one column per
                                   indicator, for config.SSA_ALL over
                                   config.YEARS_LEVELS
    data/interim/wdi_vintage.csv   each file's "Last Updated Date", so the
                                   data vintage behind the results is on
                                   record rather than remembered

ON THE PREAMBLE LENGTH
    config.WDI_SKIPROWS records the expected four, but the loader does NOT
    rely on it: find_header_row locates the line that actually starts with
    "Country Name" and skips to there, printing a note if that differs from
    the config value.

    This is deliberate. A skip that is wrong by one does not fail. pandas
    takes the first data row as the header instead, so the columns become one
    country's values, and every later step runs happily on a table that is
    quietly wrong. The number of preamble lines has varied between World Bank
    releases, so detecting it is safer than asserting it.

WHY GDP LEVELS AS WELL AS GROWTH
    The gap measure needs log differences of the constant-LCU level
    (NY.GDP.MKTP.KN), not the published growth rate, so that GDP and lights
    are both log changes and can be subtracted. KD.ZG is loaded as a
    cross-check: the two should agree almost exactly, and where they do not,
    something has happened to the level series (a currency redenomination, for
    instance).
"""

import argparse
import glob
from pathlib import Path

import numpy as np
import pandas as pd

from src import config

# The four identifying columns every WDI bulk download starts with.
WDI_ID_COLUMNS = ["Country Name", "Country Code", "Indicator Name",
                  "Indicator Code"]


def find_wdi_file(code: str, raw_dir: Path | None = None) -> Path:
    """Find the one WDI file for an indicator code, or raise.

    Finding zero files, or more than one, is an error either way: a second
    match would mean two downloads are present and choosing between them
    would be arbitrary.
    """
    directory = raw_dir if raw_dir is not None else config.DATA_RAW
    pattern = config.WDI_FILE_PATTERN.format(code=code)
    matches = sorted(glob.glob(str(directory / pattern)))

    if not matches:
        raise FileNotFoundError(
            f"no WDI file for {code}: nothing matched {pattern} in "
            f"{directory}.\nDownload it from "
            f"https://data.worldbank.org/indicator/{code} (CSV) and unzip it "
            "into data/raw/."
        )
    if len(matches) > 1:
        names = "\n  ".join(Path(m).name for m in matches)
        raise ValueError(
            f"{len(matches)} files match {pattern}; expected one. Remove the "
            f"downloads you are not using:\n  {names}"
        )
    return Path(matches[0])


def read_last_updated(path: Path, max_scan: int = 12) -> str:
    """Read the 'Last Updated Date' out of a WDI file's preamble.

    This is the data vintage. Recording it is what makes a result
    reproducible: the same indicator downloaded six months later can carry
    revised numbers under the same filename.

    Scans a few lines rather than a fixed number, for the same reason
    find_header_row does: the preamble layout has varied between releases.
    """
    with open(path, "r", encoding="utf-8-sig") as handle:
        for i, line in enumerate(handle):
            if i > max_scan:
                break
            if "Last Updated Date" in line:
                # The line looks like: "Last Updated Date","2026-10-08",
                parts = [p.strip().strip('"') for p in line.split(",")]
                for part in parts:
                    if part and part != "Last Updated Date":
                        return part
    return "unknown"


def find_header_row(path: Path, max_scan: int = 12) -> int:
    """Return how many rows to skip so that the WDI header becomes the header.

    config.WDI_SKIPROWS records the expected number, but the preamble has
    varied between World Bank releases (whether there are blank lines between
    the two metadata lines, in particular). Rather than trust a constant, this
    looks for the line that actually begins with "Country Name".

    That matters because a skip that is wrong by one does not fail: pandas
    takes the first data row as the header instead, and every later step
    carries on with a table whose columns are a country's values.
    """
    with open(path, "r", encoding="utf-8-sig") as handle:
        for i, line in enumerate(handle):
            if line.lstrip().lstrip('"').startswith("Country Name"):
                return i
            if i >= max_scan:
                break
    raise ValueError(
        f"{path.name}: no header row starting with \"Country Name\" in the "
        f"first {max_scan} lines. Is this a World Bank bulk CSV download?"
    )


def read_wdi_csv(path: Path, code: str, column_name: str) -> pd.DataFrame:
    """Read one WDI file and return it in long form.

    Long form means one row per (country, year) rather than one row per
    country with a column per year. Every later step joins on (iso3c, year),
    so the data has to be reshaped before it can be merged with anything.
    """
    skiprows = find_header_row(path)
    if skiprows != config.WDI_SKIPROWS:
        print(f"    NOTE: {path.name} has {skiprows} preamble lines, not the "
              f"{config.WDI_SKIPROWS} in config. Using {skiprows}.")

    frame = pd.read_csv(path, skiprows=skiprows)

    # Belt and braces: confirm the detected header really is the WDI header.
    missing = [c for c in WDI_ID_COLUMNS if c not in frame.columns]
    if missing:
        raise ValueError(
            f"{path.name}: after skipping {skiprows} rows the columns are "
            f"{list(frame.columns)[:6]}..., which is missing {missing}."
        )

    # Confirm the file holds the indicator we asked for. Downloads do get
    # misnamed, and a mismatch here would silently load the wrong series.
    codes_present = set(frame["Indicator Code"].dropna().unique())
    if codes_present != {code}:
        raise ValueError(
            f"{path.name} should contain only {code} but holds "
            f"{sorted(codes_present)}"
        )

    # Year columns are the ones whose name is four digits.
    year_columns = [c for c in frame.columns if c.strip().isdigit()]
    if not year_columns:
        raise ValueError(f"{path.name}: no year columns found")

    # melt turns the wide year columns into two columns: which year, and the
    # value. This is the reshape from wide to long.
    long = frame.melt(
        id_vars=["Country Code"],
        value_vars=year_columns,
        var_name="year",
        value_name=column_name,
    )
    long = long.rename(columns={"Country Code": "iso3c"})
    long["year"] = long["year"].astype(int)

    return long[["iso3c", "year", column_name]]


def load_wdi(raw_dir: Path | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Read all seven indicators and merge them into one long table."""
    # Start from the full grid of countries and years, built explicitly. If a
    # country-year is absent from every file, a grid still shows it as a row
    # with missing values, where an inner join would simply lose it.
    grid = pd.MultiIndex.from_product(
        [config.SSA_ALL, config.YEARS_LEVELS], names=["iso3c", "year"]
    ).to_frame(index=False)

    merged = grid
    vintages = []

    for code, column_name in config.WDI_INDICATORS.items():
        path = find_wdi_file(code, raw_dir)
        vintage = read_last_updated(path)
        long = read_wdi_csv(path, code, column_name)

        before = len(long)
        long = long[
            long["iso3c"].isin(config.SSA_ALL)
            & long["year"].isin(config.YEARS_LEVELS)
        ]

        merged = merged.merge(long, on=["iso3c", "year"], how="left",
                              validate="one_to_one")

        n_missing = int(merged[column_name].isna().sum())
        vintages.append({
            "indicator_code": code,
            "column": column_name,
            "last_updated": vintage,
            "file": path.name,
            "rows_in_file": before,
            "rows_kept": len(long),
            "missing_in_panel": n_missing,
        })
        print(f"  {code:<20} {column_name:<18} updated {vintage}  "
              f"missing {n_missing}")

    config.check_years(merged["year"].unique())
    return merged, pd.DataFrame(vintages)


def check_wdi(wdi: pd.DataFrame) -> None:
    """Run the checks that have to pass before anything uses this table."""
    print("\n--- checks ---")

    expected_rows = len(config.SSA_ALL) * len(config.YEARS_LEVELS)
    print(f"rows {len(wdi)} for {wdi['iso3c'].nunique()} countries "
          f"x {len(config.YEARS_LEVELS)} years (expected {expected_rows})")
    assert len(wdi) == expected_rows, "the panel is not the full grid"

    missing_codes = sorted(set(config.SSA_ALL) - set(wdi["iso3c"]))
    if missing_codes:
        print(f"WARNING: no WDI rows at all for {missing_codes}")

    # Missing values per indicator, against what the brief leads us to expect.
    print("\nmissing values by indicator (2015-2021, 48 countries):")
    expected_gaps = {
        "gdp_growth": "ERI, SSD",
        "agri_share": "ERI, SOM, SSD",
        "elec_access": "none",
        "urban_share": "none",
        "population": "none",
    }
    for column in config.WDI_INDICATORS.values():
        n_missing = int(wdi[column].isna().sum())
        countries = sorted(wdi.loc[wdi[column].isna(), "iso3c"].unique())
        note = expected_gaps.get(column, "")
        shown = ", ".join(countries) if len(countries) <= 6 else (
            f"{len(countries)} countries"
        )
        print(f"  {column:<18} {n_missing:>4}  {shown}"
              f"{'   (brief expects: ' + note + ')' if note else ''}")

    # Spot-checks against the figures in the brief. These catch a wrong
    # column, a wrong country code or a wrong vintage in one go.
    print("\nspot-checks against the brief:")
    expected = {
        ("GHA", "gdp_growth"): [3.37, 8.13, 6.20, 6.51, 0.51, 5.08],
        ("KEN", "gdp_growth"): [4.21, 3.84, 5.65, 5.11, -0.27, 7.59],
    }
    for (code, column), values in expected.items():
        actual = (
            wdi[(wdi["iso3c"] == code) & (wdi["year"].isin(config.YEARS_GROWTH))]
            .sort_values("year")[column].to_numpy()
        )
        close = np.allclose(actual, values, atol=0.02, equal_nan=False)
        print(f"  {code} {column} 2016-2021: "
              f"{', '.join(f'{v:.2f}' for v in actual)}")
        print(f"    brief says:            "
              f"{', '.join(f'{v:.2f}' for v in values)}  "
              f"{'MATCH' if close else 'MISMATCH'}")

    for code, year, value in [("GHA", 2015, 74.0), ("GHA", 2021, 86.3),
                              ("KEN", 2015, 41.6), ("KEN", 2021, 76.5)]:
        actual = wdi.loc[(wdi["iso3c"] == code) & (wdi["year"] == year),
                         "elec_access"]
        got = float(actual.iloc[0]) if len(actual) else float("nan")
        print(f"  {code} elec_access {year}: {got:.1f} "
              f"(brief says {value}) {'MATCH' if abs(got - value) < 0.3 else 'CHECK'}")


def check_growth_against_levels(wdi: pd.DataFrame) -> pd.DataFrame:
    """Compare WDI's published growth rate with growth computed from levels.

    This matters because the gap measure uses log differences of the
    constant-LCU level, not the published percentage. If the two disagree for
    a country, something has happened to its level series - a currency
    redenomination is the usual cause - and its log differences cannot be
    trusted.
    """
    frame = wdi.sort_values(["iso3c", "year"]).copy()
    # Lag within country: on a plain sorted frame the first year of one
    # country would difference against the last year of the one before it.
    frame["gdp_prev"] = frame.groupby("iso3c")["gdp_real_lcu"].shift(1)
    frame["growth_from_levels"] = 100 * (
        frame["gdp_real_lcu"] / frame["gdp_prev"] - 1
    )
    frame["growth_difference"] = frame["gdp_growth"] - frame["growth_from_levels"]

    comparable = frame.dropna(subset=["growth_difference"])
    print("\n--- published growth vs growth computed from levels ---")
    print(f"comparable country-years: {len(comparable)}")
    print(f"max absolute difference:  "
          f"{comparable['growth_difference'].abs().max():.4f} pp")
    print(f"median absolute difference: "
          f"{comparable['growth_difference'].abs().median():.4f} pp")

    worst = comparable.reindex(
        comparable["growth_difference"].abs().sort_values(ascending=False).index
    ).head(8)
    print("\nlargest disagreements (a currency break would show up here):")
    print(worst[["iso3c", "year", "gdp_growth", "growth_from_levels",
                 "growth_difference"]].round(3).to_string(index=False))

    return frame


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--raw-dir", type=Path, default=None,
        help="where the WDI CSVs live (default: data/raw)",
    )
    parser.add_argument(
        "--out-dir", type=Path, default=None,
        help="where to write the output (default: data/interim)",
    )
    parser.add_argument(
        "--no-write", action="store_true",
        help="run every check but write nothing, for testing the loader "
             "against sample files without touching data/interim",
    )
    args = parser.parse_args()

    # Reading from somewhere other than data/raw almost always means this is
    # a test against sample files. Writing the result into data/interim would
    # leave test output sitting exactly where the real table belongs, where a
    # later step would pick it up without complaint.
    if args.raw_dir is not None and args.out_dir is None and not args.no_write:
        raise SystemExit(
            "--raw-dir was given without --out-dir or --no-write.\n"
            "Refusing to write output read from a non-default directory into "
            f"{config.DATA_INTERIM}, because test data would then look like "
            "the real thing. Pass --no-write to check only, or --out-dir to "
            "send the result somewhere else."
        )

    print("reading WDI files:")
    wdi, vintages = load_wdi(args.raw_dir)

    # Every file should carry the same vintage; a mixed set means the
    # downloads come from different days and may not be mutually consistent.
    distinct = sorted(vintages["last_updated"].unique())
    print(f"\nLast Updated Date: {distinct}")
    if len(distinct) > 1:
        print("WARNING: the files have different vintages. Re-download them "
              "together so every indicator comes from one release.")

    check_wdi(wdi)
    check_growth_against_levels(wdi)

    if args.no_write:
        print("\n--no-write: every check ran, nothing was written.")
        return

    out_dir = args.out_dir if args.out_dir is not None else config.DATA_INTERIM
    out_dir.mkdir(parents=True, exist_ok=True)
    wdi_path = out_dir / config.WDI_INTERIM.name
    vintage_path = out_dir / "wdi_vintage.csv"

    wdi.to_csv(wdi_path, index=False)
    vintages.to_csv(vintage_path, index=False)
    print(f"\nwritten to {wdi_path}")
    print(f"vintage record written to {vintage_path}")


if __name__ == "__main__":
    main()
