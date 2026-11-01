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
    args = parser.parse_args()

    data = load_everything(args.panel)
    payload = build_payload(data)
    check_payload(payload)

    out_path = (config.OUTPUTS / "dashboard.html" if args.out is None
                else args.out)
    render(payload, out_path)

    if args.open:
        webbrowser.open(out_path.resolve().as_uri())


if __name__ == "__main__":
    main()
