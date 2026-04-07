import PropTypes from 'prop-types';
import { Form } from 'react-bootstrap';
import { InfoTooltip } from '@components/common/Tooltip/InfoTooltip';

export function SelectField({
  name,
  label,
  value,
  onChange,
  options = [],
  tooltip,
  required,
  className = '',
  ...props
}) {
  const labelComponent = tooltip ? (
    <InfoTooltip text={tooltip}>
      <Form.Label>{label}</Form.Label>
    </InfoTooltip>
  ) : (
    <Form.Label>{label}</Form.Label>
  );

  return (
    <Form.Group className={`mb-3 ${className}`}>
      {labelComponent}
      <Form.Select name={name} value={value} onChange={onChange} required={required} {...props}>
        {options.map(option => (
          <option key={option.value || option} value={option.value || option}>
            {option.label || option}
          </option>
        ))}
      </Form.Select>
    </Form.Group>
  );
}

SelectField.propTypes = {
  name: PropTypes.string.isRequired,
  label: PropTypes.string.isRequired,
  value: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  onChange: PropTypes.func.isRequired,
  options: PropTypes.arrayOf(
    PropTypes.oneOfType([
      PropTypes.string,
      PropTypes.shape({
        value: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
        label: PropTypes.string,
      }),
    ])
  ),
  tooltip: PropTypes.string,
  required: PropTypes.bool,
  className: PropTypes.string,
};
