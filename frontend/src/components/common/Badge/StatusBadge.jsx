import './StatusBadge.css';
import PropTypes from 'prop-types';
import { OverlayTrigger, Tooltip } from 'react-bootstrap';

export function StatusBadge({ status, errorMessage, className = '' }) {
  const badge = (
    <span className={`status-badge status-${status || 'pending'} ${className}`}>
      <span className="status-dot"></span>
      {status || 'pending'}
    </span>
  );

  if (status === 'failed' && errorMessage) {
    return (
      <OverlayTrigger
        placement="left"
        overlay={
          <Tooltip id="tooltip-error">
            <div style={{ textAlign: 'left', whiteSpace: 'pre-wrap', maxWidth: '400px' }}>
              {errorMessage}
            </div>
          </Tooltip>
        }
      >
        <span
          style={{ cursor: 'pointer' }}
          role="button"
          tabIndex={0}
          aria-label="Failed: click to view error details"
        >
          {badge}
        </span>
      </OverlayTrigger>
    );
  }

  return badge;
}

StatusBadge.propTypes = {
  status: PropTypes.oneOf(['pending', 'running', 'completed', 'failed', 'stopped', 'loading']),
  errorMessage: PropTypes.string,
  className: PropTypes.string,
};

StatusBadge.defaultProps = {
  className: '',
};
