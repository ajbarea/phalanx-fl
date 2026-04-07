import assert from 'node:assert/strict';
import test from 'node:test';

import {
  formatVisualizationLabel,
  getOrderedVisualizationKeys,
  getSummaryVisualizationKeys,
  getVizConfig,
  normalizeVisualizations,
} from '../src/components/features/simulation-details/attackSnapshotsVisualizationUtils.js';

test('normalizes visualizations and merges additional map keys', () => {
  const snapshot = {
    image_path: 'attack_snapshots_0/client_0/round_1/model_poisoning_visual.png',
    visualizations: {
      prediction_comparison:
        'attack_snapshots_0/client_0/round_1/model_poisoning_prediction_comparison.png',
      additional: {
        drift_overlay: 'attack_snapshots_0/client_0/round_1/model_poisoning_drift_overlay.png',
      },
    },
  };

  const normalized = normalizeVisualizations(snapshot);

  assert.equal(
    normalized.primary,
    'attack_snapshots_0/client_0/round_1/model_poisoning_visual.png',
    'primary should fall back to image_path when missing'
  );
  assert.equal(
    normalized.prediction_comparison,
    'attack_snapshots_0/client_0/round_1/model_poisoning_prediction_comparison.png'
  );
  assert.equal(
    normalized.drift_overlay,
    'attack_snapshots_0/client_0/round_1/model_poisoning_drift_overlay.png'
  );
});

test('orders weight visualizations and deduplicates primary path aliases', () => {
  const visualizations = {
    primary: 'prediction.png',
    prediction_comparison: 'prediction.png',
    weight_histogram: 'hist.png',
    weight_layer_delta: 'delta.png',
    unknown_overlay: 'overlay.png',
  };

  const orderedKeys = getOrderedVisualizationKeys(visualizations, 'model_poisoning');

  assert.deepEqual(orderedKeys, [
    'prediction_comparison',
    'weight_histogram',
    'weight_layer_delta',
    'unknown_overlay',
  ]);
});

test('uses readable fallback labels for unknown visualization keys', () => {
  assert.equal(formatVisualizationLabel('prediction_residual_map'), 'Prediction Residual Map');
  assert.equal(getVizConfig('prediction_residual_map').label, 'Prediction Residual Map');
});

test('summary keys keep known key order and append unknown keys', () => {
  const summaryCounts = {
    unknown_beta: 1,
    weight_layer_delta: 2,
    primary: 3,
    unknown_alpha: 4,
  };

  const orderedKeys = getSummaryVisualizationKeys(summaryCounts);

  assert.deepEqual(orderedKeys, ['primary', 'weight_layer_delta', 'unknown_alpha', 'unknown_beta']);
});
