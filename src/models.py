"""Step 7: estimate the models.

Not implemented yet. This docstring is the plan.

INPUT
    data/processed/ssa_panel.csv (from build_panel.py)

OUTPUT
    outputs/tables/   regression tables
    outputs/figures/  case-study figures (Ghana and Kenya gaps by year, actual
                      against predicted)

LIBRARY
    linearmodels: PooledOLS, PanelOLS, RandomEffects, FirstDifferenceOLS.
    The panel is indexed on config.PANEL_INDEX, that is (iso3c, year).

PREPARATION
    Centre config.CENTRE_VARIABLES (the capacity and accountability measures)
    before building any interaction term, so that in the check model the lights
    elasticity is read at average capacity and accountability rather than at
    zero, which is outside the data.

MAIN SPECIFICATION
    Outcome is the gap itself, both ways round:
        gap_it     = d_ln_gdp_it - d_ln_lights_it   (overstatement)
        abs_gap_it = |gap_it|                       (noise, either direction)

        gap_it = a + theta*SPI_it + phi*Acc_it
                   + pi1*agri_share_it + pi2*d_elec_access_it
                   + pi3*urban_share_it + pi4*ln_pop_it + pi5*covid_it
                   + country FE + year FE + e_it

    Expected signs: phi < 0 on the signed gap (less accountability, GDP grows
    faster than lights) and theta < 0 on the absolute gap (more capacity,
    smaller gaps in either direction).

    Country fixed effects absorb each country's average gap and anything
    unchanging about it; year fixed effects absorb common shocks, including the
    common part of COVID in 2020-2021. Standard errors are clustered by
    config.CLUSTER_BY (country), giving 40 clusters, because a country's errors
    are correlated across years and ignoring that understates the errors.

    COVID stringency is a main-model regressor (config.USE_COVID_IN_MAIN).
    Guinea-Bissau and Sao Tome and Principe have no stringency data and are
    therefore out of the balanced panel entirely, so every specification here
    runs on the same 38 countries / 228 rows and the coefficients across
    tables are comparable.

CHECK MODEL (lights on the right-hand side)
        d_ln_gdp_it = a + beta*d_ln_lights_it
                        + gamma*(d_ln_lights_it x SPI_it)
                        + delta*(d_ln_lights_it x Acc_it)
                        + theta*SPI_it + phi*Acc_it + controls
                        + country FE + year FE + e_it

    The gap model is the special case beta = 1, gamma = delta = 0. This matters
    because the gap assumes GDP and lights move one-for-one, while the
    literature finds GDP moves less than one-for-one (an elasticity near 0.3 in
    Henderson, Storeygard and Weil 2012, on older DMSP data - to verify).

    Decision rule, fixed in advance: estimate beta and test
    H0: beta = config.BETA_NULL (that is, 1).
        If H0 is not rejected, the simple gap is justified.
        If beta is well below 1, give the check model more weight, or use a
        scaled gap d_ln_gdp - beta_hat*d_ln_lights, noting that a two-step
        estimate of that kind needs care with the standard errors.
    No extra data is needed: the interactions are products of existing columns.

ESTIMATOR COMPARISONS
    - Pooled OLS with clustered standard errors (baseline).
    - Fixed effects: PanelOLS(entity_effects=True, time_effects=True) (main).
    - Random effects plus a Hausman test. linearmodels has no Hausman test, so
      it is hand-coded:
          H = (b_FE - b_RE)' [V_FE - V_RE]^-1 (b_FE - b_RE)
      compared with a chi-squared distribution on the number of coefficients
      compared. Only coefficients present in both models go in, the difference
      of the variance matrices should be positive definite (report it if it is
      not, which happens in finite samples), and clustered errors make the
      classical version of the test questionable - say so rather than hiding
      it. If FE and RE differ significantly, keep FE.
    - First differences. With serially correlated errors FD can be preferable
      to FE; Millimet and Bellemare (2025) recommend comparing the two when
      T > 2 (to verify).

    Known FE limitations to state: it cannot estimate time-invariant
    variables; it is imprecise when a regressor barely varies within country,
    which is the case for V-Dem accountability (within SD 0.141 against between
    SD 0.667) and for urbanisation; and it amplifies measurement error, which
    is the key limitation here because both GDP and lights are noisy.

ROBUSTNESS CHECKS (config holds the lists these use)
    1. Original published SPI instead of the rebuilt one.
    2. SPI Pillar 4 as the capacity measure.
    3. Rebuilt SPI also dropping the CPI base year indicator.
    4. Check model and the test of beta = 1.
    5. Rebasing dummy (Ghana 2019, Kenya 2021, panel-wide from base-year
       changes).
    6. Interaction of d_ln_lights with the change in electricity access.
    7. Dropping COVID stringency (config.USE_COVID_IN_MAIN = False, same 38
       countries), and separately 2016-2019 only
       (config.YEARS_PRE_COVID), where stringency is 0 throughout and so
       drops out of its own accord.
    8. Excluding Kenya; excluding Ghana.
    9. Excluding config.OIL_PRODUCERS, and separately adding oil rents.
   10. Excluding the biggest accountability movers (GMB, ETH, BEN, MLI, MUS,
       CIV - to confirm from the data).
   11. Unbalanced panel (config.USE_UNBALANCED_PANEL = True).
   12. BRIGHT-CELLS LIGHTS: rerun the main models with d_ln_lights_bright in
       place of d_ln_lights. Added after the lights diagnostics found that the
       2017 compositing change adds light in cells near the detection limit,
       not in cells that were already bright (see the README and
       process_lights.py --stage diagnose). Year fixed effects cannot remove
       it, because it lands on marginal cells and so hits dim countries
       hardest - it is correlated with the very thing the model is trying to
       explain. Separate evidence that the restricted series is the better
       economic measure: the fixed-mask total falls 4.3% in 2020, picking up
       COVID, while the all-cells total falls only 1.6%.
       Everything else in the specification is held identical, so the only
       thing that changes between the two tables is the lights measure.
       If the main results hold, the detection artefact is not driving them.
       If they do not, that IS the finding, and it belongs in the write-up
       rather than being resolved by picking whichever measure reads better.
       Decide and state which way that goes before running it.
   13. Extended period, 2016-2023 (config.YEARS_EXTENDED), which needs VIIRS
       v2.2 for 2022-2023. Report it separately and never merge it into the
       main results, because the v2.1-to-v2.2 change in compositing method sits
       inside the 2021-to-2022 growth rate, so part of any change there is
       method rather than growth. Two further gaps to state: oil rents end in
       2021, and OxCGRT stops on 2023-02-28, so 2023 has no comparable annual
       stringency mean (see load_oxcgrt.py). Pass extended=True to
       config.check_years() for this check.
       Worth reporting alongside: the same regression on 2016-2021 but with
       lights taken from v2.2 where both versions exist, which separates the
       version effect from the extra years.

CASE STUDIES
    Plot Ghana's and Kenya's gap by year against the model's prediction, and
    match the residuals to documented events (GSS and KNBS releases, IMF
    reports). Kenya's SPI rise, electrification surge and 2021 rebasing all
    coincide, so the leave-one-out check matters there. Ghana's offshore oil
    adds to GDP but not to land lights, so the case study should use GSS
    non-oil GDP. Language stays cautious: "consistent with", not "caused by".

CHECKS BEFORE REPORTING ANYTHING
    - Confirm the estimation sample size equals what config.expected_sample()
      says, currently 228 rows and 38 countries. linearmodels drops rows with
      any missing value silently, so the number of observations in the output
      must be read and checked against that, not assumed.
    - Confirm every specification runs on the same number of observations,
      except the ones that deliberately change the sample (leave-one-out,
      excluding oil producers, pre-COVID years, unbalanced panel). A table
      whose sample size moves for no stated reason is a bug, not a result.
    - Confirm the number of clusters is the number of countries. With 38
      clusters, clustered standard errors are on the small side: it is above
      the usual rule-of-thumb minimum of about 30, but worth a sentence in the
      limitations, and worth comparing with wild-bootstrap errors if time
      allows.
    - Report R-squared (within), and for FE confirm the number of entities and
      time periods absorbed.
    - Run the same specification twice with the signed and the absolute gap,
      and keep them side by side: they answer different questions.
"""

from src import config


def main() -> None:
    """Estimate and write the model tables. Not written yet."""
    raise NotImplementedError(
        "Step 7 of the pipeline is not implemented yet. "
        f"Expected input: {config.PANEL_FILE}"
    )


if __name__ == "__main__":
    main()
