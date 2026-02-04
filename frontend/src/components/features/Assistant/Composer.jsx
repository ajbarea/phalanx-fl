/**
 * Composer - Input area for sending messages.
 */
import { ComposerPrimitive } from '@assistant-ui/react';

export function Composer() {
  return (
    <ComposerPrimitive.Root className="aui-composer">
      <ComposerPrimitive.Input
        placeholder="Ask IntelliFL Assistant..."
        className="aui-composer-input"
      />
      <ComposerPrimitive.Send className="aui-composer-send">
        <span className="material-symbols-outlined">send</span>
      </ComposerPrimitive.Send>
    </ComposerPrimitive.Root>
  );
}
