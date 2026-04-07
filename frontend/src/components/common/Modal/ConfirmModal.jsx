import PropTypes from 'prop-types';
import { Modal, Button } from 'react-bootstrap';
import OutlineButton from '../Button/OutlineButton';

/**
 * Confirmation modal component
 *
 * @param {boolean} show - Whether to show the modal
 * @param {string} title - Modal title text
 * @param {string} message - Confirmation message
 * @param {function} onConfirm - Callback when user confirms
 * @param {function} onCancel - Callback when user cancels
 * @param {string} variant - Bootstrap variant for confirm button (danger, warning, primary, info)
 * @param {string} confirmText - Text for confirm button (default: "Confirm")
 * @param {string} cancelText - Text for cancel button (default: "Cancel")
 */
function ConfirmModal({
  show,
  title,
  message,
  onConfirm,
  onCancel,
  variant = 'danger',
  confirmText = 'Confirm',
  cancelText = 'Cancel',
}) {
  return (
    <Modal show={show} onHide={onCancel} centered className="confirm-modal">
      <Modal.Header closeButton>
        <Modal.Title>{title}</Modal.Title>
      </Modal.Header>
      <Modal.Body>
        {typeof message === 'string' ? (
          <p style={{ whiteSpace: 'pre-wrap', marginBottom: 0 }}>{message}</p>
        ) : (
          message
        )}
      </Modal.Body>
      <Modal.Footer>
        <OutlineButton onClick={onCancel}>{cancelText}</OutlineButton>
        <Button variant={variant} size="sm" onClick={onConfirm}>
          {confirmText}
        </Button>
      </Modal.Footer>
    </Modal>
  );
}

ConfirmModal.propTypes = {
  show: PropTypes.bool.isRequired,
  title: PropTypes.string.isRequired,
  message: PropTypes.oneOfType([PropTypes.string, PropTypes.node]).isRequired,
  onConfirm: PropTypes.func.isRequired,
  onCancel: PropTypes.func.isRequired,
  variant: PropTypes.oneOf(['danger', 'warning', 'primary', 'info', 'success']),
  confirmText: PropTypes.string,
  cancelText: PropTypes.string,
};

ConfirmModal.defaultProps = {
  variant: 'danger',
  confirmText: 'Confirm',
  cancelText: 'Cancel',
};

export default ConfirmModal;
export { ConfirmModal };
