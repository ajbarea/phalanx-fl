/**
 * Rich custom tooltip for FL charts with attack context.
 *
 * Shows:
 * - Round number and metric values
 * - Attack phase indicator (if under attack)
 * - Defense status indicator
 */

import PropTypes from 'prop-types';
import { getActiveAttackPhase, formatMetricValue, formatAttackLabel } from './chartUtils';

export default function AttackPhaseTooltip({
  active,
  payload,
  label,
  attackPhases = [],
  config = {},
  metricType = '',
  theme = 'light',
}) {
  if (!active || !payload || payload.length === 0) {
    return null;
  }

  const round = payload[0]?.payload?.round ?? label;
  const activePhase = getActiveAttackPhase(round, attackPhases);
  const defenseActive =
    config?.remove_clients === 'true' && round >= (config?.begin_removing_from_round || 999);

  const isDark = theme === 'dark';
  const bgColor = isDark ? '#2b2b2b' : '#ffffff';
  const borderColor = isDark ? '#444' : '#e0e0e0';
  const textColor = isDark ? '#e0e0e0' : '#333333';
  const mutedColor = isDark ? '#999' : '#666';

  return (
    <div
      style={{
        backgroundColor: bgColor,
        border: `1px solid ${borderColor}`,
        borderRadius: '6px',
        padding: '10px 14px',
        boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
        minWidth: '180px',
        maxWidth: '280px',
      }}
    >
      <div
        style={{
          fontWeight: 600,
          fontSize: '13px',
          color: textColor,
          marginBottom: '8px',
          paddingBottom: '6px',
          borderBottom: `1px solid ${borderColor}`,
        }}
      >
        Round {round}
      </div>

      {activePhase && (
        <div
          style={{
            backgroundColor: isDark ? 'rgba(244, 67, 54, 0.2)' : 'rgba(220, 53, 69, 0.1)',
            border: `1px solid ${isDark ? '#f44336' : '#dc3545'}`,
            borderRadius: '4px',
            padding: '4px 8px',
            marginBottom: '8px',
            fontSize: '11px',
            color: isDark ? '#ff8a80' : '#c62828',
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
          }}
        >
          <span style={{ fontSize: '12px' }}>&#9888;</span>
          <span>
            <strong>Attack:</strong> {formatAttackLabel(activePhase.attackType)}
          </span>
        </div>
      )}

      {defenseActive && (
        <div
          style={{
            backgroundColor: isDark ? 'rgba(76, 175, 80, 0.2)' : 'rgba(76, 175, 80, 0.1)',
            border: `1px solid ${isDark ? '#81c784' : '#4caf50'}`,
            borderRadius: '4px',
            padding: '4px 8px',
            marginBottom: '8px',
            fontSize: '11px',
            color: isDark ? '#a5d6a7' : '#2e7d32',
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
          }}
        >
          <span style={{ fontSize: '12px' }}>&#9745;</span>
          <span>
            <strong>Defense:</strong>{' '}
            {config?.aggregation_strategy_keyword?.toUpperCase() || 'Active'}
          </span>
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
        {payload.map((entry, index) => (
          <div
            key={index}
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              fontSize: '12px',
            }}
          >
            <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span
                style={{
                  width: '10px',
                  height: '10px',
                  backgroundColor: entry.color || entry.stroke,
                  borderRadius: '2px',
                  display: 'inline-block',
                }}
              />
              <span style={{ color: mutedColor }}>{entry.name || entry.dataKey}</span>
            </span>
            <span style={{ fontWeight: 500, color: textColor, fontFamily: 'monospace' }}>
              {formatMetricValue(entry.value, metricType)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

AttackPhaseTooltip.propTypes = {
  active: PropTypes.bool,
  payload: PropTypes.array,
  label: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  attackPhases: PropTypes.arrayOf(
    PropTypes.shape({
      startRound: PropTypes.number,
      endRound: PropTypes.number,
      attackType: PropTypes.string,
      label: PropTypes.string,
    })
  ),
  config: PropTypes.object,
  metricType: PropTypes.string,
  theme: PropTypes.string,
};
