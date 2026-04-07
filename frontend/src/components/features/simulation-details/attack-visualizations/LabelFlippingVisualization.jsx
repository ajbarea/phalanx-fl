import { Card, Badge } from 'react-bootstrap';
import { useTheme } from '../../../../contexts/ThemeContext';
import { ALERT_COLORS } from '../../../../constants/ui';

/**
 * Specialized visualization footer for label flipping attacks.
 * Displays flip statistics and patterns.
 */
export function LabelFlippingVisualization({ snapshot, activeTab, attackInfo, availableViz }) {
  const { theme } = useTheme();
  const alertColors = ALERT_COLORS[theme] || ALERT_COLORS.light;

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

      {/* Label Flipping Summary Stats */}
      {snapshot.flip_summary && (
        <Card.Footer
          className="py-2 small border-top"
          style={{ backgroundColor: alertColors.warning.bg, color: alertColors.warning.text }}
        >
          <div className="d-flex flex-wrap gap-2 align-items-center">
            <Badge bg="danger">
              {snapshot.flip_summary.flipped_samples}/{snapshot.flip_summary.total_samples} flipped
              ({snapshot.flip_summary.flip_rate}%)
            </Badge>
            {snapshot.flip_summary.top_flip_patterns?.slice(0, 3).map((pattern, i) => (
              <Badge key={i} bg="secondary">
                {pattern.from} → {pattern.to} ({pattern.count})
              </Badge>
            ))}
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
