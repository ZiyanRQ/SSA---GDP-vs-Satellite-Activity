"""Step 3b: rebuild SPI without the two circular indicators, and build the
GDP rebasing dummy from the same raw column.

Run from the project root:

    python -m src.rebuild_spi

WHY REBUILD
    SPI dimension 5.2 contains two indicators that describe the GDP series
    itself:
        5.2.1 SNAU  which System of National Accounts is in use
                    (1 = SNA2008/ESA2010, 0.5 = SNA1993/ESA1995, 0 otherwise)
        5.2.2 NABY  how old the national accounts base year is
                    (1 = chained prices, 0.5 = base year within 10 years,
                     0 otherwise)
    So SPI falls mechanically as a base year ages and jumps back at rebasing,
    which is exactly when GDP figures are revised. Using that SPI to explain
    the GDP-lights gap would be circular.

THE STRUCTURE THIS RELIES ON (verified by load_spi.py on every run)
    overall    = simple mean of the five pillars
    pillar 5   = dimension 5.2 alone, because the R code sets the weights on
                 dimensions 5.1 and 5.5 to zero
    dim 5.2    = simple mean of its ten SPI.D5.2.* indicators

    So the rebuild is: recompute pillar 5 as the mean of the EIGHT remaining
    indicators, leave pillars 1 to 4 untouched, and take the mean of the five
    again.

    It also means the circularity is sharper than it first appears. The two
    indicators are not two among many in a broad "data infrastructure"
    pillar; they are two of the ten items that ARE the pillar.

INPUT
    data/interim/spi_published.csv  (from load_spi.py)
    data/raw/SPI_data.csv           indicator level, 4,557 x 117

OUTPUT
    data/interim/spi_rebuilt.csv    published and rebuilt scores side by side
    data/interim/rebasing_dummy.csv base year and rebasing flag per country-year

REPRODUCTION BEFORE SUBSTITUTION
    Pillar 5 is recomputed from the ten indicators and checked against the
    published pillar 5 BEFORE anything is dropped. If that does not match to
    floating-point noise, the rebuild stops: a difference afterwards could
    then be the drop or could be a mistake, and there would be no way to tell
    which.
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from src import config

# How close the reproduction must be to count as exact.
TOLERANCE = 1e-6


# ===========================================================================
# PART A: the rebuild
# ===========================================================================

def load_indicator_data(raw_dir: Path | None = None) -> pd.DataFrame:
    """Read the indicator-level SPI file."""
    path = (raw_dir / config.SPI_INDICATOR_FILE.name) if raw_dir \
        else config.SPI_INDICATOR_FILE
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Download SPI_data.csv from "
            "https://github.com/worldbank/SPI (03_output_data/)."
        )
    data = pd.read_csv(path, low_memory=False)
    print(f"read {len(data):,} rows x {len(data.columns)} columns from "
          f"{path.name}")
    return data.rename(columns={"date": "year"})


def dimension_52_indicators(data: pd.DataFrame) -> list[str]:
    """Return the SPI.D5.2.* indicator columns, sorted."""
    found = sorted(c for c in data.columns if c.startswith("SPI.D5.2"))
    if not found:
        raise ValueError("no SPI.D5.2.* indicators in the file")
    return found


def reproduce_pillar5(data: pd.DataFrame, published: pd.DataFrame,
                      indicators: list[str]) -> pd.DataFrame:
    """Recompute pillar 5 from its indicators and check it against published.

    This is the step that licenses everything after it. Until the published
    number can be reproduced from the parts, a change in the output cannot be
    attributed to dropping the two indicators rather than to an error here.
    """
    merged = published.merge(
        data[["iso3c", "year"] + indicators],
        on=["iso3c", "year"], how="left", validate="one_to_one",
    )

    # skipna=False so that a country-year missing any indicator reproduces as
    # missing rather than as the mean of whatever is present. See the note in
    # rebuild_scores: this is what keeps the rebuilt index on the same
    # country-years as the published one.
    merged["p5_reproduced"] = 100 * merged[indicators].mean(axis=1,
                                                            skipna=False)

    # The claim that makes skipna=False safe: the published Pillar 5 exists
    # exactly when all ten of its indicators do. Checked every run, because if
    # a future vintage publishes a pillar built on partial indicators, the
    # rebuild would start dropping country-years the published index keeps.
    mismatch = int((merged["spi_p5_infra"].notna()
                    != merged["p5_reproduced"].notna()).sum())
    print(f"\n  pillar 5 availability vs its indicators: {mismatch} "
          "country-year(s) where one exists without the other")
    if mismatch:
        raise ValueError(
            "the published pillar 5 is available on a different set of "
            "country-years than its own ten indicators. Re-read the R code "
            "before rebuilding: the index may now tolerate missing "
            "indicators, which changes what the rebuild should do."
        )

    comparable = merged.dropna(subset=["spi_p5_infra", "p5_reproduced"])
    diff = (comparable["spi_p5_infra"] - comparable["p5_reproduced"]).abs()
    print(f"\nreproducing pillar 5 from its {len(indicators)} indicators:")
    print(f"  compared on {len(comparable):,} country-years")
    print(f"  max absolute difference: {diff.max():.10f}")

    if diff.max() > TOLERANCE:
        worst = comparable.loc[diff.idxmax()]
        raise ValueError(
            f"pillar 5 does not reproduce from its indicators (max diff "
            f"{diff.max():.6f}, worst {worst['iso3c']} {worst['year']}: "
            f"published {worst['spi_p5_infra']:.4f} vs recomputed "
            f"{worst['p5_reproduced']:.4f}).\n"
            "Do not continue: any difference after dropping the two "
            "indicators could be the drop or could be this error, and there "
            "would be no way to tell which."
        )
    print("  reproduced exactly - the rebuild can proceed")

    # The overall score must also reproduce as the mean of the five pillars,
    # since that is the other half of the arithmetic the rebuild uses.
    pillars = ["spi_p1_use", "spi_p2_services", "spi_p3_products",
               "spi_p4_sources", "spi_p5_infra"]
    ok = merged.dropna(subset=pillars + ["spi_overall"])
    overall_diff = (ok["spi_overall"] - ok[pillars].mean(axis=1)).abs().max()
    print(f"  overall vs mean of five pillars: max abs diff "
          f"{overall_diff:.10f}")
    if overall_diff > TOLERANCE:
        raise ValueError("the overall score is not the mean of the pillars")

    return merged


def rebuild_scores(merged: pd.DataFrame, indicators: list[str]) -> pd.DataFrame:
    """Drop the circular indicators and recompute pillar 5 and the overall."""
    pillars_1_4 = ["spi_p1_use", "spi_p2_services", "spi_p3_products",
                   "spi_p4_sources"]

    variants = {
        "spi_rebuilt": config.SPI_DROP_INDICATORS,
        "spi_rebuilt_no_cpiby": (config.SPI_DROP_INDICATORS
                                 + config.SPI_DROP_INDICATORS_EXTRA),
    }

    for name, dropped in variants.items():
        missing = [d for d in dropped if d not in indicators]
        if missing:
            raise ValueError(
                f"cannot drop {missing}: not among the dimension 5.2 "
                f"indicators {indicators}. A name that does not exist would "
                "be dropped silently and this variant would be identical to "
                "the published score while appearing to be a real check."
            )
        keep = [c for c in indicators if c not in dropped]
        print(f"\n{name}: keeping {len(keep)} of {len(indicators)} "
              f"indicators, dropping {dropped}")

        # skipna=False is load-bearing, not a detail. With the default
        # skipna=True, a country-year missing a pillar still gets a score -
        # the mean of whatever pillars happen to be there - so the rebuilt
        # index would exist for countries the SPI team does not score at all
        # (CAF, COD, SYC) and for 2015, where there is no published index.
        # build_panel would then keep those countries on a capacity measure
        # this project invented. The rebuilt index must exist exactly where
        # the published one does.
        #
        # It costs nothing in reproduction: in this data the published score
        # exists if and only if all five pillars do, and Pillar 5 exists if
        # and only if all ten of its indicators do, so skipna=False gives the
        # identical answer wherever an answer is defined. Checked, not assumed.
        merged[f"{name}_p5"] = 100 * merged[keep].mean(axis=1, skipna=False)
        merged[name] = merged[pillars_1_4 + [f"{name}_p5"]].mean(
            axis=1, skipna=False)

        published_only = int((merged["spi_overall"].notna()
                              & merged[name].isna()).sum())
        rebuilt_only = int((merged["spi_overall"].isna()
                            & merged[name].notna()).sum())
        print(f"  availability vs the published score: "
              f"{published_only} published-but-not-rebuilt, "
              f"{rebuilt_only} rebuilt-but-not-published")
        if published_only or rebuilt_only:
            raise ValueError(
                f"{name} is available on a different set of country-years "
                "than the published index. The rebuild changes which "
                "indicators go into the score, never which country-years "
                "have one."
            )

    return merged


def report_rebuild_effect(merged: pd.DataFrame) -> None:
    """Say how much the rebuild moved the scores, and where."""
    print("\n--- effect of the rebuild ---")

    in_sample = merged[
        merged["iso3c"].isin(config.EXPECTED_BALANCED_COUNTRIES)
        & merged["year"].isin(config.YEARS_GROWTH)
    ].copy()

    for name in ["spi_rebuilt", "spi_rebuilt_no_cpiby"]:
        delta = (in_sample[name] - in_sample["spi_overall"]).dropna()
        corr = in_sample[["spi_overall", name]].corr().iloc[0, 1]
        print(f"\n{name} minus published, across the 38-country sample "
              f"(n={len(delta)}):")
        print(f"  mean {delta.mean():+.3f}  sd {delta.std():.3f}  "
              f"min {delta.min():+.3f}  max {delta.max():+.3f}")
        print(f"  correlation with the published score: {corr:.4f}")

    # Pillar 5 is where the whole change happens, so report it separately.
    p5_delta = (in_sample["spi_rebuilt_p5"]
                - in_sample["spi_p5_infra"]).dropna()
    print(f"\npillar 5 moves by: mean {p5_delta.mean():+.2f}  "
          f"sd {p5_delta.std():.2f}  "
          f"min {p5_delta.min():+.2f}  max {p5_delta.max():+.2f}")
    print("  (the overall score moves by a fifth of this, since the overall "
          "is the mean of five pillars)")

    print("\nthe case studies, published vs rebuilt:")
    for code in config.CASE_STUDIES:
        rows = in_sample[in_sample["iso3c"] == code].sort_values("year")
        print(f"\n  {code}:")
        print("    year  published  rebuilt   diff   P5 pub  P5 new  "
              "SNAU  NABY")
        for _, r in rows.iterrows():
            snau = r.get("SPI.D5.2.1.SNAU", np.nan)
            naby = r.get("SPI.D5.2.2.NABY", np.nan)
            print(f"    {int(r['year'])}   {r['spi_overall']:8.2f}  "
                  f"{r['spi_rebuilt']:7.2f}  {r['spi_rebuilt'] - r['spi_overall']:+5.2f}  "
                  f"{r['spi_p5_infra']:6.1f}  {r['spi_rebuilt_p5']:6.1f}  "
                  f"{snau:4.1f}  {naby:4.1f}")

    biggest = in_sample.reindex(
        (in_sample["spi_rebuilt"] - in_sample["spi_overall"]).abs()
        .sort_values(ascending=False).index
    ).head(8)
    print("\nlargest individual changes:")
    for _, r in biggest.iterrows():
        print(f"  {r['iso3c']} {int(r['year'])}: "
              f"{r['spi_overall']:.2f} -> {r['spi_rebuilt']:.2f} "
              f"({r['spi_rebuilt'] - r['spi_overall']:+.2f})")


# ===========================================================================
# PART B: the rebasing dummy
# ===========================================================================

def parse_base_year(value) -> tuple[float, str]:
    """Turn one raw base-year entry into (year, status).

    Status is one of "numeric", "converted", "chained" or "missing", so the
    output records how each value was arrived at rather than presenting a
    hand-conversion as though it were in the data.

    Raises on an unrecognised text value: a silent fallback would turn a
    base year nobody has looked at into a missing value, and the rebasing
    dummy would quietly lose an event.
    """
    if pd.isna(value):
        return np.nan, "missing"

    text = str(value).strip()

    # Plain year, possibly stored as a float like "2015.0".
    try:
        number = float(text)
        if 1900 <= number <= 2100:
            return float(int(number)), "numeric"
    except ValueError:
        pass

    if text in config.SPI_BASE_YEAR_CHAINED_VALUES:
        return np.nan, "chained"

    if text in config.SPI_BASE_YEAR_TEXT_FIXES:
        return float(config.SPI_BASE_YEAR_TEXT_FIXES[text]), "converted"

    raise ValueError(
        f"unrecognised base-year value {text!r}.\n"
        "Add it to config.SPI_BASE_YEAR_TEXT_FIXES (or "
        "SPI_BASE_YEAR_CHAINED_VALUES if it means chained prices). It is "
        "deliberately not guessed: a wrong conversion would move a rebasing "
        "event to the wrong year."
    )


def build_rebasing_dummy(data: pd.DataFrame) -> pd.DataFrame:
    """Build the country-year rebasing flag from RAW.D5.2.2.NABY."""
    column = config.SPI_BASE_YEAR_COLUMN
    if column not in data.columns:
        raise ValueError(f"no {column} column in the indicator file")

    base = data[data["iso3c"].isin(config.SSA_ALL)][
        ["iso3c", "year", column]
    ].copy()

    parsed = base[column].apply(parse_base_year)
    base["base_year"] = [p[0] for p in parsed]
    base["base_year_status"] = [p[1] for p in parsed]

    print("\nhow each base-year value was read:")
    print(base["base_year_status"].value_counts().to_string())

    converted = base[base["base_year_status"] == "converted"]
    if len(converted):
        print("\nhand-converted text values:")
        for (iso, raw), group in converted.groupby(["iso3c", column]):
            years = sorted(group["year"].astype(int).tolist())
            shown = str(raw)[:60] + ("..." if len(str(raw)) > 60 else "")
            print(f"  {iso} {shown!r} -> "
                  f"{int(group['base_year'].iloc[0])}  (years {years})")

    chained = base[base["base_year_status"] == "chained"]
    if len(chained):
        print("\nchained-price countries (no fixed base year, so never "
              "'rebase'):")
        for iso, group in chained.groupby("iso3c"):
            print(f"  {iso}: {sorted(group['year'].astype(int).tolist())}")

    # A rebasing is a change in base year from the previous year. Sorting and
    # grouping by country first is essential, or the first year of one country
    # would compare against the last year of the one before it.
    base = base.sort_values(["iso3c", "year"])
    base["base_year_prev"] = base.groupby("iso3c")["base_year"].shift(1)
    base["rebased"] = (
        base["base_year"].notna()
        & base["base_year_prev"].notna()
        & (base["base_year"] != base["base_year_prev"])
    ).astype(int)

    # Base years should only move forward. One going backwards is a data
    # problem, so it is flagged and reported rather than silently counted.
    base["flag"] = ""
    backwards = (base["base_year"].notna() & base["base_year_prev"].notna()
                 & (base["base_year"] < base["base_year_prev"]))
    base.loc[backwards, "flag"] = "base year moves backwards"

    # Switching to chained prices is a real change to the national accounts,
    # but it is not a REBASING: there is no new base year, which is the whole
    # point of chaining. A chained country has base_year missing, so the
    # rebased test above gives 0 for the switch year. That is a judgement
    # call, so it is flagged and reported rather than left implicit, and the
    # flag makes it easy to run the alternative treatment if preferred.
    status_prev = base.groupby("iso3c")["base_year_status"].shift(1)
    into_chained = (base["base_year_status"] == "chained") & (
        status_prev.isin(["numeric", "converted"]))
    base.loc[into_chained, "flag"] = "switched to chained prices"

    base["rebased_source"] = np.where(base["rebased"] == 1, "SPI", "")

    # Official statistics-office release dates override SPI's reporting year.
    for (iso, year), value in config.REBASING_OVERRIDES.items():
        mask = (base["iso3c"] == iso) & (base["year"] == year)
        if not mask.any():
            print(f"  WARNING: override for {iso} {year} matches no row")
            continue
        was = int(base.loc[mask, "rebased"].iloc[0])
        base.loc[mask, "rebased"] = value
        base.loc[mask, "rebased_source"] = "official release date"
        print(f"\noverride applied: {iso} {year} rebased {was} -> {value} "
              "(official statistics-office release date)")

    return base


def check_rebasing(base: pd.DataFrame) -> None:
    """Check the rebasing flags against what the brief records."""
    print("\n--- rebasing checks ---")

    window = base[base["year"].isin(config.YEARS_GROWTH)]
    in_sample = window[window["iso3c"].isin(config.EXPECTED_BALANCED_COUNTRIES)]

    n_events = int(in_sample["rebased"].sum())
    n_countries = int(in_sample.loc[in_sample["rebased"] == 1,
                                    "iso3c"].nunique())
    print(f"rebasing events 2016-2021 in the 38-country sample: {n_events} "
          f"across {n_countries} countries")

    all_ssa = int(window["rebased"].sum())
    all_countries = int(window.loc[window["rebased"] == 1,
                                   "iso3c"].nunique())
    print(f"across all 48 SSA countries: {all_ssa} events in "
          f"{all_countries} countries")

    # RECONCILED AGAINST THE BRIEF, which reports three figures: 23 base-year
    # changes 2016-21 among its 40 countries, 28 events in 24 countries
    # 2016-22, and 24 countries across all 48 in 2016-21. All three are
    # reproduced exactly by counting the way the brief did - BEFORE the fixes
    # the brief itself lists as needed:
    #
    #   - the text base years (ETH, UGA, SDN) left unreadable rather than
    #     converted, and
    #   - no Kenya override for the KNBS September 2021 release date.
    #
    # The four extra events here are exactly ETH 2018, SDN 2018, UGA 2020 and
    # KEN 2021: the fixes, applied. So the higher count is the corrected one,
    # not a discrepancy to resolve. Quote these figures, not the brief's, and
    # say the counting rule.
    print("  (the brief's 23 / 28 / 24 are the same data counted before its "
          "own listed fixes:")
    print("   text base years unconverted and no Kenya release-date override. "
          "The four")
    print("   extra events here are ETH 2018, SDN 2018, UGA 2020, KEN 2021 - "
          "the fixes.)")

    backwards = base[base["flag"] == "base year moves backwards"]
    if len(backwards):
        print("\nflagged as moving backwards (probable data errors, counted "
              "but marked):")
        for _, r in backwards.iterrows():
            print(f"  {r['iso3c']} {int(r['year'])}: "
                  f"{int(r['base_year_prev'])} -> {int(r['base_year'])}")

    chained_switch = base[base["flag"] == "switched to chained prices"]
    if len(chained_switch):
        print("\nswitched to chained prices, NOT counted as a rebasing "
              "(there is no new base year, which is the point of chaining):")
        for _, r in chained_switch.iterrows():
            prev = ("" if pd.isna(r["base_year_prev"])
                    else int(r["base_year_prev"]))
            print(f"  {r['iso3c']} {int(r['year'])}: base year {prev} -> "
                  "chained")
        print("  This is a judgement call. If a switch to chaining should "
              "count as a national-accounts revision, the flag column makes "
              "it straightforward to set those rows to 1.")
    for iso, year in config.REBASING_SUSPECT:
        hit = backwards[(backwards["iso3c"] == iso)
                        & (backwards["year"] == year)]
        print(f"  {iso} {year} expected to be flagged: "
              f"{'yes' if len(hit) else 'NO - check the data'}")

    print("\nthe case studies:")
    for code in config.CASE_STUDIES:
        rows = base[(base["iso3c"] == code)
                    & base["year"].isin(config.YEARS_GROWTH)].sort_values("year")
        for _, r in rows.iterrows():
            by = "" if pd.isna(r["base_year"]) else str(int(r["base_year"]))
            print(f"  {code} {int(r['year'])}: base year {by or '-':>6}  "
                  f"rebased {int(r['rebased'])}"
                  f"{'  [' + r['rebased_source'] + ']' if r['rebased_source'] else ''}")

    print("\nevery flagged rebasing year in the sample:")
    events = in_sample[in_sample["rebased"] == 1].sort_values(["iso3c", "year"])
    for _, r in events.iterrows():
        prev = "" if pd.isna(r["base_year_prev"]) else int(r["base_year_prev"])
        now = "" if pd.isna(r["base_year"]) else int(r["base_year"])
        print(f"  {r['iso3c']} {int(r['year'])}: {prev} -> {now}")


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

    published_path = config.SPI_INTERIM
    if not published_path.exists():
        raise FileNotFoundError(
            f"{published_path} not found. Run load_spi.py first: "
            "python -m src.load_spi"
        )
    published = pd.read_csv(published_path)
    print(f"read {len(published):,} published rows")

    data = load_indicator_data(args.raw_dir)
    indicators = dimension_52_indicators(data)
    print(f"dimension 5.2 indicators ({len(indicators)}): {indicators}")

    merged = reproduce_pillar5(data, published, indicators)
    merged = rebuild_scores(merged, indicators)
    report_rebuild_effect(merged)

    base = build_rebasing_dummy(data)
    check_rebasing(base)

    if args.no_write:
        print("\n--no-write: every check ran, nothing was written.")
        return

    out_dir = args.out_dir if args.out_dir is not None else config.DATA_INTERIM
    out_dir.mkdir(parents=True, exist_ok=True)

    keep = (["iso3c", "year", "spi_overall", "spi_rebuilt",
             "spi_rebuilt_no_cpiby", "spi_p4_sources", "spi_p5_infra",
             "spi_rebuilt_p5", "spi_rebuilt_no_cpiby_p5",
             "spi_p1_use", "spi_p2_services", "spi_p3_products"]
            + config.SPI_DROP_INDICATORS)
    rebuilt_path = out_dir / config.SPI_REBUILT_INTERIM.name
    merged[keep].to_csv(rebuilt_path, index=False)
    print(f"\nwritten to {rebuilt_path}")

    base_path = out_dir / config.REBASING_INTERIM.name
    base[["iso3c", "year", "base_year", "base_year_status", "base_year_prev",
          "rebased", "rebased_source", "flag"]].to_csv(base_path, index=False)
    print(f"written to {base_path}")


if __name__ == "__main__":
    main()
