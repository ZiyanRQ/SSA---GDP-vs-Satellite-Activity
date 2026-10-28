"""Step 5: turn VIIRS night-lights rasters into a country-year lights series.

Not implemented yet. This docstring is the plan. This is the one variable
nobody supplies ready-made, so it is the step with the most decisions in it.

INPUT
    data/raw/viirs/   VIIRS annual VNL composites, band config.VIIRS_BAND
                      (average_masked). NOT YET DOWNLOADED. EOG requires a
                      free account; Google Earth Engine also hosts
                      NOAA/VIIRS/DNB/ANNUAL_V21 and _V22.
                        v2.1, 2015-2021  main analysis
                        v2.2, 2022-2023  extended robustness check only
                      2015 is there to form the 2016 growth rate; it is never
                      an observation itself.
    data/raw/boundaries/  A country boundary file carrying ISO3 codes in
                      config.BOUNDARY_ISO3_COLUMN. NOT YET CHOSEN.

OUTPUT
    data/interim/lights_country_year.csv, columns: iso3c, year, lights_sum,
    lit_pixels, and any flag columns the near-zero rule needs.

VERSIONS - DO NOT MIX CARELESSLY
    v2.1 covers 2012-2021 and is what the MAIN analysis uses, on its own. It
    fixed an annual-averaging bug in v2 and removed v2's low-detection filter,
    so v2 and v2.1 are not comparable and v2 is not used anywhere.

    v2.2 (2022 onward) changes the method again: it mixes satellites, accepts
    months with fewer cloud-free observations, and excludes cells without
    median values. It is needed for the extended 2016-2023 robustness check
    (config.YEARS_EXTENDED), where the 2021-to-2022 growth rate unavoidably
    straddles the version change and so contains both real growth and a method
    effect. That is a limitation to report, not a reason to skip the check.

    So: record the version for every raster read, and refuse anything not in
    config.VIIRS_VERSIONS_PERMITTED_MAIN (main) or
    ..._PERMITTED_EXTENDED (robustness). Read the version from the filename
    rather than trusting the folder it sits in, and write it into a column of
    the output so a later step cannot lose track of which years came from
    which version.

    Where v2.1 and v2.2 both cover a year, extract both. Comparing them on the
    overlap is what separates the version effect from real growth, and it costs
    only one extra extraction.

WHAT THE CODE WILL DO
    1. Read the boundary file with geopandas; keep SSA countries; confirm the
       ISO3 codes match config.SSA_ALL exactly, and report both directions of
       mismatch (a boundary file missing a country, or using a different code).
    2. Confirm the boundaries and the raster are in the same coordinate
       reference system; reproject the boundaries if not. Getting this wrong
       silently extracts the wrong area.
    3. For each year, sum masked average radiance inside each country border,
       using rasterio with exactextract (or rasterstats). Record the number of
       lit cells alongside the sum.
    4. Compute the log change: d_ln_lights = ln(L_t) - ln(L_t-1), which is why
       2015 levels are needed for a 2016 growth rate.

DECISIONS TO FIX BEFORE LOOKING AT ANY RESULTS
    - Near-zero rule. ln(0) is undefined, so a rule is needed for country-years
      whose total is zero or near zero. config.LIGHTS_NEAR_ZERO_THRESHOLD is
      deliberately None so that this module fails rather than applying an
      invented threshold. Set it, write the reasoning into the README, and do
      not revisit it after seeing results. A country with missing or near-zero
      lights is dropped, to keep the panel balanced.

      When that happens, add the country to config.EXCLUDED_LIGHTS with its
      reason. That is the single edit point: every expected count in the
      project is derived from the exclusion lists, so the panel check, the
      dropped-countries table and the README all follow from it. Expect the
      sample to fall below 38 countries / 228 rows, and say by how much.
    - Sum versus mean radiance. The brief specifies the sum within borders.
      A sum scales with country area, which country fixed effects absorb in
      levels; in log changes it is the growth of total luminosity. Keep the sum
      and say so.

CHECKS BEFORE MOVING ON
    - Row count: 48 countries x 7 years before any dropping; report every
      country lost and why. The panel stands at 38 countries / 228 rows going
      into this step, and this is the step most likely to reduce it further.
    - Call config.check_years() on the years extracted, so that a 2022 raster
      cannot slip into the main panel: pass extended=True only in the
      robustness extraction.
    - Gas flares. The VIIRS masking steps do not remove flares. Offshore flares
      should fall outside land boundaries, so verify specifically that Ghana's
      offshore oil fields lie outside the Ghana polygon (plot them, do not
      assume). Onshore flaring, in Nigeria for instance, will remain and must
      be acknowledged as a limitation.
    - Sanity ordering: South Africa and Nigeria should dominate total
      luminosity; a small country outranking them means the extraction is
      wrong.
    - Plot each country's series over 2015-2021 and look for implausible jumps,
      especially 2015-2016, in case a raster is a different version.
    - Spot-check that Kenya's lights rise over the period, given electricity
      access went from 41.6% to 76.5%. If it does not, suspect the extraction.

LIMITATION TO WRITE UP
    Lights miss agriculture, the informal sector and off-grid activity, and
    pick up electrification and flaring that are not output growth. This is the
    measurement error the check model in models.py is there to quantify.
"""

from src import config


def main() -> None:
    """Build data/interim/lights_country_year.csv. Not written yet."""
    if config.LIGHTS_NEAR_ZERO_THRESHOLD is None:
        raise NotImplementedError(
            "Decide config.LIGHTS_NEAR_ZERO_THRESHOLD before processing lights: "
            "the rule for zero or near-zero radiance totals must be fixed "
            "before any results are seen."
        )
    raise NotImplementedError(
        "Step 5 of the pipeline is not implemented yet. "
        f"Expected rasters in {config.LIGHTS_RASTER_DIR} "
        f"(VIIRS {config.VIIRS_VERSION}, band {config.VIIRS_BAND})."
    )


if __name__ == "__main__":
    main()
