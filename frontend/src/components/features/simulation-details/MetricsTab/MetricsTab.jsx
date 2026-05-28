import PropTypes from 'prop-types';
import { SimulationResultState } from '@components/common/Empty/SimulationResultState';
import { RoundMetricsTable } from './RoundMetricsTable';
import { ExecutionStats } from './ExecutionStats';
import { RawDataAccordion } from './RawDataAccordion';

export function MetricsTab({ csvData, csvFiles, config, simulationId, status }) {
  if (csvFiles.length === 0) {
    return <SimulationResultState noun="Metrics" status={status} />;
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
