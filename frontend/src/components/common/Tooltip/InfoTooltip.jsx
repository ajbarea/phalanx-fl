import PropTypes from 'prop-types';
import { OverlayTrigger, Tooltip } from 'react-bootstrap';

export function InfoTooltip({ text, placement = 'right', children }) {
  if (!text) {
    return children;
  }

  const handleKeyDown = e => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      e.target.click();
    }
  };

  return (
    <OverlayTrigger
      placement={placement}
      overlay={<Tooltip>{text}</Tooltip>}
      trigger={['hover', 'focus']}
    >
      <span
        tabIndex={0}
        role="button"
        aria-label="More information"
        onKeyDown={handleKeyDown}
        style={{ cursor: 'help', display: 'inline-flex', alignItems: 'center', gap: '4px' }}
      >
        {children}
        <span aria-hidden="true" style={{ fontSize: '0.9rem' }}>
          ℹ️
        </span>
      </span>
    </OverlayTrigger>
  );
}

InfoTooltip.propTypes = {
  text: PropTypes.string,
  placement: PropTypes.oneOf(['top', 'right', 'bottom', 'left']),
  children: PropTypes.node,
};

InfoTooltip.defaultProps = {
  placement: 'right',
};
