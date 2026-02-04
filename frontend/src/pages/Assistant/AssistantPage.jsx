/**
 * AssistantPage - Full-page assistant view at /assistant route.
 */
import { Thread } from '@components/features/Assistant';

export default function AssistantPage() {
  return (
    <div className="aui-page">
      <header className="aui-page-header">
        <h1 className="aui-page-title">IntelliFL Assistant</h1>
        <p className="aui-page-subtitle">Ask questions about your federated learning experiments</p>
      </header>
      <div className="aui-page-content">
        <Thread />
      </div>
    </div>
  );
}
