import PropTypes from 'prop-types';
import { OverlayTrigger, Tooltip } from 'react-bootstrap';
import { MaterialIcon } from '../Icon/MaterialIcon';

/** Displays GPU hardware information as an inline chip with tooltip. */
export function GpuInfoChip({ gpuInfo, className = '' }) {
  if (!gpuInfo) {
    return null;
  }

  return (
    <OverlayTrigger
      placement="top"
      overlay={
        <Tooltip id="gpu-info-tooltip">
          GPU acceleration enabled: {gpuInfo.name} with {gpuInfo.vram_gb}GB VRAM
        </Tooltip>
      }
    >
      <span
        className={`gpu-info-chip ${className}`}
        role="status"
        aria-label={`GPU: ${gpuInfo.name}`}
      >
        <MaterialIcon name="memory" size={14} />
        <span className="gpu-info-text">
          {gpuInfo.name.replace('NVIDIA GeForce ', '').replace('NVIDIA ', '')} ({gpuInfo.vram_gb}GB)
        </span>
      </span>
    </OverlayTrigger>
  );
}

GpuInfoChip.propTypes = {
  gpuInfo: PropTypes.shape({
    name: PropTypes.string.isRequired,
    vram_gb: PropTypes.number.isRequired,
  }),
  className: PropTypes.string,
};

GpuInfoChip.defaultProps = {
  gpuInfo: null,
  className: '',
};
