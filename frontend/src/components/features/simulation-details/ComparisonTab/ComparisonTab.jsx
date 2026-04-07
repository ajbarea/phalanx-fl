import { useState, useEffect } from 'react';
import { Alert, Spinner, Card, Table, Badge } from 'react-bootstrap';
import PropTypes from 'prop-types';
import { getAllPlotData } from '@api/endpoints/simulations';
import { StrategyComparisonPlot } from './StrategyComparisonPlot';
import { ConfigExplainer } from '@components/features/education/ConfigExplainer';
import { getErrorMessage } from '@utils/errorMessages';
import { formatAccuracy, formatLoss, formatDetectionMetric } from '@utils/formatters';

export function ComparisonTab({ simulation, isMultiStrategy }) {
  const [allPlotData, setAllPlotData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedStrategy, setSelectedStrategy] = useState(null);

  useEffect(() => {
    if (!isMultiStrategy || simulation.status !== 'completed') {
      setLoading(false);
      return;
    }

    const fetchAllPlotData = async () => {
      try {
        const response = await getAllPlotData(simulation.id);
        setAllPlotData(response.data.strategies);
        setLoading(false);
      } catch (err) {
        setError(getErrorMessage(err));
        setLoading(false);
      }
    };

    fetchAllPlotData();
  }, [simulation.id, simulation.status, isMultiStrategy]);

  if (!isMultiStrategy) {
    return (
      <Card className="mt-3">
        <Card.Body>
          <Alert variant="info">
            Strategy comparison is only available for multi-strategy experiments.
          </Alert>
        </Card.Body>
      </Card>
    );
  }

  if (simulation.status !== 'completed') {
    return (
      <Card className="mt-3">
        <Card.Body>
          <Alert variant="info">
            ⏳ Comparison view will be available when all strategies complete...
          </Alert>
        </Card.Body>
      </Card>
    );
  }

  if (loading) {
    return (
      <div className="text-center p-4">
        <Spinner animation="border" role="status">
          <span className="visually-hidden">Loading comparison data...</span>
        </Spinner>
        <p className="mt-2">Loading comparison data...</p>
      </div>
    );
  }

  if (error) {
    return (
      <Card className="mt-3">
        <Card.Body>
          <Alert variant="danger">Failed to load comparison data: {error}</Alert>
        </Card.Body>
      </Card>
    );
  }

  if (!allPlotData || allPlotData.length === 0) {
    return (
      <Card className="mt-3">
        <Card.Body>
          <Alert variant="warning">No comparison data available yet</Alert>
        </Card.Body>
      </Card>
    );
  }

  const strategyConfigs = {};
  simulation.config.simulation_strategies.forEach((config, index) => {
    strategyConfigs[index] = {
      ...simulation.config.shared_settings,
      ...config,
    };
  });

  const performanceSummary = allPlotData.map(strategy => {
    const config = strategyConfigs[strategy.strategy_number];
    const perClientMetrics = strategy.data.per_client_metrics;

    let finalAccuracy = null;
    let finalLoss = null;
    let removalAccuracy = null;

    if (perClientMetrics && perClientMetrics.length > 0) {
      const lastRoundAccuracies = perClientMetrics
        .map(client => {
          const history = client.metrics?.accuracy_history;
          return history && history.length > 0 ? history[history.length - 1] : null;
        })
        .filter(v => v !== null);

      if (lastRoundAccuracies.length > 0) {
        finalAccuracy = lastRoundAccuracies.reduce((a, b) => a + b, 0) / lastRoundAccuracies.length;
      }

      const lastRoundLosses = perClientMetrics
        .map(client => {
          const history = client.metrics?.loss_history;
          return history && history.length > 0 ? history[history.length - 1] : null;
        })
        .filter(v => v !== null);

      if (lastRoundLosses.length > 0) {
        finalLoss = lastRoundLosses.reduce((a, b) => a + b, 0) / lastRoundLosses.length;
      }

      const hasRemovalData = perClientMetrics.some(c =>
        c.metrics?.removal_criterion_history?.some(v => v !== null)
      );
      if (hasRemovalData) {
        const maliciousClients = perClientMetrics.filter(c => c.is_malicious);
        const nonMaliciousClients = perClientMetrics.filter(c => !c.is_malicious);

        if (maliciousClients.length > 0 && nonMaliciousClients.length > 0) {
          const getLastRemovalScore = client => {
            const history = client.metrics?.removal_criterion_history?.filter(v => v !== null);
            return history && history.length > 0 ? history[history.length - 1] : null;
          };

          const maliciousScores = maliciousClients.map(getLastRemovalScore).filter(v => v !== null);
          const nonMaliciousScores = nonMaliciousClients
            .map(getLastRemovalScore)
            .filter(v => v !== null);

          if (maliciousScores.length > 0 && nonMaliciousScores.length > 0) {
            const avgMalicious =
              maliciousScores.reduce((a, b) => a + b, 0) / maliciousScores.length;
            const avgNonMalicious =
              nonMaliciousScores.reduce((a, b) => a + b, 0) / nonMaliciousScores.length;
            removalAccuracy = avgMalicious > avgNonMalicious ? 1.0 : 0.5;
          }
        }
      }
    }

    return {
      strategyNumber: strategy.strategy_number,
      aggregationStrategy: config.aggregation_strategy_keyword || 'fedavg',
      numKrumSelections: config.num_krum_selections,
      numMalicious: config.num_of_malicious_clients || 0,
      removeClients: config.remove_clients === 'true',
      finalAccuracy,
      finalLoss,
      removalAccuracy,
    };
  });

  const sortedByAccuracy = [...performanceSummary].sort(
    (a, b) => (b.finalAccuracy || 0) - (a.finalAccuracy || 0)
  );
  const bestPerformer = sortedByAccuracy[0];
  const worstPerformer = sortedByAccuracy[sortedByAccuracy.length - 1];

  return (
    <div className="mt-3">
      <h5 className="mb-3">
        <span aria-hidden="true">🔬 </span>Multi-Strategy Comparison
      </h5>
      <p className="text-muted mb-4">
        Comparing {allPlotData.length} strategy variations across different configurations and
        attack scenarios.
      </p>

      <Card className="mb-4">
        <Card.Body>
          <h6 className="mb-3">
            <span aria-hidden="true">📊 </span>Performance Summary
          </h6>
          <div className="table-responsive">
            <Table striped bordered hover size="sm">
              <thead>
                <tr>
                  <th scope="col">#</th>
                  <th scope="col">Strategy</th>
                  <th scope="col">Config</th>
                  <th scope="col">Final Accuracy</th>
                  <th scope="col">Final Loss</th>
                  <th scope="col">Defense Accuracy</th>
                </tr>
              </thead>
              <tbody>
                {sortedByAccuracy.map(summary => (
                  <tr
                    key={summary.strategyNumber}
                    onClick={() => setSelectedStrategy(summary.strategyNumber)}
                    onKeyDown={e => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        setSelectedStrategy(summary.strategyNumber);
                      }
                    }}
                    tabIndex={0}
                    role="button"
                    aria-label={`Select strategy ${summary.strategyNumber}: ${summary.aggregationStrategy}`}
                    aria-pressed={selectedStrategy === summary.strategyNumber}
                    style={{ cursor: 'pointer' }}
                    className={selectedStrategy === summary.strategyNumber ? 'table-active' : ''}
                  >
                    <td>
                      <Badge bg="secondary">{summary.strategyNumber}</Badge>
                      {summary.strategyNumber === bestPerformer.strategyNumber && (
                        <Badge bg="success" className="ms-1">
                          🏆 Best
                        </Badge>
                      )}
                    </td>
                    <td>
                      <strong>{summary.aggregationStrategy}</strong>
                      {summary.numKrumSelections && ` (k=${summary.numKrumSelections})`}
                    </td>
                    <td>
                      <small>
                        {summary.numMalicious} malicious
                        {summary.removeClients && ' • rm=true'}
                      </small>
                    </td>
                    <td>
                      <Badge
                        bg={
                          summary.finalAccuracy >= 0.9
                            ? 'success'
                            : summary.finalAccuracy >= 0.7
                              ? 'warning'
                              : 'danger'
                        }
                      >
                        {formatAccuracy(summary.finalAccuracy)}
                      </Badge>
                    </td>
                    <td>{formatLoss(summary.finalLoss)}</td>
                    <td>{formatDetectionMetric(summary.removalAccuracy)}</td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </div>
          <small className="text-muted">💡 Click a row to view detailed strategy explanation</small>
        </Card.Body>
      </Card>

      {selectedStrategy !== null && (
        <ConfigExplainer
          strategy={strategyConfigs[selectedStrategy].aggregation_strategy_keyword}
          config={strategyConfigs[selectedStrategy]}
        />
      )}

      <Card className="mb-4">
        <Card.Body>
          <h6 className="mb-3">
            <span aria-hidden="true">🎯 </span>Key Insights
          </h6>
          <div className="d-flex flex-column gap-2">
            {bestPerformer && (
              <Alert variant="success" className="mb-2">
                <strong>🏆 Best Performer:</strong> Strategy {bestPerformer.strategyNumber} (
                {bestPerformer.aggregationStrategy}
                {bestPerformer.numKrumSelections && ` k=${bestPerformer.numKrumSelections}`}) with{' '}
                {bestPerformer.numMalicious} malicious clients achieved{' '}
                {formatAccuracy(bestPerformer.finalAccuracy)} accuracy
              </Alert>
            )}

            {worstPerformer && bestPerformer !== worstPerformer && (
              <Alert variant="warning" className="mb-2">
                <strong>⚠️ Most Vulnerable:</strong> Strategy {worstPerformer.strategyNumber} (
                {worstPerformer.aggregationStrategy}) with {worstPerformer.numMalicious} malicious
                clients had lowest accuracy at {formatAccuracy(worstPerformer.finalAccuracy)}
              </Alert>
            )}

            <Alert variant="info" className="mb-0">
              <strong>📈 Experiment Scope:</strong> This comparison includes {allPlotData.length}{' '}
              strategy variations testing{' '}
              {new Set(performanceSummary.map(s => s.aggregationStrategy)).size} different
              aggregation strategies across various attack scenarios
            </Alert>
          </div>
        </Card.Body>
      </Card>

      <StrategyComparisonPlot allPlotData={allPlotData} strategyConfigs={strategyConfigs} />

      <Card className="mb-4">
        <Card.Body>
          <h6 className="mb-2">
            <span aria-hidden="true">🎓 </span>Understanding This Comparison
          </h6>
          <p className="text-muted mb-0">
            This view allows you to compare how different aggregation strategies and configurations
            perform under varying attack conditions. Use the interactive plot above to toggle
            strategies and explore their behavior across training rounds. Click on individual
            strategies in the performance table to learn more about each approach.
          </p>
        </Card.Body>
      </Card>
    </div>
  );
}

ComparisonTab.propTypes = {
  simulation: PropTypes.shape({
    id: PropTypes.string,
    status: PropTypes.string,
    config: PropTypes.object,
  }).isRequired,
  isMultiStrategy: PropTypes.bool,
};
