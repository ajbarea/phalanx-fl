import PropTypes from 'prop-types';
import { Alert } from 'react-bootstrap';

/**
 * Validation Summary Component
 *
 * Displays aggregated validation status above the submit button
 * Shows errors, warnings, and info messages in organized alerts
 *
 * @param {Object} validation - Validation object containing errors, warnings, infos arrays
 */
function ValidationSummary({ validation }) {
  const errors = validation?.errors || [];
  const warnings = validation?.warnings || [];
  const infos = validation?.infos || [];

  if (errors.length === 0 && warnings.length === 0 && infos.length === 0) {
    return (
      <Alert variant="success" className="mb-3 py-2 validation-success-alert">
        ✓ Configuration valid - ready to launch
      </Alert>
    );
  }

  return (
    <div className="validation-summary mb-3">
      {errors.length > 0 && (
        <Alert variant="danger" className="mb-2">
          <strong>
            ❌ {errors.length} Error{errors.length > 1 ? 's' : ''}
          </strong>
          <ul className="mb-0 mt-2">
            {errors.map((e, i) => (
              <li key={i}>
                <code>{e.field}</code>: {e.message}
              </li>
            ))}
          </ul>
        </Alert>
      )}

      {warnings.length > 0 && (
        <Alert variant="warning" className="mb-2">
          <strong>
            ⚠️ {warnings.length} Warning{warnings.length > 1 ? 's' : ''}
          </strong>
          <ul className="mb-0 mt-2">
            {warnings.map((w, i) => (
              <li key={i}>
                <code>{w.field}</code>: {w.message}
              </li>
            ))}
          </ul>
        </Alert>
      )}

      {infos.length > 0 && (
        <Alert variant="info" className="mb-2">
          <strong>ℹ️ Information</strong>
          <ul className="mb-0 mt-2">
            {infos.map((info, i) => (
              <li key={i}>
                <code>{info.field}</code>: {info.message}
              </li>
            ))}
          </ul>
        </Alert>
      )}
    </div>
  );
}

const validationItemShape = PropTypes.shape({
  field: PropTypes.string.isRequired,
  message: PropTypes.string.isRequired,
});

ValidationSummary.propTypes = {
  validation: PropTypes.shape({
    errors: PropTypes.arrayOf(validationItemShape),
    warnings: PropTypes.arrayOf(validationItemShape),
    infos: PropTypes.arrayOf(validationItemShape),
  }),
};

ValidationSummary.defaultProps = {
  validation: { errors: [], warnings: [], infos: [] },
};

export default ValidationSummary;
