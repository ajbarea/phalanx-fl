import PropTypes from 'prop-types';
import { Modal, Button, Form, Row, Col, Alert } from 'react-bootstrap';
import { useDevice } from '@contexts/DeviceContext';
import { MaterialIcon } from '@components/common/Icon/MaterialIcon';
import OutlineButton from '../Button/OutlineButton';
import './DeviceSettingsModal.css';

/**
 * Modal for configuring training device settings.
 * Provides device selection and resource allocation controls.
 */
export function DeviceSettingsModal({ show, onHide }) {
  const {
    gpuAvailable,
    gpuInfo,
    deviceSettings,
    setDeviceSettings,
    isUsingGpu,
    applyRecommendedGpu,
    resetToDefaults,
  } = useDevice();

  const handleDeviceChange = device => {
    if (device === 'gpu' && gpuAvailable) {
      setDeviceSettings({
        training_device: 'gpu',
        gpus_per_client: 0.9,
      });
    } else {
      setDeviceSettings({
        training_device: 'cpu',
        gpus_per_client: 0,
      });
    }
  };

  const handleResourceChange = (field, value) => {
    const numValue = parseFloat(value);
    if (!isNaN(numValue)) {
      setDeviceSettings({ [field]: numValue });
    }
  };

  return (
    <Modal show={show} onHide={onHide} centered className="device-settings-modal">
      <Modal.Header closeButton>
        <Modal.Title>
          <MaterialIcon name="memory" size={24} className="me-2" />
          Training Device Settings
        </Modal.Title>
      </Modal.Header>

      <Modal.Body>
        {/* Device Selection */}
        <div className="device-selection mb-4">
          <label className="form-label fw-semibold">Training Device</label>
          <div className="device-options">
            <button
              type="button"
              className={`device-option ${!isUsingGpu ? 'device-option--selected' : ''}`}
              onClick={() => handleDeviceChange('cpu')}
            >
              <MaterialIcon name="computer" size={32} />
              <div className="device-option-content">
                <span className="device-option-title">CPU</span>
                <span className="device-option-desc">Reproducible baseline</span>
              </div>
            </button>

            <button
              type="button"
              className={`device-option ${isUsingGpu ? 'device-option--selected' : ''} ${!gpuAvailable ? 'device-option--disabled' : ''}`}
              onClick={() => handleDeviceChange('gpu')}
              disabled={!gpuAvailable}
            >
              <MaterialIcon name="memory" size={32} />
              <div className="device-option-content">
                <span className="device-option-title">GPU</span>
                <span className="device-option-desc">
                  {gpuAvailable ? 'Accelerated training' : 'Not available'}
                </span>
              </div>
              {gpuAvailable && !isUsingGpu && (
                <span className="device-option-badge">Recommended for LLMs</span>
              )}
            </button>
          </div>
        </div>

        {/* GPU Info Panel */}
        {gpuAvailable && gpuInfo && (
          <Alert variant={isUsingGpu ? 'success' : 'info'} className="gpu-info-panel mb-4">
            <div className="d-flex align-items-start gap-2">
              <MaterialIcon name={isUsingGpu ? 'check_circle' : 'info'} size={20} />
              <div>
                <strong>{gpuInfo.name}</strong>
                <div className="text-muted small">{gpuInfo.vram_gb} GB VRAM</div>
                {!isUsingGpu && (
                  <div className="mt-2 small">
                    GPU acceleration is recommended for transformer/LLM models. For small CNN
                    experiments, CPU may be faster due to reduced setup overhead.
                  </div>
                )}
              </div>
            </div>
          </Alert>
        )}

        {!gpuAvailable && (
          <Alert variant="secondary" className="mb-4">
            <div className="d-flex align-items-center gap-2">
              <MaterialIcon name="info" size={20} />
              <span>No CUDA-compatible GPU detected. Training will use CPU.</span>
            </div>
          </Alert>
        )}

        {/* Resource Allocation */}
        <div className="resource-allocation">
          <label className="form-label fw-semibold">Resource Allocation</label>
          <Row className="g-3">
            <Col xs={6}>
              <Form.Group>
                <Form.Label className="small text-muted">CPUs per Client</Form.Label>
                <Form.Control
                  type="number"
                  min={0.1}
                  max={8}
                  step={0.1}
                  value={deviceSettings.cpus_per_client}
                  onChange={e => handleResourceChange('cpus_per_client', e.target.value)}
                />
              </Form.Group>
            </Col>
            <Col xs={6}>
              <Form.Group>
                <Form.Label className="small text-muted">GPUs per Client</Form.Label>
                <Form.Control
                  type="number"
                  min={0}
                  max={1}
                  step={0.1}
                  value={deviceSettings.gpus_per_client}
                  onChange={e => handleResourceChange('gpus_per_client', e.target.value)}
                  disabled={!gpuAvailable}
                />
                <Form.Text className="text-muted">
                  {deviceSettings.gpus_per_client > 0
                    ? `${Math.round(1 / deviceSettings.gpus_per_client)} clients can share GPU`
                    : 'No GPU allocation'}
                </Form.Text>
              </Form.Group>
            </Col>
          </Row>
        </div>

        {/* Quick Presets */}
        <div className="quick-presets mt-4">
          <label className="form-label fw-semibold">Quick Presets</label>
          <div className="d-flex gap-2 flex-wrap">
            <OutlineButton size="sm" onClick={resetToDefaults} className="preset-btn">
              <MaterialIcon name="computer" size={16} />
              CPU Only
            </OutlineButton>
            {gpuAvailable && (
              <OutlineButton
                size="sm"
                onClick={applyRecommendedGpu}
                variant="outline-success"
                className="preset-btn"
              >
                <MaterialIcon name="memory" size={16} />
                GPU Accelerated
              </OutlineButton>
            )}
          </div>
        </div>
      </Modal.Body>

      <Modal.Footer>
        <Button variant="primary" size="sm" onClick={onHide}>
          Done
        </Button>
      </Modal.Footer>
    </Modal>
  );
}

DeviceSettingsModal.propTypes = {
  show: PropTypes.bool.isRequired,
  onHide: PropTypes.func.isRequired,
};

export default DeviceSettingsModal;
