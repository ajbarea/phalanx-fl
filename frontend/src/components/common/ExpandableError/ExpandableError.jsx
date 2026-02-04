import { useState, useRef, useEffect } from 'react';
import PropTypes from 'prop-types';
import { Alert } from 'react-bootstrap';

/**
 * ExpandableError - A truncated error display with expand/collapse toggle.
 */
export function ExpandableError({ error, maxLines = 2, variant = 'danger' }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const alertRef = useRef(null);
  const wasExpanded = useRef(false);

  useEffect(() => {
    if (wasExpanded.current && !isExpanded) {
      requestAnimationFrame(() => {
        alertRef.current?.scrollIntoView({
          behavior: 'smooth',
          block: 'nearest',
        });
      });
    }
    wasExpanded.current = isExpanded;
  }, [isExpanded]);

  if (!error) return null;

  const toggleExpanded = () => setIsExpanded(prev => !prev);

  const handleKeyDown = e => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      toggleExpanded();
    }
  };

  const handleAlertClick = e => {
    if (isExpanded) {
      e.stopPropagation();
      setIsExpanded(false);
    }
  };

  return (
    <Alert
      ref={alertRef}
      variant={variant}
      className={`expandable-error mb-2 py-1 px-2 small ${isExpanded ? 'expanded-clickable' : ''}`}
      onClick={handleAlertClick}
      style={{ cursor: isExpanded ? 'pointer' : 'default' }}
    >
      <div
        className={`error-content ${isExpanded ? 'expanded' : 'collapsed'}`}
        style={{
          display: '-webkit-box',
          WebkitLineClamp: isExpanded ? 'unset' : maxLines,
          WebkitBoxOrient: 'vertical',
          overflow: isExpanded ? 'visible' : 'hidden',
          wordBreak: 'break-word',
        }}
      >
        {error}
      </div>
      {error.length > 80 && (
        <button
          type="button"
          className="expandable-error-toggle btn btn-link btn-sm p-0 mt-1"
          onClick={e => {
            e.stopPropagation();
            toggleExpanded();
          }}
          onKeyDown={handleKeyDown}
          aria-expanded={isExpanded}
          aria-label={isExpanded ? 'Collapse error details' : 'Expand error details'}
        >
          {isExpanded ? '▲ Show less' : '▼ Show more'}
        </button>
      )}
    </Alert>
  );
}

ExpandableError.propTypes = {
  error: PropTypes.string,
  maxLines: PropTypes.number,
  variant: PropTypes.string,
};

ExpandableError.defaultProps = {
  error: null,
  maxLines: 2,
  variant: 'danger',
};
