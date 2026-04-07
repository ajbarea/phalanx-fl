/**
 * Suggestions - Quick action buttons for common prompts.
 */
import { useAui } from '@assistant-ui/react';
import PropTypes from 'prop-types';

const DEFAULT_SUGGESTIONS = [
  'What does this framework do?',
  'How do I configure and run a simulation?',
  'Which aggregation strategies are built in?',
  'What datasets are available?',
  'What are the current limitations?',
];

const NUMBER_OF_SUGGESTIONS = 3;

function getRandomSuggestions(suggestions, count) {
  const shuffled = [...suggestions].sort(() => 0.5 - Math.random());
  return shuffled.slice(0, count);
}

export function Suggestions({ suggestions = DEFAULT_SUGGESTIONS }) {
  const aui = useAui();
  const randomSuggestions = getRandomSuggestions(suggestions, NUMBER_OF_SUGGESTIONS);

  const handleClick = text => {
    aui.thread().append({
      role: 'user',
      content: [{ type: 'text', text }],
    });
  };

  return (
    <div className="aui-suggestions">
      {randomSuggestions.map((text, i) => (
        <button key={i} className="aui-suggestion-btn" onClick={() => handleClick(text)}>
          {text}
        </button>
      ))}
    </div>
  );
}

Suggestions.propTypes = {
  suggestions: PropTypes.arrayOf(PropTypes.string),
};
