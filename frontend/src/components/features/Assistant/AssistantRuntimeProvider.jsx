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
const USE_DEMO_RESPONSES = true;

const DEMO_RESPONSES = [
  {
    id: 'overview',
    patterns: [/what is|what does|purpose|overview|about/i],
    text: `Short answer: this is a Flower-based federated learning simulation framework.

It lets you configure strategies, datasets, and attack schedules in JSON, then run reproducible experiments and collect metrics like loss/accuracy (plus plots or CSVs if enabled).`,
  },
  {
    id: 'configure',
    patterns: [/configure|config|run|execute|simulation|experiment/i],
    text: `Create a JSON config under \`config/simulation_strategies/\` (see \`example_strategy_config.json\`).
Point \`src/simulation_runner.py\` at that file, then run \`sh run_simulation.sh\`.
For batch runs, use \`python -m tests.scripts.experiment_runner <group>\`.
Outputs land in \`out/\` when plots/CSVs are enabled.`,
  },
  {
    id: 'strategies',
    patterns: [/strateg(y|ies)|aggregation|fedavg|krum|bulyan|rfa|pid/i],
    text: `Built-in aggregation options include trust, PID variants (pid, pid_scaled, pid_standardized, pid_standardized_score_based),
Krum / Multi-Krum / Multi-Krum-based, RFA, trimmed_mean, bulyan, and fedavg.
You can also plug in custom strategies.`,
  },
  {
    id: 'datasets',
    patterns: [/dataset|data|femnist|medmnist|its|nlp/i],
    text: `There are several dataset keywords, including FEMNIST (IID/NIID), ITS, multiple MedMNIST variants (pneumoniamnist, pathmnist, bloodmnist, etc.),
and NLP datasets like medquad, financial_phrasebank, and lexglue.`,
  },
  {
    id: 'limitations',
    patterns: [/limit|limitation|missing|not yet|gap/i],
    text: `Honest limitation: when comparing multiple strategies in one run, \`num_of_rounds\` must be shared across them, so it cannot vary per strategy.
Also, the FLAIR dataset is listed but marked unsupported in the current version.`,
  },
];

const FALLBACK_RESPONSE = `I can help with an overview, how to configure/run simulations, built-in strategies, datasets, or current limitations.
Try asking: "What does this framework do?" or "Which strategies are built in?"`;

function getLastUserText(messages) {
  if (!Array.isArray(messages)) {
    return '';
  }

  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const message = messages[i];
    if (message?.role !== 'user') {
      continue;
    }
    const textPart = message?.content?.find(
      part => part?.type === 'text' && typeof part?.text === 'string'
    );
    if (textPart?.text) {
      return textPart.text.trim();
    }
  }

  return '';
}

function pickDemoResponse(text) {
  const normalized = text.trim();
  if (!normalized) {
    return 'Hi! Ask me about the framework, strategies, datasets, or how to run a simulation.';
  }

  if (/^(hi|hello|hey)\b/i.test(normalized)) {
    return 'Hey! Happy to help. What would you like to know about the framework?';
  }

  if (/\b(thanks|thank you|thx)\b/i.test(normalized)) {
    return 'You got it. Anything else you want to cover?';
  }

  for (const entry of DEMO_RESPONSES) {
    if (entry.patterns.some(pattern => pattern.test(normalized))) {
      return entry.text;
    }
  }

  return FALLBACK_RESPONSE;
}

const FLAssistantAdapter = {
  async run({ messages, abortSignal }) {
    if (USE_DEMO_RESPONSES) {
      if (abortSignal?.aborted) {
        throw new DOMException('Aborted', 'AbortError');
      }
      const responseText = pickDemoResponse(getLastUserText(messages));
      await new Promise(resolve => setTimeout(resolve, 350));
      return {
        content: [{ type: 'text', text: responseText }],
      };
    }

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
