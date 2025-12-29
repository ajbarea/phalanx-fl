/**
 * Attack phase overlay component for Recharts.
 *
 * Renders ReferenceArea components to shade attack phases
 * and ReferenceLine for defense milestones.
 */

import { ReferenceArea, ReferenceLine } from 'recharts';
import PropTypes from 'prop-types';
import { extractAttackPhases, getAttackPhaseColor, DEFENSE_COLORS } from './chartUtils';

/**
 * Renders attack phase shading and defense milestone lines.
 *
 * Usage:
 * ```jsx
 * <LineChart>
 *   <AttackPhaseOverlay config={config} totalRounds={20} theme="light" />
 *   {/* other chart elements *\/}
 * </LineChart>
 * ```
 *
 * @param {Object} props - Component props
 * @param {Object} props.config - Simulation configuration
 * @param {number} props.totalRounds - Total number of rounds
 * @param {string} props.theme - 'light' or 'dark'
 * @param {boolean} props.showLabels - Whether to show phase labels
 * @param {boolean} props.showDefenseLines - Whether to show defense milestone lines
 */
export default function AttackPhaseOverlay({
  config,
  totalRounds,
  theme = 'light',
  showLabels = true,
  showDefenseLines = true,
}) {
  if (!config) return null;

  const phases = extractAttackPhases(config, totalRounds);
  const colors = DEFENSE_COLORS[theme] || DEFENSE_COLORS.light;
  const labelColor = theme === 'dark' ? '#999' : '#666';

  const elements = [];

  phases.forEach((phase, idx) => {
    elements.push(
      <ReferenceArea
        key={`attack-phase-${idx}`}
        x1={phase.startRound}
        x2={phase.endRound}
        fill={getAttackPhaseColor(phase.attackType, theme)}
        fillOpacity={1}
        stroke="none"
        label={
          showLabels
            ? {
                value: phase.label,
                position: 'insideTopRight',
                fill: labelColor,
                fontSize: 10,
                fontWeight: 500,
              }
            : undefined
        }
      />
    );
  });

  if (showDefenseLines && config.remove_clients === 'true' && config.begin_removing_from_round) {
    const defenseRound = Number(config.begin_removing_from_round);
    if (defenseRound > 0 && defenseRound <= totalRounds) {
      elements.push(
        <ReferenceLine
          key="defense-start"
          x={defenseRound}
          stroke={colors.removalStart}
          strokeDasharray="5 5"
          strokeWidth={1.5}
          label={{
            value: 'Defense',
            position: 'insideTopLeft',
            fill: colors.removalStart,
            fontSize: 9,
            fontWeight: 500,
          }}
        />
      );
    }
  }

  return <>{elements}</>;
}

AttackPhaseOverlay.propTypes = {
  config: PropTypes.object,
  totalRounds: PropTypes.number.isRequired,
  theme: PropTypes.string,
  showLabels: PropTypes.bool,
  showDefenseLines: PropTypes.bool,
};

/**
 * Pre-computed attack phases component for when phases are already extracted.
 * Use this when you need to share phases between chart and tooltip.
 */
export function AttackPhaseAreas({ phases, theme = 'light', showLabels = true }) {
  const labelColor = theme === 'dark' ? '#999' : '#666';

  return (
    <>
      {phases.map((phase, idx) => (
        <ReferenceArea
          key={`attack-phase-${idx}`}
          x1={phase.startRound}
          x2={phase.endRound}
          fill={getAttackPhaseColor(phase.attackType, theme)}
          fillOpacity={1}
          stroke="none"
          label={
            showLabels
              ? {
                  value: phase.label,
                  position: 'insideTopRight',
                  fill: labelColor,
                  fontSize: 10,
                  fontWeight: 500,
                }
              : undefined
          }
        />
      ))}
    </>
  );
}

AttackPhaseAreas.propTypes = {
  phases: PropTypes.arrayOf(
    PropTypes.shape({
      startRound: PropTypes.number.isRequired,
      endRound: PropTypes.number.isRequired,
      attackType: PropTypes.string.isRequired,
      label: PropTypes.string,
    })
  ).isRequired,
  theme: PropTypes.string,
  showLabels: PropTypes.bool,
};

/**
 * Defense milestone lines component.
 */
export function DefenseLines({ config, totalRounds, theme = 'light' }) {
  const colors = DEFENSE_COLORS[theme] || DEFENSE_COLORS.light;

  if (config?.remove_clients !== 'true' || !config?.begin_removing_from_round) {
    return null;
  }

  const defenseRound = Number(config.begin_removing_from_round);
  if (defenseRound <= 0 || defenseRound > totalRounds) {
    return null;
  }

  return (
    <ReferenceLine
      x={defenseRound}
      stroke={colors.removalStart}
      strokeDasharray="5 5"
      strokeWidth={1.5}
      label={{
        value: 'Defense Active',
        position: 'insideTopLeft',
        fill: colors.removalStart,
        fontSize: 9,
        fontWeight: 500,
      }}
    />
  );
}

DefenseLines.propTypes = {
  config: PropTypes.object,
  totalRounds: PropTypes.number.isRequired,
  theme: PropTypes.string,
};
