import { createContext, useContext, useState, useCallback, useMemo } from 'react';
import { useDeviceInfo } from '@hooks/useDeviceInfo';
import { STORAGE_KEYS } from '@constants/storage';

const DeviceContext = createContext();

const DEFAULT_SETTINGS = {
  training_device: 'cpu',
  cpus_per_client: 1,
  gpus_per_client: 0,
};

const RECOMMENDED_GPU_SETTINGS = {
  training_device: 'gpu',
  cpus_per_client: 1,
  gpus_per_client: 0.9,
};

/**
 * Load device settings from localStorage with fallback to defaults.
 */
function loadStoredSettings() {
  try {
    const stored = localStorage.getItem(STORAGE_KEYS.DEVICE_SETTINGS);
    if (stored) {
      return { ...DEFAULT_SETTINGS, ...JSON.parse(stored) };
    }
  } catch {
    // Invalid JSON, use defaults
  }
  return DEFAULT_SETTINGS;
}

/**
 * Hook for accessing global device configuration.
 * Combines hardware detection with user-configurable settings.
 *
 * @returns {{
 *   gpuAvailable: boolean,
 *   gpuInfo: {name: string, vram_gb: number}|null,
 *   loading: boolean,
 *   deviceSettings: {training_device: string, cpus_per_client: number, gpus_per_client: number},
 *   setDeviceSettings: (settings: object) => void,
 *   isUsingGpu: boolean,
 *   recommendedGpuSettings: object,
 *   applyRecommendedGpu: () => void,
 *   resetToDefaults: () => void,
 * }}
 */
// eslint-disable-next-line react-refresh/only-export-components
export function useDevice() {
  const context = useContext(DeviceContext);
  if (!context) {
    throw new Error('useDevice must be used within DeviceProvider');
  }
  return context;
}

export function DeviceProvider({ children }) {
  const { gpuAvailable, gpuInfo, loading } = useDeviceInfo();

  const [deviceSettings, setDeviceSettingsState] = useState(loadStoredSettings);

  const setDeviceSettings = useCallback(newSettings => {
    setDeviceSettingsState(prev => {
      const updated = { ...prev, ...newSettings };
      localStorage.setItem(STORAGE_KEYS.DEVICE_SETTINGS, JSON.stringify(updated));
      return updated;
    });
  }, []);

  const applyRecommendedGpu = useCallback(() => {
    if (gpuAvailable) {
      setDeviceSettings(RECOMMENDED_GPU_SETTINGS);
    }
  }, [gpuAvailable, setDeviceSettings]);

  const resetToDefaults = useCallback(() => {
    setDeviceSettings(DEFAULT_SETTINGS);
  }, [setDeviceSettings]);

  const value = useMemo(
    () => ({
      // Hardware detection
      gpuAvailable,
      gpuInfo,
      loading,

      // User settings
      deviceSettings,
      setDeviceSettings,

      // Computed
      isUsingGpu: deviceSettings.training_device === 'gpu',

      // Helpers
      recommendedGpuSettings: RECOMMENDED_GPU_SETTINGS,
      applyRecommendedGpu,
      resetToDefaults,
    }),
    [
      gpuAvailable,
      gpuInfo,
      loading,
      deviceSettings,
      setDeviceSettings,
      applyRecommendedGpu,
      resetToDefaults,
    ]
  );

  return <DeviceContext.Provider value={value}>{children}</DeviceContext.Provider>;
}
