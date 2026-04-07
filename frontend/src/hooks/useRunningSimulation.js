import { useQuery } from '@tanstack/react-query';
import { fetchApi } from '@api/client';
import { POLLING_INTERVALS } from '@constants/ui';

/**
 * Hook to detect if any simulation is currently running or queued.
 * Uses the /api/queue/status endpoint for aggregate counts.
 */
export function useRunningSimulation() {
  const {
    data: queueStatus,
    isPending: loading,
    error,
  } = useQuery({
    queryKey: ['queue-status'],
    queryFn: () => fetchApi('/queue/status'),
    refetchInterval: POLLING_INTERVALS.RUNNING_CHECK,
  });

  // Derive state from aggregate response
  const hasRunning = queueStatus ? queueStatus.running > 0 || queueStatus.queued > 0 : false;

  return {
    hasRunning,
    queueStatus,
    loading,
    error: error?.message || null,
  };
}
