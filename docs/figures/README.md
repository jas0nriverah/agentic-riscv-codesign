# Research figures

These checked-in SVGs and PNGs make the repository readable on GitHub. They are snapshots of the frozen matched comparison, not illustrations or synthetic placeholder data. `make reproduce` generates the full nine-figure collection in PDF, SVG, and 300 dpi PNG from committed evidence.

| Figure | What it shows |
| --- | --- |
| [Model comparison](model-comparison.svg) | Six models; 17-program development macro-MAE and separate 192-circuit fresh-probe MAE. Development bars have descriptive program-bootstrap intervals; probe bars have none. Panel scales differ. |
| [Every probe stratum](probe-strata.svg) | MasterRTL, residual v2, and structural v3 across all eight groups. Linear and log(1 + MAE) views preserve the multiplication errors and variable-shift loss. |
| [Paired differences](paired-differences.svg) | Comparator-minus-MasterRTL MAE; positive favors MasterRTL. Descriptive 95% percentile intervals resample paired formulas within eight fixed strata. The residual-v2 interval includes zero. |

The evaluated target is isolated iCE40 LUT4 count. These charts do not compare published headline scores across different datasets and do not measure CPU speedup. See [results](../results.md), the [independent audit](../../results/2026-10-13-v3/independent-audit.txt), and the [reproduction guide](../reproduce-matched-comparison.md).

[provenance.json](provenance.json) records the source figure names, file hashes, numerical input hashes, and plotting-source hash. Complete observation arrays and captions are emitted as `figure-data.json` and `README.txt` by each figure replay. The editable architecture illustration is in [`../assets/`](../assets/) and is generated separately with `make diagram`.
