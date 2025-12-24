export const copyCSVToClipboard = (jsonData, filename, showSuccess, showError) => {
  try {
    if (!jsonData || jsonData.length === 0) {
      if (showError) {
        showError('No data to copy');
      }
      return;
    }

    const columns = Object.keys(jsonData[0]);
    const header = columns.join(',');
    const rows = jsonData.map(row =>
      columns
        .map(col => {
          const value = row[col];
          // Escape values containing commas or quotes
          if (typeof value === 'string' && (value.includes(',') || value.includes('"'))) {
            return `"${value.replace(/"/g, '""')}"`;
          }
          return value;
        })
        .join(',')
    );
    const csvString = [header, ...rows].join('\n');

    navigator.clipboard.writeText(csvString).then(
      () => {
        if (showSuccess) {
          showSuccess(`Copied ${filename} to clipboard!`);
        }
      },
      () => {
        if (showError) {
          showError('Failed to copy to clipboard. Please try again.');
        }
      }
    );
  } catch {
    if (showError) {
      showError('Failed to copy to clipboard. Please try again.');
    }
  }
};

export const parseCSV = csvString => {
  const lines = csvString.trim().split('\n');
  if (lines.length === 0) return [];

  const headers = lines[0].split(',');
  const data = [];

  for (let i = 1; i < lines.length; i++) {
    const values = lines[i].split(',');
    const row = {};
    headers.forEach((header, index) => {
      row[header] = values[index];
    });
    data.push(row);
  }

  return data;
};

/**
 * Filters out columns that contain only "not collected" values
 * @param {Array} data - Array of row objects
 * @returns {Array} Filtered columns array
 */
export const filterEmptyColumns = data => {
  if (!data || data.length === 0) return [];

  const allColumns = Object.keys(data[0]);

  return allColumns.filter(col => {
    return !data.every(row => row[col] === 'not collected');
  });
};

/**
 * Formats column names to be more readable
 * @param {string} columnName - Original column name
 * @returns {string} Formatted column name
 */
export const formatColumnName = columnName => {
  if (columnName.toLowerCase() === 'round #') {
    return 'Round';
  }

  return columnName
    .replace(/_history$/i, '')
    .replace(/_/g, ' ')
    .split(' ')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
    .replace(/\bAverage\b/g, 'Avg')
    .replace(/\bTp\b/g, 'TP')
    .replace(/\bTn\b/g, 'TN')
    .replace(/\bFp\b/g, 'FP')
    .replace(/\bFn\b/g, 'FN')
    .replace(/\bF1\b/g, 'F1')
    .replace(/\bNanos\b/g, '(ns)');
};
