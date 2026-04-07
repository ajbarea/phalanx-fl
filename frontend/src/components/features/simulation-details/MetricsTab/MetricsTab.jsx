import PropTypes from 'prop-types';
import { Alert, Spinner } from 'react-bootstrap';
import { RoundMetricsTable } from './RoundMetricsTable';
import { ExecutionStats } from './ExecutionStats';
import { RawDataAccordion } from './RawDataAccordion';

export function MetricsTab({ csvData, csvFiles, config, simulationId, status }) {
  if (csvFiles.length === 0) {
    // Distinguish between running, failed, and completed-without-metrics
    if (status === 'running' || status === 'pending' || status === 'loading') {
      return (
        <div className="text-center p-4 mt-3">
          <Spinner animation="border" role="status" className="mb-2">
            <span className="visually-hidden">Simulation in progress...</span>
          </Spinner>
          <p className="text-muted">Metrics will appear as the simulation progresses...</p>
        </div>
      );
    }

    if (status === 'failed' || status === 'stopped') {
      return (
        <Alert variant="warning" className="mt-3">
          Simulation {status}. No metrics were recorded.
        </Alert>
      );
    }

    return (
      <Alert variant="info" className="mt-3">
        No metrics available for this simulation.
      </Alert>
    );
  }

  const cfg = config.shared_settings || config;

  return (
    <div className="mt-3">
      {csvData['csv/round_metrics_0.csv'] && (
        <RoundMetricsTable data={csvData['csv/round_metrics_0.csv']} config={cfg} />
      )}

      {(csvData['csv/exec_stats_0.csv'] || csvData['csv/round_metrics_0.csv']) && (
        <ExecutionStats
          data={csvData['csv/exec_stats_0.csv']}
          roundMetrics={csvData['csv/round_metrics_0.csv']}
          config={cfg}
        />
      )}

      <RawDataAccordion csvFiles={csvFiles} csvData={csvData} simulationId={simulationId} />
    </div>
  );
}

MetricsTab.propTypes = {
  csvData: PropTypes.objectOf(PropTypes.arrayOf(PropTypes.object)).isRequired,
  csvFiles: PropTypes.arrayOf(PropTypes.string).isRequired,
  config: PropTypes.shape({
    shared_settings: PropTypes.object,
    num_of_rounds: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
    num_of_clients: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
  }).isRequired,
  simulationId: PropTypes.string.isRequired,
  status: PropTypes.oneOf(['loading', 'pending', 'running', 'completed', 'failed', 'stopped']),
};

MetricsTab.defaultProps = {
  status: 'loading',
};
