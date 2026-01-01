import { Card, Badge, ProgressBar } from 'react-bootstrap';

/**
 * Specialized visualization footer for weight-based attacks.
 * Displays weight change statistics and impact metrics.
 */
export function WeightAttackVisualization({ snapshot, activeTab, attackInfo, availableViz }) {
  const stats = snapshot.metadata?.statistics;
  const diffStats = stats?.difference;

  return (
    <>
      {/* Weight Statistics Footer */}
      {diffStats && (
        <Card.Footer className="py-2 small">
          <div className="mb-2">
            <div className="d-flex justify-content-between align-items-center mb-1">
              <span className="text-muted">Weights Changed</span>
              <Badge bg={diffStats.pct_changed > 50 ? 'danger' : 'warning'}>
                {diffStats.pct_changed?.toFixed(1)}%
              </Badge>
            </div>
            <ProgressBar
              now={diffStats.pct_changed}
              variant={diffStats.pct_changed > 50 ? 'danger' : 'warning'}
              style={{ height: '6px' }}
            />
          </div>
          <div className="d-flex justify-content-between flex-wrap gap-2 text-muted">
            <span>
              L2 Norm: <strong>{diffStats.diff_l2_norm?.toFixed(2)}</strong>
            </span>
            <span>
              Mean Diff: <strong>{diffStats.diff_mean?.toFixed(4)}</strong>
            </span>
            <span>
              Max Diff: <strong>{diffStats.diff_max?.toFixed(4)}</strong>
            </span>
          </div>
        </Card.Footer>
      )}

      {/* Before/After Stats */}
      {stats?.before && stats?.after && (
        <Card.Footer className="py-2 small border-top">
          <div className="row g-2 text-center">
            <div className="col-6">
              <div className="p-2 rounded" style={{ backgroundColor: '#e8f5e9' }}>
                <div className="fw-bold text-success">Before</div>
                <div className="small text-muted">
                  Mean: {stats.before.mean?.toFixed(4)}
                  <br />
                  Std: {stats.before.std?.toFixed(4)}
                </div>
              </div>
            </div>
            <div className="col-6">
              <div className="p-2 rounded" style={{ backgroundColor: '#ffebee' }}>
                <div className="fw-bold text-danger">After</div>
                <div className="small text-muted">
                  Mean: {stats.after.mean?.toFixed(4)}
                  <br />
                  Std: {stats.after.std?.toFixed(4)}
                </div>
              </div>
            </div>
          </div>
        </Card.Footer>
      )}

      {/* Fallback for basic metadata */}
      {!stats && snapshot.metadata && (
        <Card.Footer className="py-2 small text-muted">
          <div className="d-flex justify-content-between flex-wrap gap-1">
            {snapshot.metadata.num_samples && <span>Samples: {snapshot.metadata.num_samples}</span>}
          </div>
        </Card.Footer>
      )}

      {/* Attack Description */}
      {attackInfo && activeTab === 'primary' && (
        <Card.Footer className="py-2 small border-top bg-light">
          <div className="text-muted">
            <strong className="d-block mb-1">{attackInfo.title}</strong>
            <p className="mb-1" style={{ fontSize: '0.75rem' }}>
              {attackInfo.description}
            </p>
            {availableViz.length > 1 && (
              <p className="mb-0 fst-italic" style={{ fontSize: '0.7rem' }}>
                Tip: {attackInfo.tip}
              </p>
            )}
          </div>
        </Card.Footer>
      )}
    </>
  );
}
