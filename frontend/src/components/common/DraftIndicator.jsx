import PropTypes from 'prop-types';
import { Alert, Button } from 'react-bootstrap';

/**
 * Draft indicator component - shows when form has a draft loaded
 */
function DraftIndicator({ timestamp, onDiscard }) {
  const formatTimestamp = ts => {
    if (!ts) return 'previously';
    const date = new Date(ts);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return diffMins + ' min ago';
    if (diffHours < 24) return diffHours + ' hour' + (diffHours > 1 ? 's' : '') + ' ago';
    if (diffDays < 7) return diffDays + ' day' + (diffDays > 1 ? 's' : '') + ' ago';
    return date.toLocaleDateString();
  };

  return (
    <Alert
      variant="info"
      className="d-flex align-items-center justify-content-between mb-3"
      role="status"
      aria-live="polite"
    >
      <div className="d-flex align-items-center">
        <i className="bi bi-file-earmark-text me-2" aria-hidden="true"></i>
        <span>
          <strong>Draft restored</strong> - saved {formatTimestamp(timestamp)}
        </span>
      </div>
      <Button variant="outline-info" size="sm" onClick={onDiscard} className="ms-3">
        Discard Draft
      </Button>
    </Alert>
  );
}

DraftIndicator.propTypes = {
  timestamp: PropTypes.string,
  onDiscard: PropTypes.func.isRequired,
};

export { DraftIndicator };
