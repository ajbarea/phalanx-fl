import { Card, Table, OverlayTrigger, Tooltip } from 'react-bootstrap';
import PropTypes from 'prop-types';
import { formatAccuracy, formatLoss, formatDetectionMetric } from '@utils/formatters';

export function RoundMetricsTable({ data, config }) {
  if (!data || data.length === 0) {
    return null;
  }

  return (
    <Card className="mb-4">
      <Card.Header>
        <div className="d-flex justify-content-between align-items-center">
          <h5 className="mb-0">Round-by-Round Performance</h5>
          <small className="text-muted">Key metrics for each training round</small>
        </div>
      </Card.Header>
      <Card.Body>
        <div style={{ overflowX: 'auto' }}>
          <Table striped hover size="sm">
            <thead>
              <tr>
                <th
                  scope="col"
                  style={{
                    position: 'sticky',
                    left: 0,
                    backgroundColor: 'var(--bs-table-bg)',
                    zIndex: 1,
                  }}
                >
                  Round
                </th>
                <th scope="col">
                  <OverlayTrigger
                    placement="top"
                    overlay={<Tooltip>Average accuracy across all clients (0-100%)</Tooltip>}
                  >
                    <span style={{ cursor: 'help' }}>Accuracy</span>
                  </OverlayTrigger>
                </th>
                <th scope="col">
                  <OverlayTrigger
                    placement="top"
                    overlay={<Tooltip>Average loss across all clients (lower is better)</Tooltip>}
                  >
                    <span style={{ cursor: 'help' }}>Loss</span>
                  </OverlayTrigger>
                </th>
                {config.num_of_malicious_clients > 0 && config.remove_clients === 'true' && (
                  <>
                    <th scope="col">
                      <OverlayTrigger
                        placement="top"
                        overlay={
                          <Tooltip>Percentage of malicious clients correctly identified</Tooltip>
                        }
                      >
                        <span style={{ cursor: 'help' }}>Detection Accuracy</span>
                      </OverlayTrigger>
                    </th>
                    <th scope="col">
                      <OverlayTrigger
                        placement="top"
                        overlay={
                          <Tooltip>Of flagged clients, what % were actually malicious</Tooltip>
                        }
                      >
                        <span style={{ cursor: 'help' }}>Precision</span>
                      </OverlayTrigger>
                    </th>
                    <th scope="col">
                      <OverlayTrigger
                        placement="top"
                        overlay={<Tooltip>Of all malicious clients, what % were caught</Tooltip>}
                      >
                        <span style={{ cursor: 'help' }}>Recall</span>
                      </OverlayTrigger>
                    </th>
                  </>
                )}
              </tr>
            </thead>
            <tbody>
              {data.map((row, idx) => {
                const accuracy = parseFloat(row.average_accuracy_history || 0);
                const loss = parseFloat(row.aggregated_loss_history || 0);
                const detectionAcc = parseFloat(row.removal_accuracy_history || 0);
                const precision = parseFloat(row.removal_precision_history || 0);
                const recall = parseFloat(row.removal_recall_history || 0);

                return (
                  <tr key={idx}>
                    <td
                      style={{
                        position: 'sticky',
                        left: 0,
                        backgroundColor: 'var(--bs-table-bg)',
                        fontWeight: 'bold',
                      }}
                    >
                      {parseInt(row['round #'] || row.round || idx + 1)}
                    </td>
                    <td
                      className={
                        accuracy > 0.7
                          ? 'text-success fw-semibold'
                          : accuracy > 0.4
                            ? 'text-warning-accessible'
                            : 'text-danger'
                      }
                      aria-label={
                        accuracy > 0.7
                          ? 'Good accuracy'
                          : accuracy > 0.4
                            ? 'Moderate accuracy'
                            : 'Poor accuracy'
                      }
                    >
                      <span aria-hidden="true">
                        {accuracy > 0.7 ? '✓ ' : accuracy > 0.4 ? '◐ ' : '✗ '}
                      </span>
                      {formatAccuracy(accuracy)}
                    </td>
                    <td
                      className={
                        loss < 0.1
                          ? 'text-success fw-semibold'
                          : loss < 0.5
                            ? 'text-warning-accessible'
                            : ''
                      }
                      aria-label={
                        loss < 0.1
                          ? 'Excellent loss (very low)'
                          : loss < 0.5
                            ? 'Moderate loss'
                            : 'High loss'
                      }
                    >
                      <span aria-hidden="true">{loss < 0.1 ? '✓ ' : loss < 0.5 ? '◐ ' : ''}</span>
                      {formatLoss(loss)}
                    </td>
                    {config.num_of_malicious_clients > 0 && config.remove_clients === 'true' && (
                      <>
                        <td
                          className={
                            detectionAcc === 1.0
                              ? 'text-success fw-bold'
                              : detectionAcc > 0.7
                                ? 'text-success'
                                : detectionAcc > 0
                                  ? 'text-warning-accessible'
                                  : ''
                          }
                          aria-label={
                            detectionAcc === 1.0
                              ? 'Perfect detection'
                              : detectionAcc > 0.7
                                ? 'Good detection'
                                : 'Partial detection'
                          }
                        >
                          {isNaN(detectionAcc) || detectionAcc === 0 ? (
                            '—'
                          ) : (
                            <>
                              <span aria-hidden="true">
                                {detectionAcc === 1.0 ? '★ ' : detectionAcc > 0.7 ? '✓ ' : '◐ '}
                              </span>
                              {formatDetectionMetric(detectionAcc)}
                            </>
                          )}
                        </td>
                        <td>{formatDetectionMetric(precision)}</td>
                        <td>{formatDetectionMetric(recall)}</td>
                      </>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </Table>
        </div>
        <div className="mt-3 small text-muted">
          <strong>How to interpret:</strong>
          <div className="mb-0 mt-2">
            <div>
              <strong>Accuracy:</strong> Higher is better.{' '}
              <span className="text-success">✓ Green (&gt;70%)</span> = good,{' '}
              <span className="text-warning-accessible">◐ Amber (40-70%)</span> = learning,{' '}
              <span className="text-danger">✗ Red (&lt;40%)</span> = poor
            </div>
            <div>
              <strong>Loss:</strong> Lower is better. Shows how far predictions are from true values
            </div>
            {config.num_of_malicious_clients > 0 && config.remove_clients === 'true' && (
              <>
                <div>
                  <strong>Detection Accuracy:</strong> How well the defense identifies malicious
                  clients. 100% = perfect detection!
                </div>
                <div>
                  <strong>Precision:</strong> Avoids false positives (flagging honest clients as
                  malicious)
                </div>
                <div>
                  <strong>Recall:</strong> Catches all actual malicious clients (no false negatives)
                </div>
              </>
            )}
          </div>
        </div>
      </Card.Body>
    </Card>
  );
}

RoundMetricsTable.propTypes = {
  data: PropTypes.array,
  config: PropTypes.shape({
    num_of_malicious_clients: PropTypes.number,
    remove_clients: PropTypes.string,
  }),
};
