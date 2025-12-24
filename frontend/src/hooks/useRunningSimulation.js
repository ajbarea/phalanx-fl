import { useState, useEffect } from 'react';
import { getSimulations, getSimulationStatus } from '@api/endpoints/simulations';
import { POLLING_INTERVALS } from '@constants/ui';

/**
 * Hook to detect if any simulation is currently running
 * Used for queue blocking logic to prevent concurrent simulations
 */
export function useRunningSimulation() {
  const [hasRunning, setHasRunning] = useState(false);
  const [runningSimIds, setRunningSimIds] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let intervalId;

    const checkRunning = async () => {
      try {
        const response = await getSimulations();
        const simulations = response.data;

        const statusPromises = simulations.map(sim =>
          getSimulationStatus(sim.simulation_id).catch(() => ({ data: { status: 'unknown' } }))
        );
        const statuses = await Promise.all(statusPromises);

        const running = simulations
          .filter((sim, i) => statuses[i].data.status === 'running')
          .map(sim => sim.simulation_id);

        setRunningSimIds(running);
        setHasRunning(running.length > 0);
        setError(null);
        setLoading(false);
      } catch (err) {
        setError(err.message || 'Failed to check running simulations');
        setLoading(false);
      }
    };

    checkRunning();
    intervalId = setInterval(checkRunning, POLLING_INTERVALS.RUNNING_CHECK);

    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, []);

  return {
    hasRunning,
    runningSimIds,
    loading,
    error,
  };
}
