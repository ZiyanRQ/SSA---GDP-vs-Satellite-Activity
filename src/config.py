"""Central settings for the GDP vs night-lights project.

Everything that more than one script needs to agree on lives here: folder
paths, the country list, the year ranges, variable codes, and the switches that
change which sample the models run on.

Nothing in this file reads or writes data. It only *describes* the project, so
importing it is always fast and safe.

Import it from any module in ``src`` with::

    from src import config

Run it directly to print the settings and check they are consistent::

    python -m src.config
"""

from pathlib import Path

# ===========================================================================
# 1. FOLDER PATHS
# ===========================================================================
# __file__ is the path of this file (.../src/config.py).
# .resolve() turns it into a full absolute path.
# .parents[1] goes up two levels: src/config.py -> src -> project root.
# Deriving paths this way means the scripts work no matter which folder you run
# them from, and they keep working if you move or rename the project folder.
PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA_RAW = PROJECT_ROOT / "data" / "raw"             # original downloads (gitignored)
DATA_INTERIM = PROJECT_ROOT / "data" / "interim"     # one tidy file per source
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"  # the merged panel
OUTPUTS = PROJECT_ROOT / "outputs"
OUTPUTS_TABLES = OUTPUTS / "tables"
OUTPUTS_FIGURES = OUTPUTS / "figures"
DOCS = PROJECT_ROOT / "docs"

# ---------------------------------------------------------------------------
# Named files. Raw filenames are whatever the sources actually hand you, so
# change them here (not inside the loaders) if a download is named differently.
# ---------------------------------------------------------------------------
# WDI bulk downloads arrive as e.g. API_NY.GDP.MKTP.KN_DS2_en_csv_v2_1234567.csv
# The trailing number changes with every download, so the loader searches for
# the file using this pattern rather than hard-coding one filename.
WDI_FILE_PATTERN = "API_{code}_DS2_en_csv_v2_*.csv"
# The WDI CSV has 4 lines of preamble before the real header row.
WDI_SKIPROWS = 4

VDEM_FILE = DATA_RAW / "V-Dem-CY-Full+Others-v16.csv"
SPI_INDICATOR_FILE = DATA_RAW / "SPI_data.csv"           # indicator level, 2004-2024
SPI_INDEX_FILE = DATA_RAW / "SPI_index.csv"              # published scores (NOT YET DOWNLOADED)
SPI_METADATA_FILE = DATA_RAW / "SPI_full_metadata.csv"   # scoring rules (NOT YET DOWNLOADED)
OXCGRT_FILE = DATA_RAW / "OxCGRT_nat_latest.csv"         # (NOT YET DOWNLOADED)

# Country boundaries: Natural Earth 1:10m Admin 0, version 5.1.1, downloaded
# 2026-10-28 from naciscdn.org. Public domain. DOWNLOADED and verified.
BOUNDARY_FILE = (
    DATA_RAW / "boundaries" / "natural_earth" / "ne_10m_admin_0_countries.shp"
)
# The VIIRS rasters sit directly in data/raw/, named
# VNL_v21_npp_<YEAR>_global_vcmslcfg_c202205302300.average_masked.dat.tif.gz
# They stay gzipped: GDAL reads inside them via /vsigzip/.
LIGHTS_RASTER_DIR = DATA_RAW
LIGHTS_RASTER_PATTERN = "VNL_v21_npp_{year}_global_*.average_masked.dat.tif.gz"

# The earlier draft panel, for cross-checking only. It is never an input to the
# pipeline: anything we need is rebuilt from the raw sources.
DRAFT_PANEL_FILE = DATA_RAW / "ssa_balanced_panel_2016_2021.csv"

# Interim outputs, one per pipeline step.
WDI_INTERIM = DATA_INTERIM / "wdi_long.csv"
VDEM_INTERIM = DATA_INTERIM / "vdem_accountability.csv"
SPI_INTERIM = DATA_INTERIM / "spi_published.csv"
SPI_REBUILT_INTERIM = DATA_INTERIM / "spi_rebuilt.csv"
REBASING_INTERIM = DATA_INTERIM / "rebasing_dummy.csv"
OXCGRT_INTERIM = DATA_INTERIM / "oxcgrt_annual.csv"
LIGHTS_INTERIM = DATA_INTERIM / "lights_country_year.csv"

# Final outputs.
PANEL_FILE = DATA_PROCESSED / "ssa_panel.csv"
DROPPED_COUNTRIES_FILE = OUTPUTS_TABLES / "dropped_countries.csv"


# ===========================================================================
# 2. YEARS
# ===========================================================================
# Levels are needed from 2015 so that a 2016 growth rate (2016 vs 2015) exists.
# Growth years are the actual estimation sample.
YEAR_LEVELS_START = 2015
YEAR_LEVELS_END = 2021
YEAR_GROWTH_START = 2016
YEAR_GROWTH_END = 2021

# range() stops one short of its end value, hence the "+ 1".
YEARS_LEVELS = list(range(YEAR_LEVELS_START, YEAR_LEVELS_END + 1))   # 2015..2021
YEARS_GROWTH = list(range(YEAR_GROWTH_START, YEAR_GROWTH_END + 1))   # 2016..2021

# WHY 2015 IS IN YEARS_LEVELS BUT NOT IN THE SAMPLE
# A growth rate for 2016 is ln(GDP 2016) - ln(GDP 2015), so the 2015 *level*
# has to be loaded. But 2015 is never an observation: no 2015 row appears in
# any regression, because there is no 2015 growth rate (that would need 2014).
# So the estimation sample starts in 2016, exactly as the design says. The
# levels range is one year longer than the sample range, and that is arithmetic
# rather than a widening of the period.

# ---------------------------------------------------------------------------
# Robustness windows
# ---------------------------------------------------------------------------
# Dropping the pandemic years. A subset of YEARS_GROWTH, so it needs no extra
# data: just a filter at estimation time.
YEARS_PRE_COVID = list(range(2016, 2020))   # 2016..2019

# Extending the period to 2023. This is a REAL robustness check that the
# dissertation will run, but it is not the main period, because it needs VIIRS
# v2.2 for 2022-2023 and v2.2 composites the imagery differently from v2.1. A
# 2021-to-2022 change therefore mixes real growth with a method change, by an
# amount that may differ by country, so it must be reported separately and
# never merged into the main results.
#
# Two further limits to state when reporting it:
#   - Oil rents (NY.GDP.PETR.RT.ZS) end in 2021.
#   - OxCGRT stops on 2023-02-28, so a 2023 annual mean would cover only two
#     months. See load_oxcgrt.py.
YEARS_EXTENDED = list(range(2016, 2024))          # 2016..2023 (growth)
YEARS_EXTENDED_LEVELS = list(range(2015, 2024))   # 2015..2023 (levels)

# STRICT TIMELINE
# The MAIN analysis is fixed at 2016-2021 and nothing may quietly extend it.
# This does not forbid the extended robustness check: it forces that check to
# be asked for explicitly, by passing extended=True to check_years(), so the
# wider window can never arrive by accident in a table labelled as the main
# result.
#
# Enforced, not just documented: every loader calls check_years() on what it
# has read, so a stray year raises instead of travelling downstream.
STRICT_TIMELINE = True


def check_years(years, stage: str = "levels", extended: bool = False) -> None:
    """Raise if any year falls outside the timeline for this stage.

    Call this in every loader straight after subsetting, so that an unexpected
    year stops the pipeline instead of quietly reaching the panel.

    Parameters
    ----------
    years:
        Any iterable of years, e.g. ``df["year"].unique()``.
    stage:
        ``"levels"`` (the default) permits the extra earliest year, 2015, which
        the loaders need because a 2016 growth rate is computed from the 2015
        level. ``"growth"`` does not: use it once growth rates have been built
        and 2015 should be gone.
    extended:
        False (the default) means the main period. True means the 2016-2023
        robustness window, and must be passed deliberately.

    Examples
    --------
    After loading WDI levels::            check_years(df["year"])
    After building growth rates::         check_years(df["year"], stage="growth")
    In the extended robustness check::    check_years(df["year"], stage="growth",
                                                      extended=True)
    """
    if stage not in {"levels", "growth"}:
        raise ValueError(f"stage must be 'levels' or 'growth', not {stage!r}")
    if not STRICT_TIMELINE:
        return

    if extended:
        permitted = set(YEARS_EXTENDED_LEVELS if stage == "levels" else YEARS_EXTENDED)
        window = "extended (robustness)"
    else:
        permitted = set(YEARS_LEVELS if stage == "levels" else YEARS_GROWTH)
        window = "main"

    offenders = sorted({int(y) for y in years} - permitted)
    if offenders:
        raise ValueError(
            f"years outside the {window} {stage} timeline: {offenders}. "
            f"Permitted: {min(permitted)}-{max(permitted)}. "
            "Subset the data, or pass extended=True if this really is the "
            "2016-2023 robustness check."
        )


# ===========================================================================
# 3. COUNTRIES
# ===========================================================================
# All 48 Sub-Saharan African economies on the World Bank region definition.
# This is the *candidate universe*, not the sample: each loader subsets to these
# codes, and build_panel.py decides who survives by actually checking for
# missing values.
#
# ASSUMPTION TO VERIFY: this list was typed from the brief's description of the
# World Bank SSA region, not read off a file. build_panel.py should compare it
# against the region column in SPI_data.csv and report any difference.
SSA_ALL = [
    "AGO",  # Angola
    "BDI",  # Burundi
    "BEN",  # Benin
    "BFA",  # Burkina Faso
    "BWA",  # Botswana
    "CAF",  # Central African Republic
    "CIV",  # Cote d Ivoire
    "CMR",  # Cameroon
    "COD",  # Congo, Dem. Rep.
    "COG",  # Congo, Rep.
    "COM",  # Comoros
    "CPV",  # Cabo Verde
    "ERI",  # Eritrea
    "ETH",  # Ethiopia
    "GAB",  # Gabon
    "GHA",  # Ghana
    "GIN",  # Guinea
    "GMB",  # Gambia, The
    "GNB",  # Guinea-Bissau
    "GNQ",  # Equatorial Guinea
    "KEN",  # Kenya
    "LBR",  # Liberia
    "LSO",  # Lesotho
    "MDG",  # Madagascar
    "MLI",  # Mali
    "MOZ",  # Mozambique
    "MRT",  # Mauritania
    "MUS",  # Mauritius
    "MWI",  # Malawi
    "NAM",  # Namibia
    "NER",  # Niger
    "NGA",  # Nigeria
    "RWA",  # Rwanda
    "SDN",  # Sudan
    "SEN",  # Senegal
    "SLE",  # Sierra Leone
    "SOM",  # Somalia
    "SSD",  # South Sudan
    "STP",  # Sao Tome and Principe
    "SWZ",  # Eswatini
    "SYC",  # Seychelles
    "TCD",  # Chad
    "TGO",  # Togo
    "TZA",  # Tanzania
    "UGA",  # Uganda
    "ZAF",  # South Africa
    "ZMB",  # Zambia
    "ZWE",  # Zimbabwe
]

# ---------------------------------------------------------------------------
# Exclusions from the balanced panel
# ---------------------------------------------------------------------------
# A balanced panel must hold the SAME countries in every specification, or the
# coefficients from one model cannot be compared with another. So a country
# that is missing any model variable is excluded from the panel outright,
# rather than appearing in some regressions and not others.
#
# The exclusions come in three groups, all applied unconditionally. These are
# EXPECTED values used as a check, not a filter: build_panel.py derives the
# sample from the data and then compares it with this list, so a change in the
# data shows up as a loud failure rather than silently altering the sample.

# Group 1: missing WDI or SPI data (8 countries).
EXCLUDED_MISSING_DATA = {
    "ERI": "GDP growth, agriculture share and SPI missing, all 6 years",
    "SSD": "GDP growth and agriculture share missing, all 6 years",
    "SOM": "Agriculture share missing all 6 years (SPI also missing 2016)",
    "COM": "SPI missing all 6 years",
    "CAF": "SPI missing all 6 years",
    "GNQ": "SPI missing 2016-2019 (4 years)",
    "COD": "SPI missing 2016 (1 year)",
    "SYC": "SPI missing 2016 (1 year)",
}

# Group 2: no OxCGRT COVID stringency data (2 countries). Stringency is a main
# model variable, so these two leave the balanced panel as well, taking it from
# 40 countries / 240 rows to 38 / 228.
EXCLUDED_NO_COVID_DATA = {
    "GNB": "No OxCGRT stringency data",
    "STP": "No OxCGRT stringency data",
}

# Group 3: lost in the night-lights step. EMPTY until process_lights.py has
# run: a country with missing or near-zero radiance cannot have a log change,
# so it would break the balance. Add each code here with its reason, and every
# count in the project follows from this one place.
EXCLUDED_LIGHTS: dict[str, str] = {}

# All exclusions together, for the dropped-countries table.
EXPECTED_DROPPED_REASONS = {
    **EXCLUDED_MISSING_DATA,
    **EXCLUDED_NO_COVID_DATA,
    **EXCLUDED_LIGHTS,
}

EXPECTED_BALANCED_COUNTRIES = [
    code for code in SSA_ALL if code not in EXPECTED_DROPPED_REASONS
]

# Kept as a named list because several robustness checks refer to these two
# countries specifically (they are what separates the 38- and 40-country
# samples), even though they are now excluded unconditionally.
COVID_MISSING_COUNTRIES = list(EXCLUDED_NO_COVID_DATA)

# The two case studies.
CASE_STUDIES = ["GHA", "KEN"]

# Oil producers, for the "excluding oil producers" robustness check. Taken from
# the brief's oil-rent shares (% of GDP, 2016-2021). Ghana is included because
# its offshore oil adds to GDP but not to land-based lights.
OIL_PRODUCERS = ["AGO", "COG", "GAB", "TCD", "NGA", "GHA"]


# ===========================================================================
# 4. SAMPLE SWITCHES
# ===========================================================================
# Whether COVID stringency is a regressor in the main model.
#
# True (default): it is. The balanced panel is 38 countries / 228 rows.
#
# IMPORTANT: this flag no longer changes the SAMPLE. Because the panel must be
# balanced, GNB and STP are excluded whether or not stringency is in a given
# specification (see EXCLUDED_NO_COVID_DATA), so every model runs on the same
# 38 countries and the coefficients stay comparable. Setting this to False
# therefore drops the stringency term but keeps 38 countries; it does not
# recover the old 40-country panel.
#
# Recovering 40 countries would mean dropping stringency from the project
# entirely, which is a design change, not a flag.
USE_COVID_IN_MAIN = True

# False (default): balanced panel, any country with any missing value dropped.
# True: unbalanced panel (drop individual country-years only), a robustness
# check expected to be 43 countries / 252 rows.
USE_UNBALANCED_PANEL = False


def expected_sample() -> tuple[list[str], int]:
    """Return the country list and row count the balanced panel should have.

    Gives back a tuple ``(countries, n_rows)``. build_panel.py uses it to check
    the panel it just built against what these settings say it should be, and
    fails loudly on a difference.

    The count follows from the exclusion lists, so when the lights step costs
    more countries the only edit needed is adding them to EXCLUDED_LIGHTS:
    every count in the project updates from there.

    Covers the balanced case only. The unbalanced sample is derived from the
    data, and the brief's figure of 43 countries / 252 rows is a cross-check
    rather than a target.
    """
    countries = list(EXPECTED_BALANCED_COUNTRIES)
    return countries, len(countries) * len(YEARS_GROWTH)


# ===========================================================================
# 5. VARIABLE CODES
# ===========================================================================
# WDI: indicator code -> the short column name used from here on.
WDI_INDICATORS = {
    "NY.GDP.MKTP.KN": "gdp_real_lcu",     # GDP, constant local currency (levels)
    "NY.GDP.MKTP.KD.ZG": "gdp_growth",    # GDP growth, annual %
    "NV.AGR.TOTL.ZS": "agri_share",       # Agriculture, value added, % of GDP
    "EG.ELC.ACCS.ZS": "elec_access",      # Access to electricity, % of population
    "SP.URB.TOTL.IN.ZS": "urban_share",   # Urban population, % of total
    "SP.POP.TOTL": "population",          # Total population
    "NY.GDP.PETR.RT.ZS": "oil_rents",     # Oil rents, % of GDP
}

# V-Dem: only these columns are read from the 400 MB CSV.
VDEM_ID_COLUMNS = ["country_name", "country_text_id", "year"]
VDEM_INDICATORS = [
    "v2x_accountability",  # overall (roughly -2 to +2)
    "v2x_veracc",          # vertical: elections, parties
    "v2x_horacc",          # horizontal: courts, legislature, oversight bodies
    "v2x_diagacc",         # diagonal: media, civil society, free expression
]
# V-Dem's own region grouping includes these two, which are not WDI economies.
VDEM_EXCLUDE_CODES = ["ZZB", "SML"]  # Zanzibar, Somaliland

# SPI: the two indicators dropped when rebuilding the index, because they
# describe the GDP series itself (which system of national accounts is in use,
# and how old the base year is). They move mechanically with GDP rebasing,
# which is the circularity problem in the brief.
SPI_DROP_INDICATORS = ["SPI.D5.2.1.SNAU", "SPI.D5.2.2.NABY"]
# Dropped in one extra robustness check only (a borderline case).
SPI_DROP_INDICATORS_EXTRA = ["SPI.D5.2.3.CPIBY"]
# Raw column holding each country-year's national accounts base year, the
# source for the rebasing dummy.
SPI_BASE_YEAR_COLUMN = "RAW.D5.2.2.NABY"

# Base years stored as text in SPI_data.csv, converted by hand (brief s2.2).
# ASSUMPTION TO VERIFY: the brief names ETH, UGA, GIN and SDN as the countries
# with text values and gives "2015/2016", "2010/11" and "chained" as examples,
# but the file has not been read yet. rebuild_spi.py must print every
# non-numeric value it finds and stop if one is missing from this mapping, so
# that nothing is silently guessed.
SPI_BASE_YEAR_TEXT_FIXES: dict[str, str] = {
    # Fill in once the actual text values have been listed from the file.
}

# Rebasing events known from official statistics-office releases, which
# override whatever SPI reports. Kenya: KNBS published the 2016-base revision
# in September 2021, while SPI only shows it from 2022.
REBASING_OVERRIDES = {
    ("KEN", 2021): 1,  # KNBS press release, Sept 2021
}
# Liberia's SPI base year moves backwards (2000 -> 1992) in 2019, which is
# almost certainly a data error. Flagged here, not silently fixed.
REBASING_SUSPECT = [("LBR", 2019)]

# OxCGRT.
OXCGRT_STRINGENCY_COLUMN = "StringencyIndex_Average"
# Stringency is 0 for pre-pandemic years by construction, not missing.
OXCGRT_ZERO_YEARS = list(range(2016, 2020))  # 2016..2019


# ===========================================================================
# 6. NIGHT LIGHTS
# ===========================================================================
VIIRS_VERSION = "v2.1"       # annual composites 2012-2021: the main analysis
VIIRS_BAND = "average_masked"

# v2.2 covers 2022 onward and is used ONLY in the extended robustness check
# (YEARS_EXTENDED). Its compositing method differs from v2.1: it mixes
# satellites, accepts months with fewer cloud-free observations, and excludes
# cells without median values. So a 2021-to-2022 change contains both real
# growth and a method change.
VIIRS_VERSION_EXTENDED = "v2.2"

# Never mix v2 with v2.1: v2.1 fixed an annual-averaging bug in v2 and removed
# v2's low-detection filter, so the two are not comparable at all. v2 is not
# permitted anywhere in this project.
VIIRS_VERSIONS_PERMITTED_MAIN = ["v2.1"]
VIIRS_VERSIONS_PERMITTED_EXTENDED = ["v2.1", "v2.2"]

# Rule for country-years whose summed radiance is zero or near zero: ln(0) is
# undefined, so a rule is needed, and the brief requires fixing it BEFORE
# looking at any results.
#
# NOT YET DECIDED - deliberately left as None so that process_lights.py fails
# loudly instead of applying an invented threshold. Set it during the lights
# step, write the reasoning into the README, and do not change it afterwards.
LIGHTS_NEAR_ZERO_THRESHOLD = None

# Column in the boundary file holding the ISO3 code, so the join key is
# explicit rather than guessed at merge time.
#
# VERIFIED against the actual file: of Natural Earth's many three-letter code
# columns, only ISO_A3 and ISO_A3_EH cover all 48 SSA countries. ADM0_A3 and
# SOV_A3 miss South Sudan, WB_A3 misses DR Congo. Natural Earth sets this
# column to "-99" where ISO status is disputed, which is how Somaliland is
# excluded without becoming a duplicate Somalia.
BOUNDARY_ISO3_COLUMN = "ISO_A3"
BOUNDARY_ISO3_COLUMN_ALT = "ISO_A3_EH"  # equally complete, for cross-checking

# Bounding box to crop the global rasters to, as (min_lon, min_lat, max_lon,
# max_lat). Cropping once turns 11.6 GB per year into about 1.6 GB and avoids
# repeated slow reads through the gzip.
#
# VERIFIED to contain every SSA polygon in the boundary file. The limits are
# set by outlying islands, not the mainland, and a mainland-only guess would
# have clipped two countries:
#     west   -25.36  Cabo Verde
#     east    63.49  Mauritius (Rodrigues)
#     south  -46.97  South Africa (Prince Edward Islands, sub-Antarctic)
#     north   27.29  Mauritania
# Those outlying islands are unlit, so they add nothing to a radiance sum, but
# they must not be cut off: a clipped polygon would silently lose whatever it
# does contain. process_lights.py must re-check this box against the boundary
# file rather than trusting these numbers.
LIGHTS_CROP_BBOX = (-26.0, -47.0, 64.0, 28.0)


# ===========================================================================
# 7. MODEL SETTINGS
# ===========================================================================
# Outcome variables: the signed gap (overstatement) and the absolute gap (noise).
OUTCOME_SIGNED = "gap"
OUTCOME_ABSOLUTE = "abs_gap"

# Main-model controls, in the order they appear in the specification.
CONTROLS = ["agri_share", "elec_access_change", "urban_share", "ln_population"]

# Capacity and accountability measures. Both are centred before entering the
# model, so that in the check model the lights elasticity is read at average
# capacity and accountability.
CAPACITY_MAIN = "spi_rebuilt"
CAPACITY_ALTERNATIVES = ["spi_pillar4", "spi_overall"]  # alternative, then original
ACCOUNTABILITY_MAIN = "v2x_accountability"
ACCOUNTABILITY_ALTERNATIVES = ["v2x_diagacc", "v2x_veracc", "v2x_horacc"]
CENTRE_VARIABLES = [CAPACITY_MAIN, ACCOUNTABILITY_MAIN]

# Standard errors clustered by country (a country's errors are correlated across
# years); with 38 countries there are 38 clusters, which is above the usual
# rule-of-thumb minimum of about 30 but close enough to it to be worth a line
# in the limitations.
CLUSTER_BY = "iso3c"

# Panel index used by linearmodels: (entity, time).
PANEL_INDEX = ["iso3c", "year"]

# Null hypothesis for the check model: GDP and lights move one-for-one, which is
# what the simple gap assumes.
BETA_NULL = 1.0

# Fixed for anything involving randomness, so results reproduce exactly.
RANDOM_SEED = 20261028


# ===========================================================================
# 8. SELF-CHECK
# ===========================================================================
def _self_check() -> None:
    """Check the settings are internally consistent, then print a summary.

    These are ``assert`` statements: each one states something that must be
    true, and Python raises AssertionError if it is not. They catch typos in the
    lists above before any data is touched.
    """
    assert len(SSA_ALL) == 48, f"expected 48 SSA countries, got {len(SSA_ALL)}"
    assert len(set(SSA_ALL)) == 48, "duplicate ISO3 code in SSA_ALL"
    assert SSA_ALL == sorted(SSA_ALL), "SSA_ALL is not in alphabetical order"

    # The 8 data-missing exclusions and the 2 stringency exclusions are known.
    # EXCLUDED_LIGHTS is open-ended, so the balanced count is checked as
    # 38 minus whatever the lights step costs, not against a fixed 38.
    assert len(EXCLUDED_MISSING_DATA) == 8, "expected 8 countries missing WDI/SPI data"
    assert len(EXCLUDED_NO_COVID_DATA) == 2, "expected 2 countries missing stringency"
    expected_n = 48 - 8 - 2 - len(EXCLUDED_LIGHTS)
    assert len(EXPECTED_BALANCED_COUNTRIES) == expected_n, (
        f"expected {expected_n} balanced countries, "
        f"got {len(EXPECTED_BALANCED_COUNTRIES)}"
    )
    # The three exclusion groups must not overlap, or a country would be
    # counted twice and the arithmetic above would be wrong.
    assert len(EXPECTED_DROPPED_REASONS) == (
        len(EXCLUDED_MISSING_DATA) + len(EXCLUDED_NO_COVID_DATA) + len(EXCLUDED_LIGHTS)
    ), "a country appears in more than one exclusion group"

    # Every dropped country must be an SSA country and must not also be in the
    # balanced list; together the two groups must account for all 48.
    for code in EXPECTED_DROPPED_REASONS:
        assert code in SSA_ALL, f"{code} is not in SSA_ALL"
        assert code not in EXPECTED_BALANCED_COUNTRIES, f"{code} is both kept and dropped"
    assert len(EXPECTED_BALANCED_COUNTRIES) + len(EXPECTED_DROPPED_REASONS) == 48

    # The case studies MUST survive: the whole dissertation rests on them, so
    # losing Ghana or Kenya is a stop-everything problem, not a footnote.
    for code in CASE_STUDIES:
        assert code in EXPECTED_BALANCED_COUNTRIES, (
            f"case study {code} is not in the balanced sample - "
            "the research question cannot be answered without it"
        )

    # An oil producer dropping out (Chad, say, which is dimly lit) is a
    # legitimate outcome of the lights step, not an error: it just means the
    # "excluding oil producers" robustness check has fewer to exclude. So this
    # warns rather than failing.
    lost_oil = [c for c in OIL_PRODUCERS if c not in EXPECTED_BALANCED_COUNTRIES]
    if lost_oil:
        print(f"NOTE: oil producers no longer in the sample: {lost_oil}")

    # GNB and STP are deliberately excluded now, so check they really are.
    for code in COVID_MISSING_COUNTRIES:
        assert code not in EXPECTED_BALANCED_COUNTRIES, (
            f"{code} has no stringency data and must be excluded"
        )

    assert len(YEARS_LEVELS) == 7, "levels should cover 2015-2021 (7 years)"
    assert len(YEARS_GROWTH) == 6, "growth should cover 2016-2021 (6 years)"
    assert len(WDI_INDICATORS) == 7, "expected 7 WDI indicators"

    assert len(YEARS_EXTENDED) == 8, "extended window should cover 2016-2023"
    assert YEARS_GROWTH == YEARS_EXTENDED[: len(YEARS_GROWTH)], (
        "the main window must be the start of the extended window"
    )

    # The timeline must actually be enforced. These cases say what should pass
    # and what should fail; if any behaves the other way, check_years is wrong.
    should_pass = [
        ([2015, 2021], "levels", False),   # main levels, 2015 needed for 2016 growth
        ([2016, 2021], "growth", False),   # main sample
        ([2016, 2023], "growth", True),    # extended robustness check
        ([2015, 2023], "levels", True),    # extended levels
    ]
    should_fail = [
        ([2022], "levels", False),   # extension not asked for
        ([2015], "growth", False),   # 2015 is not an observation
        ([2024], "growth", True),    # beyond even the extended window
        ([2014], "levels", True),    # before the data starts
    ]
    for years, stage, extended in should_pass:
        check_years(years, stage=stage, extended=extended)
    for years, stage, extended in should_fail:
        try:
            check_years(years, stage=stage, extended=extended)
        except ValueError:
            pass
        else:
            raise AssertionError(
                f"check_years wrongly accepted {years} "
                f"(stage={stage}, extended={extended})"
            )

    countries, n_rows = expected_sample()
    print("Project root:", PROJECT_ROOT)
    print("SSA candidate countries:", len(SSA_ALL))
    print(f"Levels loaded:   {YEARS_LEVELS[0]}-{YEARS_LEVELS[-1]} "
          f"({YEARS_LEVELS[0]} is only a base for the {YEARS_GROWTH[0]} growth rate)")
    print(f"Estimation sample: {YEARS_GROWTH[0]}-{YEARS_GROWTH[-1]} "
          f"({len(YEARS_GROWTH)} years)")
    print(f"Robustness windows: {YEARS_PRE_COVID[0]}-{YEARS_PRE_COVID[-1]} (pre-COVID), "
          f"{YEARS_EXTENDED[0]}-{YEARS_EXTENDED[-1]} (extended, needs VIIRS "
          f"{VIIRS_VERSION_EXTENDED})")
    print("STRICT_TIMELINE:", STRICT_TIMELINE,
          "(extended window must be asked for explicitly)")
    print("USE_COVID_IN_MAIN:", USE_COVID_IN_MAIN)
    print("USE_UNBALANCED_PANEL:", USE_UNBALANCED_PANEL)
    print("Excluded - missing WDI/SPI data:", len(EXCLUDED_MISSING_DATA),
          sorted(EXCLUDED_MISSING_DATA))
    print("Excluded - no stringency data: ", len(EXCLUDED_NO_COVID_DATA),
          sorted(EXCLUDED_NO_COVID_DATA))
    print("Excluded - lost to lights:     ", len(EXCLUDED_LIGHTS),
          sorted(EXCLUDED_LIGHTS) or "(none yet - lights not processed)")
    print(f"Expected balanced sample: {len(countries)} countries, {n_rows} rows")
    print("Lights near-zero rule:", LIGHTS_NEAR_ZERO_THRESHOLD, "(must be set before Step 5)")
    print("All settings checks passed.")


if __name__ == "__main__":
    _self_check()
