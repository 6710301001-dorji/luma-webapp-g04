# Segmentation evaluation fixtures

This directory contains five deliberately authored binary ground-truth masks
and five example predictions for issue #67. The cases vary from an easy compact
object to multiple objects, thin structures, shifted boundaries, and small
false-positive regions.

These small masks make the metric tests repeatable. They are evaluation
fixtures, not evidence of real-world accuracy. Before the final report, replace
or supplement them with hand-drawn masks for five representative project
photos, then retain the resulting CSV and discuss the failure cases.

- `ground_truth/case_01.png` through `case_05.png`: expected object pixels.
- `predictions/case_01.png` through `case_05.png`: example system output.

