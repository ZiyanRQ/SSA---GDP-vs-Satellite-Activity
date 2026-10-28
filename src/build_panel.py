"""Step 6: merge every source into the balanced country-year panel.

Not implemented yet. This docstring is the plan.

This is where the sample is decided, so it is the step that most needs loud
logging: after every merge, the row count, the country count and the missing
values are printed, and the countries dropped are written to a table with a
reason for each.

INPUT (all from data/interim/)
    wdi_long.csv              load_wdi.py
    vdem_accountability.csv   load_vdem.py
    spi_rebuilt.csv           rebuild_spi.py (includes the published scores)
    rebasing_dummy.csv        rebuild_spi.py
    oxcgrt_annual.csv         load_oxcgrt.py
    lights_country_year.csv   process_lights.py

OUTPUT
    data/processed/ssa_panel.csv     the estimation panel
    outputs/tables/dropped_countries.csv  one row per dropped country, with the
        years missing and the variable(s) responsible

WHAT THE CODE WILL DO
    1. Start from the full grid: config.SSA_ALL x config.YEARS_LEVELS, built
       explicitly rather than inferred from whichever file merges first. A
       grid makes a missing country-year visible instead of simply absent.
    2. Merge each source on (iso3c, year) with ``how="left", indicator=True``,
       and after every merge print:
           - row count and country count
           - the value counts of the merge indicator (left_only means the
             source is missing that country-year)
           - missing values per column
       The merge indicator column is dropped before the next merge.
    3. Build the derived variables:
           d_ln_gdp    = ln(gdp_real_lcu) - ln(gdp_real_lcu previous year)
           d_ln_lights = ln(lights_sum)   - ln(lights_sum previous year)
           gap         = d_ln_gdp - d_ln_lights        (config.OUTCOME_SIGNED)
           abs_gap     = abs(gap)                      (config.OUTCOME_ABSOLUTE)
           elec_access_change = elec_access - previous year, in percentage points
           ln_population      = ln(population)
       Lags must be taken within country (group by iso3c, then shift), never
       across the whole sorted frame, or the first year of one country picks up
       the last year of the previous one.
    4. Restrict to config.YEARS_GROWTH, now that the 2015 levels have done
       their job.
    5. Decide the sample:
           balanced (config.USE_UNBALANCED_PANEL = False): drop any country
               with any missing value in any model variable
           unbalanced (True): drop individual country-years only
       Stringency counts as a model variable, so GNB and STP are excluded from
       the balanced panel whatever config.USE_COVID_IN_MAIN is set to. A
       balanced panel has to hold the same countries in every specification,
       or coefficients from different models cannot be compared.
    6. Write the dropped-countries table, with the years missing and the
       variable(s) responsible for each.

CHECKS BEFORE MOVING ON
    - config.expected_sample() gives the country list and row count the
      settings imply: currently 38 countries, 228 rows. Compare the panel with
      it and fail loudly on a difference, rather than quietly estimating on a
      different sample.
      If the lights step has cost further countries, they belong in
      config.EXCLUDED_LIGHTS, which is the one place to edit: the expected
      count is derived from the exclusion lists, so this check follows
      automatically.
    - Confirm the dropped set matches config.EXPECTED_DROPPED_REASONS, and that
      each country's actual reason matches the one recorded there. A country
      dropping for a different reason than expected is a signal that something
      upstream changed.
    - Call config.check_years() both before and after restricting to the growth
      years: first as check_years(years) to allow the 2015 levels, then as
      check_years(years, stage="growth") to confirm 2015 has gone. 2015 is a
      base for the 2016 growth rate, never an observation, so it must not
      survive into the panel.
    - Arithmetic worth stating because it is easy to get wrong:
          48 x 6                      = 288 possible rows
          less 8 countries missing data   -> 40 countries, 240 rows
          less GNB and STP (no stringency) -> 38 countries, 228 rows
          less any country lost to lights  -> to be determined
      It is NOT 252 - 48: the unbalanced panel's 252 rows already exclude 36 of
      those 48.
    - Confirm the panel is balanced: every kept country has exactly 6 years.
    - Compare against data/raw/ssa_balanced_panel_2016_2021.csv, the earlier
      draft, column by column for the columns it has. It is a cross-check only
      and never an input. Any difference needs explaining, not overwriting.
    - Spot-check Ghana and Kenya rows against the brief's figures (GDP growth,
      electricity access, SPI, accountability, stringency).
    - Print the correlation between gdp_growth (WDI's own percentage) and
      d_ln_gdp (computed from the levels); they should be very close, and a
      large gap points at a currency break in the constant-LCU series.

ON SURVIVORSHIP BIAS
    Most dropped countries are fragile or conflict-affected with weak
    statistics, so the balanced sample leans towards stronger statistical
    capacity. That probably understates any capacity effect, and the results
    may not generalise to fragile states. The dropped-countries table is the
    evidence for saying so explicitly in the write-up.

    Insisting on balance is itself a choice with this cost, and the sample has
    now been cut twice for data availability rather than for anything about the
    countries themselves: eight for missing WDI or SPI data, and two more for
    missing COVID stringency. If the lights step cuts it again, the write-up
    should give the running total and name every country lost.
"""

from src import config


def main() -> None:
    """Build data/processed/ssa_panel.csv. Not written yet."""
    countries, n_rows = config.expected_sample()
    raise NotImplementedError(
        "Step 6 of the pipeline is not implemented yet. "
        f"It should produce {len(countries)} countries and {n_rows} rows "
        f"(balanced={not config.USE_UNBALANCED_PANEL})."
    )


if __name__ == "__main__":
    main()
