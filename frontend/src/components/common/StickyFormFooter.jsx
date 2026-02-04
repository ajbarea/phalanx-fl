import './StickyFormFooter.css';
import PropTypes from 'prop-types';
import { Button, Spinner } from 'react-bootstrap';

/**
 * Sticky form footer that stays visible at bottom of viewport.
 * Shows validation errors and submit button so users always know form status.
 */
function StickyFormFooter({
  validation,
  isSubmitting,
  submitLabel = 'Create Simulation',
  submittingLabel = 'Creating Simulation...',
  onErrorClick,
}) {
  const errors = validation?.errors || [];
  const warnings = validation?.warnings || [];
  const hasErrors = errors.length > 0;
  const hasWarnings = warnings.length > 0;

  const handleErrorClick = () => {
    if (errors.length > 0 && onErrorClick) {
      onErrorClick(errors[0]);
    }
  };

  return (
    <div className="sticky-form-footer">
      <div className="sticky-form-footer-content">
        {/* Validation status */}
        <div className="sticky-form-footer-status">
          {hasErrors ? (
            <button
              type="button"
              className="sticky-error-badge"
              onClick={handleErrorClick}
              title="Click to jump to error"
            >
              <span className="error-icon">!</span>
              <span>
                {errors.length} error{errors.length > 1 ? 's' : ''} in{' '}
                <strong>{errors[0]?.field}</strong>
              </span>
            </button>
          ) : hasWarnings ? (
            <span className="sticky-warning-badge">
              <span className="warning-icon">!</span>
              {warnings.length} warning{warnings.length > 1 ? 's' : ''}
            </span>
          ) : (
            <span className="sticky-success-badge">
              <span className="success-icon">✓</span>
              Ready to launch
            </span>
          )}
        </div>

        <div className="sticky-footer-actions">
          <Button
            variant="primary"
            type="submit"
            disabled={isSubmitting || hasErrors}
            className="sticky-submit-btn"
          >
            {isSubmitting ? (
              <>
                <Spinner
                  as="span"
                  animation="border"
                  size="sm"
                  role="status"
                  aria-hidden="true"
                  className="me-2"
                />
                {submittingLabel}
              </>
            ) : (
              submitLabel
            )}
          </Button>

          <div className="sticky-devtools-spacer" />
        </div>
      </div>
    </div>
  );
}

StickyFormFooter.propTypes = {
  validation: PropTypes.shape({
    errors: PropTypes.arrayOf(
      PropTypes.shape({
        field: PropTypes.string.isRequired,
        message: PropTypes.string.isRequired,
      })
    ),
    warnings: PropTypes.arrayOf(
      PropTypes.shape({
        field: PropTypes.string.isRequired,
        message: PropTypes.string.isRequired,
      })
    ),
  }),
  isSubmitting: PropTypes.bool,
  submitLabel: PropTypes.string,
  submittingLabel: PropTypes.string,
  onErrorClick: PropTypes.func,
};

export default StickyFormFooter;
export { StickyFormFooter };
