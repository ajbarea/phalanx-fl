import { useState, useEffect } from 'react';
import { fetchApi } from '@api/client';

/**
 * Real-time HuggingFace dataset validation hook
 *
 * Debounces validation requests to avoid API spam
 * Returns validation status with loading, valid, compatible, info, error fields
 *
 * @param {string} datasetName - HuggingFace dataset identifier
 * @returns {Object} { loading, valid, compatible, info, error }
 */
export function useDatasetValidation(datasetName) {
  const [status, setStatus] = useState({
    loading: false,
    valid: null,
    compatible: null,
    info: null,
    error: null,
  });

  useEffect(() => {
    // Don't validate empty or very short strings
    if (!datasetName || datasetName.length < 3) {
      setStatus({ loading: false, valid: null, compatible: null, info: null, error: null });
      return;
    }

    // Debounce validation by 500ms
    const timeoutId = setTimeout(async () => {
      setStatus(prev => ({ ...prev, loading: true }));

      try {
        const data = await fetchApi(`/datasets/validate?name=${encodeURIComponent(datasetName)}`);
        setStatus({
          loading: false,
          valid: data.valid,
          compatible: data.compatible,
          info: data.info,
          error: data.error,
        });
      } catch {
        setStatus({
          loading: false,
          valid: false,
          compatible: false,
          info: null,
          error: 'Validation request failed',
        });
      }
    }, 500);

    return () => clearTimeout(timeoutId);
  }, [datasetName]);

  return status;
}
