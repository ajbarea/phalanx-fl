import { useQuery, useQueries } from '@tanstack/react-query';
import { fetchApi } from '@api/client';
import { POLLING_INTERVALS } from '@constants/ui';

export function useSimulations() {
  const {
    data: simulations = [],
    isPending: loading,
    error,
    refetch,
  } = useQuery({
    queryKey: ['simulations'],
    queryFn: () => fetchApi('/simulations'),
    refetchInterval: POLLING_INTERVALS.SIMULATIONS,
  });

  const statusQueries = useQueries({
    queries: simulations.map(sim => ({
      queryKey: ['simulation-status', sim.simulation_id],
      queryFn: () => fetchApi(`/simulations/${sim.simulation_id}/status`),
      enabled: !!sim.simulation_id,
      refetchInterval: POLLING_INTERVALS.SIMULATIONS,
    })),
  });

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
