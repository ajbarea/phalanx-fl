import { useState, useEffect, useRef } from 'react';
import { getResultFile } from '@api/endpoints/simulations';

export function useCSVData(simulationId, resultFiles, status) {
  const [csvData, setCsvData] = useState({});
  const [loading, setLoading] = useState(false);
  const isMountedRef = useRef(true);

  useEffect(() => {
    isMountedRef.current = true;

    if (!resultFiles) return;

    const csvFiles = resultFiles.filter(file => file.endsWith('.csv'));
    if (csvFiles.length === 0) return;

    setLoading(true);

    Promise.all(
      csvFiles.map(async file => {
        try {
          const response = await getResultFile(simulationId, file);
          return { file, data: response.data };
        } catch {
          return { file, data: null };
        }
      })
    ).then(results => {
      if (!isMountedRef.current) return;

      const newData = results.reduce(
        (acc, { file, data }) => (data ? { ...acc, [file]: data } : acc),
        {}
      );
      setCsvData(newData);
      setLoading(false);
    });

    return () => {
      isMountedRef.current = false;
    };
  }, [simulationId, resultFiles, status]);

  return { csvData, loading };
}
