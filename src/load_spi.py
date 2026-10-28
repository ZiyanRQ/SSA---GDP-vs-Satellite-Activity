"""Step 3a: load the published SPI scores and the indicator-level data.

Not implemented yet. This docstring is the plan.

This module only *loads* SPI. Rebuilding the index without the two circular
indicators is a separate step, in rebuild_spi.py, because the rebuild has to be
validated against the published scores loaded here.

INPUT
    data/raw/SPI_index.csv
        Published scores, from 03_output_data/ in github.com/worldbank/SPI.
        NOT YET DOWNLOADED.
    data/raw/SPI_data.csv
        Indicator level, 2004-2024. Already available.
    data/raw/SPI_full_metadata.csv
        Indicator scoring rules. NOT YET DOWNLOADED; needed to document how
        each indicator is scored, especially 5.2.1 (SNAU) and 5.2.2 (NABY).

OUTPUT
    data/interim/spi_published.csv, one row per (iso3c, year) with the overall
    score, the five pillar scores, and Pillar 4 kept separately because it is
    the alternative capacity measure.

WHAT THE CODE WILL DO
    1. Read SPI_index.csv, rename the country code column to iso3c, and keep
       SSA countries and the levels years.
    2. Read the indicator-level file and keep the indicator columns needed by
       rebuild_spi.py, plus config.SPI_BASE_YEAR_COLUMN for the rebasing dummy.
    3. Use the region column in the SPI file as the authoritative definition of
       Sub-Saharan Africa, and compare it with config.SSA_ALL. The brief says
       the 48-country universe came from this file, so any difference means
       config.SSA_ALL is wrong and must be corrected here rather than worked
       around later.

CHECKS BEFORE MOVING ON
    - Count SSA countries with a non-missing overall score per year, and
      compare with the brief: 41 (2016), 44 (2017-2019), 45 (2020-2021),
      46 (2022-2023). If these do not reproduce, the download is a different
      vintage and every sample count downstream changes.
    - Confirm the overall score is the simple mean of the five pillars (the
      brief says this was checked exactly). This is the first half of the
      reproduction that rebuild_spi.py completes.
    - List exactly which country-years are missing an SPI score and compare
      with the brief's 25 missing: CAF, COM and ERI all years; GNQ 2016-2019;
      COD, SOM and SYC in 2016. This list is what drops 6 of the 8 countries
      from the balanced panel, so it needs to match before anything is built
      on top of it.
    - Spot-check: Ghana overall 59.3 (2016), 66.2 (2021), 66.2 (2023); Kenya
      55.9, 68.1, 70.6. Pillar 4: Ghana 45.3 (2016), 54.5 (2019), 57.2 (2023);
      Kenya 35.9, 45.8, 46.5.
    - Report within- and between-country standard deviations (brief: overall
      5.5 within vs 10.9 between; Pillar 4 4.2 vs 14.2).

NOTE ON VINTAGE
    The 2025 SPI update (data through 2024) revised mainly Pillars 1 and 4.
    Record which vintage the download is, because the brief's reference figures
    come from the vintage used in the previous chat.
"""

from src import config


def main() -> None:
    """Build data/interim/spi_published.csv. Not written yet."""
    raise NotImplementedError(
        "Step 3a of the pipeline is not implemented yet. "
        f"Expected inputs: {config.SPI_INDEX_FILE} (download) and "
        f"{config.SPI_INDICATOR_FILE}"
    )


if __name__ == "__main__":
    main()
