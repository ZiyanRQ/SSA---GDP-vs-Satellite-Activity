"""Step 2: load the four V-Dem accountability measures.

Not implemented yet. This docstring is the plan.

INPUT
    data/raw/V-Dem-CY-Full+Others-v16.csv (about 400 MB, 1789-2025, 4,000+
    columns). Only six columns are needed, so the whole file must never be read
    into memory at once.

    Identifiers (config.VDEM_ID_COLUMNS): country_name, country_text_id, year
    Indicators (config.VDEM_INDICATORS):
        v2x_accountability  overall, roughly -2 to +2
        v2x_veracc          vertical (elections, parties)
        v2x_horacc          horizontal (courts, legislature, oversight)
        v2x_diagacc         diagonal (media, civil society, free expression)

OUTPUT
    data/interim/vdem_accountability.csv, one row per (iso3c, year) for
    config.SSA_ALL and config.YEARS_LEVELS.

WHAT THE CODE WILL DO
    1. Read only the needed columns: pandas.read_csv(..., usecols=[...]).
       This is the point of the step; usecols is what keeps 400 MB manageable.
    2. Rename country_text_id to iso3c (it already holds ISO3 codes).
    3. Drop config.VDEM_EXCLUDE_CODES (ZZB Zanzibar, SML Somaliland): they are
       in V-Dem's region grouping but are not WDI economies, so leaving them in
       would add rows that can never merge.
    4. Keep SSA countries and the levels years.

CHECKS BEFORE MOVING ON
    - Print the file size and the columns actually read, to confirm usecols
      worked (reading everything would be slow and may not fit in memory).
    - Expect 48 x 7 = 336 rows, and no missing values: the brief reports V-Dem
      is complete for SSA 2016-2023.
    - Confirm ZZB and SML are gone.
    - Spot-check against the brief: Ghana v2x_accountability 1.36 (2016) and
      1.16 (2023); Kenya 0.96 and 1.03. Ghana 2023 sub-components: vertical
      0.95, diagonal 1.18, horizontal 1.27.
    - Report the within- and between-country standard deviations and compare
      with the brief (overall 0.141 within vs 0.667 between). This matters:
      with between-variation 3-5 times larger, the fixed-effects estimate of
      the accountability effect comes from a few large movers, which must be
      said in the write-up.

OPEN QUESTION
    Which accountability scale to use (config section 7): the raw index
    (roughly -2 to +2), a standardised version, or V-Dem's ``_osp`` 0-1
    variants. The brief lists this as a decision still to make; it changes how
    the coefficient reads, not the fit. Decide and justify before estimating.
"""

from src import config


def main() -> None:
    """Build data/interim/vdem_accountability.csv. Not written yet."""
    raise NotImplementedError(
        "Step 2 of the pipeline is not implemented yet. "
        f"Expected input: {config.VDEM_FILE}"
    )


if __name__ == "__main__":
    main()
