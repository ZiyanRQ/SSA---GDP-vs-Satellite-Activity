"""Step 1: load the seven World Development Indicators series.

Not implemented yet. This docstring is the plan, so that the next step starts
from a written specification rather than from memory.

INPUT
    data/raw/API_<CODE>_DS2_en_csv_v2_*.csv, one file per indicator.
    The CSV has 4 preamble lines before the header (config.WDI_SKIPROWS), and
    is in *wide* form: one row per country, one column per year.

    Indicators (config.WDI_INDICATORS):
        NY.GDP.MKTP.KN       GDP, constant local currency (levels)
        NY.GDP.MKTP.KD.ZG    GDP growth, annual %
        NV.AGR.TOTL.ZS       Agriculture, value added, % of GDP
        EG.ELC.ACCS.ZS       Access to electricity, % of population
        SP.URB.TOTL.IN.ZS    Urban population, % of total
        SP.POP.TOTL          Total population
        NY.GDP.PETR.RT.ZS    Oil rents, % of GDP

OUTPUT
    data/interim/wdi_long.csv, in *long* form: one row per (iso3c, year) with
    one column per indicator, covering config.SSA_ALL and config.YEARS_LEVELS.

WHAT THE CODE WILL DO
    1. Find each indicator's file by pattern (the trailing download number
       changes every time, so do not hard-code filenames). Fail if a pattern
       matches zero files or more than one.
    2. Read the "Last Updated Date" from the preamble of every file and record
       it, so the data vintage is documented (expected 2026-10-08).
    3. Reshape wide to long with pandas.melt: the year columns become a single
       ``year`` column plus a value column.
    4. Rename "Country Code" to iso3c and keep only SSA countries and years.
    5. Merge the seven indicators on (iso3c, year) into one table.

CHECKS BEFORE MOVING ON
    - Every file's "Last Updated Date" is the same; print it.
    - Exactly 48 countries x 7 years = 336 rows after subsetting; print the
      count and any SSA code the WDI files do not contain.
    - Missing-value count per indicator, compared with the brief: GDP growth
      missing for ERI and SSD, agriculture share for ERI, SOM and SSD, and
      nothing missing for electricity, urbanisation or population.
    - Spot-check Ghana and Kenya GDP growth against the brief:
        Ghana 2016-2021: 3.37, 8.13, 6.20, 6.51, 0.51, 5.08
        Kenya 2016-2021: 4.21, 3.84, 5.65, 5.11, -0.27, 7.59
      and electricity access: Ghana 74.0 (2015) and 86.3 (2021), Kenya 41.6
      and 76.5.
    - Recompute growth from the KN levels and compare with KD.ZG. The brief
      reports they agree to 0.00, which is worth confirming, because the gap
      measure uses log differences of KN rather than KD.ZG.

OPEN QUESTION
    Sudan's constant-LCU series and the 2015 base year need a look: KN is in
    constant local currency, and a currency redenomination would break the
    log difference. Zimbabwe's 2019 currency change is flagged in the brief as
    a possible outlier for the same reason.
"""

from src import config


def main() -> None:
    """Build data/interim/wdi_long.csv. Not written yet."""
    raise NotImplementedError(
        "Step 1 of the pipeline is not implemented yet. "
        f"Raw WDI files are expected in {config.DATA_RAW}."
    )


if __name__ == "__main__":
    main()
