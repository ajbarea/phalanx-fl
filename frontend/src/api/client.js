import axios from 'axios';
import { toast } from 'sonner';
import { getErrorMessage, getErrorTitle } from '../utils/errorMessages';

export const apiClient = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
});

/**
 * Response interceptor for centralized error handling.
 * Shows user-friendly toast notifications for API errors.
 *
 * @see https://blog.logrocket.com/react-toastify-guide/
 */
apiClient.interceptors.response.use(
  response => response,
  error => {
    // Don't show toast for cancelled requests or if explicitly suppressed
    if (axios.isCancel(error) || error.config?.suppressToast) {
      return Promise.reject(error);
    }

    const message = getErrorMessage(error);
    const title = getErrorTitle(error);
    const status = error.response?.status || 'network';

    // Use toast id for deduplication - prevents spam when multiple requests fail
    const toastId = `api-error-${status}-${message.slice(0, 50)}`;

    toast.error(message, {
      id: toastId,
      description: title !== 'Error' ? title : undefined,
      duration: 5000,
    });

    return Promise.reject(error);
  }
);

// Query function helpers for TanStack Query
export const fetchApi = async endpoint => {
  const response = await apiClient.get(endpoint);
  return response.data;
};

export const postApi = async (endpoint, data) => {
  const response = await apiClient.post(endpoint, data);
  return response.data;
};

export const deleteApi = async (endpoint, data = null) => {
  const config = data ? { data } : {};
  const response = await apiClient.delete(endpoint, config);
  return response.data;
};

export const patchApi = async (endpoint, data) => {
  const response = await apiClient.patch(endpoint, data);
  return response.data;
};
