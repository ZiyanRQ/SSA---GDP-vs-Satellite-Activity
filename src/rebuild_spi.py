"""Step 3b: rebuild the SPI overall score without the two circular indicators,
and build the GDP rebasing dummy from the same raw column.

Not implemented yet. This docstring is the plan.

WHY
    SPI Pillar 5, dimension 5.2 contains two indicators that describe the GDP
    series itself:
        5.2.1 SNAU  which System of National Accounts is in use
                    (1 = SNA2008/ESA2010, 0.5 = SNA1993/ESA1995, 0 otherwise)
        5.2.2 NABY  how old the national accounts base year is
                    (1 = chained prices, 0.5 = base year within 10 years,
                     0 otherwise)
    So SPI falls mechanically as a base year ages and jumps back at rebasing,
    which is exactly when GDP figures are revised. Using that SPI to explain
    the GDP-lights gap would be circular. Dropping the two indicators gives a
    capacity measure that is independent of the GDP series.

    The magnitude is small but systematic: one 0.5 step moves the overall score
    by roughly 0.3-0.7 points, against a within-country standard deviation of
    5.5.

INPUT
    data/interim/spi_published.csv  (from load_spi.py)
    data/raw/SPI_data.csv           (indicator level)
    The weighting is taken from the SPI team's own R code,
    02_programs/02-SPI_index.Rmd in github.com/worldbank/SPI:
        dimension 5.2 = mean of its indicators          (around line 1398)
        pillar 5      = weighted average of dimensions  (around lines 1434-1442)
        overall       = mean of the 5 pillars

OUTPUT
    data/interim/spi_rebuilt.csv  columns: iso3c, year, spi_overall (published),
        spi_rebuilt (no SNAU, no NABY), spi_rebuilt_no_cpiby (extra robustness),
        spi_pillar4, and the five published pillars.
    data/interim/rebasing_dummy.csv  columns: iso3c, year, base_year,
        rebased (0/1), base_year_source, flag.

WHAT THE CODE WILL DO - PART A, THE REBUILD
    1. Reproduce the published SPI.INDEX EXACTLY from the indicator-level data,
       before changing anything. The brief records that a first attempt using
       simple means did not match, so the dimension weights in the R code have
       to be followed. Stop here until the reproduction matches: without it,
       any difference after dropping the two indicators cannot be attributed to
       the drop rather than to a mistake in the rebuild.
    2. Then drop config.SPI_DROP_INDICATORS and recompute 5.2 -> Pillar 5 ->
       overall by the same route.
    3. Also produce the variant that additionally drops
       config.SPI_DROP_INDICATORS_EXTRA (CPI base year), for one robustness
       check.

CHECKS FOR PART A
    - Maximum absolute difference between the reproduction and the published
      SPI.INDEX. Target 0 (allowing for floating-point noise, say < 1e-6).
      Report it; do not proceed if it is large.
    - Then the difference between rebuilt and published, which should be small
      and mostly negative or positive in a way that tracks base-year age.
      Expect roughly 0.3-0.7 points per 0.5 step.
    - Correlation between rebuilt and published across SSA 2016-2021 (expect
      very high, near 1), and separately the correlation of overall SPI with
      Pillar 4 (brief: 0.78).
    - Spot-check the pillar-5 moves in the brief: Ghana 45 -> 60, Kenya
      45 -> 70; Ghana NABY 0.5 (2016) -> 0 (2017-2018) -> 0.5 (2019+) and SNAU
      0.5 -> 1 in 2019; Kenya NABY 0.5 (2016-2019) -> 0 (2020-2021) ->
      0.5 (2022+).

WHAT THE CODE WILL DO - PART B, THE REBASING DUMMY
    1. Read config.SPI_BASE_YEAR_COLUMN (RAW.D5.2.2.NABY), the base year for
       each country-year.
    2. Print every value that is not a plain year. The brief names ETH, UGA,
       GIN and SDN as storing text such as "2015/2016", "2010/11" or "chained".
       Convert them using config.SPI_BASE_YEAR_TEXT_FIXES, and STOP if a text
       value is found that is not in that mapping, so nothing is guessed.
    3. Set rebased = 1 in a year when the base year changes from the previous
       year, else 0.
    4. Apply config.REBASING_OVERRIDES: Kenya 2021, because KNBS released the
       2016-base revision in September 2021 while SPI shows it only from 2022.
       Official release dates win over SPI's reporting date.
    5. Flag config.REBASING_SUSPECT: Liberia's base year moves backwards
       (2000 -> 1992) in 2019, which is probably a data error. Flag it in a
       column and report it; do not silently correct or drop it.

CHECKS FOR PART B
    - Count base-year changes and compare with the brief. The brief's figures
      are for the OLD 40-country set: 23 changes in 2016-2021 (28 events in 24
      countries 2016-2022; 24 of the 48 SSA countries rebased in 2016-2021).
      The current sample is 38 countries, so recompute the count for it and
      report both, rather than quoting the brief's number as if it still
      applied.
    - Confirm Ghana 2019 (2006 -> 2013) and Kenya 2021 (via the override) are
      both flagged as rebasing years.
    - Print the full list of flagged country-years for the write-up, since
      rebasing is a panel-wide issue affecting about half the region, not just
      the two case studies.
"""

from src import config


def main() -> None:
    """Build spi_rebuilt.csv and rebasing_dummy.csv. Not written yet."""
    raise NotImplementedError(
        "Step 3b of the pipeline is not implemented yet. "
        "Reproduce the published SPI.INDEX exactly before dropping "
        f"{config.SPI_DROP_INDICATORS}."
    )


if __name__ == "__main__":
    main()
