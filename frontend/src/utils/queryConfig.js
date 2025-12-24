/**
 * Centralized TanStack Query configuration utilities.
 * Provides consistent query options across the application.
 */

import { POLLING_INTERVALS, CACHE_DURATION } from '@constants/ui';

/**
 * Default query configuration for simulation list polling.
 * Used for pages that need to poll simulation status.
 * @param {boolean} [enabled=true] - Whether the query is enabled
 * @returns {Object} Query configuration object
 */
export function getSimulationListQueryConfig(enabled = true) {
  return {
    refetchInterval: POLLING_INTERVALS.SIMULATIONS,
    enabled,
    retry: 1,
    refetchOnWindowFocus: true,
  };
}

/**
 * Query configuration for individual simulation status polling.
 * Faster polling for active simulation monitoring.
 * @param {boolean} [enabled=true] - Whether the query is enabled
 * @returns {Object} Query configuration object
 */
export function getSimulationStatusQueryConfig(enabled = true) {
  return {
    refetchInterval: POLLING_INTERVALS.SIMULATION_DETAILS,
    enabled,
    retry: 1,
  };
}

/**
 * Query configuration for static/rarely-changing data.
 * Uses longer cache times and no polling.
 * @param {boolean} [enabled=true] - Whether the query is enabled
 * @returns {Object} Query configuration object
 */
export function getStaticDataQueryConfig(enabled = true) {
  return {
    staleTime: CACHE_DURATION.FIVE_MINUTES,
    gcTime: CACHE_DURATION.FIVE_MINUTES * 2,
    enabled,
    retry: 1,
    refetchOnWindowFocus: false,
  };
}

/**
 * Query configuration for data that changes moderately.
 * Balanced between freshness and performance.
 * @param {boolean} [enabled=true] - Whether the query is enabled
 * @returns {Object} Query configuration object
 */
export function getModerateDataQueryConfig(enabled = true) {
  return {
    staleTime: CACHE_DURATION.ONE_MINUTE,
    gcTime: CACHE_DURATION.ONE_MINUTE * 2,
    enabled,
    retry: 2,
    refetchOnWindowFocus: true,
  };
}
