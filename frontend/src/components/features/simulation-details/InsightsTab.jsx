import { Card, Alert, ListGroup, Spinner } from 'react-bootstrap';
import { formatAccuracy, formatChange, formatDetectionMetric } from '@utils/formatters';
import { SimulationResultState } from '@components/common/Empty/SimulationResultState';

export function InsightsTab({ details, csvData, status }) {
  // Check if CSV data is still loading (status is completed but no CSV data yet)
  const isLoadingCsvData =
    status === 'completed' &&
    (!csvData || Object.keys(csvData).length === 0 || !csvData['csv/round_metrics_0.csv']);
  if (!details || !details.config) {
    return (
      <Card className="mt-3">
        <Card.Body>
          <Alert variant="info">Loading simulation details...</Alert>
        </Card.Body>
      </Card>
    );
  }

  const cfg = details.config?.shared_settings || details.config;
  const isMultiStrategy =
    details.config?.simulation_strategies && details.config.simulation_strategies.length > 1;

  const generateInsights = () => {
    const insights = [];
    const roundMetrics = csvData['csv/round_metrics_0.csv'];
    const perClientMetrics = csvData['csv/per_client_metrics_0.csv'];

    if (!roundMetrics || roundMetrics.length === 0) {
      return insights;
    }

    if (roundMetrics.length >= 2) {
      const firstAccuracy = parseFloat(roundMetrics[0].average_accuracy_history);
      const lastAccuracy = parseFloat(
        roundMetrics[roundMetrics.length - 1].average_accuracy_history
      );
      const improvement = formatChange(firstAccuracy, lastAccuracy);

      if (parseFloat(improvement) > 0) {
        insights.push({
          type: 'success',
          icon: '📈',
          text: `Model accuracy improved by ${improvement}% over ${roundMetrics.length} rounds (from ${formatAccuracy(firstAccuracy)} to ${formatAccuracy(lastAccuracy)})`,
        });
      } else if (parseFloat(improvement) < 0) {
        insights.push({
          type: 'warning',
          icon: '⚠️',
          text: `Model accuracy decreased by ${Math.abs(parseFloat(improvement))}% - this may indicate attack or poor hyperparameters`,
        });
      }
    }

    if (cfg.num_of_malicious_clients > 0) {
      let attackTypes = cfg.attack_type || 'unknown';
      if (cfg.attack_schedule && cfg.attack_schedule.length > 0) {
        const uniqueTypes = [...new Set(cfg.attack_schedule.map(a => a.attack_type))];
        attackTypes = uniqueTypes.join(', ');
      }
      insights.push({
        type: 'info',
        icon: '🎯',
        text: `Simulation includes ${cfg.num_of_malicious_clients} malicious client(s) using ${attackTypes} attack`,
      });

      if (cfg.remove_clients === 'true' && roundMetrics.length > 0) {
        const lastRound = roundMetrics[roundMetrics.length - 1];
        const removalAccuracy = parseFloat(lastRound.removal_accuracy_history);
        const removalPrecision = parseFloat(lastRound.removal_precision_history);
        const removalRecall = parseFloat(lastRound.removal_recall_history);

        if (removalAccuracy === 1.0) {
          insights.push({
            type: 'success',
            icon: '✓',
            text: `Defense strategy (${cfg.aggregation_strategy_keyword}) successfully identified all malicious clients with 100% accuracy`,
          });
        } else if (removalAccuracy >= 0.7) {
          insights.push({
            type: 'success',
            icon: '✓',
            text: `Defense detected malicious clients with ${formatDetectionMetric(removalAccuracy)} accuracy (Precision: ${formatDetectionMetric(removalPrecision)}, Recall: ${formatDetectionMetric(removalRecall)})`,
          });
        } else if (removalAccuracy > 0) {
          insights.push({
            type: 'warning',
            icon: '⚠️',
            text: `Defense partially effective: ${formatDetectionMetric(removalAccuracy)} accuracy in detecting malicious clients`,
          });
        }
      }
    } else {
      insights.push({
        type: 'info',
        icon: 'ℹ️',
        text: 'Baseline simulation with no malicious clients - observing natural federated learning behavior',
      });
    }

    if (perClientMetrics && perClientMetrics.length > 0) {
      const lastRound = perClientMetrics[perClientMetrics.length - 1];
      const participationKeys = Object.keys(lastRound).filter(k =>
        k.includes('aggregation_participation_history')
      );
      const activeClients = participationKeys.filter(
        k => lastRound[k] === '1' || lastRound[k] === 1
      ).length;
      const removedClients = cfg.num_of_clients - activeClients;

      if (removedClients > 0) {
        insights.push({
          type: 'info',
          icon: '🔒',
          text: `${removedClients} client(s) removed from aggregation by round ${roundMetrics.length} (${activeClients} active clients remaining)`,
        });
      }
    }

    if (cfg.aggregation_strategy_keyword === 'pid' && cfg.remove_clients === 'true') {
      const beginRemoving = cfg.begin_removing_from_round || 2;
      insights.push({
        type: 'info',
        icon: '🛡️',
        text: `PID-based removal strategy started evaluating clients from round ${beginRemoving} with ${cfg.pid_p || 0.1} proportional gain`,
      });
    } else if (cfg.aggregation_strategy_keyword === 'krum') {
      insights.push({
        type: 'info',
        icon: '🛡️',
        text: `Krum aggregation selects the most trustworthy client update based on distance metrics`,
      });
    } else if (cfg.aggregation_strategy_keyword === 'trimmed_mean') {
      insights.push({
        type: 'info',
        icon: '🛡️',
        text: `Trimmed mean removes extreme updates before aggregation for robustness`,
      });
    }

    insights.push({
      type: 'info',
      icon: '📊',
      text: `Trained ${cfg.model_type || 'cnn'} model on ${cfg.dataset_keyword} dataset with ${cfg.num_of_clients} clients`,
    });

    if (isMultiStrategy) {
      const numStrategies = details.config.simulation_strategies.length;
      const strategyTypes = new Set(
        details.config.simulation_strategies.map(s => s.aggregation_strategy_keyword || 'fedavg')
      );

      insights.push({
        type: 'info',
        icon: '🔬',
        text: `Multi-strategy experiment with ${numStrategies} variations comparing ${Array.from(strategyTypes).join(', ')} strategies`,
      });

      if (status === 'completed') {
        insights.push({
          type: 'success',
          icon: '📈',
          text: `All ${numStrategies} strategies completed! View the Comparison tab to analyze performance differences`,
        });
      }
    }

    return insights;
  };

  const insights = status === 'completed' ? generateInsights() : [];

  if (!isLoadingCsvData && insights.length === 0) {
    return <SimulationResultState noun="Insights" status={status} />;
  }

  return (
    <Card className="mt-3">
      <Card.Body>
        {isLoadingCsvData ? (
          <div className="text-center py-4">
            <Spinner animation="border" variant="primary" size="sm" className="me-2" />
            <span className="text-muted">Loading insights...</span>
          </div>
        ) : (
          <>
            <h5 className="mb-3">Educational Insights</h5>
            <p className="text-muted mb-3">
              Automatic analysis of simulation results to help understand federated learning
              behavior and defense effectiveness.
            </p>
            <ListGroup>
              {insights.map((insight, idx) => (
                <ListGroup.Item
                  key={idx}
                  variant={
                    insight.type === 'success'
                      ? 'success'
                      : insight.type === 'warning'
                        ? 'warning'
                        : 'light'
                  }
                  className="d-flex align-items-start gap-2"
                >
                  <span style={{ fontSize: '1.2rem', minWidth: '24px' }}>{insight.icon}</span>
                  <span>{insight.text}</span>
                </ListGroup.Item>
              ))}
            </ListGroup>
          </>
        )}
      </Card.Body>
    </Card>
  );
}
