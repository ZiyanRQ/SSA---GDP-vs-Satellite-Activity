# Roadmap

What is done, what is next, and the one open question that could still move a headline number.

[← back to the README](../README.md)

---

## Open tasks

Done since the brief was written: VIIRS 2015–2021 processed (no countries lost,
so `config.EXCLUDED_LIGHTS` stays empty), SPI rebuilt against the published
index, the rebasing dummy built with all four text conversions, OxCGRT
stringency added, and every count in the brief reconciled.

Still open:

1. Interpret and write up the null results: they are bounds, not absences
   (see the minimum detectable effects in [`findings.md`](findings.md)), and
   the rejection of beta = 1 changes how the gap itself should be described
   throughout.
2. Decide the accountability scale (raw, standardised, or V-Dem's `osp` 0–1),
   and whether to centre SPI and accountability.
3. Add oil rents to the panel (already loaded in `wdi_long.csv`) and get GSS
   oil/non-oil GDP for the Ghana case study.
4. Verify the Ghana *dumsor* load-shedding timeline against Ghana Grid Company
   or Energy Commission records. If load shedding ran into 2016, the 2015
   lights baseline is artificially dark and Ghana's tripling is partly a
   recovery from it — this is the one open question that could change a
   headline number.
5. Download VIIRS v2.2 for 2022–2023 for the extended robustness check.
6. Read Martinez (2022) for his exact specification; verify every citation.
