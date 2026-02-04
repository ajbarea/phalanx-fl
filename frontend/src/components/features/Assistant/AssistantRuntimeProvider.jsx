/**
 * AssistantRuntimeProvider - App-level runtime for shared chat state.
 *
 * Both the side panel and full page view consume this same runtime,
 * ensuring conversation state is shared across views.
 */
import { AssistantRuntimeProvider as AuiProvider } from '@assistant-ui/react';
import { useLocalRuntime } from '@assistant-ui/react';
import PropTypes from 'prop-types';

/**
 * Custom adapter for IntelliFL backend.
 * Connects to /api/agent/chat endpoint (placeholder for FL Agent).
 */
const FLAssistantAdapter = {
  async run({ messages, abortSignal }) {
    const response = await fetch('/api/agent/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages }),
      signal: abortSignal,
    });

    if (!response.ok) {
      throw new Error(`API error: ${response.statusText}`);
    }

    const data = await response.json();
    return {
      content: [{ type: 'text', text: data.message }],
    };
  },
};

export function AssistantRuntimeProvider({ children }) {
  const runtime = useLocalRuntime(FLAssistantAdapter);

  return <AuiProvider runtime={runtime}>{children}</AuiProvider>;
}

AssistantRuntimeProvider.propTypes = {
  children: PropTypes.node.isRequired,
};
