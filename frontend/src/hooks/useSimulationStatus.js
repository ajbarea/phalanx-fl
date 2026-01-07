import { useState, useEffect, useCallback, useRef } from 'react';
import { useQuery, useQueries, useQueryClient } from '@tanstack/react-query';
import { fetchApi } from '@api/client';

/**
 * Terminal statuses that indicate simulation has finished.
 * When reached, SSE stream will close and polling should stop.
 */
const TERMINAL_STATUSES = ['completed', 'failed', 'stopped'];

/**
 * SSE hook for real-time simulation status updates.
 *
 * Uses Server-Sent Events for efficient, low-latency status streaming.
 * Automatically reconnects on connection loss (browser built-in).
 * Closes connection when simulation reaches terminal state.
 *
 * Benefits over polling:
 * - Sub-second updates (vs 2-5 second polling intervals)
 * - Lower bandwidth (5 bytes/message vs ~500 bytes/request)
 * - No race conditions between poll intervals
 * - Auto-reconnection built into EventSource API
 *
 * @param {string|null} simulationId - The simulation ID to stream, or null to disable
 * @returns {Object} Status data and connection state
 */
export function useSimulationStatusSSE(simulationId) {
  const [status, setStatus] = useState(null);
  const [progress, setProgress] = useState(0);
  const [currentRound, setCurrentRound] = useState(null);
  const [totalRounds, setTotalRounds] = useState(null);
  const [currentStrategy, setCurrentStrategy] = useState(null);
  const [totalStrategies, setTotalStrategies] = useState(null);
  const [error, setError] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  const queryClient = useQueryClient();
  const eventSourceRef = useRef(null);

  const connect = useCallback(() => {
    if (!simulationId) return;

    // Close existing connection before creating new one
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }

    const eventSource = new EventSource(`/api/simulations/${simulationId}/stream`);
    eventSourceRef.current = eventSource;

    eventSource.onopen = () => {
      setIsConnected(true);
      setError(null);
    };

    eventSource.onmessage = event => {
      try {
        const data = JSON.parse(event.data);
        setStatus(data.status);
        setProgress(data.progress ?? 0);
        setCurrentRound(data.current_round ?? null);
        setTotalRounds(data.total_rounds ?? null);
        setCurrentStrategy(data.current_strategy ?? null);
        setTotalStrategies(data.total_strategies ?? null);
        setError(null);

        // When terminal status is reached:
        // 1. Invalidate cached queries to trigger refetch with final data
        // 2. Close the SSE connection (server also closes, but be explicit)
        if (TERMINAL_STATUSES.includes(data.status)) {
          queryClient.invalidateQueries({
            queryKey: ['simulation-details', simulationId],
          });
          queryClient.invalidateQueries({
            queryKey: ['simulations'],
          });
          eventSource.close();
          setIsConnected(false);
        }
      } catch (e) {
        console.error('SSE parse error:', e);
      }
    };

    eventSource.onerror = () => {
      setIsConnected(false);
      // EventSource auto-reconnects on transient errors
      // Only set error if connection is permanently closed
      if (eventSource.readyState === EventSource.CLOSED) {
        setError('Connection closed');
      }
    };
  }, [simulationId, queryClient]);

  useEffect(() => {
    connect();

    // Cleanup: close EventSource on unmount or simulationId change
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };
  }, [connect]);

  return {
    status,
    progress,
    currentRound,
    totalRounds,
    currentStrategy,
    totalStrategies,
    error,
    isConnected,
  };
}

/**
 * Legacy polling-based status hook.
 *
 * Kept for backwards compatibility and fallback scenarios.
 * For single simulation status, prefer useSimulationStatusSSE.
 *
 * @param {string|Array} simulationIdOrSimulations - Single ID or array of simulation objects
 * @param {Object} options - Configuration options
 * @param {number} options.interval - Polling interval in ms (default: 2000)
 * @returns {Object} Status data
 */
export function useSimulationStatus(simulationIdOrSimulations, options = {}) {
  // Handle both single simulation (string) and multiple simulations (array)
  const isMultiple = Array.isArray(simulationIdOrSimulations);
  const interval = options.interval || 2000;

  const singleQuery = useQuery({
    queryKey: ['simulation-status', simulationIdOrSimulations],
    queryFn: () => fetchApi(`/simulations/${simulationIdOrSimulations}/status`),
    enabled: !isMultiple && !!simulationIdOrSimulations,
    refetchInterval: query => (query.state.data?.status === 'running' ? interval : false),
  });

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
    const statuses = simulationIdOrSimulations.reduce((acc, sim, index) => {
      const query = multiQueries[index];
      acc[sim.simulation_id] = query?.data ?? { status: 'loading' };
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
