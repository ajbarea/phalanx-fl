/**
 * Decimal precision for different metric types.
 */
export const METRIC_DECIMALS = {
  /** Accuracy percentages (e.g., 99.5%) */
  ACCURACY: 1,
  /** Detailed accuracy (e.g., 99.50%) */
  ACCURACY_DETAILED: 2,
  /** Whole percentages (e.g., 99%) */
  PERCENTAGE_WHOLE: 0,
  /** Loss values (e.g., 0.1234) */
  LOSS: 4,
  /** Time in milliseconds (e.g., 12.34ms) */
  TIME_MS: 2,
  /** Default precision */
  DEFAULT: 2,
};

/**
 * Formats a decimal (0-1) as a percentage string.
 * @param {number|null|undefined} value - Decimal value (0-1)
 * @param {number} [decimals=METRIC_DECIMALS.ACCURACY] - Decimal places
 * @returns {string} Formatted percentage or 'N/A'
 * @example formatAccuracy(0.9567) => '95.7%'
 * @example formatAccuracy(0.9567, 2) => '95.67%'
 */
export function formatAccuracy(value, decimals = METRIC_DECIMALS.ACCURACY) {
  if (value === null || value === undefined || isNaN(value)) {
    return 'N/A';
  }
  return `${(value * 100).toFixed(decimals)}%`;
}

/**
 * Formats a value that's already a percentage (0-100).
 * @param {number|null|undefined} value - Percentage value (0-100)
 * @param {number} [decimals=METRIC_DECIMALS.PERCENTAGE_WHOLE] - Decimal places
 * @returns {string} Formatted percentage or 'N/A'
 * @example formatPercentage(95.67) => '96%'
 * @example formatPercentage(95.67, 1) => '95.7%'
 */
export function formatPercentage(value, decimals = METRIC_DECIMALS.PERCENTAGE_WHOLE) {
  if (value === null || value === undefined || isNaN(value)) {
    return 'N/A';
  }
  return `${value.toFixed(decimals)}%`;
}

/**
 * Formats a loss value with high precision.
 * @param {number|null|undefined} value - Loss value
 * @param {number} [decimals=METRIC_DECIMALS.LOSS] - Decimal places
 * @returns {string} Formatted loss or 'N/A'
 * @example formatLoss(0.12345678) => '0.1235'
 */
export function formatLoss(value, decimals = METRIC_DECIMALS.LOSS) {
  if (value === null || value === undefined || isNaN(value)) {
    return 'N/A';
  }
  return value.toFixed(decimals);
}

/**
 * Formats a time value in milliseconds.
 * @param {number|null|undefined} value - Time in milliseconds
 * @param {number} [decimals=METRIC_DECIMALS.TIME_MS] - Decimal places
 * @returns {string} Formatted time with 'ms' suffix or 'N/A'
 * @example formatTimeMs(12.3456) => '12.35ms'
 */
export function formatTimeMs(value, decimals = METRIC_DECIMALS.TIME_MS) {
  if (value === null || value === undefined || isNaN(value)) {
    return 'N/A';
  }
  return `${value.toFixed(decimals)}ms`;
}

/**
 * Calculates and formats a percentage change (improvement/decline).
 * @param {number} initial - Initial value
 * @param {number} final - Final value
 * @param {number} [decimals=METRIC_DECIMALS.ACCURACY] - Decimal places
 * @returns {string} Formatted change percentage or 'N/A'
 * @example formatChange(0.5, 0.75) => '50.0'
 */
export function formatChange(initial, final, decimals = METRIC_DECIMALS.ACCURACY) {
  if (
    initial === null ||
    initial === undefined ||
    final === null ||
    final === undefined ||
    initial === 0
  ) {
    return 'N/A';
  }
  const change = ((final - initial) / initial) * 100;
  return change.toFixed(decimals);
}

/**
 * Safely formats accuracy, returning dash for zero/invalid values.
 * Useful for detection metrics that may be zero.
 * @param {number|null|undefined} value - Decimal value (0-1)
 * @param {number} [decimals=METRIC_DECIMALS.PERCENTAGE_WHOLE] - Decimal places
 * @returns {string} Formatted percentage, '—' for zero, or 'N/A'
 */
export function formatDetectionMetric(value, decimals = METRIC_DECIMALS.PERCENTAGE_WHOLE) {
  if (value === null || value === undefined || isNaN(value) || value === 0) {
    return '—';
  }
  return `${(value * 100).toFixed(decimals)}%`;
}

export const getRelativeTime = timestamp => {
  if (!timestamp) return '';
  const now = new Date();
  const then = new Date(timestamp);
  const diffMs = now - then;
  const diffSecs = Math.floor(diffMs / 1000);
  const diffMins = Math.floor(diffSecs / 60);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffSecs < 60) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return then.toLocaleDateString();
};

export const parseErrorMessage = errorText => {
  if (!errorText) return 'Unknown error occurred';

  if (errorText.includes('is a required property')) {
    const match = errorText.match(/'([^']+)' is a required property/);
    const field = match ? match[1] : 'field';
    return `Configuration Error: Missing required field '${field}'`;
  }

  if (errorText.includes('Error while loading config')) {
    return 'Configuration Error: Invalid or incomplete configuration';
  }

  if (errorText.includes('is not one of')) {
    const match = errorText.match(/'([^']+)' is not one of/);
    const value = match ? match[1] : 'value';
    return `Configuration Error: Invalid value '${value}'`;
  }

  const lines = errorText.split('\n');
  const firstMeaningfulLine = lines.find(
    line => line.includes('ERROR') || line.includes('Error') || line.trim().length > 0
  );

  if (firstMeaningfulLine) {
    return firstMeaningfulLine
      .replace(/^ERROR:root:/i, '')
      .replace(/^ERROR:/i, '')
      .trim();
  }

  return 'An error occurred during simulation';
};
