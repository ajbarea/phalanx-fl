/**
 * Attack and Device Constants
 */

// Data Poisoning Attacks
export const DATA_ATTACKS = [
  { value: 'gaussian_noise', label: 'Gaussian Noise' },
  { value: 'label_flipping', label: 'Label Flipping' },
  { value: 'token_replacement', label: 'Token Replacement (NLP)' },
];

// Weight/Model Poisoning Attacks
export const WEIGHT_ATTACKS = [
  { value: 'model_poisoning', label: 'Model Poisoning' },
  { value: 'gradient_scaling', label: 'Gradient Scaling' },
  { value: 'byzantine_perturbation', label: 'Byzantine Perturbation' },
];

// All attacks combined (flat array for dropdowns expecting simple strings)
export const ATTACKS = [
  'gaussian_noise',
  'label_flipping',
  'token_replacement',
  'model_poisoning',
  'gradient_scaling',
  'byzantine_perturbation',
];

// Grouped attacks for enhanced dropdowns
export const ATTACK_GROUPS = [
  { label: 'Data Poisoning', options: DATA_ATTACKS },
  { label: 'Weight Poisoning', options: WEIGHT_ATTACKS },
];

// Token replacement configuration options
export const TOKEN_REPLACEMENT_VOCABULARIES = ['medical', 'financial', 'legal'];
export const TOKEN_REPLACEMENT_STRATEGIES = ['negative', 'random'];

export const DEVICES = ['cpu', 'gpu'];
