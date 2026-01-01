import { Card, Badge } from 'react-bootstrap';

/**
 * Specialized visualization footer for Gaussian noise attacks.
 * Displays noise statistics and SNR information.
 */
export function GaussianNoiseVisualization({ snapshot, activeTab, attackInfo, availableViz }) {
  // Extract SNR from attack config if available
  const snr = snapshot.metadata?.attack_config?.target_noise_snr;

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
            {snr && (
              <Badge bg="info" className="ms-auto">
                SNR: {snr} dB
              </Badge>
            )}
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
