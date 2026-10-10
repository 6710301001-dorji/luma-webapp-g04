# Auto-tag evaluation — annotation pending (#201)

This directory prepares evidence; it does **not** contain measured real-image
classification accuracy yet. Production tags describe image attributes, not
objects such as cats, grass or flowers. No Forge connection is required.

## Review the images, not classifier predictions

`candidate_labels.csv` contains 50 **unlabelled** sunflower candidates already
used in the segmentation evaluation. `diverse_candidate_labels.csv` adds 58
unlabelled candidates from the OpenCV and scikit-image sample repositories.
Each new row points to its original file at a pinned Git commit and records its
SHA-256. No image is committed here. The new pool has 35 landscape, 20 roughly
square and 3 portrait files by the geometric rule below. This is a more varied
starting pool, **not** a representative or reviewed dataset; the portrait class
is especially small. Check after annotation that every tag has positive and
negative examples. Add team-owned images where coverage is weak. Prefer at least
50 reviewed images with both positive and negative support per tag. Do not
select only images that the classifier gets right.

Download the diverse candidates outside the repository (requires `curl`):

```bash
python services/ai-engine/samples/classification/fetch_candidate_images.py \
  --sheet services/ai-engine/samples/classification/diverse_candidate_labels.csv \
  --images-dir /path/to/private/classification-images
```

The downloader refuses changed or mismatched files; re-running it skips files
that still match the recorded hashes. Keep the original images out of Git and
check each source's terms before using or sharing them outside the team's course
evaluation. The `image` column gives paths under `--images-dir`; the `source`
column is the exact URL. Rows remain `pending`, with `?` in every label cell.
Boss/Jet should inspect the downloaded images without running the classifier,
agree on the guide below, and fill the labels, reviewer and notes. Keep uncertain
labels as `?`. This PR does not claim accuracy or complete #201.

Boss/Jet: review the following definitions before labelling. Look at the original
images without predictions. Enter `1` for present, `0` for absent, `?` for uncertain.
Unknown is not equivalent to absent. Mixed/neutral images may have neither warm
nor cool; moderate brightness/contrast may have neither extreme tag.

| Tags | Proposed independent annotation guide |
|---|---|
| warm / cool | Dominant visible colour impression: red/orange/yellow versus cyan/blue/purple. Mark ambiguous mixtures `?`; green alone need not belong to either. |
| monochrome | Visually grayscale or essentially lacking noticeable colour. |
| dark / bright | Overall image appears predominantly dark or predominantly bright; ordinary mid-tone images may have neither. |
| low-contrast / high-contrast | Overall tonal separation appears flat/narrow or strongly separated. Use `?` for borderline cases. |
| landscape-orientation / portrait-orientation / square-orientation | Image shape, not scene content. Width/height > 1.10 is landscape; < 1/1.10 is portrait; otherwise square. This geometric check is objective and should be reported separately from subjective visual labels. |

These are proposed human-perception labels; they need team agreement. The
classifier's numerical colour/brightness thresholds may disagree with visual
judgements. Preserve disagreement rather than adjusting labels to match output.
Ask a second person to resolve disagreements before marking a row `reviewed`;
record the reviewer role and decisions in `notes`. Rows may remain `pending`
or become `exclude` with a reason. Never mark generated predictions as reviewed
labels. The tool checks fields but cannot verify that review really happened.

## Prepare a sheet (no predictions are generated)

```bash
python services/ai-engine/samples/classification/evaluate_auto_tags.py prepare \
  --images-dir /path/to/images --sheet /path/to/labels.csv \
  --source "dataset URL and pinned revision, or team-owned photo provenance"
```

Existing sheets are never overwritten. Paths are relative to `images-dir`;
SHA-256 hashes use colon-separated groups (remove colons for standard output).
The supplied candidates use PhotoArt50 `204.sunflower`, revision
`c5f6bc1736607862290b5e2b3cc7522e20d0499f` of
https://github.com/BathVisArtData/PhotoArt50 . Obtain originals there, respecting
its redistribution restrictions. Combining pools requires keeping unique paths
and accurate source attribution in each row.

## Evaluate after review

```bash
python services/ai-engine/samples/classification/evaluate_auto_tags.py evaluate \
  --images-dir /path/to/images --sheet /path/to/reviewed_labels.csv \
  --output /path/to/evaluation-report
```

Pending/excluded rows and unknown label cells are omitted and counted explicitly.
With no reviewed known labels the command fails without creating a report.
Image hashes, sources, reviewer fields and label vocabulary are checked.
Outputs: per-image predictions/reasons/provenance in `predictions.json`, per-tag
metrics in `metrics.csv`, summaries in `summary.json`, ten 2×2 confusion matrices
and `REPORT.md`. Original images are not copied.

Accuracy is correct known image/tag decisions divided by all known decisions.
Exact-match accuracy uses only fully labelled images. Micro metrics pool known
label decisions; macro metrics average defined per-tag values. Division by zero
is `null` in JSON / `NA` in CSV; macro denominators are explicit. Report support
and missing classes alongside scores; a high accuracy from mostly absent tags
or easy orientation labels can be misleading. Keep synthetic rule fixtures
separate from real-image results. Do not close #201 or check off #27's
classification requirements until labels, coverage and final results are reviewed.
