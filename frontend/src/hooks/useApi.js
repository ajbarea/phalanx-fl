import { useState, useEffect, useCallback, useRef } from 'react';
import { getErrorMessage } from '../utils/errorMessages';

/**
 * Generic API hook for data fetching with user-friendly error handling.
 *
 * @param {Function} apiFunc - The API function to call
 * @param {...any} args - Arguments to pass to the API function
 * @returns {Object} { data, loading, error, refetch }
 */
const useApi = (apiFunc, ...args) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Serialize args to detect changes (handles primitives, arrays, objects)
  const argsKey = JSON.stringify(args);
  const argsRef = useRef(args);
  argsRef.current = args;

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiFunc(...argsRef.current);
      setData(response.data);
    } catch (err) {
      setError(getErrorMessage(err));
    }
    setLoading(false);
    // argsKey is intentional - triggers refetch when serialized args change
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiFunc, argsKey]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return { data, loading, error, refetch: fetchData };
};

export default useApi;
