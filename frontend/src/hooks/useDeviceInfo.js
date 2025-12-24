import { useQuery } from '@tanstack/react-query';
import { getSystemDevices } from '@api';
import { CACHE_DURATION } from '@constants/ui';
import { STORAGE_KEYS } from '@constants/storage';

/**
 * Hook for detecting available training devices (CPU/GPU).
 * Caches device info for 5 minutes and manages GPU notification state.
 *
 * @returns {{
 *   gpuAvailable: boolean,
 *   gpuInfo: {name: string, vram_gb: number}|null,
 *   recommendedDevice: string,
 *   loading: boolean,
 *   hasBeenNotified: () => boolean,
 *   markNotified: () => void
 * }}
 */
export function useDeviceInfo() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['system-devices'],
    queryFn: getSystemDevices,
    staleTime: CACHE_DURATION.FIVE_MINUTES,
    gcTime: CACHE_DURATION.FIVE_MINUTES * 2, // gcTime must be >= staleTime
    retry: 1, // Single retry, then graceful fallback
    refetchOnWindowFocus: false, // Device info doesn't change on focus
  });

  const hasBeenNotified = () => localStorage.getItem(STORAGE_KEYS.GPU_NOTIFIED) === 'true';
  const markNotified = () => localStorage.setItem(STORAGE_KEYS.GPU_NOTIFIED, 'true');

  // Graceful fallback to CPU if error or no data
  return {
    gpuAvailable: data?.gpu_available ?? false,
    gpuInfo: data?.gpu_info ?? null,
    recommendedDevice: isError ? 'cpu' : (data?.recommended_device ?? 'cpu'),
    loading: isLoading,
    hasBeenNotified,
    markNotified,
  };
}
