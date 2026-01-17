import { useQuery } from '@tanstack/react-query';
import { fetchApi } from '@api/client';
import { useMemo } from 'react';
import { POLLING_INTERVALS } from '@constants/ui';

export function useQueueStatus(simulationId) {
  const {
    data: simulation,
    isPending: detailsLoading,
    error: detailsError,
  } = useQuery({
    queryKey: ['simulation-details', simulationId],
    queryFn: () => fetchApi(`/simulations/${simulationId}`),
    enabled: !!simulationId,
    refetchInterval: POLLING_INTERVALS.SIMULATIONS,
  });

  const {
    data: status,
    isPending: statusLoading,
    error: statusError,
  } = useQuery({
    queryKey: ['simulation-status', simulationId],
    queryFn: () => fetchApi(`/simulations/${simulationId}/status`),
    enabled: !!simulationId,
    refetchInterval: POLLING_INTERVALS.SIMULATIONS,
  });

  const progress = useMemo(() => {
    if (!simulation?.config?.simulation_strategies || !status) {
      return { current: 0, total: 1, strategies: [] };
    }

    const totalStrategies = simulation.config.simulation_strategies.length;
    const resultFiles = simulation.result_files || [];

    const completedStrategies = [];
    for (let i = 0; i < totalStrategies; i++) {
      const hasResults = resultFiles.some(f => f.includes(`csv/round_metrics_${i}.csv`));
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

      const strategyData = {
        index,
        config: strat,
        status: stratStatus,
      };

      // Enrich with real-time progress if this is the active strategy
      if (stratStatus === 'running') {
        strategyData.progress = status.progress;
        strategyData.currentRound = status.current_round;
        strategyData.totalRounds = status.total_rounds;
      }

      return strategyData;
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
