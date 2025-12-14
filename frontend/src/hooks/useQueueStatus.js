import { useQuery } from '@tanstack/react-query';
import { fetchApi } from '@api/client';
import { useMemo } from 'react';

export function useQueueStatus(simulationId) {
  // Fetch simulation details
  const {
    data: simulation,
    isLoading: detailsLoading,
    error: detailsError,
  } = useQuery({
    queryKey: ['simulation-details', simulationId],
    queryFn: () => fetchApi(`/simulations/${simulationId}`),
    enabled: !!simulationId,
    refetchInterval: 5000,
  });

  // Fetch simulation status
  const {
    data: status,
    isLoading: statusLoading,
    error: statusError,
  } = useQuery({
    queryKey: ['simulation-status', simulationId],
    queryFn: () => fetchApi(`/simulations/${simulationId}/status`),
    enabled: !!simulationId,
    refetchInterval: 5000,
  });

  const progress = useMemo(() => {
    if (!simulation?.config?.simulation_strategies || !status) {
      return { current: 0, total: 1, strategies: [] };
    }

    const totalStrategies = simulation.config.simulation_strategies.length;
    const resultFiles = simulation.result_files || [];

    const completedStrategies = [];
    for (let i = 0; i < totalStrategies; i++) {
      const hasResults = resultFiles.some((f) => f.includes(`csv/exec_stats_${i}.csv`));
      if (hasResults) {
        completedStrategies.push(i);
      }
    }

    const currentStrategy = completedStrategies.length;
    const isComplete = currentStrategy >= totalStrategies;

    const strategies = simulation.config.simulation_strategies.map((strat, index) => {
      let stratStatus = 'queued';
      if (completedStrategies.includes(index)) {
        stratStatus = 'completed';
      } else if (index === currentStrategy && status.status === 'running') {
        stratStatus = 'running';
      } else if (status.status === 'failed') {
        stratStatus = 'failed';
      }

      return {
        index,
        config: strat,
        status: stratStatus,
      };
    });

    return {
      current: currentStrategy,
      total: totalStrategies,
      strategies,
      isComplete: isComplete && status.status === 'completed',
    };
  }, [simulation, status]);

  return {
    simulation,
    status,
    progress,
    loading: detailsLoading || statusLoading,
    error: detailsError?.message || statusError?.message || null,
  };
}
