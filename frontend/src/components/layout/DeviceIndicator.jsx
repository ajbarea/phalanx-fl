import { useState } from 'react';
import { Nav, OverlayTrigger, Tooltip } from 'react-bootstrap';
import { useDevice } from '@contexts/DeviceContext';
import { MaterialIcon } from '@components/common/Icon/MaterialIcon';
import { DeviceSettingsModal } from '@components/common/Modal/DeviceSettingsModal';
import './DeviceIndicator.css';

/**
 * Navbar indicator showing current training device configuration.
 * Displays device status and opens settings modal on click.
 */
export function DeviceIndicator() {
  const [showModal, setShowModal] = useState(false);
  const { gpuAvailable, gpuInfo, loading, isUsingGpu, deviceSettings } = useDevice();

  if (loading) {
    return (
      <Nav.Link as="button" className="device-indicator device-indicator--loading" disabled>
        <MaterialIcon name="memory" size={18} />
        <span className="device-indicator-text">Detecting...</span>
      </Nav.Link>
    );
  }

  const getTooltipContent = () => {
    if (isUsingGpu && gpuInfo) {
      return `GPU: ${gpuInfo.name} (${gpuInfo.vram_gb}GB VRAM) - ${deviceSettings.gpus_per_client} GPU/client`;
    }
    if (gpuAvailable && !isUsingGpu) {
      return 'Using CPU. GPU available - click to enable.';
    }
    return 'Using CPU for training. No GPU detected.';
  };

  const renderIndicatorContent = () => {
    if (isUsingGpu && gpuInfo) {
      // GPU active - show success state with GPU name
      const shortName = gpuInfo.name.replace('NVIDIA GeForce ', '').replace('NVIDIA ', '');
      return (
        <>
          <MaterialIcon name="memory" size={18} />
          <span className="device-indicator-text device-indicator-text--full">
            {shortName} ({gpuInfo.vram_gb}GB)
          </span>
          <span className="device-indicator-text device-indicator-text--short">GPU</span>
        </>
      );
    }

    if (gpuAvailable) {
      // GPU available but not enabled - show attention state
      return (
        <>
          <span className="device-chip device-chip--cpu">
            <MaterialIcon name="computer" size={14} />
            <span>CPU</span>
          </span>
          <span className="device-chip device-chip--gpu-available">
            <MaterialIcon name="memory" size={14} />
            <span>GPU Available</span>
          </span>
        </>
      );
    }

    // CPU only - muted state
    return (
      <>
        <MaterialIcon name="computer" size={18} />
        <span className="device-indicator-text">CPU</span>
      </>
    );
  };

  const indicatorClass = [
    'device-indicator',
    isUsingGpu && 'device-indicator--gpu-active',
    gpuAvailable && !isUsingGpu && 'device-indicator--gpu-available',
    !gpuAvailable && 'device-indicator--cpu-only',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <>
      <OverlayTrigger
        placement="bottom"
        overlay={<Tooltip id="device-tooltip">{getTooltipContent()}</Tooltip>}
      >
        <Nav.Link
          as="button"
          className={indicatorClass}
          onClick={() => setShowModal(true)}
          aria-label="Configure training device"
        >
          {renderIndicatorContent()}
        </Nav.Link>
      </OverlayTrigger>

      <DeviceSettingsModal show={showModal} onHide={() => setShowModal(false)} />
    </>
  );
}
