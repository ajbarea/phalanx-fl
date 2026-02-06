import { useState, useEffect, useCallback, useRef } from 'react';
import { useQuery, useQueries, useQueryClient } from '@tanstack/react-query';
import { fetchApi } from '@api/client';

const TERMINAL_STATUSES = ['completed', 'failed', 'stopped'];

/**
 * SSE hook for real-time simulation status and output streaming.
 *
 * @param {string|null} simulationId - The simulation ID to stream, or null to disable
 * @param {Object} [options]
 * @param {function} [options.onOutput] - Callback receiving new output text chunks
 * @returns {Object} Status data and connection state
 */
export function useSimulationStatusSSE(simulationId, { onOutput } = {}) {
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
  const onOutputRef = useRef(onOutput);

  // Ref avoids reconnecting SSE when onOutput callback identity changes
  useEffect(() => {
    onOutputRef.current = onOutput;
  }, [onOutput]);

  const connect = useCallback(() => {
    if (!simulationId) return;

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

    eventSource.addEventListener('status', event => {
      try {
        const data = JSON.parse(event.data);
        setStatus(data.status);
        setProgress(data.progress ?? 0);
        setCurrentRound(data.current_round ?? null);
        setTotalRounds(data.total_rounds ?? null);
        setCurrentStrategy(data.current_strategy ?? null);
        setTotalStrategies(data.total_strategies ?? null);
        setError(null);
      } catch (e) {
        console.error('SSE status parse error:', e);
      }
    });

    // Server sends "done" after the final output flush on terminal status.
    // Close only here so no trailing output events are lost.
    eventSource.addEventListener('done', () => {
      queryClient.invalidateQueries({
        queryKey: ['simulation-details', simulationId],
      });
      queryClient.invalidateQueries({
        queryKey: ['simulations'],
      });
      eventSource.close();
      setIsConnected(false);
    });

    eventSource.addEventListener('output', event => {
      try {
        const data = JSON.parse(event.data);
        if (data.text && onOutputRef.current) {
          onOutputRef.current(data.text);
        }
      } catch (e) {
        console.error('SSE output parse error:', e);
      }
    });

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
 * Polling-based status hook for batch simulation status fetching.
 *
 * Best suited for list views (e.g. Dashboard) where multiple simulations
 * need status updates without opening an SSE connection per card.
 *
 * @param {string|Array} simulationIdOrSimulations - Single ID or array of simulation objects
 * @param {Object} options - Configuration options
 * @param {number} options.interval - Polling interval in ms (default: 2000)
 * @returns {Object} Status data
 */
export function useSimulationStatus(simulationIdOrSimulations, options = {}) {
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

  const data = singleQuery.data;
  return {
    status: data?.status ?? null,
    progress: data?.progress ?? 0,
    currentRound: data?.current_round ?? null,
    totalRounds: data?.total_rounds ?? null,
    currentStrategy: data?.current_strategy ?? null,
    totalStrategies: data?.total_strategies ?? null,
    error: data?.error ?? singleQuery.error?.message ?? null,
    refetch: singleQuery.refetch,
  };
}
