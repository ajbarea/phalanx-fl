/**
 * Centralized localStorage key definitions.
 * All localStorage access should use these constants for consistency.
 */
export const STORAGE_KEYS = {
  /** User's preferred color theme ('light' | 'dark') */
  THEME: 'theme',
  /** Draft simulation configuration JSON */
  SIMULATION_DRAFT: 'simulation-draft',
  /** Flag indicating user has been notified about GPU availability */
  GPU_NOTIFIED: 'fl_gpu_notified',
};
