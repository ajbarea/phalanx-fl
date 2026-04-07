import { Card } from 'react-bootstrap';

/**
 * Generic visualization footer for unknown or unsupported attack types.
 * Displays basic metadata without specialized formatting.
 */
export function GenericAttackVisualization({ snapshot, activeTab, attackInfo, availableViz }) {
  return (
    <>
      {/* Metadata Footer */}
      {snapshot.metadata && (
        <Card.Footer className="py-2 small text-muted">
          <div className="d-flex justify-content-between flex-wrap gap-1">
            {snapshot.metadata.num_samples && <span>Samples: {snapshot.metadata.num_samples}</span>}
            {snapshot.metadata.data_shape && (
              <span>Shape: {snapshot.metadata.data_shape.join(' x ')}</span>
            )}
          </div>
        </Card.Footer>
      )}

      {/* Attack Description (if available) */}
      {attackInfo && activeTab === 'primary' && (
        <Card.Footer className="py-2 small border-top bg-light">
          <div className="text-muted">
            <strong className="d-block mb-1">{attackInfo.title}</strong>
            <p className="mb-1" style={{ fontSize: '0.75rem' }}>
              {attackInfo.description}
            </p>
            {availableViz.length > 1 && attackInfo.tip && (
              <p className="mb-0 fst-italic" style={{ fontSize: '0.7rem' }}>
                Tip: {attackInfo.tip}
              </p>
            )}
          </div>
        </Card.Footer>
      )}

      {/* Fallback for completely unknown attacks */}
      {!attackInfo && activeTab === 'primary' && (
        <Card.Footer className="py-2 small border-top bg-light">
          <div className="text-muted">
            <strong className="d-block mb-1">
              {snapshot.attack_type.replace(/_/g, ' ').toUpperCase()}
            </strong>
            <p className="mb-0" style={{ fontSize: '0.75rem' }}>
              Attack visualization showing the effect of {snapshot.attack_type.replace(/_/g, ' ')}{' '}
              on training data or model weights.
            </p>
          </div>
        </Card.Footer>
      )}
    </>
  );
}
