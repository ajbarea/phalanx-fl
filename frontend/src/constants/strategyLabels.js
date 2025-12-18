// Human-readable formatting functions for simulation parameters

export const formatStrategyName = keyword => {
  const names = {
    fedavg: 'Federated Averaging',
    trust: 'Trust-based',
    pid: 'PID Controller',
    pid_scaled: 'PID Controller (Scaled)',
    pid_standardized: 'PID Controller (Standardized)',
    pid_standardized_score_based: 'PID Controller (Standardized Score-Based)',
    'multi-krum': 'Multi-Krum',
    krum: 'Krum',
    'multi-krum-based': 'Multi-Krum Based',
    trimmed_mean: 'Trimmed Mean',
    rfa: 'RFA',
    bulyan: 'Bulyan',
  };
  return names[keyword] || keyword;
};

export const formatDatasetName = keyword => {
  const names = {
    femnist_iid: 'FEMNIST (IID)',
    femnist_niid: 'FEMNIST (Non-IID)',
    its: 'ITS',
    pneumoniamnist: 'PneumoniaMNIST',
    flair: 'FLAIR',
    bloodmnist: 'BloodMNIST',
    medquad: 'MedQuAD',
    lung_photos: 'Lung Photos',
    financial_phrasebank: 'Financial PhraseBank',
    lexglue: 'LexGLUE LEDGAR',
    medal: 'PubMed MEDLINE',
    breastmnist: 'BreastMNIST',
    pathmnist: 'PathMNIST',
    dermamnist: 'DermaMNIST',
    octmnist: 'OCTMNIST',
    retinamnist: 'RetinaMNIST',
    tissuemnist: 'TissueMNIST',
    organamnist: 'OrganAMNIST',
    organcmnist: 'OrganCMNIST',
    organsmnist: 'OrganSMNIST',
  };
  return names[keyword] || keyword;
};

export const formatAttackName = keyword => {
  const names = {
    gaussian_noise: 'Gaussian Noise',
    label_flipping: 'Label Flipping',
    token_replacement: 'Token Replacement',
    model_poisoning: 'Model Poisoning',
    gradient_scaling: 'Gradient Scaling',
    byzantine_perturbation: 'Byzantine Perturbation',
  };
  return names[keyword] || keyword;
};
