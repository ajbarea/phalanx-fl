import { Card, Badge } from 'react-bootstrap';

/**
 * Specialized visualization footer for token replacement attacks (NLP).
 * Displays token replacement statistics.
 */
export function TokenReplacementVisualization({ snapshot, activeTab, attackInfo, availableViz }) {
  // Extract attack config details if available
  const attackConfig = snapshot.metadata?.attack_config;
  const targetVocab = attackConfig?.target_vocabulary;
  const replacementStrategy = attackConfig?.replacement_strategy;
  const replacementProb = attackConfig?.replacement_probability;

  return (
    <>
      {/* Token Replacement Config */}
      {attackConfig && (
        <Card.Footer className="py-2 small">
          <div className="d-flex flex-wrap gap-2 align-items-center">
            {targetVocab && <Badge bg="info">Target: {targetVocab}</Badge>}
            {replacementStrategy && <Badge bg="secondary">Strategy: {replacementStrategy}</Badge>}
            {replacementProb !== undefined && (
              <Badge bg="warning" text="dark">
                Prob: {(replacementProb * 100).toFixed(0)}%
              </Badge>
            )}
          </div>
        </Card.Footer>
      )}

      {/* Metadata Footer */}
      {snapshot.metadata && (
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
