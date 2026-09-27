"""Multi-label attribute metrics; unknown labels never count as negatives."""
TAGS = ('warm', 'cool', 'monochrome', 'dark', 'bright', 'low-contrast',
        'high-contrast', 'landscape-orientation', 'portrait-orientation', 'square-orientation')


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def scores(tp, fp, fn, tn):
    return {'tp': tp, 'fp': fp, 'fn': fn, 'tn': tn, 'support': tp + fn,
            'evaluated': tp + fp + fn + tn, 'accuracy': ratio(tp + tn, tp + fp + fn + tn),
            'precision': ratio(tp, tp + fp), 'recall': ratio(tp, tp + fn),
            'f1': ratio(2 * tp, 2 * tp + fp + fn)}


def evaluate(cases):
    """cases: [{expected: {tag: 0/1/None}, predicted: [tag, ...]}]."""
    if not cases:
        raise ValueError('at least one reviewed case is required')
    counts = {tag: [0, 0, 0, 0] for tag in TAGS}
    complete = exact = 0
    for case in cases:
        expected, predicted = case['expected'], set(case['predicted'])
        if set(expected) != set(TAGS) or not predicted.issubset(TAGS):
            raise ValueError('labels and predictions must use the supported tag vocabulary')
        if any(value not in (0, 1, None) for value in expected.values()):
            raise ValueError('expected labels must be 0, 1 or None')
        for tag, value in expected.items():
            if value is not None:
                index = (0 if tag in predicted else 2) if value else (1 if tag in predicted else 3)
                counts[tag][index] += 1
        if all(value is not None for value in expected.values()):
            complete += 1
            exact += predicted == {tag for tag, value in expected.items() if value == 1}
    per_tag = {tag: scores(*values) for tag, values in counts.items()}
    totals = [sum(values[index] for values in counts.values()) for index in range(4)]
    if sum(totals) == 0:
        raise ValueError('at least one known reviewed label is required')
    macro, defined = {}, {}
    for metric in ('accuracy', 'precision', 'recall', 'f1'):
        values = [row[metric] for row in per_tag.values() if row[metric] is not None]
        macro[metric] = sum(values) / len(values) if values else None
        defined[metric] = len(values)
    return {'images': len(cases), 'fully_labelled_images': complete,
            'exact_match_accuracy': ratio(exact, complete), 'per_tag': per_tag,
            'micro': scores(*totals), 'macro': macro, 'macro_defined_tags': defined}
