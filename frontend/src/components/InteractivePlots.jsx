import { useState, useEffect } from 'react';
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
} from 'recharts';
import { Form, Button } from 'react-bootstrap';
import { useTheme } from '../contexts/ThemeContext';
import RoundMetricsPlot from './RoundMetricsPlot';
import { getAllPlotData } from '@api/endpoints/simulations';
import { CHART_COLORS, CHART_UI_COLORS, MALICIOUS_COLORS } from '@constants/ui';
import { useResponsiveChartHeight } from '@hooks/useResponsiveChartHeight';

const METRIC_INFO = {
  removal_criterion_history: {
    label: 'Client Removal Scores',
    description: 'Per-client scores used for removal decisions',
  },
  absolute_distance_history: {
    label: 'Model Distances',
    description: 'Distance from each client model to the cluster center',
  },
  loss_history: {
    label: 'Training Loss',
    description: 'Per-client loss values showing learning progress',
  },
  accuracy_history: {
    label: 'Model Accuracy',
    description: 'Per-client accuracy over training rounds',
  },
  trust_score_history: {
    label: 'Trust Scores',
    description: 'Client trustworthiness score computed by defense strategy',
  },
  participation_history: {
    label: 'Participation',
    description: 'Whether client participated in each round',
  },
  aggregation_participation_history: {
    label: 'Aggregation Status',
    description: "Whether client's update was included in aggregation",
  },
};

const METRIC_LABELS = Object.fromEntries(
  Object.entries(METRIC_INFO).map(([key, { label }]) => [key, label])
);

const getAvailableMetrics = perClientMetrics => {
  if (!perClientMetrics || perClientMetrics.length === 0) return [];
  const allMetrics = Object.keys(perClientMetrics[0].metrics);
  return allMetrics.filter(metricName =>
    perClientMetrics.some(client =>
      client.metrics[metricName]?.some(value => value !== null && value !== undefined)
    )
  );
};

export default function InteractivePlots({ simulation }) {
  const { theme } = useTheme();
  const [plotData, setPlotData] = useState(null);
  const [selectedMetric, setSelectedMetric] = useState('');
  const [visibleClients, setVisibleClients] = useState({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (simulation.status !== 'completed') {
      setLoading(false);
      return;
    }

    const fetchPlotData = async () => {
      try {
        const response = await getAllPlotData(simulation.id);
        const apiData = response.data;
        // Handle multi-strategy format: extract first strategy's data for single-strategy sims
        const data = apiData.strategies ? apiData.strategies[0].data : apiData;
        setPlotData(data);

        if (data.per_client_metrics.length > 0) {
          const metrics = Object.keys(data.per_client_metrics[0].metrics);
          if (metrics.length > 0) {
            setSelectedMetric(metrics[0]);
          }
        }

        const clientsVisibility = {};
        data.per_client_metrics.forEach(client => {
          clientsVisibility[`client_${client.client_id}`] = true;
        });
        if (data.removal_threshold_history) {
          clientsVisibility.threshold = true;
        }
        setVisibleClients(clientsVisibility);

        setLoading(false);
      } catch {
        setLoading(false);
      }
    };

    fetchPlotData();
  }, [simulation.id, simulation.status]);

  useEffect(() => {
    if (!plotData) return;

    const metrics = getAvailableMetrics(plotData.per_client_metrics);

    if (metrics.length > 0 && (!selectedMetric || !metrics.includes(selectedMetric))) {
      setSelectedMetric(metrics[0]);
    }
  }, [plotData, selectedMetric]);

  const chartHeight = useResponsiveChartHeight();

  if (loading) return <div className="text-center p-4">Loading interactive plots...</div>;
  if (!plotData) {
    if (simulation.status === 'running') {
      return (
        <div className="text-center p-4">
          ⏳ Plots will be available when the simulation completes...
        </div>
      );
    }
    return <div className="text-center p-4">No plot data available</div>;
  }

  const metrics = getAvailableMetrics(plotData.per_client_metrics);

  if (metrics.length === 0) {
    // Show round-level metrics instead
    return <RoundMetricsPlot plotData={plotData} />;
  }

  const chartData = plotData.rounds.map((round, idx) => {
    const point = { round, name: `Round ${round}` }; // Add 'name' for Brush aria-label

    plotData.per_client_metrics.forEach(client => {
      const metricValues = client.metrics[selectedMetric];
      if (metricValues && metricValues[idx] !== undefined) {
        point[`client_${client.client_id}`] = metricValues[idx];
      }
    });

    if (plotData.removal_threshold_history && selectedMetric === 'removal_criterion_history') {
      point.threshold = plotData.removal_threshold_history[idx];
    }

    return point;
  });

  const toggleClient = clientKey => {
    setVisibleClients(prev => ({
      ...prev,
      [clientKey]: !prev[clientKey],
    }));
  };

  const chartColors = CHART_UI_COLORS[theme] || CHART_UI_COLORS.light;
  const COLORS = CHART_COLORS[theme] || CHART_COLORS.light;
  const MALICIOUS_COLOR = MALICIOUS_COLORS[theme] || MALICIOUS_COLORS.light;

  return (
    <div className="mb-4">
      <h5 className="mb-3">Interactive Plots</h5>
      <div>
        <Form.Group className="mb-3" style={{ maxWidth: '60%', margin: '0 auto' }}>
          <Form.Label>Select Metric:</Form.Label>
          <Form.Select value={selectedMetric} onChange={e => setSelectedMetric(e.target.value)}>
            {metrics.map(metric => (
              <option key={metric} value={metric}>
                {METRIC_LABELS[metric] || metric}
              </option>
            ))}
          </Form.Select>
          {selectedMetric && METRIC_INFO[selectedMetric]?.description && (
            <Form.Text className="text-muted">{METRIC_INFO[selectedMetric].description}</Form.Text>
          )}
        </Form.Group>

        <div className="mb-3 text-center">
          <small className="text-muted d-block mb-2">Toggle clients:</small>
          <div className="d-flex flex-wrap gap-2 justify-content-center">
            {plotData.per_client_metrics.map((client, idx) => {
              const clientKey = `client_${client.client_id}`;
              const color = client.is_malicious ? MALICIOUS_COLOR : COLORS[idx % COLORS.length];
              return (
                <Button
                  key={clientKey}
                  size="sm"
                  variant={visibleClients[clientKey] ? 'primary' : 'outline-secondary'}
                  onClick={() => toggleClient(clientKey)}
                  className="py-2 px-3"
                  style={{
                    backgroundColor: visibleClients[clientKey] ? color : 'transparent',
                    borderColor: color,
                    color: visibleClients[clientKey] ? 'white' : color,
                  }}
                >
                  Client {client.client_id}
                  {client.is_malicious ? ' (M)' : ''}
                </Button>
              );
            })}
            {plotData.removal_threshold_history &&
              selectedMetric === 'removal_criterion_history' && (
                <Button
                  size="sm"
                  variant={visibleClients.threshold ? 'danger' : 'outline-danger'}
                  onClick={() => toggleClient('threshold')}
                  className="py-2 px-3"
                >
                  Threshold
                </Button>
              )}
          </div>
        </div>

        <div style={{ width: '100%', minWidth: 300, height: chartHeight }}>
          <ResponsiveContainer
            width="100%"
            height="100%"
            minWidth={300}
            minHeight={300}
            debounce={1}
          >
            <LineChart data={chartData} margin={{ top: 10, right: 30, left: 50, bottom: 80 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} />
              <XAxis
                dataKey="round"
                stroke={chartColors.axis}
                tick={{ fill: chartColors.text, fontSize: chartHeight < 400 ? 10 : 12 }}
                label={{
                  value: 'Round #',
                  position: 'insideBottom',
                  offset: -10,
                  fill: chartColors.text,
                  fontSize: chartHeight < 400 ? 10 : 12,
                }}
                height={60}
              />
              <YAxis
                stroke={chartColors.axis}
                tick={{ fill: chartColors.text, fontSize: chartHeight < 400 ? 10 : 12 }}
                label={{
                  value: METRIC_LABELS[selectedMetric] || selectedMetric,
                  angle: -90,
                  position: 'insideLeft',
                  fill: chartColors.text,
                  fontSize: chartHeight < 400 ? 10 : 12,
                }}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'var(--bs-body-bg)',
                  border: `1px solid ${chartColors.grid}`,
                  color: 'var(--bs-body-color)',
                }}
              />
              <Legend wrapperStyle={{ color: chartColors.text }} />
              <Brush
                dataKey="round"
                height={30}
                stroke={chartColors.brush}
                fill={chartColors.brushFill}
                y={chartHeight - 70}
              />

              {plotData.per_client_metrics.map((client, idx) => {
                const clientKey = `client_${client.client_id}`;
                const color = client.is_malicious ? MALICIOUS_COLOR : COLORS[idx % COLORS.length];
                return (
                  visibleClients[clientKey] && (
                    <Line
                      key={clientKey}
                      type="monotone"
                      dataKey={clientKey}
                      stroke={color}
                      strokeWidth={2}
                      strokeDasharray={client.is_malicious ? '5 5' : undefined}
                      dot={{ r: 3 }}
                      name={`Client ${client.client_id}${client.is_malicious ? ' (Malicious)' : ''}`}
                    />
                  )
                );
              })}

              {plotData.removal_threshold_history &&
                selectedMetric === 'removal_criterion_history' &&
                visibleClients.threshold && (
                  <Line
                    type="monotone"
                    dataKey="threshold"
                    stroke={MALICIOUS_COLOR}
                    strokeWidth={2}
                    strokeDasharray="5 5"
                    dot={false}
                    name="Removal Threshold"
                  />
                )}
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="mt-3 text-muted">
          <small>
            <span aria-hidden="true">📊</span> Zoom: Drag on brush below chart |{' '}
            <span aria-hidden="true">👆</span> Toggle: Tap client buttons to show/hide lines |{' '}
            <span aria-hidden="true">ℹ️</span> Tap chart: View exact values
          </small>
        </div>
      </div>
    </div>
  );
}

InteractivePlots.propTypes = {
  simulation: PropTypes.shape({
    id: PropTypes.string.isRequired,
    status: PropTypes.string.isRequired,
  }).isRequired,
};
