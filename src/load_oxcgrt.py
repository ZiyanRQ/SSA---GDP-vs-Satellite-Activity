"""Step 4: turn daily COVID policy stringency into an annual country series.

Not implemented yet. This docstring is the plan.

INPUT
    data/raw/OxCGRT_nat_latest.csv, from data/ in
    github.com/OxCGRT/covid-policy-tracker. NOT YET DOWNLOADED.
    Daily, 2020-01-01 to 2023-02-28, national level.
    Column used: config.OXCGRT_STRINGENCY_COLUMN (StringencyIndex_Average,
    scale 0-100).

OUTPUT
    data/interim/oxcgrt_annual.csv, one row per (iso3c, year) for
    config.YEARS_GROWTH.

WHAT THE CODE WILL DO
    1. Read the daily file, keep the country code, date and stringency columns.
    2. Parse the date and take the calendar-year mean of the daily index for
       2020 and 2021 (the brief confirms both years have full daily coverage).
       For the extended 2016-2023 robustness check, 2022 is also a full year,
       but the file STOPS ON 2023-02-28: a 2023 "annual mean" would cover
       January and February only, and averaging two winter months against full
       years would be wrong. So leave 2023 stringency missing rather than
       computing it, and report in the extended check that stringency is
       unavailable for 2023.
    3. Set stringency to 0 for config.OXCGRT_ZERO_YEARS (2016-2019). This is
       not imputation: there was no pandemic policy to measure, so 0 is the
       true value and leaving these years missing would wrongly delete them.
    4. Keep SSA countries.

CHECKS BEFORE MOVING ON
    - Confirm coverage: config.COVID_MISSING_COUNTRIES (GNB, STP) have no data
      at all. This is why those two are excluded from the balanced panel
      outright, so verify it rather than assume it: if stringency turns out to
      exist for them, the panel goes back to 40 countries and
      config.EXCLUDED_NO_COVID_DATA should be emptied.
    - Call config.check_years() on the result, to be sure the 2022 and 2023
      daily data has really been dropped rather than averaged in.
    - Count the days averaged per country-year and print it, rather than
      trusting that a year is complete. Flag any year with fewer than about 360
      days: a partial year is not comparable with a full one. 2023 should show
      roughly 59 days, which is exactly why it is left missing.
    - Spot-check the brief's annual means: Ghana 42.5 (2020) and 42.8 (2021);
      Kenya 58.0 and 56.1; SSA mean 46.6 and 44.0.
    - Confirm every 2016-2019 value is exactly 0 and nothing is missing.

DESIGN NOTE
    Year fixed effects already absorb the part of the COVID shock that is
    common to all countries. Stringency adds the part that differs by country,
    and it is a main-model regressor (config.USE_COVID_IN_MAIN = True).

    Because the panel must be balanced, the two countries without stringency
    data leave the sample altogether rather than appearing in some
    specifications and not others: 38 countries / 228 rows. Re-estimating on
    2016-2019 only (config.YEARS_PRE_COVID), where stringency is 0 throughout
    and so drops out, is the complementary check.
"""

from src import config


def main() -> None:
    """Build data/interim/oxcgrt_annual.csv. Not written yet."""
    raise NotImplementedError(
        "Step 4 of the pipeline is not implemented yet. "
        f"Expected input: {config.OXCGRT_FILE} (download from "
        "github.com/OxCGRT/covid-policy-tracker)."
    )


if __name__ == "__main__":
    main()
