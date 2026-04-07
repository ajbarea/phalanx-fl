import PropTypes from 'prop-types';

/**
 * Consistent empty state display for when data is unavailable or loading.
 * Replaces scattered "text-center p-4" patterns throughout the codebase.
 */
export function EmptyState({ message, icon, children, className = '' }) {
  return (
    <div className={`text-center p-4 ${className}`}>
      {icon && <div className="empty-state-icon mb-2">{icon}</div>}
      {children || <p className="text-muted mb-0">{message}</p>}
    </div>
  );
}

EmptyState.propTypes = {
  /** Message to display when no children provided */
  message: PropTypes.string,
  /** Optional icon to display above the message */
  icon: PropTypes.node,
  /** Custom content (overrides message if provided) */
  children: PropTypes.node,
  /** Additional CSS classes */
  className: PropTypes.string,
};

EmptyState.defaultProps = {
  message: 'No data available',
  icon: null,
  children: null,
  className: '',
};
