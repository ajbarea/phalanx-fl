import { useQuery, useQueries } from '@tanstack/react-query';
import { fetchApi } from '@api/client';
import { POLLING_INTERVALS } from '@constants/ui';

// Helper to fetch config and status for a simulation
async function fetchSimDetails(sim) {
  const [status, config] = await Promise.all([
    fetchApi(`/simulations/${sim.simulation_id}/status`).catch(() => null),
    fetchApi(`/simulations/${sim.simulation_id}/config`).catch(() => null),
  ]);
  return {
    ...sim,
    status,
    config,
  };
}

export function useSimulations() {
  // Fetch the list of simulations
  const {
    data: simulationsRaw = [],
    isPending: loading,
    error,
    refetch,
  } = useQuery({
    queryKey: ['simulations'],
    queryFn: () => fetchApi('/simulations'),
    refetchInterval: POLLING_INTERVALS.SIMULATIONS,
  });

  // Fetch config and status for each simulation
  const detailsQueries = useQueries({
    queries: simulationsRaw.map(sim => ({
      queryKey: ['simulation-list-item', sim.simulation_id],
      queryFn: () => fetchSimDetails(sim),
      enabled: !!sim.simulation_id,
      refetchInterval: POLLING_INTERVALS.SIMULATIONS,
    })),
  });

  // Merge details into a single array
  const simulations = detailsQueries.map(q => q.data).filter(Boolean);

  // Build statuses map for compatibility
  const statuses = simulations.reduce((acc, sim) => {
    acc[sim.simulation_id] = sim.status || { status: 'unknown' };
    return acc;
  }, {});

  return {
    simulations,
    statuses,
    loading,
    error: error?.message,
    refetch,
  };
}
