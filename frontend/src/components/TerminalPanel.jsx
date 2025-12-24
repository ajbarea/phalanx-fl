import { useState, useEffect, useCallback } from 'react';
import Terminal from './Terminal';
import { ConfirmModal } from './common/Modal/ConfirmModal';
import { useTheme } from '../contexts/ThemeContext';
import { useTerminal } from '../contexts/TerminalContext';
import { toast } from 'sonner';

const MIN_HEIGHT = 150;
const DEFAULT_HEIGHT = 400;

const getMaxHeight = () =>
  typeof window !== 'undefined' ? Math.floor(window.innerHeight * 0.95) : 800;

export default function TerminalPanel() {
  const { theme } = useTheme();
  const { isOpen, setIsOpen, terminalRef } = useTerminal();
  const [height, setHeight] = useState(DEFAULT_HEIGHT);
  const [isResizing, setIsResizing] = useState(false);
  const [showPurgeConfirm, setShowPurgeConfirm] = useState(false);
  const [showResetConfirm, setShowResetConfirm] = useState(false);

  const handlePurgeConfirm = () => {
    setShowPurgeConfirm(false);
    terminalRef.current?.sendCommand?.('bash clean.sh\n');
    toast.success('Purging simulation data, logs & caches...');
  };

  const handleResetConfirm = () => {
    setShowResetConfirm(false);
    terminalRef.current?.reset();
    toast.info('Terminal reset');
  };

  useEffect(() => {
    const handleKeyDown = e => {
      if ((e.ctrlKey || e.metaKey) && e.key === '`') {
        e.preventDefault();
        setIsOpen(prev => !prev);
      }
      if (e.key === 'Escape' && isOpen) {
        setIsOpen(false);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, setIsOpen]);

  const handleMouseDown = useCallback(
    e => {
      e.preventDefault();
      setIsResizing(true);

      const startY = e.clientY;
      const startHeight = height;

      const handleMouseMove = e => {
        const delta = startY - e.clientY;
        const maxHeight = getMaxHeight();
        const newHeight = Math.min(maxHeight, Math.max(MIN_HEIGHT, startHeight + delta));
        setHeight(newHeight);
      };

      const handleMouseUp = () => {
        setIsResizing(false);
        document.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseup', handleMouseUp);
      };

      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
    },
    [height]
  );

  const handleResizeKeyDown = useCallback(e => {
    const step = 20;
    const maxHeight = getMaxHeight();
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHeight(h => Math.min(maxHeight, h + step));
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHeight(h => Math.max(MIN_HEIGHT, h - step));
    } else if (e.key === 'Home') {
      e.preventDefault();
      setHeight(maxHeight);
    } else if (e.key === 'End') {
      e.preventDefault();
      setHeight(DEFAULT_HEIGHT);
    }
  }, []);

  const colors =
    theme === 'dark'
      ? {
          bg: '#1e1e1e',
          border: '#404040',
          handle: '#555',
          handleHover: '#666',
          text: '#ccc',
          buttonBg: '#2d2d2d',
        }
      : {
          bg: '#f8f9fa',
          border: '#dee2e6',
          handle: '#adb5bd',
          handleHover: '#6c757d',
          text: '#495057',
          buttonBg: '#e9ecef',
        };

  return (
    <>
      <button
        onClick={() => setIsOpen(prev => !prev)}
        className="terminal-toggle-btn"
        title="Toggle Terminal (Ctrl+`)"
        style={{
          position: 'fixed',
          bottom: isOpen ? height + 10 : 13,
          right: 68,
          zIndex: 1050,
          width: 48,
          height: 48,
          borderRadius: '50%',
          border: 'none',
          backgroundColor: isOpen ? 'var(--bs-success)' : colors.buttonBg,
          color: isOpen ? 'white' : colors.text,
          boxShadow: '0 2px 10px rgba(0,0,0,0.2)',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          transition: 'all 0.3s ease',
          fontSize: '20px',
        }}
      >
        {isOpen ? '▼' : '>_'}
      </button>

      <div
        className="terminal-panel"
        style={{
          position: 'fixed',
          bottom: 0,
          left: 12,
          right: 12,
          height: isOpen ? height : 0,
          backgroundColor: colors.bg,
          borderTop: isOpen ? `1px solid ${colors.border}` : 'none',
          borderLeft: isOpen ? `1px solid ${colors.border}` : 'none',
          borderRight: isOpen ? `1px solid ${colors.border}` : 'none',
          borderRadius: isOpen ? '8px 8px 0 0' : 0,
          zIndex: 1040,
          transition: isResizing ? 'none' : 'height 0.3s ease',
          overflow: 'hidden',
          boxShadow: isOpen ? '0 -4px 20px rgba(0,0,0,0.15)' : 'none',
          pointerEvents: isOpen ? 'auto' : 'none',
        }}
      >
        <div
          onMouseDown={handleMouseDown}
          onDoubleClick={() =>
            setHeight(height >= getMaxHeight() - 50 ? DEFAULT_HEIGHT : getMaxHeight())
          }
          onKeyDown={handleResizeKeyDown}
          tabIndex={0}
          role="separator"
          aria-orientation="horizontal"
          aria-label="Resize terminal panel. Use Up/Down arrows to adjust, Home/End for max/default"
          aria-valuenow={height}
          aria-valuemin={MIN_HEIGHT}
          aria-valuemax={getMaxHeight()}
          style={{
            height: 6,
            cursor: 'ns-resize',
            backgroundColor: colors.handle,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            transition: 'background-color 0.2s',
          }}
          onMouseEnter={e => (e.target.style.backgroundColor = colors.handleHover)}
          onMouseLeave={e => (e.target.style.backgroundColor = colors.handle)}
        >
          <div
            style={{
              width: 40,
              height: 3,
              backgroundColor: theme === 'dark' ? '#888' : '#6c757d',
              borderRadius: 2,
            }}
          />
        </div>

        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '4px 12px',
            backgroundColor: theme === 'dark' ? '#252526' : '#e9ecef',
            borderBottom: `1px solid ${colors.border}`,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ color: colors.text, fontSize: '12px', fontWeight: 500 }}>TERMINAL</span>
            <span
              style={{
                fontSize: '10px',
                color: theme === 'dark' ? '#666' : '#999',
              }}
            >
              Ctrl+` to toggle
            </span>
          </div>
          <div style={{ display: 'flex', gap: 4 }}>
            <button
              onClick={() => setShowPurgeConfirm(true)}
              title="Purge all simulation data, logs & caches"
              aria-label="Purge all simulation data, logs and caches"
              style={{
                border: 'none',
                background: 'transparent',
                color: 'var(--bs-danger)',
                cursor: 'pointer',
                padding: '2px 6px',
                fontSize: '11px',
                opacity: 0.7,
              }}
              onMouseEnter={e => (e.target.style.opacity = 1)}
              onMouseLeave={e => (e.target.style.opacity = 0.7)}
            >
              <span aria-hidden="true">⚠️</span>
            </button>
            <button
              onClick={() => setShowResetConfirm(true)}
              title="Reset terminal"
              aria-label="Reset terminal"
              style={{
                border: 'none',
                background: 'transparent',
                color: colors.text,
                cursor: 'pointer',
                padding: '2px 6px',
                fontSize: '14px',
              }}
            >
              <span aria-hidden="true">↻</span>
            </button>
            <button
              onClick={() => setIsOpen(false)}
              title="Minimize (Ctrl+`)"
              aria-label="Minimize terminal"
              style={{
                border: 'none',
                background: 'transparent',
                color: colors.text,
                cursor: 'pointer',
                padding: '2px 6px',
                fontSize: '14px',
              }}
            >
              <span aria-hidden="true">−</span>
            </button>
            <button
              onClick={() => {
                setIsOpen(false);
                terminalRef.current?.reset();
              }}
              title="Close terminal"
              aria-label="Close terminal"
              style={{
                border: 'none',
                background: 'transparent',
                color: colors.text,
                cursor: 'pointer',
                padding: '2px 6px',
                fontSize: '14px',
              }}
            >
              <span aria-hidden="true">✕</span>
            </button>
          </div>
        </div>

        {/* Terminal content - always mounted to preserve connection */}
        <div
          style={{
            height: height - 40,
            visibility: isOpen ? 'visible' : 'hidden',
            position: isOpen ? 'relative' : 'absolute',
            overflow: 'hidden',
          }}
        >
          <Terminal
            ref={terminalRef}
            height={height - 40}
            showQuickCommands={true}
            isVisible={isOpen}
          />
        </div>
      </div>

      <style>{`
        .terminal-toggle-btn:hover {
          transform: scale(1.1);
        }
        .terminal-toggle-btn:active {
          transform: scale(0.95);
        }
      `}</style>

      <ConfirmModal
        show={showPurgeConfirm}
        title="⚠️ Purge All Data"
        message={
          <div>
            <p>This will permanently delete:</p>
            <ul style={{ marginBottom: '1rem' }}>
              <li>
                All simulation results <code>out/</code>
              </li>
              <li>
                All log files <code>logs/</code>
              </li>
              <li>All Python caches</li>
            </ul>
            <p className="text-danger mb-0">
              <strong>This cannot be undone.</strong>
            </p>
          </div>
        }
        variant="danger"
        confirmText="Purge Everything"
        onConfirm={handlePurgeConfirm}
        onCancel={() => setShowPurgeConfirm(false)}
      />

      <ConfirmModal
        show={showResetConfirm}
        title="Reset Terminal"
        message="This will clear the terminal output and reconnect. Any running commands will be interrupted."
        variant="warning"
        confirmText="Reset"
        onConfirm={handleResetConfirm}
        onCancel={() => setShowResetConfirm(false)}
      />
    </>
  );
}
