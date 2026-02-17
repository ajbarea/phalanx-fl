/**
 * Input area for sending messages.
 */
import { ComposerPrimitive } from '@assistant-ui/react';
import { ASSISTANT_BRANDING } from '@constants/assistantBranding';

export function Composer() {
  return (
    <ComposerPrimitive.Root className="aui-composer">
      <ComposerPrimitive.Input
        id="assistant-composer-input"
        name="assistant-composer-input"
        placeholder={ASSISTANT_BRANDING.placeholder}
        className="aui-composer-input"
      />
      <ComposerPrimitive.Send className="aui-composer-send">
        <span className="material-symbols-outlined">send</span>
      </ComposerPrimitive.Send>
    </ComposerPrimitive.Root>
  );
}
