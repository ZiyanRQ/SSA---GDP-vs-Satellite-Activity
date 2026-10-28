"""Step 5: turn VIIRS night-lights rasters into a country-year lights series.

Not implemented yet. This docstring is the plan. This is the one variable
nobody supplies ready-made, so it is the step with the most decisions in it.

INPUT
    data/raw/   VIIRS annual VNL composites, band config.VIIRS_BAND
                (average_masked). The v2.1 files for 2015-2021 are DOWNLOADED
                and verified; v2.2 (2022-2023, extended check only) is not.
                2015 is there to form the 2016 growth rate; it is never an
                observation itself.

                Files present, 268-298 MB each gzipped:
                    VNL_v21_npp_<YEAR>_global_vcmslcfg_c202205302300
                        .average_masked.dat.tif.gz

CONFIRMED BY READING THE FILES (not assumed)
    All seven share one grid, so no reprojection or resampling is needed
    between years and the cell-by-cell comparison across years is valid:
        86401 x 33601 pixels, 1 band, float32
        EPSG:4326, 15.00 arcsec/px (about 500 m at the equator)
        bounds -180.002 to 180.002 lon, -65.002 to 75.002 lat
        2.90 billion pixels, 11.6 GB uncompressed per year
    Accra 5x5-pixel mean rises 24.6 (2015) to 46.3 (2021) nW/cm2/sr, which is
    plausible for Ghana over this period and confirms the band is radiance and
    the coordinate lookup is right.

    THEY DO NOT NEED DECOMPRESSING. GDAL reads inside the gzip via its virtual
    filesystem, so open them as:
        "/vsigzip/" + str(path).replace("\\", "/")
    Random window access through gzip is slow, because gzip must be
    decompressed sequentially to reach a given byte. That is fine for one pass
    per file, which is what the SSA crop below does, but it is the reason for
    cropping once rather than reading the global file repeatedly.

    NODATA IS NOT SET (nodata=None). Two consequences:
      - Zero means "dark", not "missing", so zeros must be summed, not
        skipped, and exactextract will not exclude anything by itself.
      - Check for NEGATIVE values before summing. VNL radiance can go slightly
        negative where background noise was removed. Decide explicitly whether
        to clamp negatives to zero or keep them, say which, and apply it
        consistently - it changes every country total.
    data/raw/boundaries/natural_earth/ne_10m_admin_0_countries.shp
                Natural Earth 1:10m Admin 0, version 5.1.1, public domain,
                downloaded 2026-10-28. DOWNLOADED and verified.
                258 features worldwide, EPSG:4326 (so it already matches the
                rasters and needs no reprojection).

                Join on config.BOUNDARY_ISO3_COLUMN = "ISO_A3". Of Natural
                Earth's many three-letter code columns, only ISO_A3 and
                ISO_A3_EH cover all 48 SSA countries: ADM0_A3 and SOV_A3 miss
                South Sudan, WB_A3 misses DR Congo. Filtering on ISO_A3 gives
                exactly 48 features for 48 codes, one each, so no polygons
                need merging.

                BOUNDARY CAVEAT: Natural Earth sets ISO_A3 to "-99" for
                entities of disputed ISO status, and carries Somaliland as a
                separate feature (ADM0_A3 = SOL). Somalia's polygon therefore
                EXCLUDES Somaliland. That does not affect this project, since
                Somalia is already out of the sample for a missing agriculture
                share, but it would matter if Somalia were ever added back.
                Cross-check against the World Bank Official Boundaries file,
                whose definitions match WDI, before relying on any single
                country's coastline.

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
    1. Crop each global raster once to config.LIGHTS_CROP_BBOX and write the
       result to data/interim/, then work from those. The crop is 21600 x 18000
       pixels, about 1.56 GB per year instead of 11.6 GB, and it turns one slow
       sequential pass through the gzip into many fast reads afterwards.

       The box is lon -26 to 64, lat -47 to 28, and it has been VERIFIED to
       contain every SSA polygon. Worth knowing why it is that shape: the
       limits come from outlying islands, not the mainland, and a sensible
       mainland guess (lon -26 to 60, lat -35 to 28) clipped two countries.
           east   63.49  Mauritius (Rodrigues)
           south -46.97  South Africa (Prince Edward Islands, sub-Antarctic)
       Those islands are unlit and add nothing to a radiance sum, but a clipped
       polygon would silently lose whatever it does contain.

       Re-check the box against the boundary file at run time rather than
       trusting the stored numbers, and fail if any polygon sticks out.
    2. Read the boundary file with geopandas; keep SSA countries; confirm the
       ISO3 codes match config.SSA_ALL exactly, and report both directions of
       mismatch (a boundary file missing a country, or using a different code).
    3. Confirm the boundaries and the raster are in the same coordinate
       reference system. The rasters are EPSG:4326 (confirmed above), so
       reproject the boundaries to match if they are not. Getting this wrong
       extracts the wrong area silently.
    4. For each year, sum masked average radiance inside each country border
       with exactextract, which weights cells by the fraction that falls inside
       the polygon. Record the lit-cell count and the polygon area alongside
       the sum. Cross-check a few countries against rasterstats, which does
       whole-cell assignment: the two should be close but not identical, and a
       large divergence points at a boundary or CRS problem.
    5. Compute the log change: d_ln_lights = ln(L_t) - ln(L_t-1), which is why
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
    - Gas flares. The VIIRS masking steps do not remove flares.
      EARLY RESULT, needs confirming: Ghana's land polygon stops at 4.74 N,
      and the Jubilee field is at roughly 4.0 N, 2.8 W, so it falls OUTSIDE
      the polygon. That supports the brief's assumption that offshore flares
      do not contaminate land-based totals. But the Jubilee coordinates used
      were approximate, so confirm against real flare locations (the EOG
      flare dataset, or by plotting the brightest offshore cells near the
      coast) rather than treating this as settled.
      Onshore flaring, in Nigeria for instance, will remain inside the
      borders and must be acknowledged as a limitation.
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
