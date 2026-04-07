/**
 * Plot Metadata Constants
 *
 * Provides friendly names, descriptions, and categorization for FL simulation plots.
 * Used by ComparisonView and SimulationDetails for consistent, accessible display.
 *
 * Categories:
 * - training: Core training metrics (always shown)
 * - defense: Defense effectiveness metrics (only for removal strategies)
 * - advanced: Technical/performance metrics (collapsed by default)
 */

// Aggregation strategies that support client removal
export const REMOVAL_STRATEGIES = [
  'krum',
  'multi-krum',
  'pid',
  'trust',
  'rfa',
  'trimmed_mean',
  'bulyan',
];

// Plot metadata with friendly names, descriptions, and categories
export const PLOT_METADATA = {
  // === TRAINING PROGRESS (Core - Always Shown) ===
  accuracy_history_0: {
    displayName: 'Model Accuracy',
    description: 'Per-client accuracy over training rounds',
    category: 'training',
    priority: 1,
  },
  loss_history_0: {
    displayName: 'Training Loss',
    description: 'Per-client loss values showing learning progress',
    category: 'training',
    priority: 2,
  },
  average_accuracy_history: {
    displayName: 'Average Accuracy',
    description: 'Mean accuracy across all participating clients',
    category: 'training',
    priority: 3,
  },
  aggregated_loss_history: {
    displayName: 'Aggregated Loss',
    description: 'Combined loss from the global model',
    category: 'training',
    priority: 4,
  },

  // === DEFENSE EFFECTIVENESS (Only for removal strategies) ===
  removal_accuracy_history: {
    displayName: 'Defense Accuracy',
    description: 'How accurately malicious clients were identified (TP+TN)/(Total)',
    category: 'defense',
    requiresRemoval: true,
    priority: 1,
  },
  removal_precision_history: {
    displayName: 'Defense Precision',
    description: 'Avoiding false positives - not flagging honest clients',
    category: 'defense',
    requiresRemoval: true,
    priority: 2,
  },
  removal_recall_history: {
    displayName: 'Defense Recall',
    description: 'Catching all actual malicious clients',
    category: 'defense',
    requiresRemoval: true,
    priority: 3,
  },
  removal_f1_history: {
    displayName: 'Defense F1 Score',
    description: 'Balanced measure of precision and recall',
    category: 'defense',
    requiresRemoval: true,
    priority: 4,
  },
  total_fp_and_fn_history: {
    displayName: 'Detection Errors',
    description: 'Total false positives + false negatives per round',
    category: 'defense',
    requiresRemoval: true,
    priority: 5,
  },

  // === ADVANCED (Collapsed by default) ===
  removal_criterion_history_0: {
    displayName: 'Client Removal Scores',
    description: 'Per-client scores used for removal decisions',
    category: 'advanced',
    requiresRemoval: true,
    priority: 1,
  },
  absolute_distance_history_0: {
    displayName: 'Model Distances',
    description: 'Distance from each client model to the cluster center',
    category: 'advanced',
    requiresRemoval: true,
    priority: 2,
  },
  score_calculation_time_nanos_history: {
    displayName: 'Score Calculation Time',
    description: 'Performance metric: time to compute removal scores',
    category: 'advanced',
    priority: 3,
  },
};

// Category display info
export const CATEGORY_INFO = {
  training: {
    title: 'Training Progress',
    icon: '📊',
    description: 'Core metrics showing model learning over time',
  },
  defense: {
    title: 'Defense Effectiveness',
    icon: '🛡️',
    description: 'How well the aggregation strategy detects malicious clients',
  },
  advanced: {
    title: 'Advanced Metrics',
    icon: '🔧',
    description: 'Technical and performance metrics for detailed analysis',
  },
};

/**
 * Get display info for a plot file
 * @param {string} filename - The plot filename (e.g., "accuracy_history_0.pdf")
 * @returns {object|null} - Plot metadata or null if unknown
 */
export function getPlotDisplayInfo(filename) {
  // Remove .pdf extension and any path prefix
  const baseName = filename.replace('.pdf', '').split('/').pop();
  return PLOT_METADATA[baseName] || null;
}

/**
 * Check if a strategy supports client removal
 * @param {string} strategyKeyword - The aggregation strategy keyword
 * @returns {boolean}
 */
export function isRemovalStrategy(strategyKeyword) {
  if (!strategyKeyword) return false;
  return REMOVAL_STRATEGIES.includes(strategyKeyword.toLowerCase());
}

/**
 * Filter plots to only show relevant ones based on strategy
 * @param {string[]} plotFiles - Array of plot filenames
 * @param {string} strategyKeyword - The aggregation strategy keyword
 * @returns {string[]} - Filtered array of relevant plot files
 */
export function filterRelevantPlots(plotFiles, strategyKeyword) {
  const hasRemoval = isRemovalStrategy(strategyKeyword);

  return plotFiles.filter(filename => {
    const meta = getPlotDisplayInfo(filename);
    if (!meta) return true; // Keep unknown plots

    // Filter out removal-only plots for non-removal strategies
    if (meta.requiresRemoval && !hasRemoval) {
      return false;
    }

    return true;
  });
}

/**
 * Group plots by category
 * @param {string[]} plotFiles - Array of plot filenames
 * @param {string} strategyKeyword - The aggregation strategy keyword
 * @returns {object} - Object with category keys and arrays of plot info
 */
export function groupPlotsByCategory(plotFiles, strategyKeyword) {
  const filtered = filterRelevantPlots(plotFiles, strategyKeyword);

  const groups = {
    training: [],
    defense: [],
    advanced: [],
    other: [],
  };

  filtered.forEach(filename => {
    const meta = getPlotDisplayInfo(filename);
    if (meta) {
      groups[meta.category].push({
        filename,
        ...meta,
      });
    } else {
      // Unknown plots go to "other"
      groups.other.push({
        filename,
        displayName: filename.replace('.pdf', '').replace(/_/g, ' '),
        description: null,
        category: 'other',
        priority: 999,
      });
    }
  });

  // Sort each group by priority
  Object.keys(groups).forEach(category => {
    groups[category].sort((a, b) => a.priority - b.priority);
  });

  return groups;
}
