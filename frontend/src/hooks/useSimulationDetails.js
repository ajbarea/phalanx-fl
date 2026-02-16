import { useQuery } from '@tanstack/react-query';
import { fetchApi } from '@api/client';
import { useMemo, useEffect, useRef, useState, useCallback } from 'react';
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

  const [output, setOutput] = useState('');

  const handleOutput = useCallback(text => {
    setOutput(prev => prev + text);
  }, []);

  useEffect(() => {
    setOutput('');
  }, [simulationId]);

  const {
    status: sseStatus,
    progress: sseProgress,
    currentRound: currentRoundSse,
    totalRounds: totalRoundsSse,
    currentStrategy: currentStrategySse,
    totalStrategies: totalStrategiesSse,
    isConnected: isStreaming,
  } = useSimulationStatusSSE(shouldStream ? simulationId : null, {
    onOutput: handleOutput,
  });

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

  const detailsStatus =
    typeof details?.status === 'string' ? details.status : (details?.status?.status ?? null);
  const status = sseStatus ?? detailsStatus ?? null;
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

  const strategyProgress = useMemo(() => {
    if (!isMultiStrategy || !details) return null;

    const totalStrats = details.config.simulation_strategies.length;
    const resultFiles = details.result_files || [];

    const completedIndices = [];
    for (let i = 0; i < totalStrats; i++) {
      if (resultFiles.some(f => f.includes(`csv/round_metrics_${i}.csv`))) {
        completedIndices.push(i);
      }
    }

    const currentIdx = completedIndices.length;
    const isComplete = currentIdx >= totalStrats;

    const strategies = details.config.simulation_strategies.map((strat, index) => {
      let stratStatus = 'queued';
      if (completedIndices.includes(index)) {
        stratStatus = 'completed';
      } else if (index === currentIdx && status === 'running') {
        stratStatus = 'running';
      } else if (status === 'failed') {
        stratStatus = 'failed';
      }

      const data = { index, config: strat, status: stratStatus };
      if (stratStatus === 'running') {
        data.progress = progress;
        data.currentRound = currentRound;
        data.totalRounds = totalRounds;
      }
      return data;
    });

    return {
      current: currentIdx,
      total: totalStrats,
      strategies,
      isComplete: isComplete && status === 'completed',
    };
  }, [isMultiStrategy, details, status, progress, currentRound, totalRounds]);

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
    strategyProgress,
    isStreaming,
    output,
  };
}
