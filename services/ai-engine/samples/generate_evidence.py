"""Generate labelled pipeline evidence from deterministic synthetic fixtures.

Run from the repository root with the project Python environment. No Forge needed.
"""
import json
import platform
from datetime import datetime, timezone
import sys
from importlib import import_module
from pathlib import Path

import cv2
import matplotlib
import numpy as np

matplotlib.use('Agg')
from matplotlib import pyplot as plt

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))
OUTPUT = ROOT / 'output'
EVALUATION = ROOT / 'evaluation'
MANIFEST = {}


def module(stage, name):
    return import_module(f'pipeline.{stage}.{name}')


def display(axis, pixels, title):
    if pixels.ndim == 3:
        pixels = cv2.cvtColor(pixels, cv2.COLOR_BGRA2RGBA if pixels.shape[2] == 4 else cv2.COLOR_BGR2RGB)
    axis.imshow(pixels, cmap='gray', vmin=0, vmax=255, interpolation='nearest')
    axis.set_title(title, fontsize=10)
    axis.axis('off')


def figure(name, panels):
    fig, axes = plt.subplots(1, panels, figsize=(4 * panels, 4), squeeze=False)
    fig.suptitle(name.replace('_', ' ').title() + ' | Synthetic demonstration', fontsize=13)
    return fig, axes[0]


def save(fig, stage, name, note):
    filename = f'{name}_before_after.png'
    fig.tight_layout(rect=(0, 0.05, 1, 0.91))
    fig.text(0.5, 0.015, note, ha='center', fontsize=8)
    fig.savefig(OUTPUT / filename, dpi=130)
    plt.close(fig)
    MANIFEST[f'pipeline/{stage}/{name}.py'] = {'image': f'output/{filename}', 'note': note}


def comparison(stage, name, panels, note):
    fig, axes = figure(name, len(panels))
    for axis, (label, pixels) in zip(axes, panels):
        display(axis, pixels, label)
    save(fig, stage, name, note)


def main():
    OUTPUT.mkdir(exist_ok=True)
    EVALUATION.mkdir(exist_ok=True)
    # Analytical shapes make hue selection and contour geometry easy to inspect.
    scene = np.full((192, 256, 3), (45, 40, 35), dtype=np.uint8)
    cv2.circle(scene, (70, 95), 43, (30, 30, 230), -1)
    cv2.rectangle(scene, (150, 35), (230, 95), (40, 190, 40), -1)
    cv2.rectangle(scene, (140, 125), (230, 160), (220, 70, 30), -1)
    gray = np.tile(np.linspace(20, 230, 256, dtype=np.uint8), (192, 1))
    cv2.rectangle(gray, (45, 40), (110, 145), 180, -1)
    cv2.circle(gray, (180, 100), 35, 55, -1)
    low = (gray.astype(np.float64) * 0.25 + 45).astype(np.uint8)
    rng = np.random.default_rng(132)
    noisy = gray.copy()
    impulses = rng.random(gray.shape)
    noisy[impulses < 0.035] = 0
    noisy[impulses > 0.965] = 255
    for name, image in [('evidence_scene', scene), ('evidence_reference', gray), ('evidence_low_contrast', low), ('evidence_noisy', noisy)]:
        if not cv2.imwrite(str(ROOT / 'input' / f'{name}.png'), image):
            raise RuntimeError(f'Cannot save {name}')

    stage = '01_acquisition'
    acquisition = module(stage, 'acquisition')
    source = acquisition.load(ROOT / 'input/evidence_scene.png')
    resized = acquisition.normalize_width(source, 128)
    comparison(stage, 'acquisition', [('Before: 256 x 192', source), ('After: 128 x 96', resized)],
               'Actual normalize_width output; display panels share a size, pixel dimensions differ.')

    stage = '02_enhancement'
    hist = module(stage, 'histogram')
    fig, axes = figure('histogram', 2)
    display(axes[0], low, 'Input: low contrast')
    axes[1].plot(hist.histogram(low)['gray'])
    stats = hist.statistics(low)['gray']
    axes[1].set(xlabel='Intensity (0-255)', ylabel='Pixels', xlim=(0, 255),
                title=f"Mean {stats['mean']:.1f}; variance {stats['variance']:.1f}\nSkew {stats['skewness']:.2f}; kurtosis {stats['kurtosis']:.2f}")
    save(fig, stage, 'histogram', 'A measurement module: input image and computed histogram, not an enhanced image.')
    point = module(stage, 'point_operations')
    comparison(stage, 'point_operations', [('Before', low), ('Gamma = 0.5', point.gamma(low, 0.5)),
                ('Log transform', point.log_transform(low)), ('Contrast stretch', point.contrast_stretch(low))],
                'All panels use the same display range 0-255; brightness changes are not autoscaled.')
    mapping = module(stage, 'histogram_mapping')
    comparison(stage, 'histogram_mapping', [('Before', low), ('Reference', gray),
                ('Equalization', mapping.equalize(low)), ('Histogram matching', mapping.match_histogram(low, gray))],
                'Matching uses the displayed reference; equalization uses the input distribution.')
    filters = module(stage, 'spatial_filters')
    comparison(stage, 'spatial_filters', [('Before: impulse noise', noisy), ('Box 3 x 3', filters.box(noisy)),
                ('Gaussian 3 x 3', filters.gaussian(noisy)), ('Median 3 x 3', filters.median(noisy))],
                'Seed 132; salt/pepper probabilities 3.5% each; identical noisy input for every filter.')

    stage = '03_segmentation'
    segmentation = module(stage, 'segmentation')
    selected = segmentation.segment(scene, center_degrees=0, tolerance_degrees=20)
    comparison(stage, 'segmentation', [('Before', scene), ('Red selection mask', selected['mask']),
                ('After: transparent background', selected['image'])],
                'Hue 0 +/- 20 degrees; saturation >= 60, value >= 40; morphology kernel 3.')

    stage = '04_features'
    palette = module(stage, 'color_palette').extract_palette(scene, colors=4)
    fig, axes = figure('color_palette', 2)
    display(axes[0], scene, 'Input')
    axes[1].barh([e['hex'] for e in palette], [e['proportion'] for e in palette], color=[e['hex'] for e in palette])
    axes[1].set(xlabel='Fraction of all pixels', xlim=(0, 1), title='Extracted palette')
    save(fig, stage, 'color_palette', 'Four-color synthetic fixture; bar lengths are computed pixel proportions.')
    vector = module(stage, 'feature_vector').extract(scene)
    fig, axes = figure('feature_vector', 2)
    display(axes[0], scene, 'Input')
    axes[1].bar(np.arange(len(vector)), vector)
    axes[1].set(xlabel='Feature index', ylabel='Normalized value', title='Computed 28-value descriptor')
    save(fig, stage, 'feature_vector', 'Indices 0-23: 8-bin B/G/R histograms; 24-27: normalized grayscale statistics.')
    shape = module(stage, 'shape_sharpness')
    blurred = filters.gaussian(scene, size=15, sigma=4)
    geometry = shape.contour_features(selected['objects'][0]['contour'])
    comparison(stage, 'shape_sharpness', [(f'Input sharpness: {shape.sharpness(scene):.2f}', scene),
                (f'Blurred sharpness: {shape.sharpness(blurred):.2f}', blurred)],
                f"Red contour: area {geometry['area']:.0f}, perimeter {geometry['perimeter']:.1f}, circularity {geometry['circularity']:.3f}.")

    stage = '05_evaluation'
    quality = module(stage, 'quality_metrics')
    denoised = filters.median(noisy)
    panels = [('Reference', gray)]
    for label, candidate in [('Before', noisy), ('After: median', denoised)]:
        scores = quality.image_quality(gray, candidate)
        panels.append((f"{label}\nPSNR {scores['psnr']:.2f} dB; SSIM {scores['ssim']:.3f}", candidate))
    comparison(stage, 'quality_metrics', panels, 'Scores use the clean reference, not the noisy input; this is one controlled example.')
    # Keep every method on the same noisy input and clean reference so the
    # report table compares methods fairly, including methods that worsen it.
    enhanced = {
        'gamma': point.gamma(noisy, 0.5),
        'log': point.log_transform(noisy),
        'contrast_stretch': point.contrast_stretch(noisy),
        'equalization': mapping.equalize(noisy),
        'histogram_matching': mapping.match_histogram(noisy, gray),
        'box': filters.box(noisy),
        'gaussian': filters.gaussian(noisy),
        'median': denoised,
    }
    quality.write_csv(quality.before_after_table(gray, noisy, enhanced), EVALUATION / 'quality_metrics_table.csv')
    MANIFEST['pipeline/05_evaluation/quality_metrics.py']['table'] = 'evaluation/quality_metrics_table.csv'
    MANIFEST['pipeline/05_evaluation/quality_metrics.py']['table_inputs'] = {
        'reference': 'input/evidence_reference.png',
        'before': 'input/evidence_noisy.png',
    }
    MANIFEST['pipeline/05_evaluation/quality_metrics.py']['table_parameters'] = {
        'gamma': 0.5,
        'box_size': 3,
        'gaussian_size': 3,
        'median_size': 3,
        'histogram_matching_reference': 'input/evidence_reference.png',
    }
    metrics = module(stage, 'segmentation_metrics')
    truth = np.zeros(gray.shape, dtype=np.uint8)
    prediction = truth.copy()
    cv2.circle(truth, (120, 95), 45, 255, -1)
    cv2.circle(prediction, (132, 95), 45, 255, -1)
    score = metrics.segmentation_quality(truth, prediction)
    comparison(stage, 'segmentation_metrics', [('Ground truth', truth), ('Prediction: shifted 12 px', prediction)],
                f"IoU {score['iou']:.3f}; precision {score['precision']:.3f}; recall {score['recall']:.3f}. Synthetic mask pair, not real annotation.")
    benchmark = module(stage, 'benchmark_baseline')
    timing = benchmark.benchmark_box_filter(gray, kernel_size=15, repeats=10)
    fig, axes = figure('benchmark_baseline', 2)
    display(axes[0], gray, 'Input: 256 x 192, kernel 15 x 15')
    axes[1].bar(['2D box', 'Separable box'], [timing['box_2d_ms'], timing['box_separable_ms']])
    axes[1].set(ylabel='Median milliseconds (10 trials)', title=f"Measured speedup: {timing['speedup']:.2f}x")
    save(fig, stage, 'benchmark_baseline', f"Local measured timing; varies by machine. Max output difference: {timing['max_pixel_difference']:.6f}.")
    MANIFEST['pipeline/05_evaluation/benchmark_baseline.py']['measurement'] = {
        **timing, 'recorded_at_utc': datetime.now(timezone.utc).isoformat(),
        'machine': platform.machine(), 'system': platform.system(),
        'python': platform.python_version(), 'opencv': cv2.__version__,
        'image_shape': list(gray.shape), 'kernel_size': 15, 'repeats': 10,
    }
    (ROOT / 'evidence_manifest.json').write_text(json.dumps(MANIFEST, indent=2) + '\n', encoding='utf-8')
    print(f'Generated {len(MANIFEST)} module figures in {OUTPUT}')


if __name__ == '__main__':
    main()
