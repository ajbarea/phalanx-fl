/**
 * UserMessage - Renders user messages in the chat thread.
 */
import { MessagePrimitive } from '@assistant-ui/react';

export function UserMessage() {
  return (
    <MessagePrimitive.Root className="aui-message aui-user-message">
      <MessagePrimitive.Content />
    </MessagePrimitive.Root>
  );
}
