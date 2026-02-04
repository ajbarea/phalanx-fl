import { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { Offcanvas, OffcanvasHeader, OffcanvasBody } from '../../Offcanvas';
import { OutlineButton } from '../../common/Button/OutlineButton';
import { Form, Alert } from 'react-bootstrap';
import { toast } from 'sonner';

export function ConfigEditorOffcanvas({ isOpen, toggle, config, onSave }) {
  const [jsonText, setJsonText] = useState('');
  const [error, setError] = useState(null);

  // Update local text when config changes (e.g., from form updates)
  useEffect(() => {
    if (isOpen) {
      setJsonText(JSON.stringify(config, null, 2));
      setError(null);
    }
  }, [isOpen, config]);

  const handleTextChange = e => {
    setJsonText(e.target.value);
    // Real-time syntax check
    try {
      JSON.parse(e.target.value);
      setError(null);
    } catch (err) {
      setError(`Invalid JSON: ${err.message}`);
    }
  };

  const handleFormat = () => {
    try {
      const parsed = JSON.parse(jsonText);
      setJsonText(JSON.stringify(parsed, null, 2));
      setError(null);
    } catch (err) {
      setError(`Cannot format: ${err.message}`);
    }
  };

  const handleSave = () => {
    try {
      const parsed = JSON.parse(jsonText);
      onSave(parsed);
      toast.success('Configuration updated from JSON');
      toggle();
    } catch (err) {
      setError(`Cannot save invalid JSON: ${err.message}`);
      toast.error('Failed to update configuration');
    }
  };

  return (
    <Offcanvas
      isOpen={isOpen}
      toggle={toggle}
      direction="end"
      style={{ width: '600px' }}
      labelledBy="config-editor-title"
    >
      <OffcanvasHeader toggle={toggle} id="config-editor-title">
        <i className="bi bi-braces me-2"></i>
        Raw JSON Configuration
      </OffcanvasHeader>
      <OffcanvasBody className="d-flex flex-column">
        <p className="text-muted small">
          Edit the raw simulation configuration below. Changes will be reflected in the form after
          saving.
        </p>

        {error && (
          <Alert variant="danger" className="py-2 small mb-3">
            <i className="bi bi-exclamation-circle me-2"></i>
            {error}
          </Alert>
        )}

        <Form.Group className="flex-grow-1 mb-3">
          <Form.Control
            as="textarea"
            value={jsonText}
            onChange={handleTextChange}
            className="font-monospace h-100"
            style={{
              fontSize: '13px',
              resize: 'none',
              backgroundColor: 'var(--bs-tertiary-bg)',
              color: 'var(--bs-emphasis-color)',
            }}
            placeholder="Enter simulation config JSON..."
          />
        </Form.Group>

        <div className="d-flex gap-2">
          <OutlineButton variant="outline-secondary" className="flex-grow-1" onClick={handleFormat}>
            Format JSON
          </OutlineButton>
          <OutlineButton
            variant="primary"
            className="btn-primary-action flex-grow-1"
            onClick={handleSave}
            disabled={!!error}
          >
            Save Changes
          </OutlineButton>
        </div>
      </OffcanvasBody>
    </Offcanvas>
  );
}

ConfigEditorOffcanvas.propTypes = {
  isOpen: PropTypes.bool.isRequired,
  toggle: PropTypes.func.isRequired,
  config: PropTypes.object.isRequired,
  onSave: PropTypes.func.isRequired,
};
