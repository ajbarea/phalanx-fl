/**
 * AssistantPage - Full-page assistant view at /assistant route.
 */
import { Thread } from '@components/features/Assistant';
import { ASSISTANT_BRANDING } from '@constants/assistantBranding';

export default function AssistantPage() {
  return (
    <div className="aui-page">
      <header className="aui-page-header">
        <h1 className="aui-page-title">{ASSISTANT_BRANDING.pageTitle}</h1>
        <p className="aui-page-subtitle">{ASSISTANT_BRANDING.pageSubtitle}</p>
      </header>
      <div className="aui-page-content">
        <Thread />
      </div>
    </div>
  );
}
