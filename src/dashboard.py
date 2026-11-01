"""Step 8: build the interactive results dashboard.

Run from the project root, after models.py:

    python -m src.dashboard
    python -m src.dashboard --open      # and open it in the browser

INPUT
    data/processed/ssa_panel.csv            the estimation panel
    data/interim/vdem_accountability.csv    country names
    outputs/tables/panel_fitted.csv         per-observation prediction and
                                            residual, from models.py
    outputs/tables/main_results.csv         headline coefficients
    outputs/tables/check_model.csv          the beta = 1 test
    outputs/tables/minimum_detectable_effects.csv

OUTPUT
    outputs/dashboard.html      one self-contained file, no server needed

WHY IT IS BUILT THIS WAY
    Python does every calculation; the page only draws. Nothing is computed
    in JavaScript that could disagree with the pipeline, so the dashboard
    cannot drift away from the numbers in the tables. The charts are plain
    SVG written by hand rather than a charting library: it keeps the project
    to its existing dependencies, the output works offline from a file:// URL,
    and it gives exact control over the look.

    Every figure shown is read from the committed outputs. The dashboard has
    no opinions of its own and no hard-coded results: if models.py is re-run
    and a number changes, the dashboard changes with it.

THE ORGANISING IDEA
    Countries are ranked by DIVERGENCE, and divergence can be read four ways,
    which is why the ranking is sortable rather than fixed:

      mean gap        signed. Negative means lights grew faster than
                      reported GDP, which is the direction the
                      under-reporting story predicts.
      mean |gap|      size of the disagreement, ignoring direction. This is
                      the noise measure, and the one statistical capacity
                      should move.
      volatility      standard deviation of the gap within the country. A
                      country can have a small average gap made of large
                      swings in both directions.
      largest year    the single worst year, which is what a case study
                      would start from.

A WARNING THE PAGE REPEATS, AND SO DOES THIS DOCSTRING
    A large divergence is NOT evidence of misreporting. Night lights miss
    agriculture, the informal economy and off-grid activity, and they pick up
    gas flaring and electrification. The 2017 detection change inflates growth
    for dim countries specifically. Ranking countries by divergence is a way
    of choosing where to look, not a league table of statistical honesty.
"""

import argparse
import json
import webbrowser
from pathlib import Path

import numpy as np
import pandas as pd

from src import config

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
TEMPLATE_NAME = "dashboard.html.j2"


def load_everything(panel_path: Path | None = None) -> dict:
    """Read the panel and every results table the dashboard displays."""
    panel = pd.read_csv(config.PANEL_FILE if panel_path is None else panel_path)
    print(f"panel: {len(panel)} rows, {panel['iso3c'].nunique()} countries")

    countries, n_rows = config.expected_sample()
    if len(panel) != n_rows:
        raise ValueError(
            f"the panel has {len(panel)} rows but config.expected_sample() "
            f"says {n_rows}. Rebuild it before building the dashboard."
        )

    # Country names come from the V-Dem table, which is the only interim file
    # that carries them. Falling back to the ISO code keeps the dashboard
    # working if that ever changes.
    names = {}
    vdem_path = config.DATA_INTERIM / "vdem_accountability.csv"
    if vdem_path.exists():
        vdem = pd.read_csv(vdem_path)
        if "country_name" in vdem.columns:
            names = dict(zip(vdem["iso3c"], vdem["country_name"]))
    missing_names = sorted(set(panel["iso3c"]) - set(names))
    if missing_names:
        print(f"  no country name for {missing_names}; using the ISO code")

    fitted_path = config.OUTPUTS_TABLES / "panel_fitted.csv"
    if not fitted_path.exists():
        raise FileNotFoundError(
            f"{fitted_path} not found. Run `python -m src.models` first: the "
            "dashboard shows the model's prediction and residual per "
            "country-year, which only that step produces."
        )
    fitted = pd.read_csv(fitted_path)
    panel = panel.merge(fitted[["iso3c", "year", "prediction", "residual"]],
                        on=["iso3c", "year"], how="left", validate="one_to_one")
    if panel["prediction"].isna().any():
        raise ValueError(
            "some country-years have no model prediction. panel_fitted.csv is "
            "out of date with the panel; re-run models.py."
        )

    return {"panel": panel, "names": names}


def read_headline_numbers() -> dict:
    """Pull the headline results out of the committed tables.

    Read rather than restated, so the dashboard cannot quietly disagree with
    the model output sitting next to it.
    """
    numbers = {}

    main = pd.read_csv(config.OUTPUTS_TABLES / "main_results.csv")
    main = main[main["specification"] == "main FE"]
    for outcome, term, key in [
        (config.OUTCOME_ABSOLUTE, config.CAPACITY_MAIN + "_c", "capacity"),
        (config.OUTCOME_SIGNED, config.ACCOUNTABILITY_MAIN + "_c",
         "accountability"),
    ]:
        row = main[(main["outcome"] == outcome) & (main["term"] == term)]
        if len(row):
            numbers[key] = {
                "outcome": outcome,
                "coefficient": float(row["coefficient"].iloc[0]),
                "std_error": float(row["std_error"].iloc[0]),
                "p_value": float(row["p_value"].iloc[0]),
            }

    check = pd.read_csv(config.OUTPUTS_TABLES / "check_model.csv")
    beta_test = check[check["term"].str.startswith("test beta")]
    if len(beta_test):
        numbers["beta"] = {
            "estimate": float(beta_test["coefficient"].iloc[0]),
            "std_error": float(beta_test["std_error"].iloc[0]),
            "t_stat": float(beta_test["t_stat"].iloc[0]),
            "p_value": float(beta_test["p_value"].iloc[0]),
            "null": config.BETA_NULL,
        }

    mde_path = config.OUTPUTS_TABLES / "minimum_detectable_effects.csv"
    if mde_path.exists():
        mde = pd.read_csv(mde_path)
        numbers["mde"] = [
            {"term": r["term"], "outcome": r["outcome"],
             "mde_in_sd": float(r["mde_in_outcome_sd"]),
             "observed_in_sd": float(r["observed_in_outcome_sd"])}
            for _, r in mde.iterrows()
        ]
    return numbers


def build_country_records(panel: pd.DataFrame, names: dict) -> list[dict]:
    """One record per country: the ranking metrics plus the yearly series."""
    records = []
    for iso, rows in panel.groupby("iso3c"):
        rows = rows.sort_values("year")
        gap = rows[config.OUTCOME_SIGNED]

        # The four ways of reading divergence. Each is a different question,
        # which is why the dashboard offers all four rather than picking one.
        worst_index = gap.abs().idxmax()
        records.append({
            "iso3c": iso,
            "name": names.get(iso, iso),
            "mean_gap": float(gap.mean()),
            "mean_abs_gap": float(rows[config.OUTCOME_ABSOLUTE].mean()),
            "volatility": float(gap.std()),
            "worst_gap": float(gap.loc[worst_index]),
            "worst_year": int(rows.loc[worst_index, "year"]),
            "mean_d_ln_gdp": float(rows["d_ln_gdp"].mean()),
            "mean_d_ln_lights": float(rows["d_ln_lights"].mean()),
            "mean_gap_bright": float(rows["gap_bright"].mean()),
            "spi_rebuilt": float(rows[config.CAPACITY_MAIN].mean()),
            "spi_overall": float(rows["spi_overall"].mean()),
            "accountability": float(
                rows[config.ACCOUNTABILITY_MAIN].mean()),
            "elec_access_start": float(rows["elec_access"].iloc[0]),
            "elec_access_end": float(rows["elec_access"].iloc[-1]),
            "elec_change_total": float(rows["elec_access_change"].sum()),
            "agri_share": float(rows["agri_share"].mean()),
            "oil_rents": float(rows["oil_rents"].mean()),
            "rebasing_years": [int(y) for y in
                               rows.loc[rows["rebased"] == 1, "year"]],
            "is_case_study": iso in config.CASE_STUDIES,
            "is_oil_producer": iso in config.OIL_PRODUCERS,
            "series": [
                {
                    "year": int(r["year"]),
                    "d_ln_gdp": float(r["d_ln_gdp"]),
                    "d_ln_lights": float(r["d_ln_lights"]),
                    "d_ln_lights_bright": float(r["d_ln_lights_bright"]),
                    "gap": float(r[config.OUTCOME_SIGNED]),
                    "gap_bright": float(r["gap_bright"]),
                    "prediction": float(r["prediction"]),
                    "residual": float(r["residual"]),
                    "spi_rebuilt": float(r[config.CAPACITY_MAIN]),
                    "accountability": float(r[config.ACCOUNTABILITY_MAIN]),
                    "elec_access": float(r["elec_access"]),
                    "stringency": float(r["covid_stringency"]),
                    "rebased": int(r["rebased"]),
                }
                for _, r in rows.iterrows()
            ],
        })
    records.sort(key=lambda record: record["mean_gap"])
    return records


def build_year_summary(panel: pd.DataFrame) -> list[dict]:
    """Panel-wide distribution of the gap, year by year."""
    summary = []
    for year, rows in panel.groupby("year"):
        gap = rows[config.OUTCOME_SIGNED]
        summary.append({
            "year": int(year),
            "median": float(gap.median()),
            "q1": float(gap.quantile(0.25)),
            "q3": float(gap.quantile(0.75)),
            "min": float(gap.min()),
            "max": float(gap.max()),
            "share_negative": float((gap < 0).mean()),
            "median_d_ln_gdp": float(rows["d_ln_gdp"].median()),
            "median_d_ln_lights": float(rows["d_ln_lights"].median()),
        })
    return summary


# The map window, in degrees: west, south, east, north. Chosen rather than
# taken from the data's own bounds, which run to -47 south (South Africa's
# Prince Edward Islands) and 63.5 east (Mauritius's Rodrigues) and would put
# most of the picture in empty ocean. Those two outliers are clipped; every
# country still appears, which build_map() checks.
MAP_WINDOW = (-26.0, -36.0, 58.0, 28.0)
MAP_SCALE = 10          # SVG units per degree
MAP_TOLERANCE = 0.08    # simplification, in degrees


def build_map() -> dict:
    """Turn the Natural Earth boundaries into SVG paths, one per country.

    The same boundary file the night-lights step sums radiance inside, so the
    shape on screen is the shape the data was measured in rather than a
    decorative outline from somewhere else.

    Plain equirectangular projection: at these latitudes it is close enough
    to undistorted, and the map is a locator, not a measuring instrument.
    """
    from shapely.geometry import box

    from src.process_lights import load_ssa_boundaries

    boundaries = load_ssa_boundaries()
    west, south, east, north = MAP_WINDOW
    window = box(west, south, east, north)

    paths = {}
    for _, row in boundaries.iterrows():
        geometry = row.geometry.intersection(window)
        if geometry.is_empty:
            continue
        geometry = geometry.simplify(MAP_TOLERANCE, preserve_topology=True)
        if geometry.is_empty:
            continue

        parts = (list(geometry.geoms) if geometry.geom_type == "MultiPolygon"
                 else [geometry])
        pieces = []
        for polygon in parts:
            xs, ys = polygon.exterior.coords.xy
            points = [f"{(x - west) * MAP_SCALE:.0f},"
                      f"{(north - y) * MAP_SCALE:.0f}"
                      for x, y in zip(xs, ys)]
            if len(points) > 2:
                pieces.append("M" + "L".join(points) + "Z")
        if pieces:
            paths[row["iso3c"]] = "".join(pieces)

    missing = sorted(set(config.SSA_ALL) - set(paths))
    if missing:
        raise ValueError(
            f"no map path for {missing}. The display window {MAP_WINDOW} "
            "clips them out entirely, or the simplification tolerance "
            f"({MAP_TOLERANCE}) removed them. Widen one or the other: a "
            "country in the panel must be on the map."
        )
    print(f"  map: {len(paths)} country outlines, "
          f"{sum(len(p) for p in paths.values()) / 1024:.0f} KB of path data")

    return {
        "width": int((east - west) * MAP_SCALE),
        "height": int((north - south) * MAP_SCALE),
        "paths": paths,
    }


def describe_file(path: Path) -> dict:
    """Report whether a raw file is actually here, and how big it is.

    Read off the filesystem rather than copied from the README, because the
    README's download table went stale once the files arrived and a sources
    list that says "not yet downloaded" about a file sitting on disk is worse
    than no sources list.
    """
    if path.exists():
        size = path.stat().st_size
        unit = "MB" if size >= 1_000_000 else "KB"
        shown = size / (1_000_000 if unit == "MB" else 1_000)
        return {"present": True, "size": f"{shown:.1f} {unit}"}
    return {"present": False, "size": "—"}


def build_sources() -> list[dict]:
    """Where every number in this dashboard comes from."""
    wdi_vintage = "—"
    vintage_path = config.DATA_INTERIM / "wdi_vintage.csv"
    if vintage_path.exists():
        vintage = pd.read_csv(vintage_path)
        dates = sorted(set(vintage["last_updated"].astype(str)))
        wdi_vintage = ", ".join(dates)

    wdi_files = sorted(config.DATA_RAW.glob("API_*.csv"))
    wdi_present = {"present": bool(wdi_files),
                   "size": f"{len(wdi_files)} files"}

    rasters = sorted(config.LIGHTS_RASTER_DIR.glob(
        config.LIGHTS_RASTER_PATTERN.replace("{year}", "*")))
    raster_bytes = sum(r.stat().st_size for r in rasters) if rasters else 0

    return [
        {
            "name": "World Bank WDI",
            "provides": "GDP (constant LCU and growth), agriculture share, "
                        "electricity access, urban share, population, "
                        "oil rents",
            "detail": "NY.GDP.MKTP.KN · NY.GDP.MKTP.KD.ZG · NV.AGR.TOTL.ZS · "
                      "EG.ELC.ACCS.ZS · SP.URB.TOTL.IN.ZS · SP.POP.TOTL · "
                      "NY.GDP.PETR.RT.ZS",
            "vintage": f"last updated {wdi_vintage}",
            "url": "https://databank.worldbank.org/source/"
                   "world-development-indicators",
            "note": "GDP levels are in each country's own currency at its own "
                    "base year, so they are never compared across countries — "
                    "only differenced within one.",
            **wdi_present,
        },
        {
            "name": "EOG VIIRS Nighttime Lights",
            "provides": "The night-lights side of every gap on this page",
            "detail": f"VNL {config.VIIRS_VERSION} annual composites "
                      f"{min(config.YEARS_LEVELS)}–{max(config.YEARS_LEVELS)}, "
                      "average_masked band, 15 arc-second",
            "vintage": f"{len(rasters)} annual rasters",
            "url": "https://eogdata.mines.edu/products/vnl/",
            "note": "Summed inside national borders with area-weighted zonal "
                    "statistics. The 2017 composite changed detection "
                    "sensitivity, which inflates growth for dim countries — "
                    "hence the bright-cells series shown alongside.",
            "present": bool(rasters),
            "size": (f"{raster_bytes / 1_000_000:.0f} MB"
                     if raster_bytes else "—"),
        },
        {
            "name": "Natural Earth",
            "provides": "Country boundaries used to sum radiance per country",
            "detail": "1:10m Admin 0 Countries, version 5.1.1, "
                      f"ISO3 from the {config.BOUNDARY_ISO3_COLUMN} column",
            "vintage": "public domain",
            "url": "https://www.naturalearthdata.com/",
            "note": "Checked both ways against the 48-country list: no "
                    "country missing, no extra polygon, no duplicates.",
            **describe_file(config.BOUNDARY_FILE),
        },
        {
            "name": "World Bank SPI",
            "provides": "Statistical capacity — the published index, its five "
                        "pillars, and the rebuilt version used here",
            "detail": "SPI_index.csv (published scores) and SPI_data.csv "
                      "(indicator level, 2004–2024)",
            "vintage": "2016–2024",
            "url": "https://github.com/worldbank/SPI",
            "note": "Pillar 5 is Dimension 5.2 alone, and two of its ten "
                    "indicators describe the GDP series itself. Those two are "
                    "removed in the rebuilt score, after reproducing the "
                    "published index exactly.",
            **describe_file(config.SPI_INDEX_FILE),
        },
        {
            "name": "V-Dem",
            "provides": "Political accountability, and its vertical, "
                        "horizontal and diagonal components",
            "detail": "Country-Year Full+Others v16, v2x_accountability",
            "vintage": "published 2026, covers 1789–2025",
            "url": "https://v-dem.net/data/the-v-dem-dataset/",
            "note": "Varies about 4.6× more between countries than within "
                    "them, so fixed effects identify it weakly.",
            **describe_file(config.VDEM_FILE),
        },
        {
            "name": "OxCGRT",
            "provides": "COVID-19 policy stringency, 2020–2021",
            "detail": "OxCGRT_nat_latest.csv, "
                      f"{config.OXCGRT_STRINGENCY_COLUMN}, daily → annual mean",
            "vintage": "daily 2020-01-01 to 2023-02-28",
            "url": "https://github.com/OxCGRT/covid-policy-tracker",
            "note": "Set to 0 for 2016–2019: there was no pandemic policy to "
                    "measure, so zero is the true value, not a gap. Missing "
                    "for Guinea-Bissau and São Tomé, which is why the panel "
                    "is 38 countries and not 40.",
            **describe_file(config.OXCGRT_FILE),
        },
        {
            "name": "National statistics offices",
            "provides": "GDP rebasing dates",
            "detail": "SPI raw column RAW.D5.2.2.NABY, plus official release "
                      "dates where they differ",
            "vintage": "—",
            "url": "https://www.knbs.or.ke/press-release-on-launch-of-the-"
                   "revised-national-accounts-estimates/",
            "note": "Kenya's 2016 base year appears in SPI only from 2022, but "
                    "KNBS released it in September 2021, so the official date "
                    "is used instead.",
            "present": True, "size": "—",
        },
    ]


# The processed tables this project produces, in pipeline order. These are
# OUTPUTS, not sources: each one is what a loader made from the raw files.
PROCESSED = [
    ("ssa_panel.csv", "processed", "build_panel.py",
     "The estimation panel. Everything the models run on: 38 countries x 6 "
     "years, with the gap, both lights measures, capacity, accountability, "
     "the controls and the rebasing dummy."),
    ("wdi_long.csv", "interim", "load_wdi.py",
     "Seven World Bank indicators reshaped to one row per country-year. GDP "
     "is kept in constant local currency, never converted: only its log "
     "difference is used."),
    ("lights_country_year.csv", "interim", "process_lights.py",
     "Night-lights totals and growth rates per country-year, summed inside "
     "national borders from the VIIRS rasters. Carries both the all-cells "
     "and the bright-cells measure."),
    ("lights_country_year_raw.csv", "interim", "process_lights.py",
     "The same radiance totals as levels for 2015-2021, before differencing. "
     "2015 exists only as the base year for 2016 growth."),
    ("spi_published.csv", "interim", "load_spi.py",
     "The World Bank's published SPI scores and all five pillars, subset to "
     "Sub-Saharan Africa."),
    ("spi_rebuilt.csv", "interim", "rebuild_spi.py",
     "SPI rebuilt without the two indicators that describe the GDP series "
     "itself, after reproducing the published index exactly. Carries the "
     "published score alongside for comparison."),
    ("rebasing_dummy.csv", "interim", "rebuild_spi.py",
     "Base year per country-year and a 0/1 flag for the years it changed, "
     "with a status column recording how each text base year was read."),
    ("vdem_accountability.csv", "interim", "load_vdem.py",
     "V-Dem accountability and its vertical, horizontal and diagonal "
     "components: 7 columns pulled from a 4,618-column source file."),
    ("oxcgrt_annual.csv", "interim", "load_oxcgrt.py",
     "COVID policy stringency averaged from daily to annual, zero for "
     "2016-2019 because there was no pandemic policy to measure."),
    ("panel_fitted.csv", "tables", "models.py",
     "The model's prediction and residual for every country-year, which is "
     "what the gap-versus-prediction chart draws."),
]


def build_datasets(embed: bool = True) -> list[dict]:
    """Describe (and optionally embed) every table the pipeline produced.

    Embedding makes the dashboard a portable copy of the processed data:
    one file that can be sent to a supervisor who can then read the numbers
    behind any chart without the repository. It roughly triples the file
    size, which is still small, and --no-embed turns it off.
    """
    folders = {"processed": config.DATA_PROCESSED,
               "interim": config.DATA_INTERIM,
               "tables": config.OUTPUTS_TABLES}

    datasets = []
    for filename, where, producer, description in PROCESSED:
        path = folders[where] / filename
        record = {"file": filename, "folder": where, "producer": producer,
                  "description": description, "present": path.exists(),
                  "rows": None, "columns": None, "size": "—", "csv": None}
        if path.exists():
            frame = pd.read_csv(path)
            record["rows"] = int(len(frame))
            record["columns"] = int(len(frame.columns))
            record["column_names"] = list(frame.columns)
            size = path.stat().st_size
            record["size"] = (f"{size / 1_000_000:.1f} MB" if size >= 1_000_000
                              else f"{size / 1000:.0f} KB")
            if embed:
                record["csv"] = path.read_text(encoding="utf-8")
        datasets.append(record)

    present = sum(1 for d in datasets if d["present"])
    embedded = sum(1 for d in datasets if d["csv"])
    total = sum(len(d["csv"]) for d in datasets if d["csv"])
    print(f"  datasets: {present} of {len(datasets)} present, "
          f"{embedded} embedded ({total / 1024:.0f} KB)")
    return datasets


def build_context(panel: pd.DataFrame) -> dict:
    """Live figures for the rationale section.

    Computed rather than written into the template, because a motivating
    statistic that has quietly stopped being true is worse than none. If the
    data changes, the argument on the page changes with it.
    """
    by_country = panel.groupby("iso3c")[config.OUTCOME_SIGNED].mean()
    lights_by_year = panel.groupby("year")["d_ln_lights"].median()
    artefact_year = int(lights_by_year.idxmax())
    others = lights_by_year.drop(artefact_year)

    median_abs_gap = float(panel[config.OUTCOME_ABSOLUTE].median())
    median_growth = float(panel["d_ln_gdp"].median())

    return {
        "n_negative_countries": int((by_country < 0).sum()),
        "n_countries": int(len(by_country)),
        "median_abs_gap": median_abs_gap,
        "median_growth": median_growth,
        # The figure that makes the case: the typical year-to-year
        # disagreement is a multiple of the typical growth rate, so this is
        # not a rounding-error problem.
        "disagreement_ratio": median_abs_gap / median_growth,
        "median_lights_growth": float(panel["d_ln_lights"].median()),
        "artefact_year": artefact_year,
        "artefact_median": float(lights_by_year.max()),
        "other_years_median": float(others.median()),
        "n_rebasing": int(panel["rebased"].sum()),
        "n_rebasing_countries": int(
            panel.loc[panel["rebased"] == 1, "iso3c"].nunique()),
        "widest": by_country.idxmin(),
        "widest_value": float(by_country.min()),
    }


def build_specification() -> dict:
    """The equations the dashboard displays, with every symbol explained.

    Kept here rather than written into the template so that the variable
    names come from config: if the main capacity measure changes, the
    equation on the page changes with it instead of quietly going stale.
    """
    return {
        "gap": {
            "latex": "gap<sub>it</sub> &nbsp;=&nbsp; Δln GDP<sub>it</sub> "
                     "&nbsp;−&nbsp; Δln L<sub>it</sub>",
            "words": "The outcome. How much faster reported GDP grew than "
                     "night lights did, in country i in year t. Negative "
                     "means lights grew faster.",
            "chart": "Every bar in the gap chart, and the vertical distance "
                     "between the two lines in the growth trace.",
        },
        "main": {
            "latex": "gap<sub>it</sub> = α + <b>θ</b>·SPI<sub>it</sub> + "
                     "<b>φ</b>·Acc<sub>it</sub> + "
                     "π′X<sub>it</sub> + <b>μ<sub>i</sub></b> + "
                     "<b>λ<sub>t</sub></b> + ε<sub>it</sub>",
            "words": "The main specification, estimated with country and "
                     "year fixed effects and standard errors clustered by "
                     "country.",
        },
        "check": {
            "latex": "Δln GDP<sub>it</sub> = α + <b>β</b>·Δln L<sub>it</sub> "
                     "+ <b>γ</b>·(Δln L<sub>it</sub>×SPI<sub>it</sub>) + "
                     "<b>δ</b>·(Δln L<sub>it</sub>×Acc<sub>it</sub>) + "
                     "π′X<sub>it</sub> + μ<sub>i</sub> + λ<sub>t</sub> + "
                     "ε<sub>it</sub>",
            "words": "The check model. The gap above is this model with β "
                     "forced to 1 and γ = δ = 0, so estimating β tests the "
                     "gap's central assumption instead of assuming it.",
        },
        "symbols": [
            {"sym": "i", "name": "country",
             "means": f"One of the {len(config.EXPECTED_BALANCED_COUNTRIES)} "
                      "countries in the balanced panel.",
             "chart": "One row in the ranking, one dot in the scatter."},
            {"sym": "t", "name": "year",
             "means": f"{min(config.YEARS_GROWTH)} to "
                      f"{max(config.YEARS_GROWTH)}, six years.",
             "chart": "The x-axis of every time-series chart."},
            {"sym": "Δln", "name": "log difference",
             "means": "ln(value this year) − ln(value last year). A growth "
                      "rate that is unit-free, so a country's own currency "
                      "cancels out. 0.05 ≈ 5% growth.",
             "chart": "Both lines in the growth trace."},
            {"sym": "L", "name": "night lights",
             "means": "Total VIIRS radiance summed inside the country's "
                      "borders. The bright-cells version counts only cells "
                      "above a fixed 5 nW/cm²/sr floor.",
             "chart": "The violet line; the rose dashed line is the "
                      "bright-cells version."},
            {"sym": "θ", "name": "theta — capacity effect",
             "means": "What the dissertation is testing. How much the gap "
                      "moves with statistical capacity, within a country. "
                      "Expected negative on the ABSOLUTE gap: better "
                      "statistics, smaller disagreement either way.",
             "chart": "The slope you would see in the scatter if capacity "
                      "explained divergence. Estimated at "
                      f"{read_headline_numbers().get('capacity', {}).get('coefficient', float('nan')):+.5f}, "
                      "not distinguishable from zero."},
            {"sym": "φ", "name": "phi — accountability effect",
             "means": "How much the gap moves with political "
                      "accountability. Expected negative on the SIGNED gap: "
                      "weaker accountability, GDP grows faster than lights.",
             "chart": "The scatter's accountability axis. Estimated at "
                      f"{read_headline_numbers().get('accountability', {}).get('coefficient', float('nan')):+.4f}, "
                      "not distinguishable from zero."},
            {"sym": "β", "name": "beta — lights elasticity",
             "means": "How much reported GDP moves when lights move 1%. The "
                      "simple gap assumes this is exactly 1.",
             "chart": "Not drawn directly. Estimated at "
                      f"{read_headline_numbers().get('beta', {}).get('estimate', float('nan')):.3f}, "
                      "and H₀: β = 1 is rejected — so the gap is a "
                      "difference in growth rates, not an elasticity."},
            {"sym": "γ, δ", "name": "gamma, delta — interactions",
             "means": "Whether the lights-to-GDP relationship itself depends "
                      "on capacity or accountability, rather than just "
                      "shifting the gap up or down.",
             "chart": "Not drawn. Both are small and insignificant."},
            {"sym": "X", "name": "controls",
             "means": "Agriculture share, change in electricity access, "
                      "urban share, log population, COVID stringency. Things "
                      "that move the gap for mechanical reasons.",
             "chart": "The scatter's electrification and agriculture axes "
                      "show two of them."},
            {"sym": "μ<sub>i</sub>", "name": "country fixed effect",
             "means": "One intercept per country. Absorbs each country's "
                      "average gap and anything about it that does not "
                      "change — geography, currency, how its statistics "
                      "office works.",
             "chart": "Why the prediction line sits near each country's own "
                      "average rather than near zero."},
            {"sym": "λ<sub>t</sub>", "name": "year fixed effect",
             "means": "One intercept per year. Absorbs shocks common to all "
                      "countries, such as the global part of COVID. It "
                      "CANNOT absorb the 2017 detection change, because that "
                      "hit dim countries harder than bright ones.",
             "chart": "Why the year distribution chart matters: 2017 is low "
                      "for a measurement reason, not an economic one."},
            {"sym": "ε<sub>it</sub>", "name": "residual",
             "means": "What the model does not explain for that country-year.",
             "chart": "The vertical distance between a bar and the dashed "
                      "prediction line."},
        ],
    }


def build_payload(data: dict) -> dict:
    """Assemble everything the page needs into one JSON-serialisable dict."""
    panel = data["panel"]
    countries = build_country_records(panel, data["names"])
    gap = panel[config.OUTCOME_SIGNED]

    payload = {
        "meta": {
            "n_obs": int(len(panel)),
            "n_countries": int(panel["iso3c"].nunique()),
            "year_min": int(panel["year"].min()),
            "year_max": int(panel["year"].max()),
            "share_negative": float((gap < 0).mean()),
            "n_negative": int((gap < 0).sum()),
            "mean_gap": float(gap.mean()),
            "capacity_label": config.CAPACITY_MAIN,
            "accountability_label": config.ACCOUNTABILITY_MAIN,
            "case_studies": config.CASE_STUDIES,
        },
        "countries": countries,
        "years": build_year_summary(panel),
        "results": read_headline_numbers(),
        "sources": build_sources(),
        "datasets": build_datasets(embed=data.get("embed", True)),
        "spec": build_specification(),
        "context": build_context(panel),
        "map": build_map(),
    }

    # The scales the charts share, computed here so every chart of the same
    # quantity uses the same axis and two countries can be compared by eye.
    growth = pd.concat([panel["d_ln_gdp"], panel["d_ln_lights"]])
    payload["scales"] = {
        "growth_min": float(growth.min()), "growth_max": float(growth.max()),
        "gap_min": float(gap.min()), "gap_max": float(gap.max()),
        "spi_min": float(panel[config.CAPACITY_MAIN].min()),
        "spi_max": float(panel[config.CAPACITY_MAIN].max()),
        "acc_min": float(panel[config.ACCOUNTABILITY_MAIN].min()),
        "acc_max": float(panel[config.ACCOUNTABILITY_MAIN].max()),
    }
    return payload


def check_payload(payload: dict) -> None:
    """Confirm the payload says the same thing as the pipeline."""
    print("\n--- checks ---")
    countries, n_rows = config.expected_sample()

    n_country_records = len(payload["countries"])
    assert n_country_records == len(countries), (
        f"{n_country_records} country records, expected {len(countries)}"
    )
    print(f"  PASS  {n_country_records} country records")

    total_points = sum(len(c["series"]) for c in payload["countries"])
    assert total_points == n_rows, (
        f"{total_points} country-year points, expected {n_rows}"
    )
    print(f"  PASS  {total_points} country-year points")

    # Every gap must equal its two components, in the payload itself and not
    # only upstream: a mistake in assembling the JSON would show up here.
    worst = 0.0
    for country in payload["countries"]:
        for point in country["series"]:
            difference = abs(point["d_ln_gdp"] - point["d_ln_lights"]
                             - point["gap"])
            worst = max(worst, difference)
    assert worst < 1e-9, f"gap does not equal its components (max {worst:.3e})"
    print(f"  PASS  gap = d_ln_gdp - d_ln_lights everywhere "
          f"(max difference {worst:.1e})")

    # And the same for the model's decomposition.
    worst = 0.0
    for country in payload["countries"]:
        for point in country["series"]:
            difference = abs(point["gap"] - point["prediction"]
                             - point["residual"])
            worst = max(worst, difference)
    assert worst < 1e-9, f"gap != prediction + residual (max {worst:.3e})"
    print(f"  PASS  gap = prediction + residual everywhere "
          f"(max difference {worst:.1e})")

    expected_negative = payload["meta"]["n_negative"]
    counted = sum(1 for c in payload["countries"] for p in c["series"]
                  if p["gap"] < 0)
    assert counted == expected_negative, (
        f"{counted} negative gaps in the series, header says "
        f"{expected_negative}"
    )
    print(f"  PASS  {counted} negative gaps, matching the header figure")

    for iso in config.CASE_STUDIES:
        assert any(c["iso3c"] == iso for c in payload["countries"]), (
            f"{iso} is a case study but is not in the dashboard"
        )
    print(f"  PASS  both case studies present")

    results = payload["results"]
    for key in ["capacity", "accountability", "beta"]:
        assert key in results, f"no {key} figure read from the results tables"
    print(f"  PASS  headline results read from the tables "
          f"(beta = {results['beta']['estimate']:.3f})")

    # A sources list that claims a file is present when it is not would be
    # worse than none, so the presence flags are reported rather than assumed.
    missing = [s["name"] for s in payload["sources"] if not s["present"]]
    print(f"  INFO  {len(payload['sources'])} sources listed; "
          f"{'all raw files present' if not missing else 'MISSING: ' + ', '.join(missing)}")


def render(payload: dict, out_path: Path) -> None:
    """Fill the template with the payload and write the single HTML file."""
    from jinja2 import Environment, FileSystemLoader, select_autoescape

    environment = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(["html"]),
    )
    template = environment.get_template(TEMPLATE_NAME)

    # The payload goes in as a JSON string inside a <script type=application/json>
    # block rather than interpolated into JavaScript, so no value in the data
    # can be read as code.
    # "<" is escaped so that no value in the data could close the script tag
    # early. < is valid JSON and parses back to "<".
    payload_json = json.dumps(payload, separators=(",", ":")).replace(
        "<", "\\u003c")

    html = template.render(
        payload_json=payload_json,
        meta=payload["meta"],
        results=payload["results"],
        sources=payload["sources"],
        datasets=payload["datasets"],
        spec=payload["spec"],
        context=payload["context"],
        map_=payload["map"],
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    size_kb = out_path.stat().st_size / 1024
    print(f"\nwritten to {out_path}  ({size_kb:.0f} KB, self-contained)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--panel", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--open", action="store_true",
                        help="open the dashboard in the default browser")
    parser.add_argument("--no-embed", action="store_true",
                        help="do not embed the processed CSVs (smaller file, "
                             "but the download buttons are removed)")
    args = parser.parse_args()

    data = load_everything(args.panel)
    data["embed"] = not args.no_embed
    payload = build_payload(data)
    check_payload(payload)

    out_path = (config.OUTPUTS / "dashboard.html" if args.out is None
                else args.out)
    render(payload, out_path)

    if args.open:
        webbrowser.open(out_path.resolve().as_uri())


if __name__ == "__main__":
    main()
