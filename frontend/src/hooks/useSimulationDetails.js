import { useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchApi } from '@api/client';
import { useMemo } from 'react';

export function useSimulationDetails(simulationId) {
  const queryClient = useQueryClient();

  // Fetch simulation details
  const {
    data: details,
    isLoading: loading,
    error,
    refetch,
  } = useQuery({
    queryKey: ['simulation-details', simulationId],
    queryFn: () => fetchApi(`/simulations/${simulationId}`),
    enabled: !!simulationId,
  });

  // Poll status while simulation is running
  const { data: statusData } = useQuery({
    queryKey: ['simulation-status', simulationId],
    queryFn: async () => {
      const data = await fetchApi(`/simulations/${simulationId}/status`);
      // Refetch details when status changes to completed
      if (data.status === 'completed' && details?.status !== 'completed') {
        queryClient.invalidateQueries({ queryKey: ['simulation-details', simulationId] });
      }
      return data;
    },
    enabled: !!simulationId && details?.status === 'running',
    refetchInterval: 2000,
  });

  const status = statusData?.status ?? details?.status ?? null;

  const isMultiStrategy = useMemo(
    () => details?.config?.simulation_strategies?.length > 1,
    [details]
  );

  const strategyGroups = useMemo(() => {
    if (!isMultiStrategy) return null;
    return details.config.simulation_strategies.reduce((groups, strategy, index) => {
      const key = strategy.aggregation_strategy_keyword || 'fedavg';
      if (!groups[key]) {
        groups[key] = [];
      }
      groups[key].push({ ...strategy, index });
      return groups;
    }, {});
  }, [details, isMultiStrategy]);

  return {
    details,
    status,
    loading,
    error: error?.message,
    refetch,
    isMultiStrategy,
    strategyGroups,
  };
}
