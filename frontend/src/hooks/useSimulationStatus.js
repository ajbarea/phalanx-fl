import { useQuery, useQueries } from '@tanstack/react-query';
import { fetchApi } from '@api/client';

export function useSimulationStatus(simulationIdOrSimulations, options = {}) {
  // Handle both single simulation (string) and multiple simulations (array)
  const isMultiple = Array.isArray(simulationIdOrSimulations);
  const interval = options.interval || 2000;

  // Single simulation status query
  const singleQuery = useQuery({
    queryKey: ['simulation-status', simulationIdOrSimulations],
    queryFn: () => fetchApi(`/simulations/${simulationIdOrSimulations}/status`),
    enabled: !isMultiple && !!simulationIdOrSimulations,
    refetchInterval: query => (query.state.data?.status === 'running' ? interval : false),
  });

  // Multiple simulations status queries
  const multiQueries = useQueries({
    queries: isMultiple
      ? simulationIdOrSimulations.map(sim => ({
          queryKey: ['simulation-status', sim.simulation_id],
          queryFn: () => fetchApi(`/simulations/${sim.simulation_id}/status`),
          enabled: !!sim.simulation_id,
          refetchInterval: query => (query.state.data?.status === 'running' ? interval : false),
        }))
      : [],
  });

  if (isMultiple) {
    // Build statuses object from parallel queries
    const statuses = simulationIdOrSimulations.reduce((acc, sim, index) => {
      const query = multiQueries[index];
      acc[sim.simulation_id] = query?.data ?? { status: 'unknown' };
      return acc;
    }, {});

    const hasError = multiQueries.some(q => q.error);

    return {
      statuses,
      error: hasError ? 'Failed to fetch some statuses' : null,
      refetch: () => multiQueries.forEach(q => q.refetch()),
    };
  }

  return {
    status: singleQuery.data ?? null,
    error: singleQuery.error?.message ?? null,
    refetch: singleQuery.refetch,
  };
}
