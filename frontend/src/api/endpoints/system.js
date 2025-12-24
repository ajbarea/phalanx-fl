import { fetchApi } from '../client';

/**
 * Fetches available training devices and GPU information.
 * @returns {Promise<{available_devices: string[], gpu_available: boolean, gpu_info: {name: string, vram_gb: number}|null, recommended_device: string}>}
 */
export const getSystemDevices = () => fetchApi('/system/devices');
