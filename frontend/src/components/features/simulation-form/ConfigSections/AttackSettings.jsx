import { SelectField } from '../FormFields/SelectField';
import { NumberField } from '../FormFields/NumberField';
import {
  ATTACKS,
  TOKEN_REPLACEMENT_VOCABULARIES,
  TOKEN_REPLACEMENT_STRATEGIES,
} from '@constants/attacks';

export function AttackSettings({ config, onChange }) {
  const needsGaussianParams = config.attack_type === 'gaussian_noise';
  const needsTokenReplacementParams = config.attack_type === 'token_replacement';
  const needsWeightAttackParams = [
    'model_poisoning',
    'gradient_scaling',
    'byzantine_perturbation',
  ].includes(config.attack_type);

  return (
    <>
      <NumberField
        name="num_of_malicious_clients"
        label="Number of Malicious Clients"
        value={config.num_of_malicious_clients}
        onChange={onChange}
        min={0}
        max={config.num_of_clients}
        tooltip="Number of malicious/Byzantine clients in the simulation. Set to 0 for baseline experiments."
      />

      {config.num_of_malicious_clients > 0 && (
        <>
          <SelectField
            name="attack_type"
            label="Attack Type"
            value={config.attack_type}
            onChange={onChange}
            options={ATTACKS}
            tooltip="Type of Byzantine attack. Data poisoning attacks corrupt training data; weight poisoning attacks manipulate model parameters."
          />

          {needsGaussianParams && (
            <>
              <NumberField
                name="gaussian_noise_mean"
                label="Gaussian Noise Mean"
                value={config.gaussian_noise_mean}
                onChange={onChange}
                step={0.1}
                tooltip="Mean (μ) of Gaussian noise distribution added to model weights. Typically set to 0 for zero-centered noise."
              />

              <NumberField
                name="gaussian_noise_std"
                label="Gaussian Noise Std Dev"
                value={config.gaussian_noise_std}
                onChange={onChange}
                step={0.1}
                min={0}
                tooltip="Standard deviation (σ) of Gaussian noise distribution. Higher values create stronger perturbations and more aggressive attacks."
              />

              <NumberField
                name="attack_ratio"
                label="Attack Ratio"
                value={config.attack_ratio}
                onChange={onChange}
                step={0.1}
                min={0}
                max={1}
                tooltip="Fraction of model parameters to attack (0-1). 1.0 = attack all parameters."
              />
            </>
          )}

          {needsTokenReplacementParams && (
            <>
              <SelectField
                name="target_vocabulary"
                label="Target Vocabulary"
                value={config.target_vocabulary || 'medical'}
                onChange={onChange}
                options={TOKEN_REPLACEMENT_VOCABULARIES}
                tooltip="Domain vocabulary for token replacement attacks. Medical for healthcare terms, financial for finance terms, legal for legal terminology."
              />

              <SelectField
                name="replacement_strategy"
                label="Replacement Strategy"
                value={config.replacement_strategy || 'negative'}
                onChange={onChange}
                options={TOKEN_REPLACEMENT_STRATEGIES}
                tooltip="Strategy for replacing tokens. 'negative' replaces with semantically opposite terms, 'random' replaces with random vocabulary words."
              />
            </>
          )}

          {needsWeightAttackParams && (
            <NumberField
              name="poison_scale"
              label="Poison Scale"
              value={config.poison_scale || 1.0}
              onChange={onChange}
              step={0.1}
              min={0}
              tooltip="Scale factor for weight poisoning attacks. Higher values create stronger perturbations to model weights."
            />
          )}
        </>
      )}
    </>
  );
}
