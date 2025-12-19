import { useEffect, useRef, useState, useCallback, forwardRef, useImperativeHandle } from 'react';
import { Terminal as XTerm } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import { Button, ButtonGroup } from 'react-bootstrap';
import { useTheme } from '../contexts/ThemeContext';
import '@xterm/xterm/css/xterm.css';

const WEBSOCKET_URL = 'ws://127.0.0.1:8000/api/terminal';

/** Quick command definitions. */
const QUICK_COMMANDS = [
  { label: 'Run Simulation', cmd: './run_simulation.sh\n' },
  { label: 'Run Tests', cmd: 'python -m tests.scripts.experiment_runner testing\n' },
  { label: 'Git Status', cmd: 'git status\n' },
];

/** Terminal theme configurations. */
const TERMINAL_THEMES = {
  dark: {
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
  },
  light: {
    background: '#ffffff',
    foreground: '#383a42',
    cursor: '#383a42',
    cursorAccent: '#ffffff',
    selectionBackground: '#b4d5fe',
    black: '#383a42',
    red: '#e45649',
    green: '#50a14f',
    yellow: '#c18401',
    blue: '#4078f2',
    magenta: '#a626a4',
    cyan: '#0184bc',
    white: '#fafafa',
    brightBlack: '#a0a1a7',
    brightRed: '#e45649',
    brightGreen: '#50a14f',
    brightYellow: '#c18401',
    brightBlue: '#4078f2',
    brightMagenta: '#a626a4',
    brightCyan: '#0184bc',
    brightWhite: '#ffffff',
  },
};

/**
 * Renders a terminal interface with WebSocket connectivity.
 */
const Terminal = forwardRef(function Terminal(
  { height = 400, showQuickCommands = true, isVisible = true },
  ref
) {
  const { theme } = useTheme();
  const terminalRef = useRef(null);
  const xtermRef = useRef(null);
  const fitAddonRef = useRef(null);
  const wsRef = useRef(null);
  const messageQueueRef = useRef([]); // Queue for messages sent before WebSocket is ready
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState(null);

  const getTerminalTheme = useCallback(() => {
    return TERMINAL_THEMES[theme] || TERMINAL_THEMES.dark;
  }, [theme]);

  /** Establishes WebSocket connection. */
  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    setError(null);
    const ws = new WebSocket(WEBSOCKET_URL);

    ws.onopen = () => {
      setConnected(true);
      setError(null);

      if (xtermRef.current && xtermRef.current.rows && xtermRef.current.cols) {
        const { rows, cols } = xtermRef.current;
        ws.send(JSON.stringify({ type: 'resize', rows, cols }));
      }

      // Flush queued messages that were sent before connection was ready
      if (messageQueueRef.current.length > 0) {
        messageQueueRef.current.forEach(msg => ws.send(msg));
        messageQueueRef.current = [];
      }

      // Focus terminal after connection is established
      if (xtermRef.current) {
        xtermRef.current.focus();
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

  /** Closes WebSocket connection. */
  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setConnected(false);
  }, []);

  /** Sends command to terminal via WebSocket. Queues if not yet connected. */
  const sendCommand = useCallback(cmd => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(cmd);
    } else {
      // Queue the message to be sent when WebSocket connects
      messageQueueRef.current.push(cmd);
    }
  }, []);

  /** Resets terminal state and reconnects. */
  const reset = useCallback(() => {
    if (xtermRef.current) {
      xtermRef.current.clear();
      xtermRef.current.reset();
    }
    disconnect();
    setTimeout(() => connect(), 100);
  }, [disconnect, connect]);

  /** Sends Ctrl+C to interrupt current process. */
  const interrupt = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send('\x03'); // Ctrl+C
    }
  }, []);

  useImperativeHandle(
    ref,
    () => ({
      reset,
      sendCommand,
      interrupt,
    }),
    [reset, sendCommand, interrupt]
  );

  useEffect(() => {
    if (!terminalRef.current) return;

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

    const initializeTerminal = () => {
      if (!isVisible) return false;

      const rect = terminalRef.current?.getBoundingClientRect();
      if (rect && rect.width > 0 && rect.height > 0) {
        if (dimensionCheckInterval) {
          clearInterval(dimensionCheckInterval);
          dimensionCheckInterval = null;
        }

        xterm.open(terminalRef.current);

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

    if (!initializeTerminal()) {
      dimensionCheckInterval = setInterval(() => {
        initializeTerminal();
      }, 100);
    }

    xterm.onData(data => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(data);
      } else {
        // Queue input to be sent when WebSocket connects
        messageQueueRef.current.push(data);
      }
    });

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
  }, [connect, disconnect]);

  useEffect(() => {
    if (xtermRef.current) {
      xtermRef.current.options.theme = getTerminalTheme();
    }
  }, [getTerminalTheme]);

  useEffect(() => {
    if (!isVisible || !xtermRef.current || !terminalRef.current) return;

    if (xtermRef.current.element?.parentElement) return;

    const rect = terminalRef.current.getBoundingClientRect();
    if (rect && rect.width > 0 && rect.height > 0) {
      xtermRef.current.open(terminalRef.current);
      setTimeout(() => {
        try {
          fitAddonRef.current?.fit();
        } catch (err) {
          console.warn('Terminal fit failed during initialization:', err.message);
        }
        if (!connected) {
          connect();
        }
      }, 150);
    }
  }, [isVisible, connected, connect]);

  // Focus terminal when it becomes visible
  useEffect(() => {
    if (isVisible && xtermRef.current) {
      // Small delay to ensure terminal is rendered
      const focusTimer = setTimeout(() => {
        xtermRef.current?.focus();
      }, 50);
      return () => clearTimeout(focusTimer);
    }
  }, [isVisible]);

  useEffect(() => {
    const handleResize = () => {
      if (fitAddonRef.current) {
        try {
          const parentRect = terminalRef.current?.getBoundingClientRect();
          if (parentRect && parentRect.width > 0 && parentRect.height > 0) {
            fitAddonRef.current.fit();
          }
        } catch (err) {
          console.warn('Terminal fit failed during resize:', err.message);
        }
      }
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  useEffect(() => {
    if (fitAddonRef.current) {
      setTimeout(() => {
        try {
          const parentRect = terminalRef.current?.getBoundingClientRect();
          if (parentRect && parentRect.width > 0 && parentRect.height > 0) {
            fitAddonRef.current.fit();
          }
        } catch (err) {
          console.warn('Terminal fit failed during height change:', err.message);
        }
      }, 0);
    }
  }, [height]);

  const termTheme = getTerminalTheme();
  const isDark = theme === 'dark';

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
        .terminal-container .xterm,
        .terminal-container .xterm-viewport,
        .terminal-container .xterm-screen {
          background-color: ${termTheme.background} !important;
        }
      `}</style>
      <div
        className="terminal-toolbar d-flex justify-content-between align-items-center p-2"
        style={{
          backgroundColor: isDark ? '#2d2d2d' : '#e9ecef',
          borderBottom: `1px solid ${isDark ? '#404040' : '#dee2e6'}`,
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
                variant={isDark ? 'outline-light' : 'outline-secondary'}
                onClick={() => sendCommand(cmd.cmd)}
                className="terminal-quick-btn"
              >
                {cmd.label}
              </Button>
            ))}
          </ButtonGroup>
        )}
      </div>

      {error && (
        <div className="alert alert-warning m-2 py-2" role="alert">
          {error}
        </div>
      )}

      <div
        ref={terminalRef}
        style={{
          height: `${height - 42}px`, // Subtract toolbar height (~42px) to prevent overflow
          backgroundColor: termTheme.background,
          overflow: 'hidden',
        }}
      />
    </div>
  );
});

export default Terminal;
