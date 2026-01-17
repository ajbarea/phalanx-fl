import { useQuery } from '@tanstack/react-query';
import { fetchApi } from '@api/client';
import { useMemo } from 'react';
import { useSimulationStatusSSE } from './useSimulationStatus';

/**
 * Terminal statuses that indicate simulation has finished.
 */
const TERMINAL_STATUSES = ['completed', 'failed', 'stopped'];

/**
 * Hook for fetching simulation details with real-time status updates via SSE.
 *
 * This hook combines:
 * 1. React Query for fetching simulation configuration and metadata
 * 2. Server-Sent Events (SSE) for real-time status streaming
 *
 * The SSE connection:
 * - Opens automatically for non-terminal simulations
 * - Streams status updates in real-time
 * - Closes automatically when simulation reaches terminal state
 * - Triggers cache invalidation on completion for fresh data
 *
 * @param {string} simulationId - The simulation ID to fetch details for
 * @returns {Object} Simulation details, status, and helper properties
 */
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
    // Only stream if simulation exists and is not in a terminal state
    if (!simulationId) return false;
    const currentStatus = details?.status;
    // Stream if no status yet (initial load), or if not in terminal state
    return !currentStatus || !TERMINAL_STATUSES.includes(currentStatus);
  }, [simulationId, details?.status]);

  // Use SSE for real-time status updates (replaces polling)
  const {
    status: sseStatus,
    progress: sseProgress,
    currentRound: currentRoundSse,
    totalRounds: totalRoundsSse,
    currentStrategy: currentStrategySse,
    totalStrategies: totalStrategiesSse,
    isConnected: isStreaming,
  } = useSimulationStatusSSE(shouldStream ? simulationId : null);

  // SSE status takes priority over cached details status
  // This ensures UI reflects real-time state without waiting for refetch
  // SSE values take priority, fallback to cached details
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

  // Group strategies by aggregation algorithm for UI organization
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
    // Core data
    details,
    status,
    progress,
    currentRound,
    totalRounds,
    currentStrategy,
    totalStrategies,

    // Loading/error states
    loading,
    error: error?.message,
    refetch,

    // Multi-strategy helpers
    isMultiStrategy,
    strategyGroups,

    // SSE connection state (useful for debugging/UI indicators)
    isStreaming,
  };
}
