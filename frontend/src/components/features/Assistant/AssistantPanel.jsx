/**
 * AssistantPanel - Side panel wrapper for the assistant.
 * Slides in from the right, contains the Thread component.
 */
import './Assistant.css';
import PropTypes from 'prop-types';
import { useNavigate } from 'react-router-dom';
import { Thread } from './Thread';
import { ASSISTANT_BRANDING } from '@constants/assistantBranding';

export function AssistantPanel({ isOpen, onClose }) {
  const navigate = useNavigate();

  const handleExpand = () => {
    onClose();
    navigate('/assistant');
  };

  return (
    <>
      {/* Backdrop */}
      {isOpen && <div className="aui-panel-backdrop" onClick={onClose} aria-hidden="true" />}

      {/* Panel */}
      <aside
        className={`aui-panel ${isOpen ? 'open' : ''}`}
        aria-label={ASSISTANT_BRANDING.panelAriaLabel}
        aria-hidden={!isOpen}
      >
        <header className="aui-panel-header">
          <h3 className="aui-panel-title">{ASSISTANT_BRANDING.panelTitle}</h3>
          <div className="aui-panel-actions">
            <button
              className="aui-panel-btn"
              onClick={handleExpand}
              title="Open full page"
              aria-label="Expand to full page"
            >
              <span className="material-symbols-outlined">open_in_full</span>
            </button>
            <button
              className="aui-panel-btn"
              onClick={onClose}
              title="Close"
              aria-label="Close panel"
            >
              <span className="material-symbols-outlined">close</span>
            </button>
          </div>
        </header>
        <div className="aui-panel-content">
          <Thread />
        </div>
      </aside>
    </>
  );
}

AssistantPanel.propTypes = {
  isOpen: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
};
