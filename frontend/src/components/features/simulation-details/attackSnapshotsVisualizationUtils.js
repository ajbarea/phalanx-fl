const UNKNOWN_VIZ_ICON = '📄';

const WEIGHT_ATTACK_TYPES = new Set([
  'model_poisoning',
  'gradient_scaling',
  'byzantine_perturbation',
  'boosted_scaling',
  'inner_product_manipulation',
  'alternating_min_poisoning',
]);

const TEXT_ATTACK_TYPES = new Set(['token_replacement']);

const WEIGHT_VIZ_ORDER = [
  'prediction_comparison',
  'weight_histogram',
  'weight_layer_delta',
  'prediction_grid',
  'comparison',
  'primary',
  'confusion_matrix',
  'difference_heatmap',
  'html_diff',
];

const DATA_VIZ_ORDER = [
  'primary',
  'comparison',
  'confusion_matrix',
  'difference_heatmap',
  'prediction_comparison',
  'prediction_grid',
  'weight_histogram',
  'weight_layer_delta',
  'html_diff',
];

const TEXT_VIZ_ORDER = ['html_diff', 'primary', 'comparison', 'prediction_comparison'];

const SUMMARY_VIZ_ORDER = [
  'primary',
  'prediction_comparison',
  'comparison',
  'confusion_matrix',
  'difference_heatmap',
  'weight_histogram',
  'weight_layer_delta',
  'prediction_grid',
  'html_diff',
];

export const VIZ_TYPES = {
  primary: { label: 'Samples', icon: '🖼️' },
  prediction_comparison: { label: 'Prediction Comparison', icon: '🎯' },
  comparison: { label: 'Comparison', icon: '🔄' },
  confusion_matrix: { label: 'Confusion Matrix', icon: '📊' },
  difference_heatmap: { label: 'Difference Heatmap', icon: '🌡️' },
  weight_histogram: { label: 'Weight Distribution', icon: '📈' },
  weight_layer_delta: { label: 'Layer Delta', icon: '🧮' },
  prediction_grid: { label: 'Prediction Impact', icon: '🧭' },
  html_diff: { label: 'Token Diff', icon: '📝' },
};

const ATTACK_VIZ_OVERRIDES = {
  model_poisoning: {
    primary: { label: 'Primary Samples', icon: '🖼️' },
  },
  gradient_scaling: {
    primary: { label: 'Primary Samples', icon: '🖼️' },
  },
  byzantine_perturbation: {
    primary: { label: 'Primary Samples', icon: '🖼️' },
  },
};

export const ATTACK_DESCRIPTIONS = {
  label_flipping: {
    title: 'Label Flipping Attack',
    description:
      'Changes training labels to wrong classes without modifying the actual images. The visual comparison shows identical images with different labels.',
    tip: 'Check the Confusion Matrix tab to see label remapping patterns.',
  },
  targeted_label_flipping: {
    title: 'Targeted Label Flipping Attack',
    description:
      'Re-labels one class as a specific target class, causing focused model errors rather than broad degradation.',
    tip: 'Compare Confusion Matrix and Difference Heatmap for directional misclassification.',
  },
  gaussian_noise: {
    title: 'Gaussian Noise Attack',
    description: 'Adds random noise to training images, disrupting the learning process.',
    tip: 'Check the Difference Heatmap tab to see pixel-level noise patterns.',
  },
  backdoor_trigger: {
    title: 'Backdoor Trigger Attack',
    description:
      'Injects a trigger pattern into samples so the model learns an attacker-chosen behavior when the trigger appears.',
    tip: 'Use Comparison and Confusion Matrix views to inspect trigger-induced misclassification.',
  },
  model_poisoning: {
    title: 'Model Poisoning Attack',
    description: 'Manipulates model weights to extreme values, degrading performance.',
    tip: 'Review Prediction Comparison, Weight Distribution, and Layer Delta tabs together.',
  },
  gradient_scaling: {
    title: 'Gradient Scaling Attack',
    description: 'Multiplies weight updates by a factor, amplifying malicious changes.',
    tip: 'Use Weight Distribution and Layer Delta to gauge amplification magnitude.',
  },
  byzantine_perturbation: {
    title: 'Byzantine Perturbation Attack',
    description: 'Injects random noise into model weights during training.',
    tip: 'Check Weight Distribution and Layer Delta tabs to see perturbation structure.',
  },
  boosted_scaling: {
    title: 'Boosted Scaling Attack',
    description:
      'Applies aggressive scaling to malicious updates to overpower benign client contributions.',
    tip: 'Look for extreme Weight Distribution shifts and large Layer Delta values.',
  },
  inner_product_manipulation: {
    title: 'Inner Product Manipulation Attack',
    description:
      'Crafts malicious updates to manipulate directional alignment with benign gradients during aggregation.',
    tip: 'Use Prediction Comparison and Layer Delta to inspect directional impact.',
  },
  alternating_min_poisoning: {
    title: 'Alternating-Min Poisoning Attack',
    description:
      'Alternates malicious update objectives across rounds to evade simple detection while degrading training.',
    tip: 'Compare multiple rounds to detect alternating behavior in weight and prediction visuals.',
  },
  token_replacement: {
    title: 'Token Replacement Attack',
    description: 'Replaces tokens in text data with adversarial alternatives.',
    tip: 'Check the Token Diff tab for detailed before/after comparison.',
  },
};

export function formatVisualizationLabel(vizType) {
  return vizType
    .replace(/[_-]+/g, ' ')
    .trim()
    .replace(/\b\w/g, char => char.toUpperCase());
}

export function getVizConfig(vizType, attackType) {
  const override = ATTACK_VIZ_OVERRIDES[attackType]?.[vizType];
  if (override) {
    return override;
  }

  const knownConfig = VIZ_TYPES[vizType];
  if (knownConfig) {
    return knownConfig;
  }

  return { label: formatVisualizationLabel(vizType), icon: UNKNOWN_VIZ_ICON };
}

function getPreferredVisualizationOrder(attackType) {
  if (WEIGHT_ATTACK_TYPES.has(attackType)) {
    return WEIGHT_VIZ_ORDER;
  }

  if (TEXT_ATTACK_TYPES.has(attackType)) {
    return TEXT_VIZ_ORDER;
  }

  return DATA_VIZ_ORDER;
}

export function normalizeVisualizations(snapshot) {
  const rawVisualizations =
    snapshot?.visualizations && typeof snapshot.visualizations === 'object'
      ? snapshot.visualizations
      : {};

  const normalized = {};

  Object.entries(rawVisualizations).forEach(([key, value]) => {
    if (key === 'additional') {
      return;
    }

    if (typeof value === 'string' && value) {
      normalized[key] = value;
    }
  });

  if (!normalized.primary && snapshot?.image_path) {
    normalized.primary = snapshot.image_path;
  }

  const additional = rawVisualizations.additional;
  if (additional && typeof additional === 'object' && !Array.isArray(additional)) {
    Object.entries(additional).forEach(([key, value]) => {
      if (!normalized[key] && typeof value === 'string' && value) {
        normalized[key] = value;
      }
    });
  }

  return normalized;
}

export function getOrderedVisualizationKeys(visualizations, attackType) {
  const keys = Object.keys(visualizations || {}).filter(
    key => typeof visualizations[key] === 'string' && visualizations[key]
  );

  if (!keys.length) {
    return [];
  }

  const preferred = getPreferredVisualizationOrder(attackType);
  const unknownKeys = keys.filter(key => !preferred.includes(key)).sort();

  const orderedByKey = [...preferred.filter(key => keys.includes(key)), ...unknownKeys];

  const orderedByPath = [];
  const seenPaths = new Set();

  orderedByKey.forEach(key => {
    const path = visualizations[key];
    if (seenPaths.has(path)) {
      return;
    }
    seenPaths.add(path);
    orderedByPath.push(key);
  });

  return orderedByPath;
}

export function getAvailableVisualizations(snapshot) {
  const visualizations = normalizeVisualizations(snapshot);
  const orderedKeys = getOrderedVisualizationKeys(visualizations, snapshot?.attack_type);
  return orderedKeys.map(key => ({ key, ...getVizConfig(key, snapshot?.attack_type) }));
}

export function getSummaryVisualizationKeys(vizTypeCounts) {
  const keys = Object.keys(vizTypeCounts || {});
  if (!keys.length) {
    return [];
  }

  const unknownKeys = keys.filter(key => !SUMMARY_VIZ_ORDER.includes(key)).sort();
  return [...SUMMARY_VIZ_ORDER.filter(key => keys.includes(key)), ...unknownKeys];
}

export function isHtmlVisualization(vizType, vizPath) {
  const normalizedPath = typeof vizPath === 'string' ? vizPath.toLowerCase() : '';
  return (
    vizType === 'html_diff' || normalizedPath.endsWith('.html') || normalizedPath.endsWith('.htm')
  );
}
