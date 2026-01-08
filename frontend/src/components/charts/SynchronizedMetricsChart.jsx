/**
 * Synchronized multi-panel chart component for comparing metrics.
 *
 * Uses Recharts syncId to link multiple charts together,
 * allowing coordinated hovering and zooming across panels.
 */

import { useState, useMemo, useCallback } from 'react';
import PropTypes from 'prop-types';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Brush,
  ReferenceArea,
  ReferenceLine,
} from 'recharts';
import { Button, Form } from 'react-bootstrap';
import { useTheme } from '../../contexts/ThemeContext';
import { CHART_COLORS, CHART_UI_COLORS, MALICIOUS_COLORS } from '@constants/ui';
import { extractAttackPhases, getAttackPhaseColor, getChartColors } from './chartUtils';
import AttackPhaseTooltip from './AttackPhaseTooltip';

const METRIC_INFO = {
  removal_criterion_history: {
    label: 'Removal Scores',
    shortLabel: 'Removal',
    yAxisLabel: 'Score',
  },
  absolute_distance_history: {
    label: 'Model Distances',
    shortLabel: 'Distance',
    yAxisLabel: 'Distance',
  },
  loss_history: {
    label: 'Training Loss',
    shortLabel: 'Loss',
    yAxisLabel: 'Loss',
  },
  accuracy_history: {
    label: 'Accuracy',
    shortLabel: 'Accuracy',
    yAxisLabel: 'Accuracy',
  },
  trust_score_history: {
    label: 'Trust Scores',
    shortLabel: 'Trust',
    yAxisLabel: 'Score',
  },
};

/**
 * Single synchronized chart panel.
 */
function ChartPanel({
  data,
  metricKey,
  metricLabel,
  yAxisLabel,
  clients,
  visibleClients,
  attackPhases,
  defenseStartRound,
  config,
  theme,
  chartColors,
  clientColors,
  maliciousColor,
  syncId,
  height,
}) {
  const defenseColors = getChartColors(theme).defense;
  // Reserve space for title above chart
  const titleHeight = 28;
  const chartHeight = height - titleHeight;

  return (
    <div style={{ width: '100%', height }}>
      <div
        style={{
          textAlign: 'center',
          fontSize: 13,
          fontWeight: 600,
          color: chartColors.text,
          height: titleHeight,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          borderBottom: `1px solid ${chartColors.grid}`,
          marginBottom: 4,
        }}
      >
        {metricLabel}
      </div>
      <ResponsiveContainer width="100%" height={chartHeight}>
        <LineChart data={data} margin={{ top: 5, right: 20, left: 10, bottom: 5 }} syncId={syncId}>
          {attackPhases.map((phase, idx) => (
            <ReferenceArea
              key={`attack-phase-${idx}`}
              x1={phase.startRound}
              x2={phase.endRound}
              fill={getAttackPhaseColor(phase.attackType, theme)}
              fillOpacity={1}
              stroke="none"
            />
          ))}

          {defenseStartRound && defenseStartRound > 0 && (
            <ReferenceLine
              x={defenseStartRound}
              stroke={defenseColors.removalStart}
              strokeDasharray="5 5"
              strokeWidth={1.5}
            />
          )}

          <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} />
          <XAxis
            dataKey="round"
            stroke={chartColors.axis}
            tick={{ fill: chartColors.text, fontSize: 10 }}
          />
          <YAxis
            stroke={chartColors.axis}
            tick={{ fill: chartColors.text, fontSize: 9 }}
            label={{
              value: yAxisLabel,
              angle: -90,
              position: 'insideLeft',
              fill: chartColors.text,
              fontSize: 9,
              offset: 5,
            }}
            width={45}
            tickFormatter={v => (v >= 1000 ? `${(v / 1000).toFixed(1)}k` : (v.toFixed?.(2) ?? v))}
          />
          <Tooltip
            content={
              <AttackPhaseTooltip
                attackPhases={attackPhases}
                config={config}
                metricType={metricKey}
                theme={theme}
              />
            }
          />
          <Legend
            verticalAlign="top"
            height={20}
            wrapperStyle={{ fontSize: 10, color: chartColors.text, paddingBottom: 4 }}
            iconSize={8}
          />

          {clients.map((client, idx) => {
            const clientKey = `client_${client.client_id}`;
            const color = client.is_malicious
              ? maliciousColor
              : clientColors[idx % clientColors.length];
            return (
              visibleClients[clientKey] && (
                <Line
                  key={clientKey}
                  type="monotone"
                  dataKey={clientKey}
                  stroke={color}
                  strokeWidth={1.5}
                  strokeDasharray={client.is_malicious ? '4 4' : undefined}
                  dot={false}
                  name={`C${client.client_id}${client.is_malicious ? '*' : ''}`}
                />
              )
            );
          })}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

ChartPanel.propTypes = {
  data: PropTypes.array.isRequired,
  metricKey: PropTypes.string.isRequired,
  metricLabel: PropTypes.string.isRequired,
  yAxisLabel: PropTypes.string.isRequired,
  clients: PropTypes.array.isRequired,
  visibleClients: PropTypes.object.isRequired,
  attackPhases: PropTypes.array.isRequired,
  defenseStartRound: PropTypes.number,
  config: PropTypes.object,
  theme: PropTypes.string.isRequired,
  chartColors: PropTypes.object.isRequired,
  clientColors: PropTypes.array.isRequired,
  maliciousColor: PropTypes.string.isRequired,
  syncId: PropTypes.string.isRequired,
  height: PropTypes.number.isRequired,
};

/**
 * Synchronized multi-panel chart for comparing multiple metrics.
 *
 * Features:
 * - Linked hovering across all panels (syncId)
 * - Shared brush for coordinated zooming
 * - Attack phase shading
 * - Defense milestone markers
 *
 * @param {Object} props - Component props
 * @param {Object} props.plotData - Plot data from API
 * @param {Object} props.config - Simulation configuration
 * @param {Array} props.selectedMetrics - Array of metric keys to display
 * @param {string} props.layout - 'horizontal' or 'vertical'
 */
export default function SynchronizedMetricsChart({
  plotData,
  config,
  selectedMetrics = ['accuracy_history', 'loss_history'],
  layout = 'horizontal',
}) {
  const { theme } = useTheme();
  const [visibleClients, setVisibleClients] = useState(() => {
    const clients = {};
    plotData.per_client_metrics?.forEach(client => {
      clients[`client_${client.client_id}`] = true;
    });
    return clients;
  });
  const [brushIndex, setBrushIndex] = useState(null);

  const chartColors = CHART_UI_COLORS[theme] || CHART_UI_COLORS.light;
  const clientColors = CHART_COLORS[theme] || CHART_COLORS.light;
  const maliciousColor = MALICIOUS_COLORS[theme] || MALICIOUS_COLORS.light;

  const attackPhases = useMemo(() => {
    if (!config || !plotData?.rounds) return [];
    const totalRounds = plotData.rounds.length > 0 ? Math.max(...plotData.rounds) : 0;
    return extractAttackPhases(config, totalRounds);
  }, [config, plotData?.rounds]);

  const defenseStartRound = useMemo(() => {
    if (config?.remove_clients === 'true' && config?.begin_removing_from_round) {
      return Number(config.begin_removing_from_round);
    }
    return null;
  }, [config]);

  const chartDataByMetric = useMemo(() => {
    const result = {};
    selectedMetrics.forEach(metricKey => {
      result[metricKey] = plotData.rounds.map((round, idx) => {
        const point = { round, name: `Round ${round}` };
        plotData.per_client_metrics?.forEach(client => {
          const metricValues = client.metrics[metricKey];
          if (metricValues && metricValues[idx] !== undefined) {
            point[`client_${client.client_id}`] = metricValues[idx];
          }
        });
        return point;
      });
    });
    return result;
  }, [plotData, selectedMetrics]);

  const toggleClient = useCallback(clientKey => {
    setVisibleClients(prev => ({ ...prev, [clientKey]: !prev[clientKey] }));
  }, []);

  const handleBrushChange = useCallback(newIndex => {
    setBrushIndex(newIndex);
  }, []);

  const clients = plotData.per_client_metrics || [];
  const syncId = 'synchronized-metrics';
  const panelCount = selectedMetrics.length;
  const panelHeight = layout === 'horizontal' ? 280 : 220;
  const useGrid = layout === 'horizontal' && panelCount >= 2;

  return (
    <div className="synchronized-metrics-chart">
      <div className="mb-3 text-center">
        <small className="text-muted d-block mb-2">Toggle clients:</small>
        <div className="d-flex flex-wrap gap-1 justify-content-center">
          {clients.map((client, idx) => {
            const clientKey = `client_${client.client_id}`;
            const color = client.is_malicious
              ? maliciousColor
              : clientColors[idx % clientColors.length];
            return (
              <Button
                key={clientKey}
                size="sm"
                variant={visibleClients[clientKey] ? 'primary' : 'outline-secondary'}
                onClick={() => toggleClient(clientKey)}
                className="py-1 px-2"
                style={{
                  backgroundColor: visibleClients[clientKey] ? color : 'transparent',
                  borderColor: color,
                  color: visibleClients[clientKey] ? 'white' : color,
                  fontSize: 11,
                }}
              >
                C{client.client_id}
                {client.is_malicious ? '*' : ''}
              </Button>
            );
          })}
        </div>
      </div>

      <div
        className="chart-panels"
        style={
          useGrid
            ? {
                display: 'grid',
                gridTemplateColumns: 'repeat(2, 1fr)',
                gap: '16px',
                width: '100%',
              }
            : {
                display: 'flex',
                flexDirection: 'column',
                gap: '16px',
                width: '100%',
              }
        }
      >
        {selectedMetrics.map(metricKey => {
          const info = METRIC_INFO[metricKey] || {
            label: metricKey,
            shortLabel: metricKey,
            yAxisLabel: 'Value',
          };

          // Filter data based on brush selection
          const filteredData = brushIndex
            ? chartDataByMetric[metricKey].slice(brushIndex.startIndex, brushIndex.endIndex + 1)
            : chartDataByMetric[metricKey];

          return (
            <div key={metricKey} style={{ width: '100%' }}>
              <ChartPanel
                data={filteredData}
                metricKey={metricKey}
                metricLabel={info.shortLabel}
                yAxisLabel={info.yAxisLabel}
                clients={clients}
                visibleClients={visibleClients}
                attackPhases={attackPhases}
                defenseStartRound={defenseStartRound}
                config={config}
                theme={theme}
                chartColors={chartColors}
                clientColors={clientColors}
                maliciousColor={maliciousColor}
                syncId={syncId}
                height={panelHeight}
              />
            </div>
          );
        })}
      </div>
      <div
        className="shared-brush-container mt-3 px-4"
        style={{
          borderTop: `1px solid ${chartColors.grid}`,
          paddingTop: 12,
        }}
      >
        <div className="d-flex align-items-center gap-2 mb-1">
          <small className="text-muted" style={{ fontSize: 10, fontWeight: 500 }}>
            📊 Zoom Range (affects all charts):
          </small>
        </div>
        <div style={{ width: '100%', height: 40 }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={chartDataByMetric[selectedMetrics[0]] || []}
              margin={{ top: 0, right: 20, left: 45, bottom: 0 }}
            >
              <XAxis dataKey="round" hide />
              <Brush
                dataKey="round"
                height={30}
                stroke={chartColors.brush}
                fill={chartColors.brushFill}
                startIndex={brushIndex?.startIndex}
                endIndex={brushIndex?.endIndex}
                onChange={handleBrushChange}
                tickFormatter={v => `R${v}`}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="mt-2 text-center">
        <small className="text-muted">
          Choose which Simulation Rounds to display
          {attackPhases.length > 0 && ' | Shaded regions = attack phases | Dashed line = defense'}
        </small>
      </div>
    </div>
  );
}

SynchronizedMetricsChart.propTypes = {
  plotData: PropTypes.shape({
    rounds: PropTypes.array.isRequired,
    per_client_metrics: PropTypes.array,
  }).isRequired,
  config: PropTypes.object,
  selectedMetrics: PropTypes.arrayOf(PropTypes.string),
  layout: PropTypes.oneOf(['horizontal', 'vertical']),
};

/**
 * Metric selector component for choosing which metrics to display.
 */
export function MetricSelector({ availableMetrics, selectedMetrics, onChange }) {
  const handleToggle = metricKey => {
    if (selectedMetrics.includes(metricKey)) {
      if (selectedMetrics.length > 1) {
        onChange(selectedMetrics.filter(m => m !== metricKey));
      }
    } else {
      onChange([...selectedMetrics, metricKey]);
    }
  };

  return (
    <div className="metric-selector mb-3">
      <Form.Label className="d-block mb-2">Compare metrics:</Form.Label>
      <div className="d-flex flex-wrap gap-2">
        {availableMetrics.map(metricKey => {
          const info = METRIC_INFO[metricKey] || { label: metricKey };
          const isSelected = selectedMetrics.includes(metricKey);
          return (
            <Button
              key={metricKey}
              size="sm"
              variant={isSelected ? 'primary' : 'outline-secondary'}
              onClick={() => handleToggle(metricKey)}
              className="py-1 px-2"
            >
              {info.shortLabel || info.label}
            </Button>
          );
        })}
      </div>
    </div>
  );
}

MetricSelector.propTypes = {
  availableMetrics: PropTypes.arrayOf(PropTypes.string).isRequired,
  selectedMetrics: PropTypes.arrayOf(PropTypes.string).isRequired,
  onChange: PropTypes.func.isRequired,
};
