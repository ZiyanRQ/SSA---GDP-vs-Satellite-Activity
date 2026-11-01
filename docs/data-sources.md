# Data sources

Seven sources, their exact identifiers, vintages and the catch that matters for each. The dashboard renders this same list with an "on disk" status read from the filesystem at build time, so the two cannot silently disagree.

[← back to the README](../README.md)

---

## Data sources

Sizes and "last updated" dates are what the brief records. Download dates
marked *to confirm* were not noted at the time and should be filled in when
each file is next fetched.

The dashboard renders this list too, with the "on disk" status read from the
filesystem at build time rather than from this table, so the two cannot
silently disagree.

| Variable | Source | Code / file | Vintage | Download date |
| --- | --- | --- | --- | --- |
| GDP, constant LCU | World Bank WDI | `NY.GDP.MKTP.KN` | last updated 2026-10-08 | Oct 2026 *(to confirm)* |
| GDP growth, annual % | World Bank WDI | `NY.GDP.MKTP.KD.ZG` | last updated 2026-10-08 | Oct 2026 *(to confirm)* |
| Agriculture, % of GDP | World Bank WDI | `NV.AGR.TOTL.ZS` | last updated 2026-10-08 | Oct 2026 *(to confirm)* |
| Electricity access, % | World Bank WDI | `EG.ELC.ACCS.ZS` | last updated 2026-10-08 | Oct 2026 *(to confirm)* |
| Urban population, % | World Bank WDI | `SP.URB.TOTL.IN.ZS` | last updated 2026-10-08 | Oct 2026 *(to confirm)* |
| Population | World Bank WDI | `SP.POP.TOTL` | last updated 2026-10-08 | Oct 2026 *(to confirm)* |
| Oil rents, % of GDP | World Bank WDI | `NY.GDP.PETR.RT.ZS` | last updated 2026-10-08; series ends 2021 | Oct 2026 *(to confirm)* |
| Accountability | [V-Dem v16](https://v-dem.net/data/the-v-dem-dataset/) | `V-Dem-CY-Full+Others-v16.csv` (~400 MB) | published March 2026, covers 1789–2025 | Oct 2026 *(to confirm)* |
| Statistical capacity, indicator level | [worldbank/SPI](https://github.com/worldbank/SPI) | `SPI_data.csv` | 2004–2024 | Oct 2026 *(to confirm)* |
| Statistical capacity, published scores | [worldbank/SPI](https://github.com/worldbank/SPI), `03_output_data/` | `SPI_index.csv` | 2016–2024 | downloaded, 1.8 MB |
| SPI scoring rules | [worldbank/SPI](https://github.com/worldbank/SPI) | `SPI_full_metadata.csv` | — | **not yet downloaded** |
| SPI weighting logic | [worldbank/SPI](https://github.com/worldbank/SPI), `02_programs/` | `02-SPI_index.Rmd` (reference; weights at lines 1283–1285) | — | downloaded |
| COVID stringency | [OxCGRT](https://github.com/OxCGRT/covid-policy-tracker), `data/` | `OxCGRT_nat_latest.csv` | daily 2020-01-01 to 2023-02-28; 2020–2022 are full years, 2023 is 2 months so no annual mean is computed | downloaded, 48.6 MB |
| Night lights, main | [EOG VIIRS annual VNL](https://eogdata.mines.edu/products/vnl/) (also on Google Earth Engine as `NOAA/VIIRS/DNB/ANNUAL_V21`) | v2.1 annual composites 2015–2021, `average_masked` band | v2.1 covers 2012–2021 | downloaded, 7 rasters, ~2.1 GB gzipped |
| Night lights, extended check | same, `ANNUAL_V22` | v2.2 composites 2022–2023 | different compositing method from v2.1 | **not yet downloaded** |
| Country boundaries | [Natural Earth](https://www.naturalearthdata.com/) 1:10m Admin 0 | `ne_10m_admin_0_countries.shp`, ISO3 from `ISO_A3` | version 5.1.1, public domain | downloaded 2026-10-28, 8.8 MB |

`data/raw/ssa_balanced_panel_2016_2021.csv` is an earlier draft panel kept for
cross-checking only. It is never an input to the pipeline.
