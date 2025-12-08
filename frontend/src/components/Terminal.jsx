import { useEffect, useRef, useState, useCallback, forwardRef, useImperativeHandle } from 'react';
import { Terminal as XTerm } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import { Button, ButtonGroup } from 'react-bootstrap';
import { useTheme } from '../contexts/ThemeContext';
import '@xterm/xterm/css/xterm.css';

const WEBSOCKET_URL = 'ws://127.0.0.1:8000/api/terminal';

// Predefined commands for quick access
const QUICK_COMMANDS = [
  { label: 'Run Simulation', cmd: './run_simulation.sh\n' },
  { label: 'Run Tests', cmd: 'python -m tests.scripts.experiment_runner testing\n' },
  { label: 'Git Status', cmd: 'git status\n' },
];

const Terminal = forwardRef(function Terminal(
  { height = 400, showQuickCommands = true, isVisible = true },
  ref
) {
  const { theme } = useTheme();
  const terminalRef = useRef(null);
  const xtermRef = useRef(null);
  const fitAddonRef = useRef(null);
  const wsRef = useRef(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState(null);

  // Theme-aware terminal colors
  const getTerminalTheme = useCallback(() => {
    if (theme === 'dark') {
      return {
        background: '#1e1e1e',
        foreground: '#d4d4d4',
        cursor: '#d4d4d4',
        cursorAccent: '#1e1e1e',
        selectionBackground: '#264f78',
        black: '#1e1e1e',
        red: '#f44747',
        green: '#6a9955',
        yellow: '#dcdcaa',
        blue: '#569cd6',
        magenta: '#c586c0',
        cyan: '#4ec9b0',
        white: '#d4d4d4',
        brightBlack: '#808080',
        brightRed: '#f44747',
        brightGreen: '#6a9955',
        brightYellow: '#dcdcaa',
        brightBlue: '#569cd6',
        brightMagenta: '#c586c0',
        brightCyan: '#4ec9b0',
        brightWhite: '#ffffff',
      };
    }
    return {
      background: '#f8f8f8',
      foreground: '#1a1a1a',
      cursor: '#1a1a1a',
      cursorAccent: '#f8f8f8',
      selectionBackground: '#bfceff',
      black: '#1a1a1a',
      red: '#c41a16',
      green: '#007400',
      yellow: '#826b28',
      blue: '#0451a5',
      magenta: '#a626a4',
      cyan: '#0598bc',
      white: '#5c5c5c',
      brightBlack: '#1a1a1a',
      brightRed: '#c41a16',
      brightGreen: '#007400',
      brightYellow: '#826b28',
      brightBlue: '#0451a5',
      brightMagenta: '#a626a4',
      brightCyan: '#0598bc',
      brightWhite: '#1a1a1a',
    };
  }, [theme]);

  // Connect to WebSocket
  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    setError(null);
    const ws = new WebSocket(WEBSOCKET_URL);

    ws.onopen = () => {
      setConnected(true);
      setError(null);

      // Send initial resize
      if (xtermRef.current && xtermRef.current.rows && xtermRef.current.cols) {
        const { rows, cols } = xtermRef.current;
        ws.send(JSON.stringify({ type: 'resize', rows, cols }));
      }
    };

    ws.onmessage = event => {
      if (xtermRef.current) {
        xtermRef.current.write(event.data);
      }
    };

    ws.onerror = () => {
      setError('Connection error. Is the API server running?');
    };

    ws.onclose = () => {
      setConnected(false);
    };

    wsRef.current = ws;
  }, []);

  // Disconnect WebSocket
  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setConnected(false);
  }, []);

  // Send command to terminal
  const sendCommand = useCallback(cmd => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(cmd);
    }
  }, []);

  // Reset terminal - clears output and reconnects for fresh shell
  const reset = useCallback(() => {
    if (xtermRef.current) {
      xtermRef.current.clear();
      xtermRef.current.reset();
    }
    disconnect();
    setTimeout(() => connect(), 100);
  }, [disconnect, connect]);

  // Expose methods to parent components
  useImperativeHandle(
    ref,
    () => ({
      reset,
      sendCommand,
    }),
    [reset, sendCommand]
  );

  // Initialize terminal
  useEffect(() => {
    if (!terminalRef.current) return;

    // Prevent double initialization in React Strict Mode
    if (xtermRef.current) {
      return;
    }

    const xterm = new XTerm({
      cursorBlink: true,
      fontSize: 12,
      fontFamily: 'Menlo, Monaco, "Courier New", monospace',
      theme: getTerminalTheme(),
      allowProposedApi: true,
    });

    const fitAddon = new FitAddon();
    xterm.loadAddon(fitAddon);

    xtermRef.current = xterm;
    fitAddonRef.current = fitAddon;

    let initTimer;
    let dimensionCheckInterval;

    // Function to initialize terminal when visible and has dimensions
    const initializeTerminal = () => {
      if (!isVisible) return false; // Don't initialize if not visible

      const rect = terminalRef.current?.getBoundingClientRect();
      if (rect && rect.width > 0 && rect.height > 0) {
        // Clear the check interval if it was running
        if (dimensionCheckInterval) {
          clearInterval(dimensionCheckInterval);
          dimensionCheckInterval = null;
        }

        // Open terminal now that it's visible and has dimensions
        xterm.open(terminalRef.current);

        // Fit and connect after a short delay
        initTimer = setTimeout(() => {
          try {
            fitAddon.fit();
          } catch (err) {
            console.warn('Terminal fit failed:', err.message);
          }
          connect();
        }, 150);

        return true;
      }
      return false;
    };

    // Try immediate initialization
    if (!initializeTerminal()) {
      // Not visible or no dimensions, poll until ready
      dimensionCheckInterval = setInterval(() => {
        initializeTerminal();
      }, 100);
    }

    // Handle user input
    xterm.onData(data => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(data);
      }
    });

    // Handle resize
    xterm.onResize(({ rows, cols }) => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'resize', rows, cols }));
      }
    });

    return () => {
      if (initTimer) clearTimeout(initTimer);
      if (dimensionCheckInterval) clearInterval(dimensionCheckInterval);
      disconnect();
      xterm.dispose();
      xtermRef.current = null;
      fitAddonRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connect, disconnect, getTerminalTheme]);

  // Update theme when it changes
  useEffect(() => {
    if (xtermRef.current) {
      xtermRef.current.options.theme = getTerminalTheme();
    }
  }, [theme, getTerminalTheme]);

  // Handle window resize
  useEffect(() => {
    const handleResize = () => {
      if (fitAddonRef.current) {
        try {
          const parentRect = terminalRef.current?.getBoundingClientRect();
          if (parentRect && parentRect.width > 0 && parentRect.height > 0) {
            fitAddonRef.current.fit();
          }
        } catch {
          // Ignore fit errors during resize
        }
      }
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Fit terminal when height changes
  useEffect(() => {
    if (fitAddonRef.current) {
      setTimeout(() => {
        try {
          const parentRect = terminalRef.current?.getBoundingClientRect();
          if (parentRect && parentRect.width > 0 && parentRect.height > 0) {
            fitAddonRef.current.fit();
          }
        } catch {
          // Ignore fit errors
        }
      }, 0);
    }
  }, [height]);

  return (
    <div className="terminal-container">
      <style>{`
        .terminal-quick-btn {
          padding: 6px 8px !important;
          line-height: 1 !important;
          font-size: 12px !important;
          height: auto !important;
          min-height: unset !important;
        }
      `}</style>
      {/* Toolbar */}
      <div
        className="terminal-toolbar d-flex justify-content-between align-items-center p-2"
        style={{
          backgroundColor: theme === 'dark' ? '#2d2d2d' : '#f5f5f5',
          borderBottom: `1px solid ${theme === 'dark' ? '#404040' : '#ddd'}`,
        }}
      >
        <div className="d-flex align-items-center gap-2">
          <span
            className={`badge ${connected ? 'bg-success' : 'bg-danger'}`}
            style={{ fontSize: '0.7rem' }}
          >
            {connected ? 'Connected' : 'Disconnected'}
          </span>
          {!connected && (
            <Button size="sm" variant="outline-primary" onClick={connect}>
              Reconnect
            </Button>
          )}
        </div>

        {showQuickCommands && connected && (
          <ButtonGroup size="sm">
            {QUICK_COMMANDS.map((cmd, idx) => (
              <Button
                key={idx}
                variant={theme === 'dark' ? 'outline-light' : 'outline-secondary'}
                onClick={() => sendCommand(cmd.cmd)}
                className="terminal-quick-btn"
              >
                {cmd.label}
              </Button>
            ))}
          </ButtonGroup>
        )}
      </div>

      {/* Error message */}
      {error && (
        <div className="alert alert-warning m-2 py-2" role="alert">
          {error}
        </div>
      )}

      {/* Terminal */}
      <div
        ref={terminalRef}
        style={{
          height: `${height}px`,
          backgroundColor: theme === 'dark' ? '#1e1e1e' : '#f8f8f8',
        }}
      />
    </div>
  );
});

export default Terminal;
