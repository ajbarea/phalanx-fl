import { useEffect, useRef } from 'react';
import PropTypes from 'prop-types';
import { Terminal as XTerm } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import { useTheme } from '@contexts/ThemeContext';
import { TERMINAL_THEMES } from '@constants/ui';
import '@xterm/xterm/css/xterm.css';

/**
 * Read-only xterm.js viewer for simulation output.
 * Receives output text via props (from SSE) and renders with ANSI color support.
 */
export function OutputViewer({ output = '', height = 350 }) {
  const { theme } = useTheme();
  const containerRef = useRef(null);
  const xtermRef = useRef(null);
  const fitAddonRef = useRef(null);
  const writtenLengthRef = useRef(0);

  useEffect(() => {
    if (!containerRef.current) return;

    const xterm = new XTerm({
      cursorBlink: false,
      fontSize: 12,
      fontFamily: 'Menlo, Monaco, "Courier New", monospace',
      theme: TERMINAL_THEMES[theme] || TERMINAL_THEMES.dark,
      disableStdin: true,
      scrollback: 5000,
    });

    const fitAddon = new FitAddon();
    xterm.loadAddon(fitAddon);

    xtermRef.current = xterm;
    fitAddonRef.current = fitAddon;

    xterm.open(containerRef.current);

    const fitTimer = setTimeout(() => {
      try {
        fitAddon.fit();
      } catch {
        // Fit may fail if dimensions not ready
      }
    }, 150);

    return () => {
      clearTimeout(fitTimer);
      xterm.dispose();
      xtermRef.current = null;
      fitAddonRef.current = null;
      writtenLengthRef.current = 0;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (xtermRef.current) {
      xtermRef.current.options.theme = TERMINAL_THEMES[theme] || TERMINAL_THEMES.dark;
    }
  }, [theme]);

  useEffect(() => {
    if (!xtermRef.current || !output) return;

    const newContent = output.slice(writtenLengthRef.current);
    if (newContent) {
      xtermRef.current.write(newContent);
      writtenLengthRef.current = output.length;
    }
  }, [output]);

  useEffect(() => {
    const handleResize = () => {
      if (fitAddonRef.current) {
        try {
          fitAddonRef.current.fit();
        } catch {
          // ignore
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
          fitAddonRef.current.fit();
        } catch {
          // ignore
        }
      }, 0);
    }
  }, [height]);

  const termTheme = TERMINAL_THEMES[theme] || TERMINAL_THEMES.dark;

  return (
    <div
      ref={containerRef}
      style={{
        height: `${height}px`,
        backgroundColor: termTheme.background,
        overflow: 'hidden',
      }}
    />
  );
}

OutputViewer.propTypes = {
  output: PropTypes.string,
  height: PropTypes.number,
};
