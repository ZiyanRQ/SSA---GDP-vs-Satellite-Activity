# The dashboard

How `outputs/dashboard.html` is built, what is in it, and why the charts are hand-written SVG rather than a plotting library.

[← back to the README](../README.md)

---

## The dashboard

`python -m src.dashboard` writes **`outputs/dashboard.html`** — one
self-contained file, about 135 KB, that opens straight from disk with no
server and no internet connection.

Countries are ranked by **divergence**, which can be read four ways, so the
ranking is sortable rather than fixed:

| Sort | Question it answers |
| --- | --- |
| Mean gap (signed) | Did lights consistently outgrow reported GDP? |
| Mean \|gap\| | How big is the disagreement, ignoring direction? |
| Volatility | Is a small average gap hiding large swings both ways? |
| Worst year | Where would a case study start? |

Selecting a country loads its growth trace (Δln GDP against both lights
measures, with the gap drawn as the vertical distance it literally is), its
gap against the model's prediction with rebasing years flagged, its position
in the panel-wide distribution, and a cross-section scatter against capacity,
accountability, electrification or agriculture share.

**Python does every calculation; the page only draws.** Nothing is computed in
JavaScript that could disagree with the pipeline, every figure is read from
the committed tables rather than hard-coded, and `dashboard.py` re-checks in
the payload itself that `gap = Δln GDP − Δln lights` and
`gap = prediction + residual` for all 228 observations before writing the file.
Re-run `models.py` and the dashboard changes with it.

The charts are hand-written SVG rather than a plotting library: it keeps the
project to its existing dependencies and gives exact control over the layout.

It opens with **Why this question** — the case for the project, built on live
figures rather than prose alone. The one that makes it: the median yearly
disagreement between reported GDP growth and lights growth is **0.081 log
points against median GDP growth of 0.037**, so *the typical gap is more than
twice the size of the thing being measured*. An expandable panel sets out what
the data says so far, what the project explicitly is **not** claiming, and why
the nulls are bounds rather than absences.

**Compare countries** puts up to eight countries on one shared axis — gap,
bright-cells gap, GDP growth, lights growth, capacity or electrification — with
rebasing years ringed, and a sortable summary table underneath. Quick picks for
the case studies and the five widest gaps. Unlike the single-country trace,
these lines are always on a common scale, so they are directly comparable.

It also carries three reference sections:

- **A Sub-Saharan Africa locator**, generated from the *same* Natural Earth
  file the night lights were summed inside — so the shape on screen is the
  shape the data was measured in, not a decorative outline from elsewhere.
  All 48 countries are drawn; the 10 outside the balanced panel are dimmed
  rather than hidden, and the selected country is lit. Clicking a country
  selects it.
- **The models, symbol by symbol.** All three equations — the gap definition,
  the main specification and the check model — with every symbol explained in
  three parts: what it is, what it means in this data, and *where it shows up
  on the charts*. The estimated values of θ, φ and β are read from the
  results tables, so they cannot go stale.
- **The processed datasets**, all ten of them, each with its row × column
  shape, the module that built it, its full column list and a **Download CSV**
  button. The CSVs are embedded in the page, so the dashboard is a portable
  copy of the processed data: one file that can be sent to a supervisor who
  can then read the numbers behind any chart without the repository.
  `--no-embed` drops them (586 KB → 205 KB).

> The page carries the same warning this README does: **a large divergence is
> not evidence of misreporting.** Lights miss agriculture, the informal economy
> and off-grid activity, they pick up flaring and electrification, and the 2017
> detection change inflates growth for dim countries specifically. The ranking
> is for choosing where to look.
