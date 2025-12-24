import PropTypes from 'prop-types';

/**
 * Material Symbols icon wrapper component
 *
 * @see https://fonts.google.com/icons
 * @see https://developers.google.com/fonts/docs/material_symbols
 */
export function MaterialIcon({
  name,
  size = 24,
  fill = 0, // 0 = outlined, 1 = filled
  weight = 400, // 100-700 (thin to bold)
  grade = 0, // -25 to 200 (thinner to thicker)
  className = '',
  style = {},
  ...props
}) {
  return (
    <span
      className={`material-symbols-outlined ${className}`}
      style={{
        fontSize: `${size}px`,
        fontVariationSettings: `'FILL' ${fill}, 'wght' ${weight}, 'GRAD' ${grade}, 'opsz' ${size}`,
        display: 'inline-flex',
        alignItems: 'center',
        ...style,
      }}
      {...props}
    >
      {name}
    </span>
  );
}

MaterialIcon.propTypes = {
  name: PropTypes.string.isRequired,
  size: PropTypes.number,
  fill: PropTypes.oneOf([0, 1]),
  weight: PropTypes.number,
  grade: PropTypes.number,
  className: PropTypes.string,
  style: PropTypes.object,
};

MaterialIcon.defaultProps = {
  size: 24,
  fill: 0,
  weight: 400,
  grade: 0,
  className: '',
  style: {},
};
