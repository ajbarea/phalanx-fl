/**
 * AssistantMessage - Renders AI assistant messages with markdown support.
 */
import { MessagePrimitive } from '@assistant-ui/react';
import ReactMarkdown from 'react-markdown';

export function AssistantMessage() {
  return (
    <MessagePrimitive.Root className="aui-message aui-assistant-message">
      <MessagePrimitive.Content
        components={{
          Text: ({ text }) => (
            <div className="aui-message-text">
              <ReactMarkdown>{text}</ReactMarkdown>
            </div>
          ),
        }}
      />
    </MessagePrimitive.Root>
  );
}
