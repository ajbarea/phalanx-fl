import axios from 'axios';

export const apiClient = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

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
