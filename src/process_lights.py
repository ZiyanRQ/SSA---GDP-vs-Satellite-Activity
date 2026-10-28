"""Step 5: turn VIIRS night-lights rasters into a country-year lights series.

STAGE 1 (cropping the rasters to Sub-Saharan Africa) IS IMPLEMENTED.
Stage 2 (zonal sums per country) and stage 3 (log changes) are not: they wait
on two decisions, listed under DECISIONS below, which must be fixed before any
results are seen.

Run stage 1 from the project root:

    python -m src.process_lights              # crop all 7 years, skip existing
    python -m src.process_lights --overwrite  # redo them
    python -m src.process_lights --years 2015 2016

INPUT
    data/raw/   VIIRS annual VNL composites, band config.VIIRS_BAND
                (average_masked). The v2.1 files for 2015-2021 are DOWNLOADED
                and verified; v2.2 (2022-2023, extended check only) is not.
                2015 is there to form the 2016 growth rate; it is never an
                observation itself.

                Files present, 268-298 MB each gzipped:
                    VNL_v21_npp_<YEAR>_global_vcmslcfg_c202205302300
                        .average_masked.dat.tif.gz

    data/raw/boundaries/natural_earth/ne_10m_admin_0_countries.shp
                Natural Earth 1:10m Admin 0, public domain, downloaded
                2026-10-28. DOWNLOADED and verified. 258 features worldwide,
                EPSG:4326, so it already matches the rasters.

                Join on config.BOUNDARY_ISO3_COLUMN = "ISO_A3". Of Natural
                Earth's many three-letter code columns, only ISO_A3 and
                ISO_A3_EH cover all 48 SSA countries: ADM0_A3 and SOV_A3 miss
                South Sudan, WB_A3 misses DR Congo. Filtering on ISO_A3 gives
                exactly 48 features for 48 codes, one each, so no polygons need
                merging.

                BOUNDARY CAVEAT: Natural Earth sets ISO_A3 to "-99" for
                entities of disputed ISO status, and carries Somaliland as a
                separate feature (ADM0_A3 = SOL). Somalia's polygon therefore
                EXCLUDES Somaliland. That does not affect this project, since
                Somalia is already out of the sample for a missing agriculture
                share, but it would matter if Somalia were ever added back.
                Cross-check against the World Bank Official Boundaries file,
                whose definitions match WDI, before relying on any single
                country's coastline.

CONFIRMED BY READING THE FILES (not assumed)
    All seven share one grid, so no reprojection or resampling is needed
    between years and the year-on-year comparison is valid:
        86401 x 33601 pixels, 1 band, float32
        EPSG:4326, 15.00 arcsec/px (about 500 m at the equator)
        bounds -180.002 to 180.002 lon, -65.002 to 75.002 lat
        2.90 billion pixels, 11.6 GB uncompressed per year
    Accra 5x5-pixel mean rises 24.6 (2015) to 46.3 (2021) nW/cm2/sr, which is
    plausible for Ghana over this period and confirms the band is radiance and
    the coordinate lookup is right.

    THEY DO NOT NEED DECOMPRESSING. GDAL reads inside the gzip via its virtual
    filesystem; see gzip_vsi_path() below. Random window access through gzip is
    slow, because gzip must be decompressed sequentially to reach a given byte.
    That is fine for one forward pass per file, which is what the crop does,
    and it is exactly why we crop once rather than reading the global file
    repeatedly.

    NODATA IS NOT SET (nodata=None). Two consequences:
      - Zero means "dark", not "missing", so zeros must be summed, not
        skipped, and exactextract will not exclude anything by itself.
      - Negative radiance may be present where background noise was removed.
        The crop stage counts negatives so the decision below can be made on
        evidence rather than guesswork.

OUTPUT
    stage 1  data/interim/lights_ssa_<YEAR>_v21.tif       cropped raster
             data/interim/lights_crop_report.csv          crop diagnostics
             outputs/figures/lights_quicklook_<YEAR>.png  preview with borders
    stage 2  data/interim/lights_ssa_<YEAR>_v21_clamped.tif  negatives zeroed
             data/interim/lights_clamp_report.csv         how much was removed
             data/interim/lights_country_year_raw.csv     totals per country-year
    stage 3  data/interim/lights_country_year.csv         with log changes,
             NOT YET BUILT - needs config.LIGHTS_NEAR_ZERO_THRESHOLD

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

    The version is read from the filename, never from the folder it sits in,
    and written into every output so a later step cannot lose track of which
    years came from which version. Where v2.1 and v2.2 both cover a year,
    extract both: comparing them on the overlap is what separates the version
    effect from real growth, and it costs only one extra extraction.

DECISIONS TO FIX BEFORE LOOKING AT ANY RESULTS
    - Near-zero rule. ln(0) is undefined, so a rule is needed for country-years
      whose total is zero or near zero. config.LIGHTS_NEAR_ZERO_THRESHOLD is
      deliberately None so stage 2 refuses to run rather than applying an
      invented threshold. Set it, write the reasoning into the README, and do
      not revisit it after seeing results. A country with missing or near-zero
      lights is dropped, to keep the panel balanced.

      When that happens, add the country to config.EXCLUDED_LIGHTS with its
      reason. That is the single edit point: every expected count in the
      project is derived from the exclusion lists, so the panel check, the
      dropped-countries table and the README all follow from it.
    - Negative radiance: clamp to zero, or keep? It changes every country
      total. Decide from the counts in lights_crop_report.csv.
    - Sum versus mean radiance. The brief specifies the sum within borders.
      A sum scales with country area, which country fixed effects absorb in
      levels; in log changes it is the growth of total luminosity. Keep the sum
      and say so.

STAGE 2 PLAN (not yet written)
    1. Read the boundaries, keep SSA, confirm the ISO3 codes match
       config.SSA_ALL and report mismatches in both directions.
    2. For each year, sum radiance inside each country border with
       exactextract, which weights cells by the fraction falling inside the
       polygon. Record the lit-cell count and polygon area alongside the sum.
       Cross-check a few countries against rasterstats, which assigns whole
       cells: the two should be close but not identical, and a large divergence
       points at a boundary or CRS problem.
    3. Compute d_ln_lights = ln(L_t) - ln(L_t-1), which is why 2015 is loaded.

CHECKS BEFORE MOVING ON
    - Row count: 48 countries x 7 years before any dropping; report every
      country lost and why. The panel stands at 38 countries / 228 rows going
      into this step, and this is the step most likely to reduce it further.
    - Call config.check_years() on the years extracted, so a 2022 raster cannot
      slip into the main panel: pass extended=True only in the robustness run.
    - Gas flares. The VIIRS masking steps do not remove flares.
      EARLY RESULT, needs confirming: Ghana's land polygon stops at 4.74 N, and
      the Jubilee field is at roughly 4.0 N, 2.8 W, so it falls OUTSIDE the
      polygon. That supports the brief's assumption that offshore flares do not
      contaminate land-based totals. The Jubilee coordinates used were
      approximate, so confirm against real flare locations (the EOG flare
      dataset, or by plotting the brightest offshore cells near the coast)
      rather than treating this as settled. Onshore flaring, in Nigeria for
      instance, stays inside the borders and is a limitation to acknowledge.
    - Sanity ordering: South Africa and Nigeria should dominate total
      luminosity; a small country outranking them means the extraction is wrong.
    - Plot each country's series over 2015-2021 and look for implausible jumps,
      especially 2015-2016, in case a raster is a different version.
    - Spot-check that Kenya's lights rise over the period, given electricity
      access went from 41.6% to 76.5%. If not, suspect the extraction.

LIMITATION TO WRITE UP
    Lights miss agriculture, the informal sector and off-grid activity, and
    pick up electrification and flaring that are not output growth. This is the
    measurement error the check model in models.py is there to quantify.
"""

import argparse
import glob
import re
import time
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import from_bounds

from src import config

# Rows of pixels read and written at a time. The cropped raster is 21600 px
# wide, so 2048 rows is about 177 MB per block in float32: large enough that
# the gzip is read in long forward runs, small enough never to hold the whole
# 1.56 GB image in memory.
BLOCK_ROWS = 2048

# Width in pixels of the quicklook PNG. The raster is downsampled to roughly
# this by GDAL as it reads, so the preview costs little.
QUICKLOOK_WIDTH = 1800


def gzip_vsi_path(path: Path) -> str:
    """Return a GDAL path that reads inside a .gz without unpacking it.

    GDAL has "virtual filesystems" addressed by a prefix on the path. The
    /vsigzip/ one decompresses on the fly, so rasterio can open a .tif.gz
    directly. GDAL wants forward slashes even on Windows.

    A plain .tif is returned unchanged, so this is safe to call on anything.
    """
    text = str(path).replace("\\", "/")
    if text.endswith(".gz"):
        return "/vsigzip/" + text
    return text


def viirs_version_from_name(filename: str) -> str:
    """Pull the VIIRS version out of a filename, e.g. "v21" -> "v2.1".

    Read from the filename rather than from the folder, because a file can be
    moved into the wrong folder but its name travels with it. Raises if the
    name carries no version, so an unknown file can never be processed as
    though its version were known.
    """
    match = re.search(r"_v(\d)(\d)_", filename)
    if match is None:
        raise ValueError(
            f"cannot read a VIIRS version from the filename {filename!r}. "
            "Expected something like VNL_v21_npp_2015_global_..."
        )
    return f"v{match.group(1)}.{match.group(2)}"


def find_raster(year: int, raster_dir: Path | None = None) -> Path:
    """Find the one VIIRS raster for a year, or raise.

    The EOG download filenames end in a creation timestamp that changes
    between releases, so the file is found by pattern rather than by an exact
    name. Finding zero files, or more than one, is an error either way: a
    second match would mean two vintages are present and the choice between
    them would be arbitrary.
    """
    directory = raster_dir if raster_dir is not None else config.LIGHTS_RASTER_DIR
    pattern = config.LIGHTS_RASTER_PATTERN.format(year=year)
    matches = sorted(glob.glob(str(directory / pattern)))

    if not matches:
        raise FileNotFoundError(
            f"no raster for {year}: nothing matched {pattern} in {directory}"
        )
    if len(matches) > 1:
        names = "\n  ".join(Path(m).name for m in matches)
        raise ValueError(
            f"{len(matches)} rasters match {pattern} for {year}; expected one. "
            f"Remove the ones you are not using:\n  {names}"
        )
    return Path(matches[0])


def cropped_path(year: int, version: str = config.VIIRS_VERSION) -> Path:
    """Where the cropped raster for a year goes."""
    tag = version.replace(".", "")
    return config.DATA_INTERIM / f"lights_ssa_{year}_{tag}.tif"


def quicklook_path(year: int) -> Path:
    """Where the preview PNG for a year goes."""
    return config.OUTPUTS_FIGURES / f"lights_quicklook_{year}.png"


def crop_to_bbox(
    src_path: Path,
    dst_path: Path,
    bbox: tuple[float, float, float, float] = config.LIGHTS_CROP_BBOX,
    block_rows: int = BLOCK_ROWS,
) -> dict:
    """Crop one global raster to a bounding box, gathering diagnostics.

    Reads and writes a block of rows at a time, so memory stays flat whatever
    the size of the image, and the gzip is read in one forward pass.

    While the data is passing through, this also counts negative, zero and
    positive cells and totals the radiance. Those numbers are needed to settle
    the "clamp negatives?" decision, and collecting them here is free: the
    alternative is another 11.6 GB read per year.

    Returns a dict of diagnostics for one row of the crop report.
    """
    left, bottom, right, top = bbox

    with rasterio.open(gzip_vsi_path(src_path)) as src:
        # Translate the geographic box into a pixel window. round_offsets and
        # round_lengths snap it outwards to whole pixels, so the crop can only
        # ever be slightly larger than asked for, never smaller - cutting a
        # polygon short is the failure we are guarding against.
        window = from_bounds(left, bottom, right, top, transform=src.transform)
        window = window.round_offsets(op="floor").round_lengths(op="ceil")

        # Clip to the raster, in case the box reaches past its edge. The VIIRS
        # grid stops at 65 S and 75 N, so a southern box could overhang.
        full = rasterio.windows.Window(0, 0, src.width, src.height)
        window = window.intersection(full)

        profile = src.profile.copy()
        profile.update(
            driver="GTiff",
            height=int(window.height),
            width=int(window.width),
            transform=src.window_transform(window),
            count=1,
            dtype="float32",
            # Tiled and compressed: predictor 3 is the floating-point
            # predictor, which makes deflate far more effective on smooth
            # radiance data. BIGTIFF when needed, since these are over 4 GB
            # before compression.
            tiled=True,
            blockxsize=512,
            blockysize=512,
            compress="deflate",
            predictor=3,
            zlevel=6,
            BIGTIFF="IF_SAFER",
        )
        # The source has no nodata and zero means dark, so the crop must not
        # invent one. Writing a nodata value here would make every unlit cell
        # look missing to exactextract later.
        profile.pop("nodata", None)

        n_negative = 0
        n_zero = 0
        n_positive = 0
        total = 0.0
        most_negative = 0.0
        largest = 0.0

        dst_path.parent.mkdir(parents=True, exist_ok=True)
        started = time.time()

        with rasterio.open(dst_path, "w", **profile) as dst:
            n_blocks = int(np.ceil(window.height / block_rows))
            for i in range(n_blocks):
                row_offset = i * block_rows
                rows = min(block_rows, int(window.height) - row_offset)

                read_window = rasterio.windows.Window(
                    col_off=window.col_off,
                    row_off=window.row_off + row_offset,
                    width=window.width,
                    height=rows,
                )
                block = src.read(1, window=read_window)

                # Diagnostics on the real values, before anything is changed.
                # Nothing is clamped here: that decision is still open, and
                # the crop must stay a faithful copy of the source so it does
                # not have to be redone once the decision is made.
                n_negative += int(np.count_nonzero(block < 0))
                n_zero += int(np.count_nonzero(block == 0))
                n_positive += int(np.count_nonzero(block > 0))
                total += float(block.sum(dtype=np.float64))
                if block.size:
                    most_negative = min(most_negative, float(block.min()))
                    largest = max(largest, float(block.max()))

                dst.write(
                    block,
                    1,
                    window=rasterio.windows.Window(
                        0, row_offset, window.width, rows
                    ),
                )
                print(
                    f"    block {i + 1}/{n_blocks}  rows "
                    f"{row_offset}-{row_offset + rows}",
                    flush=True,
                )

        elapsed = time.time() - started
        n_cells = n_negative + n_zero + n_positive

        return {
            "year": None,  # filled in by the caller
            "version": viirs_version_from_name(src_path.name),
            "source_file": src_path.name,
            "cropped_file": dst_path.name,
            "width": int(window.width),
            "height": int(window.height),
            "cells": n_cells,
            "n_negative": n_negative,
            "n_zero": n_zero,
            "n_positive": n_positive,
            "pct_negative": 100.0 * n_negative / n_cells if n_cells else np.nan,
            "min_value": most_negative,
            "max_value": largest,
            "sum_radiance": total,
            "crop_seconds": round(elapsed, 1),
            "size_mb": round(dst_path.stat().st_size / 1e6, 1),
        }


def check_crop_box_covers_boundaries(
    bbox: tuple[float, float, float, float] = config.LIGHTS_CROP_BBOX,
) -> None:
    """Raise if any SSA polygon sticks out of the crop box.

    The box in config was checked once by hand, but it is re-derived from the
    boundary file every run: swapping in a different boundary file is exactly
    the kind of change that would silently clip a country otherwise.
    """
    import geopandas as gpd

    boundaries = gpd.read_file(config.BOUNDARY_FILE)
    ssa = boundaries[boundaries[config.BOUNDARY_ISO3_COLUMN].isin(config.SSA_ALL)]

    found = set(ssa[config.BOUNDARY_ISO3_COLUMN])
    missing = sorted(set(config.SSA_ALL) - found)
    if missing:
        raise ValueError(
            f"the boundary file has no polygon for {missing} under column "
            f"{config.BOUNDARY_ISO3_COLUMN!r}"
        )

    min_lon, min_lat, max_lon, max_lat = ssa.total_bounds
    left, bottom, right, top = bbox
    if not (min_lon >= left and min_lat >= bottom
            and max_lon <= right and max_lat <= top):
        raise ValueError(
            "config.LIGHTS_CROP_BBOX does not contain every SSA polygon.\n"
            f"  polygons span lon {min_lon:.2f} to {max_lon:.2f}, "
            f"lat {min_lat:.2f} to {max_lat:.2f}\n"
            f"  box spans    lon {left} to {right}, lat {bottom} to {top}\n"
            "Widen the box in src/config.py."
        )
    print(
        f"crop box check: all {len(found)} SSA polygons fall inside "
        f"lon {left} to {right}, lat {bottom} to {top}"
    )


def max_pool_read(src, target_width: int, out_rows_per_block: int = 100):
    """Downsample a raster for display by taking the MAXIMUM of each block.

    Why not just read a smaller version? Because GDAL's default downsampling
    picks one representative pixel per block (nearest neighbour), and lit areas
    here are often one or two pixels across. Sampling every twelfth pixel lands
    between them and throws most of them away, so the map looks far emptier
    than the data really is. Taking the maximum keeps every lit cell visible.
    GDAL will not do max-resampling on a plain read, so it is done here.

    This is a DISPLAY choice only. Stage 2 sums the full-resolution data and is
    completely unaffected by anything in this function.

    Reads a block of rows at a time so memory stays flat: at the sizes here
    each block is roughly 100 MB rather than the full 1.56 GB.
    """
    factor = max(1, src.width // target_width)
    out_w = src.width // factor
    out_h = src.height // factor

    out = np.zeros((out_h, out_w), dtype="float32")

    for first_row in range(0, out_h, out_rows_per_block):
        n_out_rows = min(out_rows_per_block, out_h - first_row)

        block = src.read(
            1,
            window=rasterio.windows.Window(
                col_off=0,
                row_off=first_row * factor,
                width=out_w * factor,
                height=n_out_rows * factor,
            ),
        )
        # Split each axis into (output cell, position within cell), then take
        # the maximum over the two "within cell" axes. This is exact: every
        # source pixel in the block is considered.
        pooled = block.reshape(n_out_rows, factor, out_w, factor).max(axis=(1, 3))
        out[first_row:first_row + n_out_rows] = pooled

    return out


def write_quicklook(year: int, tif_path: Path, png_path: Path) -> None:
    """Save a downsampled preview of a cropped raster, with borders drawn on.

    This is the visual check that the extraction is aligned: if the lit areas
    do not sit inside the country outlines, something is wrong with the
    coordinates, and no amount of summing will reveal it as clearly as looking.

    Radiance spans several orders of magnitude, so the colour scale is
    logarithmic; on a linear scale a few city centres saturate everything else
    to black.
    """
    import geopandas as gpd
    import matplotlib
    matplotlib.use("Agg")  # no interactive window; just write the file
    import matplotlib.pyplot as plt
    from matplotlib.colors import LogNorm

    with rasterio.open(tif_path) as src:
        data = max_pool_read(src, QUICKLOOK_WIDTH)
        bounds = src.bounds

    # LogNorm cannot take zero or negative values, so mask everything at or
    # below a small positive floor.
    floor = config.LIGHTS_QUICKLOOK_VMIN
    shown = np.ma.masked_less_equal(data, floor)

    # The scale is FIXED across years (see config), not derived from this
    # year's data: a per-year scale re-normalises every map to itself, so the
    # years cannot be compared by eye. It is capped well below the true
    # maximum because the brightest cells are gas flares at tens of thousands
    # of nW/cm2/sr, around 1000x a bright city, which would push every
    # settlement to the bottom of the colour map.
    vmax = config.LIGHTS_QUICKLOOK_VMAX

    fig, ax = plt.subplots(figsize=(11, 9.5), dpi=120)
    fig.patch.set_facecolor("#0b0b10")
    ax.set_facecolor("#0b0b10")

    image = ax.imshow(
        shown,
        extent=(bounds.left, bounds.right, bounds.bottom, bounds.top),
        cmap="inferno",
        norm=LogNorm(vmin=floor, vmax=vmax),
        interpolation="nearest",
    )

    boundaries = gpd.read_file(config.BOUNDARY_FILE)
    ssa = boundaries[boundaries[config.BOUNDARY_ISO3_COLUMN].isin(config.SSA_ALL)]
    ssa.boundary.plot(ax=ax, linewidth=0.35, edgecolor="#4da3d8", alpha=0.75)

    bar = fig.colorbar(image, ax=ax, shrink=0.72, pad=0.02, extend="max")
    bar.set_label("radiance (nW/cm2/sr, log scale)", color="#d8d8e0", fontsize=9)
    bar.ax.tick_params(colors="#d8d8e0", labelsize=8)
    bar.outline.set_edgecolor("#55555f")

    ax.set_xlim(bounds.left, bounds.right)
    ax.set_ylim(bounds.bottom, bounds.top)
    ax.set_title(
        f"Night-time lights, {year}\n"
        f"VIIRS {config.VIIRS_VERSION} {config.VIIRS_BAND}, "
        "Sub-Saharan Africa crop",
        color="#f0f0f5", fontsize=12, pad=12,
    )
    ax.set_xlabel("longitude", color="#b8b8c2", fontsize=9)
    ax.set_ylabel("latitude", color="#b8b8c2", fontsize=9)
    ax.tick_params(colors="#b8b8c2", labelsize=8)
    for spine in ax.spines.values():
        spine.set_edgecolor("#55555f")

    # Lit areas outside the blue outlines are North Africa and the Arabian
    # peninsula, which fall inside the rectangular crop but are not Sub-Saharan
    # countries. Stage 2 sums within polygons, so they are never counted; say
    # so on the figure rather than leaving a reader to wonder.
    ax.text(
        0.005, -0.085,
        f"Colour scale fixed at {floor:g}-{vmax:,.0f} nW/cm2/sr across all "
        f"years, so the maps are comparable; brighter cells, mostly gas "
        f"flares, are drawn at the top colour. Lights outside the outlines "
        f"are non-SSA countries inside the crop rectangle and are excluded "
        f"from all totals.",
        transform=ax.transAxes, fontsize=7.5, color="#90909c",
        va="top", ha="left", wrap=True,
    )

    fig.tight_layout()
    png_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(png_path, facecolor=fig.get_facecolor())
    plt.close(fig)


def run_crop_stage(
    years: list[int] | None = None,
    overwrite: bool = False,
) -> pd.DataFrame:
    """Crop every year's raster and write the diagnostics report.

    Skips a year whose cropped file already exists, unless overwrite is True,
    so an interrupted run can be resumed without redoing finished work.
    """
    target_years = years if years is not None else config.YEARS_LEVELS
    config.check_years(target_years)

    check_crop_box_covers_boundaries()

    # Rows already on disk from an earlier run. A year whose raster is skipped
    # still needs its diagnostics in the report, or rewriting the file would
    # quietly delete the evidence the negative-radiance decision rests on.
    report_path = config.DATA_INTERIM / "lights_crop_report.csv"
    previous = {}
    if report_path.exists():
        existing = pd.read_csv(report_path)
        previous = {int(r["year"]): dict(r) for _, r in existing.iterrows()}

    rows = []
    for year in target_years:
        src_path = find_raster(year)
        version = viirs_version_from_name(src_path.name)

        if version not in config.VIIRS_VERSIONS_PERMITTED_MAIN:
            raise ValueError(
                f"{src_path.name} is VIIRS {version}, but the main analysis "
                f"permits only {config.VIIRS_VERSIONS_PERMITTED_MAIN}."
            )

        dst_path = cropped_path(year, version)
        print(f"\n{year}: {src_path.name}  ({version})")

        if dst_path.exists() and not overwrite:
            print(f"  cropped file already exists, skipping: {dst_path.name}")
            if year in previous:
                rows.append(previous[year])
                print("  carried its diagnostics over from the previous report")
            else:
                print(
                    "  WARNING: no diagnostics on record for this year. "
                    "Re-run with --overwrite to regenerate them."
                )
        else:
            print(f"  cropping to {dst_path.name}")
            record = crop_to_bbox(src_path, dst_path)
            record["year"] = year
            rows.append(record)
            print(
                f"  done in {record['crop_seconds']}s, "
                f"{record['size_mb']} MB, "
                f"{record['n_negative']:,} negative cells "
                f"({record['pct_negative']:.4f}%), "
                f"range {record['min_value']:.3f} to {record['max_value']:.1f}"
            )

        print("  writing quicklook preview")
        write_quicklook(year, dst_path, quicklook_path(year))

    if not rows:
        print("\nnothing cropped (all years already done)")
        return pd.DataFrame()

    report = pd.DataFrame(rows)
    columns = ["year", "version", "width", "height", "cells", "n_negative",
               "pct_negative", "n_zero", "n_positive", "min_value",
               "max_value", "sum_radiance", "size_mb", "crop_seconds",
               "source_file", "cropped_file"]
    report = report[columns].sort_values("year")

    out_path = config.DATA_INTERIM / "lights_crop_report.csv"
    report.to_csv(out_path, index=False)
    print(f"\ncrop report written to {out_path}")
    return report


# ===========================================================================
# STAGE 2: clamp negatives, then sum radiance inside each country
# ===========================================================================


def clamped_path(year: int, version: str = config.VIIRS_VERSION) -> Path:
    """Where the clamped copy of a cropped raster goes."""
    tag = version.replace(".", "")
    return config.DATA_INTERIM / f"lights_ssa_{year}_{tag}_clamped.tif"


def clamp_raster(src_path: Path, dst_path: Path) -> dict:
    """Write a copy of a cropped raster with negative values set to zero.

    config.LIGHTS_CLAMP_NEGATIVES records the decision and the reasoning. This
    is done as a separate file rather than during the crop, so that the crop
    stays a faithful copy of the source: if the decision is ever revisited,
    only this cheap pass is redone, not the slow gzip read.

    Returns how much was removed, so the size of the adjustment can be stated
    as a measured number rather than asserted.
    """
    with rasterio.open(src_path) as src:
        profile = src.profile.copy()
        n_clamped = 0
        magnitude_removed = 0.0
        total_before = 0.0

        dst_path.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(dst_path, "w", **profile) as dst:
            # Follow the file's own tiling when reading, which is the fastest
            # order and keeps memory to one block at a time.
            for _, window in src.block_windows(1):
                block = src.read(1, window=window)

                negative = block < 0
                n_clamped += int(np.count_nonzero(negative))
                magnitude_removed += float(-block[negative].sum(dtype=np.float64))
                total_before += float(block.sum(dtype=np.float64))

                np.maximum(block, 0.0, out=block)
                dst.write(block, 1, window=window)

    return {
        "cells_clamped": n_clamped,
        "magnitude_removed": magnitude_removed,
        "total_before": total_before,
        "total_after": total_before + magnitude_removed,
        "pct_of_total": (
            100.0 * magnitude_removed / (total_before + magnitude_removed)
            if total_before + magnitude_removed else 0.0
        ),
    }


def load_ssa_boundaries():
    """Read the boundary file and return one row per SSA country.

    Checks both directions of mismatch against config.SSA_ALL: a country the
    boundary file lacks, and a code it carries that we do not expect. Either
    would quietly change which areas get summed.
    """
    import geopandas as gpd

    boundaries = gpd.read_file(config.BOUNDARY_FILE)
    column = config.BOUNDARY_ISO3_COLUMN

    ssa = boundaries[boundaries[column].isin(config.SSA_ALL)].copy()
    ssa = ssa.rename(columns={column: "iso3c"})
    ssa = ssa[["iso3c", "ADMIN", "geometry"]].sort_values("iso3c")

    found = set(ssa["iso3c"])
    missing = sorted(set(config.SSA_ALL) - found)
    if missing:
        raise ValueError(
            f"boundary file has no polygon for {missing} under {column!r}"
        )

    duplicated = ssa["iso3c"].value_counts()
    duplicated = duplicated[duplicated > 1]
    if len(duplicated):
        raise ValueError(
            "more than one polygon per country, which would double-count:\n"
            f"{duplicated.to_string()}"
        )

    print(f"boundaries: {len(ssa)} SSA countries, CRS {ssa.crs}")
    return ssa


def extract_year(year: int, boundaries, raster_path: Path) -> pd.DataFrame:
    """Sum radiance inside every country border for one year.

    Uses exactextract, which weights each cell by the fraction of it that
    falls inside the polygon. That matters at 15 arcsec: a whole-cell rule
    would hand an entire border cell to one country or neither, and small
    countries have a high ratio of border to area.
    """
    from exactextract import exact_extract

    with rasterio.open(raster_path) as src:
        if boundaries.crs.to_epsg() != src.crs.to_epsg():
            raise ValueError(
                f"CRS mismatch: boundaries are {boundaries.crs}, raster is "
                f"{src.crs}. Reproject before extracting, or the wrong area "
                "is summed."
            )

        results = exact_extract(
            src,
            boundaries,
            ["sum", "count", "mean", "max", "min"],
            include_cols=["iso3c"],
            output="pandas",
        )

    # NOTE ON "count": exactextract's count is the sum of cell coverage
    # fractions over cells with valid data. Because nodata is not set on these
    # rasters, every cell is valid, so this is the country's AREA measured in
    # cells, not a count of lit cells. Naming it area_cells keeps that
    # straight: DR Congo has far more cells than South Africa while being far
    # darker, and a column called "lit_cells" holding area would invite
    # exactly the wrong reading.
    #
    # A real lit-cell count needs a brightness threshold, which is a separate
    # decision; it is not needed for the sum-based measure the brief specifies.
    results = results.rename(columns={
        "sum": "lights_sum",
        "count": "area_cells",
        "mean": "lights_mean",
        "max": "lights_max",
        "min": "lights_min",
    })
    results["year"] = year
    return results


def run_extract_stage(years: list[int] | None = None) -> pd.DataFrame:
    """Stage 2: clamp each cropped raster, then sum within every border.

    Deliberately does NOT apply the near-zero rule or compute log changes:
    those need config.LIGHTS_NEAR_ZERO_THRESHOLD, which is set only after
    looking at the totals this produces. Separating them is what makes it
    possible to choose the threshold on evidence without having already seen
    which countries a particular threshold would drop.
    """
    target_years = years if years is not None else config.YEARS_LEVELS
    config.check_years(target_years)

    boundaries = load_ssa_boundaries()

    frames = []
    clamp_rows = []
    for year in target_years:
        crop = cropped_path(year)
        if not crop.exists():
            raise FileNotFoundError(
                f"no cropped raster for {year} at {crop}. Run stage 1 first: "
                "python -m src.process_lights"
            )

        source = crop
        if config.LIGHTS_CLAMP_NEGATIVES:
            clamped = clamped_path(year)
            if not clamped.exists():
                print(f"{year}: clamping negatives -> {clamped.name}")
                stats = clamp_raster(crop, clamped)
                stats["year"] = year
                clamp_rows.append(stats)
                print(
                    f"  {stats['cells_clamped']:,} cells raised to zero, "
                    f"removing {stats['magnitude_removed']:,.1f} nW/cm2/sr "
                    f"({stats['pct_of_total']:.6f}% of the SSA total)"
                )
            else:
                print(f"{year}: clamped raster already exists")
            source = clamped

        print(f"{year}: extracting from {source.name}")
        frames.append(extract_year(year, boundaries, source))

    lights = pd.concat(frames, ignore_index=True)
    lights = lights[["iso3c", "year", "lights_sum", "area_cells", "lights_mean",
                     "lights_max", "lights_min"]]
    lights = lights.sort_values(["iso3c", "year"]).reset_index(drop=True)

    out_path = config.DATA_INTERIM / "lights_country_year_raw.csv"
    lights.to_csv(out_path, index=False)
    print(f"\ncountry-year totals written to {out_path}")

    if clamp_rows:
        clamp_report = pd.DataFrame(clamp_rows)
        clamp_path = config.DATA_INTERIM / "lights_clamp_report.csv"
        clamp_report.to_csv(clamp_path, index=False)
        print(f"clamp report written to {clamp_path}")

    # --- checks -----------------------------------------------------------
    expected_rows = len(config.SSA_ALL) * len(target_years)
    print(f"\nrows: {len(lights)} (expected {expected_rows})")
    assert len(lights) == expected_rows, "missing country-years in the extract"

    missing_sum = lights["lights_sum"].isna().sum()
    print(f"missing lights_sum: {missing_sum}")

    if config.LIGHTS_CLAMP_NEGATIVES:
        n_negative_min = int((lights["lights_min"] < 0).sum())
        print(f"country-years with a negative minimum cell: {n_negative_min} "
              "(should be 0 after clamping)")
        assert n_negative_min == 0, "clamping did not take effect"

    return lights


# ===========================================================================
# STAGE 3: log changes, the near-zero rule, and the countries it costs
# ===========================================================================


def run_growth_stage(years: list[int] | None = None) -> pd.DataFrame:
    """Turn country-year totals into log changes, and report any country lost.

    This is where config.LIGHTS_NEAR_ZERO_THRESHOLD is applied. A country-year
    at or below it has no usable measurement, and because the panel must stay
    balanced the whole country goes, not just that year.
    """
    if config.LIGHTS_NEAR_ZERO_THRESHOLD is None:
        raise NotImplementedError(
            "Set config.LIGHTS_NEAR_ZERO_THRESHOLD before computing log "
            "changes: the rule for zero or near-zero totals must be fixed "
            "before any results are seen."
        )

    raw_path = config.DATA_INTERIM / "lights_country_year_raw.csv"
    if not raw_path.exists():
        raise FileNotFoundError(
            f"{raw_path} is missing. Run stage 2 first: "
            "python -m src.process_lights --stage extract"
        )

    lights = pd.read_csv(raw_path)
    target_years = years if years is not None else config.YEARS_LEVELS
    lights = lights[lights["year"].isin(target_years)].copy()
    config.check_years(lights["year"].unique())

    # --- apply the near-zero rule ----------------------------------------
    threshold = config.LIGHTS_NEAR_ZERO_THRESHOLD
    below = lights[lights["lights_sum"] <= threshold]
    lost_to_lights = sorted(below["iso3c"].unique())

    print(f"near-zero rule: lights_sum <= {threshold} nW/cm2/sr")
    print(f"  country-years at or below it: {len(below)}")
    print(f"  smallest total in the panel:  {lights['lights_sum'].min():,.1f} "
          f"({lights.loc[lights['lights_sum'].idxmin(), 'iso3c']} "
          f"{lights.loc[lights['lights_sum'].idxmin(), 'year']})")
    if lost_to_lights:
        print(f"  countries dropped: {lost_to_lights}")
        print("  -> add these to config.EXCLUDED_LIGHTS with their reason")
    else:
        print("  countries dropped: none")

    lights = lights[~lights["iso3c"].isin(lost_to_lights)].copy()

    # --- log changes ------------------------------------------------------
    lights = lights.sort_values(["iso3c", "year"])
    lights["ln_lights"] = np.log(lights["lights_sum"])
    # Lag WITHIN country. Grouping first is essential: on a plain sorted frame
    # the first year of one country would difference against the last year of
    # the one before it, which produces a nonsense number that looks fine.
    lights["d_ln_lights"] = lights.groupby("iso3c")["ln_lights"].diff()

    # 2015 exists only to give 2016 its growth rate, so it now drops out.
    growth = lights[lights["year"].isin(config.YEARS_GROWTH)].copy()
    config.check_years(growth["year"].unique(), stage="growth")

    # --- checks -----------------------------------------------------------
    n_countries = growth["iso3c"].nunique()
    expected = n_countries * len(config.YEARS_GROWTH)
    print(f"\nrows {len(growth)} for {n_countries} countries "
          f"x {len(config.YEARS_GROWTH)} years (expected {expected})")
    assert len(growth) == expected, "panel is not rectangular"
    assert growth["d_ln_lights"].notna().all(), "missing growth rates"

    out_path = config.LIGHTS_INTERIM
    growth.to_csv(out_path, index=False)
    print(f"lights series written to {out_path}")

    return growth


def report_sample_effect(growth: pd.DataFrame) -> None:
    """Say what the lights step did to the estimation sample."""
    have_lights = set(growth["iso3c"])
    expected_sample = set(config.EXPECTED_BALANCED_COUNTRIES)

    lost = sorted(expected_sample - have_lights)
    print("\n--- effect on the sample ---")
    print(f"countries in the balanced panel before lights: "
          f"{len(expected_sample)}")
    if lost:
        print(f"lost to the lights step: {len(lost)} {lost}")
        print(f"remaining: {len(expected_sample) - len(lost)} countries, "
              f"{(len(expected_sample) - len(lost)) * len(config.YEARS_GROWTH)} rows")
        print("\nAdd to config.EXCLUDED_LIGHTS, then re-run python -m src.config:")
        for code in lost:
            print(f'    "{code}": "Near-zero radiance",')
    else:
        print("lost to the lights step: none")
        print(f"sample unchanged: {len(expected_sample)} countries, "
              f"{len(expected_sample) * len(config.YEARS_GROWTH)} rows")


def write_series_figure(growth: pd.DataFrame, raw: pd.DataFrame) -> Path:
    """Chart the lights series for the estimation sample.

    Two panels, because they answer different questions:
      left   each country's total indexed to 2015, which shows how far apart
             the countries travel and where the outliers are
      right  the spread of year-on-year log changes, which shows whether any
             YEAR moves the whole panel at once - the signature of a
             compositing change rather than economic growth

    Only the 38 countries in the estimation sample are drawn, since those are
    what the models use.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    sample = config.EXPECTED_BALANCED_COUNTRIES
    levels = raw[raw["iso3c"].isin(sample)].copy()

    base = levels[levels["year"] == config.YEAR_LEVELS_START].set_index("iso3c")
    levels["index_2015"] = (
        100.0 * levels["lights_sum"].values
        / base.loc[levels["iso3c"], "lights_sum"].values
    )

    highlight = {
        "GHA": ("#e6194b", "Ghana"),
        "KEN": ("#3cb44b", "Kenya"),
        "NGA": ("#4363d8", "Nigeria"),
        "ZAF": ("#f58231", "South Africa"),
    }

    fig, (ax1, ax2) = plt.subplots(
        1, 2, figsize=(13.5, 6), dpi=130,
        gridspec_kw={"width_ratios": [1.35, 1]},
    )

    # --- left panel: indexed series -------------------------------------
    for code, group in levels.groupby("iso3c"):
        group = group.sort_values("year")
        if code in highlight:
            continue
        ax1.plot(group["year"], group["index_2015"],
                 color="#b9bcc6", linewidth=0.8, alpha=0.65, zorder=1)

    median = levels.groupby("year")["index_2015"].median()
    ax1.plot(median.index, median.values, color="#222222", linewidth=2.4,
             zorder=3, label="median of the 38")

    for code, (colour, label) in highlight.items():
        group = levels[levels["iso3c"] == code].sort_values("year")
        ax1.plot(group["year"], group["index_2015"], color=colour,
                 linewidth=2.2, zorder=4, label=label)

    ax1.axhline(100, color="#888888", linewidth=0.8, linestyle=":", zorder=0)
    # A log scale is right here: it makes a doubling look the same size
    # wherever it starts, so countries at very different levels are
    # comparable. But matplotlib then labels its own minor ticks in scientific
    # notation ("6 x 10^1") alongside our plain major labels, so the minor
    # formatter is silenced.
    ax1.set_yscale("log")
    ax1.set_yticks([50, 75, 100, 150, 200, 300, 400])
    ax1.get_yaxis().set_major_formatter(matplotlib.ticker.ScalarFormatter())
    ax1.get_yaxis().set_minor_formatter(matplotlib.ticker.NullFormatter())
    ax1.set_ylim(levels["index_2015"].min() * 0.92,
                 levels["index_2015"].max() * 1.08)
    ax1.set_ylabel("total radiance, 2015 = 100 (log scale)")
    ax1.set_xlabel("year")
    ax1.set_title("Night-lights totals, indexed to 2015", fontsize=11)
    ax1.legend(frameon=False, fontsize=8.5, loc="upper left")
    ax1.grid(axis="y", color="#e8e8ec", linewidth=0.7)
    ax1.set_axisbelow(True)

    # --- right panel: spread of growth rates by year ---------------------
    in_sample = growth[growth["iso3c"].isin(sample)]
    years = sorted(in_sample["year"].unique())
    data = [in_sample.loc[in_sample["year"] == y, "d_ln_lights"] for y in years]

    parts = ax2.boxplot(data, tick_labels=years, widths=0.6,
                        patch_artist=True, showfliers=True)
    for patch in parts["boxes"]:
        patch.set_facecolor("#cfd8e8")
        patch.set_edgecolor("#4a5568")
    for whisker in parts["whiskers"] + parts["caps"]:
        whisker.set_color("#4a5568")
    for med in parts["medians"]:
        med.set_color("#c0392b")
        med.set_linewidth(1.8)

    ax2.axhline(0, color="#888888", linewidth=0.8, linestyle=":")
    ax2.set_ylabel("change in log total radiance")
    ax2.set_xlabel("year")
    ax2.set_title("Year-on-year log changes across the 38", fontsize=11)
    ax2.grid(axis="y", color="#e8e8ec", linewidth=0.7)
    ax2.set_axisbelow(True)

    fig.suptitle(
        f"Sub-Saharan Africa night-lights series, VIIRS {config.VIIRS_VERSION} "
        f"{config.VIIRS_BAND}, estimation sample of {len(sample)} countries",
        fontsize=12.5, y=0.99,
    )
    fig.text(
        0.005, 0.005,
        "Totals are the sum of radiance within national land borders, "
        "negatives clamped to zero. Note that 2017 shifts the whole panel up "
        "at once, which growth in 38 separate economies would not do; year "
        "fixed effects absorb a common shift of this kind.",
        fontsize=7.5, color="#55555f", ha="left", va="bottom",
    )
    fig.tight_layout(rect=(0, 0.035, 1, 0.97))

    out_path = config.OUTPUTS_FIGURES / "lights_series.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path)
    plt.close(fig)
    print(f"series figure written to {out_path}")
    return out_path


def main() -> None:
    """Run the lights pipeline stages."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--stage", choices=["crop", "extract", "growth", "all"], default="crop",
        help="which stage to run (default: crop)",
    )
    parser.add_argument(
        "--years", type=int, nargs="+", default=None,
        help="years to process (default: all of config.YEARS_LEVELS)",
    )
    parser.add_argument(
        "--overwrite", action="store_true",
        help="redo years whose output already exists",
    )
    args = parser.parse_args()

    if args.stage in ("crop", "all"):
        report = run_crop_stage(years=args.years, overwrite=args.overwrite)
        if not report.empty:
            print("\n--- crop summary ---")
            summary = report[["year", "n_negative", "pct_negative", "min_value",
                              "max_value", "size_mb", "crop_seconds"]]
            print(summary.to_string(index=False))

    if args.stage in ("extract", "all"):
        lights = run_extract_stage(years=args.years)
        print("\n--- 10 largest country totals, final year ---")
        last = lights[lights["year"] == max(lights["year"])]
        top = last.nlargest(10, "lights_sum")[
            ["iso3c", "lights_sum", "area_cells", "lights_mean"]
        ]
        print(top.to_string(index=False))

    if args.stage in ("growth", "all"):
        growth = run_growth_stage(years=args.years)
        report_sample_effect(growth)
        print("\n--- d_ln_lights by year, across countries ---")
        print(growth.groupby("year")["d_ln_lights"].agg(
            ["median", "mean", "std", "min", "max"]).round(4).to_string())

        raw = pd.read_csv(config.DATA_INTERIM / "lights_country_year_raw.csv")
        write_series_figure(growth, raw)

    if args.stage == "crop":
        print("\nStage 1 complete. Run --stage extract for country totals.")


if __name__ == "__main__":
    main()
