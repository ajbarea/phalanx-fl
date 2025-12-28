// Quick pattern presets for experiment queue strategy variations

export const QUICK_PATTERNS = {
  sweepMalicious: {
    id: 'sweepMalicious',
    name: 'Sweep Malicious Clients (0-5)',
    description: 'Test defense robustness by increasing malicious clients from 0 to 5',
    generate: (baseStrategy, numOfClients = 5) => {
      // Limit sweep to valid range for the number of clients
      const maxMalicious = Math.min(5, numOfClients - 1);
      return Array.from({ length: maxMalicious + 1 }, (_, i) => ({
        name: `${baseStrategy || 'fedavg'}_mal_${i}`,
        aggregation_strategy_keyword: baseStrategy || 'fedavg',
        num_of_malicious_clients: i,
        remove_clients: i > 0 ? 'true' : 'false',
      }));
    },
  },

  compareStrategies: {
    id: 'compareStrategies',
    name: 'Compare All Strategies',
    description: 'Compare all 8 aggregation strategies with no attacks',
    generate: (baseStrategy, numOfClients = 5) => {
      // With 0 malicious, maxK = numOfClients
      const maxK = numOfClients;
      return [
        {
          name: 'fedavg_baseline',
          aggregation_strategy_keyword: 'fedavg',
          num_of_malicious_clients: 0,
          remove_clients: 'false',
        },
        {
          name: 'krum_baseline',
          aggregation_strategy_keyword: 'krum',
          num_of_malicious_clients: 0,
          num_krum_selections: 1,
          remove_clients: 'false',
        },
        {
          name: 'multi_krum_baseline',
          aggregation_strategy_keyword: 'multi-krum',
          num_of_malicious_clients: 0,
          num_krum_selections: Math.min(4, maxK),
          remove_clients: 'false',
        },
        {
          name: 'bulyan_baseline',
          aggregation_strategy_keyword: 'bulyan',
          num_of_malicious_clients: 0,
          num_krum_selections: Math.min(4, maxK),
          remove_clients: 'false',
        },
        {
          name: 'trimmed_mean_baseline',
          aggregation_strategy_keyword: 'trimmed_mean',
          num_of_malicious_clients: 0,
          trim_ratio: 0.1,
          remove_clients: 'false',
        },
        {
          name: 'rfa_baseline',
          aggregation_strategy_keyword: 'rfa',
          num_of_malicious_clients: 0,
          remove_clients: 'false',
        },
        {
          name: 'trust_baseline',
          aggregation_strategy_keyword: 'trust',
          num_of_malicious_clients: 0,
          trust_threshold: 0.15,
          beta_value: 0.75,
          remove_clients: 'false',
        },
        {
          name: 'pid_baseline',
          aggregation_strategy_keyword: 'pid',
          num_of_malicious_clients: 0,
          Kp: 1.0,
          Ki: 0.05,
          Kd: 0.05,
          num_std_dev: 2.0,
          remove_clients: 'false',
        },
      ];
    },
  },

  sweepKrumSelections: {
    id: 'sweepKrumSelections',
    name: 'Sweep Krum Selections (1-5)',
    description: 'Test multi-krum with different selection thresholds',
    generate: (baseStrategy, numOfClients = 5) => {
      // With 0 malicious, maxK = numOfClients
      const maxK = Math.min(5, numOfClients);
      return Array.from({ length: maxK }, (_, i) => i + 1).map(k => ({
        name: `multi_krum_k${k}`,
        aggregation_strategy_keyword: 'multi-krum',
        num_of_malicious_clients: 0,
        num_krum_selections: k,
        remove_clients: 'false',
      }));
    },
  },

  defenseComparison: {
    id: 'defenseComparison',
    name: 'Defense Comparison (1 Malicious)',
    description: 'Compare Byzantine-resilient defenses under attack (1 malicious client)',
    generate: (baseStrategy, numOfClients = 5) => {
      // Use 1 malicious to satisfy Byzantine constraints with default 5 clients:
      // - Krum/Multi-Krum: n > 2f + 2 -> 5 > 4 OK
      // - Bulyan still needs n >= 4f + 3 = 7 clients for f=1
      const malicious = 1;
      const maxK = numOfClients - malicious; // Available honest clients for selection
      return [
        {
          name: 'fedavg_1mal',
          aggregation_strategy_keyword: 'fedavg',
          num_of_malicious_clients: malicious,
          remove_clients: 'false',
        },
        {
          name: 'krum_1mal',
          aggregation_strategy_keyword: 'krum',
          num_of_malicious_clients: malicious,
          num_krum_selections: 1,
          remove_clients: 'true',
          begin_removing_from_round: 2,
        },
        {
          name: 'multi_krum_1mal',
          aggregation_strategy_keyword: 'multi-krum',
          num_of_malicious_clients: malicious,
          num_krum_selections: Math.min(3, maxK),
          remove_clients: 'true',
          begin_removing_from_round: 2,
        },
        {
          name: 'bulyan_1mal',
          aggregation_strategy_keyword: 'bulyan',
          num_of_malicious_clients: malicious,
          num_krum_selections: Math.min(3, maxK),
          remove_clients: 'true',
          begin_removing_from_round: 2,
        },
        {
          name: 'trimmed_mean_1mal',
          aggregation_strategy_keyword: 'trimmed_mean',
          num_of_malicious_clients: malicious,
          trim_ratio: 0.1,
          remove_clients: 'true',
          begin_removing_from_round: 2,
        },
        {
          name: 'rfa_1mal',
          aggregation_strategy_keyword: 'rfa',
          num_of_malicious_clients: malicious,
          remove_clients: 'true',
          begin_removing_from_round: 2,
        },
        {
          name: 'trust_1mal',
          aggregation_strategy_keyword: 'trust',
          num_of_malicious_clients: malicious,
          trust_threshold: 0.15,
          beta_value: 0.75,
          remove_clients: 'true',
          begin_removing_from_round: 2,
        },
        {
          name: 'pid_1mal',
          aggregation_strategy_keyword: 'pid',
          num_of_malicious_clients: malicious,
          Kp: 1.0,
          Ki: 0.05,
          Kd: 0.05,
          num_std_dev: 2.0,
          remove_clients: 'true',
          begin_removing_from_round: 2,
        },
      ];
    },
  },

  byzantineRobustness: {
    id: 'byzantineRobustness',
    name: 'Byzantine Robustness Sweep',
    description:
      'Test Byzantine-resilient strategies with increasing attack severity (respects research constraints)',
    generate: (baseStrategy, numOfClients = 5) => {
      // Research-backed constraints:
      // - Krum: n > 2f + 2 → max f = floor((n-2)/2)
      // - Bulyan: n ≥ 4f + 3 → max f = floor((n-3)/4)
      // - Trimmed Mean: generally needs trim_ratio * n clients trimmed from each end
      const strategyConstraints = {
        krum: { maxMalicious: Math.floor((numOfClients - 2) / 2) },
        'multi-krum': { maxMalicious: Math.floor((numOfClients - 2) / 2) },
        bulyan: { maxMalicious: Math.floor((numOfClients - 3) / 4) },
        trimmed_mean: { maxMalicious: Math.floor(numOfClients / 2) - 1 }, // More lenient
      };

      const variations = [];
      for (const [strategy, constraints] of Object.entries(strategyConstraints)) {
        const maxMal = Math.max(0, constraints.maxMalicious);
        for (let mal = 0; mal <= maxMal; mal++) {
          const honestClients = numOfClients - mal;
          // Calculate valid krum selections: at least 1, prefer 3, but cap at honest clients
          const validK = Math.max(1, Math.min(3, honestClients));
          variations.push({
            name: `${strategy.replace('-', '_')}_mal${mal}`,
            aggregation_strategy_keyword: strategy,
            num_of_malicious_clients: mal,
            num_krum_selections: strategy === 'trimmed_mean' ? undefined : validK,
            trim_ratio: strategy === 'trimmed_mean' ? 0.1 : undefined,
            remove_clients: mal > 0 ? 'true' : 'false',
            begin_removing_from_round: mal > 0 ? 2 : undefined,
          });
        }
      }
      return variations;
    },
  },
};

// Strategy parameter fields that can be overridden per strategy
export const OVERRIDABLE_FIELDS = [
  'aggregation_strategy_keyword',
  'num_of_malicious_clients',
  'num_krum_selections',
  'remove_clients',
  'begin_removing_from_round',
  'trust_threshold',
  'beta_value',
  'Kp',
  'Ki',
  'Kd',
  'num_std_dev',
  'trim_ratio',
  'attack_type',
];

// Aggregation strategy options
export const AGGREGATION_STRATEGIES = [
  { value: 'fedavg', label: 'FedAvg', group: 'baseline' },
  { value: 'krum', label: 'Krum', group: 'byzantine' },
  { value: 'multi-krum', label: 'Multi-Krum', group: 'byzantine' },
  { value: 'bulyan', label: 'Bulyan', group: 'byzantine' },
  { value: 'trimmed_mean', label: 'Trimmed Mean', group: 'byzantine' },
  { value: 'rfa', label: 'RFA (Geometric Median)', group: 'byzantine' },
  { value: 'trust', label: 'Trust-Based', group: 'adaptive' },
  { value: 'pid', label: 'PID Controller', group: 'adaptive' },
];

// Strategy-specific required parameters
export const STRATEGY_REQUIRED_PARAMS = {
  trust: ['trust_threshold', 'beta_value', 'begin_removing_from_round'],
  pid: ['Kp', 'Ki', 'Kd', 'num_std_dev'],
  'multi-krum': ['num_krum_selections'],
  krum: ['num_krum_selections'],
  bulyan: ['num_krum_selections'],
  trimmed_mean: ['trim_ratio'],
  rfa: [],
  fedavg: [],
};

// Default values for strategy-specific parameters
export const STRATEGY_DEFAULTS = {
  trust: {
    trust_threshold: 0.15,
    beta_value: 0.75,
    begin_removing_from_round: 2,
  },
  pid: {
    Kp: 1.0,
    Ki: 0.05,
    Kd: 0.05,
    num_std_dev: 2.0,
    begin_removing_from_round: 2,
  },
  krum: {
    num_krum_selections: 1,
  },
  'multi-krum': {
    num_krum_selections: 3,
  },
  bulyan: {
    num_krum_selections: 3,
    begin_removing_from_round: 2,
  },
  trimmed_mean: {
    trim_ratio: 0.1,
    begin_removing_from_round: 2,
  },
  rfa: {
    begin_removing_from_round: 2,
  },
  fedavg: {},
};
