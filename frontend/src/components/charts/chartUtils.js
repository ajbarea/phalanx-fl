/**
 * Shared chart utilities for research-quality FL visualizations.
 *
 * Provides consistent, publication-ready chart components:
 * - Attack phase extraction and shading
 * - Defense threshold reference lines
 * - Rich tooltips with attack context
 * - Synchronized chart helpers
 */

import { MALICIOUS_COLORS, CHART_UI_COLORS } from '@constants/ui';

/**
 * Attack phase colors with semi-transparent backgrounds.
 * Uses distinct colors for different attack types.
 */
export const ATTACK_PHASE_COLORS = {
  light: {
    label_flipping: 'rgba(220, 53, 69, 0.12)', // Red tint
    gaussian_noise: 'rgba(255, 152, 0, 0.12)', // Orange tint
    model_poisoning: 'rgba(156, 39, 176, 0.12)', // Purple tint
    backdoor: 'rgba(63, 81, 181, 0.12)', // Indigo tint
    free_rider: 'rgba(0, 150, 136, 0.12)', // Teal tint
    default: 'rgba(211, 47, 47, 0.10)', // Default red tint
  },
  dark: {
    label_flipping: 'rgba(244, 67, 54, 0.18)',
    gaussian_noise: 'rgba(255, 167, 38, 0.18)',
    model_poisoning: 'rgba(186, 104, 200, 0.18)',
    backdoor: 'rgba(121, 134, 203, 0.18)',
    free_rider: 'rgba(77, 182, 172, 0.18)',
    default: 'rgba(255, 107, 107, 0.15)',
  },
};

/**
 * Defense activation colors for reference lines.
 */
export const DEFENSE_COLORS = {
  light: {
    threshold: '#2196F3',
    removalStart: '#4CAF50',
    warning: '#FF9800',
  },
  dark: {
    threshold: '#64B5F6',
    removalStart: '#81C784',
    warning: '#FFB74D',
  },
};

/**
 * Extract attack phases from simulation config.
 * Handles both attack_schedule array and simple attack_type.
 *
 * @param {Object} config - Simulation configuration
 * @param {number} totalRounds - Total number of rounds
 * @returns {Array<{startRound: number, endRound: number, attackType: string, label: string}>}
 */
export function extractAttackPhases(config, totalRounds) {
  if (!config) return [];

  const phases = [];

  // Handle attack_schedule array (multi-phase attacks)
  if (
    config.attack_schedule &&
    Array.isArray(config.attack_schedule) &&
    config.attack_schedule.length > 0
  ) {
    config.attack_schedule.forEach((phase, idx) => {
      const startRound = phase.start_round || phase.startRound || 1;
      const endRound = phase.end_round || phase.endRound || totalRounds;
      const attackType = phase.attack_type || phase.attackType || 'unknown';

      phases.push({
        startRound,
        endRound,
        attackType,
        label: formatAttackLabel(attackType, idx + 1),
        intensity: phase.attack_ratio || phase.intensity || 1.0,
      });
    });
  }
  // Handle simple attack_type (single attack throughout)
  else if (config.attack_type && config.num_of_malicious_clients > 0) {
    phases.push({
      startRound: 1,
      endRound: totalRounds,
      attackType: config.attack_type,
      label: formatAttackLabel(config.attack_type),
      intensity: config.attack_ratio || 1.0,
    });
  }

  return phases;
}

/**
 * Format attack type into human-readable label.
 *
 * @param {string} attackType - Raw attack type string
 * @param {number} [phaseNum] - Optional phase number for multi-phase attacks
 * @returns {string} Formatted label
 */
export function formatAttackLabel(attackType, phaseNum = null) {
  const labels = {
    label_flipping: 'Label Flip',
    gaussian_noise: 'Noise',
    model_poisoning: 'Model Poison',
    backdoor: 'Backdoor',
    free_rider: 'Free Rider',
    token_replacement: 'Token Replace',
  };

  const base =
    labels[attackType] || attackType.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  return phaseNum ? `${base} (Phase ${phaseNum})` : base;
}

/**
 * Get attack phase color for a given attack type and theme.
 *
 * @param {string} attackType - Attack type string
 * @param {string} theme - 'light' or 'dark'
 * @returns {string} CSS color string
 */
export function getAttackPhaseColor(attackType, theme = 'light') {
  const colors = ATTACK_PHASE_COLORS[theme] || ATTACK_PHASE_COLORS.light;
  return colors[attackType] || colors.default;
}

/**
 * Generate ReferenceArea props for attack phase shading.
 * Use with Recharts ReferenceArea component.
 *
 * @param {Array} phases - Attack phases from extractAttackPhases
 * @param {string} theme - 'light' or 'dark'
 * @returns {Array<Object>} Props for ReferenceArea components
 */
export function generateAttackAreaProps(phases, theme = 'light') {
  return phases.map((phase, idx) => ({
    key: `attack-phase-${idx}`,
    x1: phase.startRound,
    x2: phase.endRound,
    fill: getAttackPhaseColor(phase.attackType, theme),
    fillOpacity: 1,
    stroke: 'none',
    label: {
      value: phase.label,
      position: 'insideTopRight',
      fill: theme === 'dark' ? '#999' : '#666',
      fontSize: 10,
    },
  }));
}

/**
 * Generate ReferenceLine props for defense milestones.
 *
 * @param {Object} config - Simulation configuration
 * @param {string} theme - 'light' or 'dark'
 * @returns {Array<Object>} Props for ReferenceLine components
 */
export function generateDefenseLineProps(config, theme = 'light') {
  const lines = [];
  const colors = DEFENSE_COLORS[theme] || DEFENSE_COLORS.light;

  if (config.remove_clients === 'true' && config.begin_removing_from_round) {
    lines.push({
      key: 'defense-start',
      x: config.begin_removing_from_round,
      stroke: colors.removalStart,
      strokeDasharray: '5 5',
      strokeWidth: 2,
      label: {
        value: 'Defense Active',
        position: 'insideTopLeft',
        fill: colors.removalStart,
        fontSize: 10,
      },
    });
  }

  return lines;
}

/**
 * Check if a round is within an attack phase.
 *
 * @param {number} round - Round number
 * @param {Array} phases - Attack phases
 * @returns {Object|null} Active phase or null
 */
export function getActiveAttackPhase(round, phases) {
  return phases.find(phase => round >= phase.startRound && round <= phase.endRound) || null;
}

/**
 * Build tooltip content with attack context.
 *
 * @param {Object} payload - Recharts tooltip payload
 * @param {Array} phases - Attack phases
 * @param {Object} config - Simulation config
 * @returns {Object} Enhanced tooltip data
 */
export function buildTooltipContext(payload, phases, config) {
  if (!payload || !payload.length) return null;

  const round = payload[0]?.payload?.round;
  const activePhase = getActiveAttackPhase(round, phases);

  return {
    round,
    values: payload.map(p => ({
      name: p.name,
      value: p.value,
      color: p.color || p.stroke,
      dataKey: p.dataKey,
    })),
    attackContext: activePhase
      ? {
          isUnderAttack: true,
          attackType: activePhase.attackType,
          label: activePhase.label,
          intensity: activePhase.intensity,
        }
      : { isUnderAttack: false },
    defenseContext: {
      isActive:
        config?.remove_clients === 'true' && round >= (config?.begin_removing_from_round || 1),
      strategy: config?.aggregation_strategy_keyword || 'fedavg',
    },
  };
}

/**
 * Format metric value for display.
 *
 * @param {number} value - Raw metric value
 * @param {string} metricType - Type of metric for formatting
 * @returns {string} Formatted string
 */
export function formatMetricValue(value, metricType) {
  if (value === null || value === undefined) return 'N/A';

  if (
    metricType?.includes('accuracy') ||
    metricType?.includes('precision') ||
    metricType?.includes('recall')
  ) {
    return `${(value * 100).toFixed(1)}%`;
  }
  if (metricType?.includes('loss')) {
    return value.toFixed(4);
  }
  if (metricType?.includes('time')) {
    return `${(value / 1e6).toFixed(2)}ms`;
  }
  return typeof value === 'number' ? value.toFixed(4) : String(value);
}

/**
 * Get chart UI colors for current theme.
 *
 * @param {string} theme - 'light' or 'dark'
 * @returns {Object} Chart UI color palette
 */
export function getChartColors(theme) {
  return {
    ui: CHART_UI_COLORS[theme] || CHART_UI_COLORS.light,
    malicious: MALICIOUS_COLORS[theme] || MALICIOUS_COLORS.light,
    attack: ATTACK_PHASE_COLORS[theme] || ATTACK_PHASE_COLORS.light,
    defense: DEFENSE_COLORS[theme] || DEFENSE_COLORS.light,
  };
}

/**
 * Sync ID generator for linked charts.
 * Charts with the same syncId will synchronize hover states.
 *
 * @param {string} simulationId - Simulation identifier
 * @returns {string} Sync ID for Recharts
 */
export function generateSyncId(simulationId) {
  return `fl-metrics-${simulationId}`;
}
