/**
 * Centralized localStorage key definitions.
 * All localStorage access should use these constants for consistency.
 */
export const STORAGE_KEYS = {
  /** User's preferred color theme ('light' | 'dark') */
  THEME: 'theme',
  /** Draft simulation configuration JSON */
  SIMULATION_DRAFT: 'simulation-draft',
  /** Source of draft data: 'user-input' | 'preset' | null */
  DRAFT_SOURCE: 'simulation-draft-source',
  /** Timestamp when draft was last saved */
  DRAFT_TIMESTAMP: 'simulation-draft-timestamp',
  /** Flag indicating user has been notified about GPU availability */
  GPU_NOTIFIED: 'fl_gpu_notified',
  /** User's device configuration settings (training_device, cpus/gpus per client) */
  DEVICE_SETTINGS: 'fl_device_settings',
};
