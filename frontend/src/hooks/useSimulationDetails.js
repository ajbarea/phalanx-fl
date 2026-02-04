import { useQuery } from '@tanstack/react-query';
import { fetchApi } from '@api/client';
import { useMemo, useEffect, useRef } from 'react';
import { useSimulationStatusSSE } from './useSimulationStatus';

const TERMINAL_STATUSES = ['completed', 'failed', 'stopped'];

export function useSimulationDetails(simulationId) {
  const {
    data: details,
    isPending: loading,
    error,
    refetch,
  } = useQuery({
    queryKey: ['simulation-details', simulationId],
    queryFn: () => fetchApi(`/simulations/${simulationId}`),
    enabled: !!simulationId,
  });

  const shouldStream = useMemo(() => {
    if (!simulationId) return false;
    const currentStatus = details?.status;
    return !currentStatus || !TERMINAL_STATUSES.includes(currentStatus);
  }, [simulationId, details?.status]);

  const {
    status: sseStatus,
    progress: sseProgress,
    currentRound: currentRoundSse,
    totalRounds: totalRoundsSse,
    currentStrategy: currentStrategySse,
    totalStrategies: totalStrategiesSse,
    isConnected: isStreaming,
  } = useSimulationStatusSSE(shouldStream ? simulationId : null);

  const prevSseStatusRef = useRef(null);
  useEffect(() => {
    if (
      sseStatus &&
      TERMINAL_STATUSES.includes(sseStatus) &&
      prevSseStatusRef.current !== sseStatus
    ) {
      prevSseStatusRef.current = sseStatus;
      const timer = setTimeout(() => refetch(), 1500);
      return () => clearTimeout(timer);
    }
  }, [sseStatus, refetch]);

  const status = sseStatus ?? details?.status ?? null;
  const progress = sseProgress ?? details?.progress ?? 0;
  const currentRound = currentRoundSse ?? details?.current_round ?? null;
  const totalRounds = totalRoundsSse ?? details?.total_rounds ?? null;
  const currentStrategy = currentStrategySse ?? details?.current_strategy ?? null;
  const totalStrategies = totalStrategiesSse ?? details?.total_strategies ?? null;

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
    progress,
    currentRound,
    totalRounds,
    currentStrategy,
    totalStrategies,
    loading,
    error: error?.message,
    refetch,
    isMultiStrategy,
    strategyGroups,
    isStreaming,
  };
}
