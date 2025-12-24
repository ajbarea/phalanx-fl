import PropTypes from 'prop-types';
import { Spinner as BSSpinner } from 'react-bootstrap';

export function Spinner({ size = 'md', className = '' }) {
  const sizeMap = {
    sm: { width: '1rem', height: '1rem' },
    md: { width: '2rem', height: '2rem' },
    lg: { width: '3rem', height: '3rem' },
  };

  return (
    <BSSpinner animation="border" role="status" style={sizeMap[size]} className={className}>
      <span className="visually-hidden">Loading...</span>
    </BSSpinner>
  );
}

Spinner.propTypes = {
  size: PropTypes.oneOf(['sm', 'md', 'lg']),
  className: PropTypes.string,
};

Spinner.defaultProps = {
  size: 'md',
  className: '',
};
