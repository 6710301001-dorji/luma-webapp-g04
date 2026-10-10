# YuNet face-detection evaluation (#207)

This small evaluation uses one close portrait, two group portraits, and a
no-face sunflower photo. The boxes in `cases.json` were drawn by visual
inspection of the original photos before running YuNet. They are manual labels,
not official annotations from NASA or PhotoArt50. Source photos are not stored
in this repository. `RESULTS.json` and `REPORT.md` contain the run and its
limitations.

To reproduce it, download the four exact source files named in `cases.json`
into a temporary folder. For example, from the repository root:

```bash
mkdir -p /tmp/luma-yunet-207
curl -L 'https://images-assets.nasa.gov/image/s69-32616/s69-32616~large.jpg' -o /tmp/luma-yunet-207/single.jpg
curl -L 'https://assets.science.nasa.gov/dynamicimage/assets/science/psd/lunar-science/2023/09/s69-34385_orig.jpg?crop=faces%2Cfocalpoint&fit=clip&h=5712&w=3916' -o /tmp/luma-yunet-207/triple.jpg
curl -L 'https://science.nasa.gov/wp-content/uploads/2022/05/missions-sm4-jpg.webp' -o /tmp/luma-yunet-207/seven.jpg
curl -L 'https://raw.githubusercontent.com/BathVisArtData/PhotoArt50/c5f6bc1736607862290b5e2b3cc7522e20d0499f/204.sunflower/204p_0001.jpg' -o /tmp/luma-yunet-207/no-face.jpg
python services/ai-engine/samples/face_detection/evaluate_yunet.py --images-dir /tmp/luma-yunet-207
```

The script verifies SHA-256 and dimensions before running the detector. A
changed source file fails rather than silently changing the result. Input
photos are resized to a longest side of 1024 pixels. Ground-truth coordinates
in `cases.json` refer to the originals and are scaled with the images. The
detector settings are confidence 0.6 and minimum box side 20 pixels. The report
shows two one-to-one scores: whether a detection center is inside a hand-drawn
face box, and whether the boxes overlap with IoU of at least 0.5.

The strict score is sensitive to the hand-drawn box extent. This four-photo
sample is a reproducible course demonstration, not a held-out face benchmark.
The source pages and photo credits are linked in `cases.json`.
