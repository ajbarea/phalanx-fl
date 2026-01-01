// Attack Visualization Component Library
// Provides specialized visualization components for different attack types

import { AttackVisualizationCard } from './AttackVisualizationCard';
import { GaussianNoiseVisualization } from './GaussianNoiseVisualization';
import { LabelFlippingVisualization } from './LabelFlippingVisualization';
import { WeightAttackVisualization } from './WeightAttackVisualization';
import { TokenReplacementVisualization } from './TokenReplacementVisualization';
import { GenericAttackVisualization } from './GenericAttackVisualization';

export {
  AttackVisualizationCard,
  GaussianNoiseVisualization,
  LabelFlippingVisualization,
  WeightAttackVisualization,
  TokenReplacementVisualization,
  GenericAttackVisualization,
};

// Visualization type configuration
export const VIZ_TYPES = {
  primary: { label: 'Samples', icon: '🖼️', priority: 1 },
  comparison: { label: 'Comparison', icon: '🔄', priority: 2 },
  confusion_matrix: { label: 'Confusion Matrix', icon: '📊', priority: 3 },
  difference_heatmap: { label: 'Difference Heatmap', icon: '🌡️', priority: 4 },
  weight_histogram: { label: 'Weight Distribution', icon: '📈', priority: 5 },
  prediction_grid: { label: 'Prediction Impact', icon: '🎯', priority: 6 },
  html_diff: { label: 'Token Diff', icon: '📝', priority: 7 },
};

// Attack type metadata
export const ATTACK_TYPES = {
  label_flipping: {
    title: 'Label Flipping Attack',
    description:
      'Changes training labels to wrong classes without modifying the actual images. The attack is invisible at the data level.',
    tip: 'Check the Confusion Matrix tab to see label remapping patterns.',
    color: '#e74c3c',
    icon: '🏷️',
    category: 'data_poisoning',
  },
  gaussian_noise: {
    title: 'Gaussian Noise Attack',
    description: 'Adds random noise to training images, disrupting the learning process.',
    tip: 'Check the Difference Heatmap tab to see pixel-level noise patterns.',
    color: '#9b59b6',
    icon: '📡',
    category: 'data_poisoning',
  },
  model_poisoning: {
    title: 'Model Poisoning Attack',
    description: 'Manipulates model weights to extreme values, degrading performance.',
    tip: 'Check the Prediction Impact and Weight Distribution tabs.',
    color: '#c0392b',
    icon: '⚡',
    category: 'weight_attack',
  },
  gradient_scaling: {
    title: 'Gradient Scaling Attack',
    description: 'Multiplies weight updates by a factor, amplifying malicious changes.',
    tip: 'Check the Weight Distribution tab to see the scale of modifications.',
    color: '#d35400',
    icon: '📐',
    category: 'weight_attack',
  },
  byzantine_perturbation: {
    title: 'Byzantine Perturbation Attack',
    description: 'Injects random noise into model weights during training.',
    tip: 'Check the Weight Distribution tab to see noise patterns.',
    color: '#8e44ad',
    icon: '🎲',
    category: 'weight_attack',
  },
  token_replacement: {
    title: 'Token Replacement Attack',
    description: 'Replaces tokens in text data with adversarial alternatives.',
    tip: 'Check the Token Diff tab for detailed before/after comparison.',
    color: '#2980b9',
    icon: '📝',
    category: 'nlp_attack',
  },
};

// Helper function to get visualization component for attack type
export function getVisualizationComponent(attackType) {
  const attackInfo = ATTACK_TYPES[attackType];

  if (!attackInfo) {
    return { Component: GenericAttackVisualization, category: 'unknown' };
  }

  switch (attackInfo.category) {
    case 'data_poisoning':
      if (attackType === 'label_flipping') {
        return { Component: LabelFlippingVisualization, category: 'data_poisoning' };
      }
      return { Component: GaussianNoiseVisualization, category: 'data_poisoning' };
    case 'weight_attack':
      return { Component: WeightAttackVisualization, category: 'weight_attack' };
    case 'nlp_attack':
      return { Component: TokenReplacementVisualization, category: 'nlp_attack' };
    default:
      return { Component: GenericAttackVisualization, category: 'unknown' };
  }
}

// Helper to check if attack type is composite
export function isCompositeAttack(attackType) {
  if (!attackType) return false;
  const parts = attackType.split('_');
  // Check if multiple attack keywords are present
  const attackKeywords = [
    'label',
    'flipping',
    'gaussian',
    'noise',
    'model',
    'poisoning',
    'gradient',
    'scaling',
    'byzantine',
    'perturbation',
    'token',
    'replacement',
  ];
  const matchedKeywords = parts.filter(p => attackKeywords.includes(p.toLowerCase()));
  return matchedKeywords.length > 3; // More than one attack type's keywords
}
