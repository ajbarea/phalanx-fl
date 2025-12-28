import PropTypes from 'prop-types';
import { useState, useMemo } from 'react';
import { Modal, Form, Table, Badge } from 'react-bootstrap';
import OutlineButton from '../Button/OutlineButton';

/**
 * Preset confirmation modal with optional config diff view
 * Shows when user switches presets and has unsaved changes
 */
function PresetConfirmModal({
  show,
  presetName,
  currentConfig,
  presetConfig,
  onConfirm,
  onCancel,
}) {
  const [showDiff, setShowDiff] = useState(false);

  const formatValue = val => {
    if (val === undefined || val === null) return '-';
    if (typeof val === 'boolean') return val ? 'Yes' : 'No';
    if (Array.isArray(val)) return val.length > 0 ? val.join(', ') : '-';
    return String(val);
  };

  const formatFieldName = field => {
    return field
      .replace(/_/g, ' ')
      .replace(/\b[a-z]/g, c => c.toUpperCase());
  };

  const differences = useMemo(() => {
    const diffs = [];
    const relevantKeys = [
      'display_name',
      'num_of_rounds',
      'num_of_clients',
      'num_of_malicious_clients',
      'aggregation_strategy_keyword',
      'dataset_keyword',
      'model_type',
      'use_llm',
      'training_device',
      'batch_size',
      'num_of_client_epochs',
      'training_subset_fraction',
    ];

    for (const key of relevantKeys) {
      const currentVal = currentConfig[key];
      const presetVal = presetConfig[key];
      if (JSON.stringify(currentVal) !== JSON.stringify(presetVal)) {
        diffs.push({
          field: key,
          current: formatValue(currentVal),
          preset: formatValue(presetVal),
        });
      }
    }
    return diffs;
  }, [currentConfig, presetConfig]);

  return (
    <Modal show={show} onHide={onCancel} centered size="lg">
      <Modal.Header closeButton>
        <Modal.Title>Switch to &quot;{presetName}&quot;?</Modal.Title>
      </Modal.Header>
      <Modal.Body>
        <div className="alert alert-info d-flex align-items-center mb-3">
          <i className="bi bi-info-circle me-2"></i>
          <span>
            Your current form has <strong>{differences.length} different settings</strong> that
            will be replaced.
          </span>
        </div>

        <Form.Check
          type="switch"
          id="show-diff-switch"
          label="Show differences"
          checked={showDiff}
          onChange={e => setShowDiff(e.target.checked)}
          className="mb-3"
        />

        {showDiff && differences.length > 0 && (
          <Table striped bordered hover size="sm">
            <thead>
              <tr>
                <th>Setting</th>
                <th>Current</th>
                <th>Preset</th>
              </tr>
            </thead>
            <tbody>
              {differences.map(({ field, current, preset }) => (
                <tr key={field}>
                  <td>
                    <strong>{formatFieldName(field)}</strong>
                  </td>
                  <td>
                    <Badge bg="secondary">{current}</Badge>
                  </td>
                  <td>
                    <Badge bg="primary">{preset}</Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Modal.Body>
      <Modal.Footer>
        <OutlineButton onClick={onCancel}>Keep Current</OutlineButton>
        <OutlineButton variant="primary" onClick={onConfirm}>
          Apply Preset
        </OutlineButton>
      </Modal.Footer>
    </Modal>
  );
}

PresetConfirmModal.propTypes = {
  show: PropTypes.bool.isRequired,
  presetName: PropTypes.string.isRequired,
  currentConfig: PropTypes.object.isRequired,
  presetConfig: PropTypes.object.isRequired,
  onConfirm: PropTypes.func.isRequired,
  onCancel: PropTypes.func.isRequired,
};

export { PresetConfirmModal };
