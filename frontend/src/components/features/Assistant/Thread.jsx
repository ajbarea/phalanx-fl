/**
 * Thread - Main chat thread component with messages and composer.
 */
import { ThreadPrimitive, useAui } from '@assistant-ui/react';
import { UserMessage } from './UserMessage';
import { AssistantMessage } from './AssistantMessage';
import { Composer } from './Composer';
import { Suggestions } from './Suggestions';

export function Thread() {
  const aui = useAui();
  const hasMessages = aui.thread().getState().messages.length > 0;

  return (
    <ThreadPrimitive.Root className="aui-thread-root">
      <ThreadPrimitive.Viewport className="aui-thread-viewport">
        {!hasMessages && <Suggestions />}
        <ThreadPrimitive.Messages
          components={{
            UserMessage,
            AssistantMessage,
          }}
        />
      </ThreadPrimitive.Viewport>
      <Composer />
    </ThreadPrimitive.Root>
  );
}
