/** Maps HTTP status codes and error types to user-friendly messages. */

const HTTP_ERROR_MESSAGES = {
  // Client Errors (4xx)
  400: 'Invalid request. Please check your input and try again.',
  401: 'Please log in to continue.',
  403: 'You do not have permission to perform this action.',
  404: 'The requested resource was not found.',
  408: 'Request timed out. Please try again.',
  409: 'Conflict detected. The resource may have been modified.',
  413: 'The file or data is too large.',
  422: 'Invalid data format. Please check your input.',
  429: 'Too many requests. Please wait a moment and try again.',

  // Server Errors (5xx)
  500: 'Server error. Our team has been notified.',
  502: 'Server temporarily unavailable. Please try again shortly.',
  503: 'Service unavailable. Please try again in a few minutes.',
  504: 'Server took too long to respond. Please try again.',
};

const CONTEXT_ERROR_MESSAGES = {
  simulation: {
    create: 'Failed to create simulation. Please check your configuration.',
    delete: 'Failed to delete simulation. It may already be removed.',
    fetch: 'Failed to load simulation details.',
    start: 'Failed to start simulation. Please try again.',
    stop: 'Failed to stop simulation.',
  },
  queue: {
    submit: 'Failed to submit experiment queue.',
    fetch: 'Failed to load queue status.',
  },
  general: {
    network: 'Network error. Please check your connection.',
    timeout: 'Request timed out. The operation may still be processing.',
    unknown: 'An unexpected error occurred. Please try again.',
  },
};

/**
 * Extract a user-friendly error message from an axios error or Error object.
 *
 * @param {Error|Object} error - The error object (axios error or standard Error)
 * @param {string} [context] - Optional context for more specific messages (e.g., 'simulation.create')
 * @returns {string} User-friendly error message
 */
export function getErrorMessage(error, context = null) {
  if (!error) {
    return CONTEXT_ERROR_MESSAGES.general.unknown;
  }

  if (error.response) {
    const status = error.response.status;
    const serverMessage = error.response.data?.detail || error.response.data?.message;
    if (serverMessage && typeof serverMessage === 'string' && serverMessage.length < 200) {
      return serverMessage;
    }
    return HTTP_ERROR_MESSAGES[status] || `Server error (${status}). Please try again.`;
  }

  if (error.request && !error.response) {
    return CONTEXT_ERROR_MESSAGES.general.network;
  }

  if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
    return CONTEXT_ERROR_MESSAGES.general.timeout;
  }

  if (context) {
    const [category, action] = context.split('.');
    const contextMessage = CONTEXT_ERROR_MESSAGES[category]?.[action];
    if (contextMessage) {
      return contextMessage;
    }
  }

  if (error.message && typeof error.message === 'string') {
    // Don't expose technical error messages to users
    if (
      error.message.includes('Network Error') ||
      error.message.includes('Failed to fetch') ||
      error.message.includes('ERR_')
    ) {
      return CONTEXT_ERROR_MESSAGES.general.network;
    }
    if (error.message.length < 150 && !error.message.includes('Error:')) {
      return error.message;
    }
  }

  return CONTEXT_ERROR_MESSAGES.general.unknown;
}

/**
 * Get an error title based on HTTP status code category
 *
 * @param {Error|Object} error - The error object
 * @returns {string} Error title for toast/alert header
 */
export function getErrorTitle(error) {
  if (error?.response?.status) {
    const status = error.response.status;
    if (status >= 400 && status < 500) {
      return 'Request Error';
    }
    if (status >= 500) {
      return 'Server Error';
    }
  }

  if (error?.code === 'ECONNABORTED' || error?.message?.includes('timeout')) {
    return 'Timeout';
  }

  if (error?.request && !error?.response) {
    return 'Connection Error';
  }

  return 'Error';
}

export default { getErrorMessage, getErrorTitle };
