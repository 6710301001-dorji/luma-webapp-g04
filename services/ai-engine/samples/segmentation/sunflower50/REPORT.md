# Full sunflower evaluation

All 50 cases (0001–0050) use the unchanged five-photo HSV settings; no per-image tuning.

- Macro IoU: **0.6609**; precision: **0.8740**; recall: **0.7369**.
- Images below IoU 0.5: **5 / 50**.
- Worst case: **204p_0018**, IoU **0.2827**.
- Pre-morphology, pooled-pixel ROC AUC: **0.8785**.

The earlier selected five-image macro IoU was 0.7133. The wider set is more representative of this sunflower class, but is not an independent held-out dataset or evidence for other object classes.

## Interpretation and limits

Precision exceeds recall: the fixed selection misses substantial parts of some flowers. See worst_cases.png rather than only the strongest examples.

ROC ranks raw HSV pixels by 180 minus circular hue distance to 50 degrees. Pixels below saturation 60 or value 40 receive score -1. Thresholds 181 down to -1 include select-none and select-all. Ties are accumulated together; AUC uses trapezoidal integration. Scores are not probabilities. Morphology is excluded from this ranking; its final binary operating point is shown separately in red.

Pooled pixels weight larger images more heavily. The ROC is descriptive on this same dataset, not a tuned-threshold validation or a classification accuracy result.

Ground truth is attributed to the team workshop; its manual annotation process was not independently observed. Source photos are not redistributed. See the parent README for pinned sources and reproduction; source_hashes.csv identifies every input and prediction.

metrics.csv includes every case. summary.json contains parameters and aggregate confusion counts; roc_histograms.csv and roc.csv make ROC calculations independently reproducible.
