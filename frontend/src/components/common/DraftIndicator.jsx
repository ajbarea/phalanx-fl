import { useState } from 'react';
import PropTypes from 'prop-types';
import { Accordion, Button } from 'react-bootstrap';
import { MaterialIcon } from './Icon/MaterialIcon';

/**
 * Draft indicator component - shows when form has a draft loaded
 * Expandable accordion reveals JSON config with copy functionality
 */
function DraftIndicator({ timestamp, config, onDiscard }) {
  const [copied, setCopied] = useState(false);

  const formatTimestamp = ts => {
    if (!ts) return 'previously';
    const date = new Date(ts);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return diffMins + ' min ago';
    if (diffHours < 24) return diffHours + ' hour' + (diffHours > 1 ? 's' : '') + ' ago';
    if (diffDays < 7) return diffDays + ' day' + (diffDays > 1 ? 's' : '') + ' ago';
    return date.toLocaleDateString();
  };

  const handleCopy = async e => {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(JSON.stringify(config, null, 2));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  const handleDiscard = e => {
    e.stopPropagation();
    onDiscard();
  };

  return (
    <Accordion className="mb-3 draft-indicator-accordion">
      <Accordion.Item eventKey="0">
        <div className="d-flex align-items-center">
          <Accordion.Header className="flex-grow-1 draft-indicator-header">
            <MaterialIcon name="draft" size={18} className="me-2" aria-hidden="true" />
            <span>
              <strong>Draft restored</strong> - saved {formatTimestamp(timestamp)}
            </span>
          </Accordion.Header>
          <Button variant="outline-danger" size="sm" onClick={handleDiscard} className="me-3">
            Discard Draft
          </Button>
        </div>
        <Accordion.Body className="p-0">
          <div style={{ position: 'relative' }}>
            <Button
              variant="outline-secondary"
              size="sm"
              onClick={handleCopy}
              title={copied ? 'Copied!' : 'Copy JSON to clipboard'}
              aria-label="Copy JSON to clipboard"
              style={{
                position: 'absolute',
                top: '0.5rem',
                right: '0.5rem',
                zIndex: 1,
                padding: '0.25rem 0.5rem',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <MaterialIcon name={copied ? 'check' : 'content_copy'} size={16} aria-hidden="true" />
            </Button>
            <pre
              className="m-0 p-3"
              style={{
                overflow: 'auto',
                fontSize: '0.85rem',
                backgroundColor: 'transparent',
              }}
            >
              {JSON.stringify(config, null, 2)}
            </pre>
          </div>
        </Accordion.Body>
      </Accordion.Item>
    </Accordion>
  );
}

DraftIndicator.propTypes = {
  timestamp: PropTypes.string,
  config: PropTypes.object.isRequired,
  onDiscard: PropTypes.func.isRequired,
};

export { DraftIndicator };
