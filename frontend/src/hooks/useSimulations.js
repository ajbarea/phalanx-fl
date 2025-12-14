import { useQuery, useQueries } from '@tanstack/react-query';
import { fetchApi } from '@api/client';

export function useSimulations() {
  // Fetch all simulations
  const {
    data: simulations = [],
    isLoading: loading,
    error,
    refetch,
  } = useQuery({
    queryKey: ['simulations'],
    queryFn: () => fetchApi('/simulations'),
    refetchInterval: 5000, // Poll every 5 seconds
  });

  // Fetch statuses for all simulations in parallel
  const statusQueries = useQueries({
    queries: simulations.map(sim => ({
      queryKey: ['simulation-status', sim.simulation_id],
      queryFn: () => fetchApi(`/simulations/${sim.simulation_id}/status`),
      enabled: !!sim.simulation_id,
      refetchInterval: 5000,
    })),
  });

  // Build statuses object from parallel queries
  const statuses = simulations.reduce((acc, sim, index) => {
    const query = statusQueries[index];
    acc[sim.simulation_id] = query?.data ?? { status: 'unknown' };
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
