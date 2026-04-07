import { useTerminal } from '../../contexts/TerminalContext';
import { useTheme } from '../../contexts/ThemeContext';

export default function TerminalToggle({ className = '', style = {} }) {
  const { isOpen, setIsOpen } = useTerminal();
  const { theme } = useTheme();

  const colors =
    theme === 'dark'
      ? {
          text: '#ccc',
          buttonBg: '#2d2d2d',
        }
      : {
          text: '#495057',
          buttonBg: '#e9ecef',
        };

  return (
    <button
      onClick={() => setIsOpen(prev => !prev)}
      className={`terminal-toggle-btn ${className}`}
      title="Toggle Terminal (Ctrl+`)"
      style={{
        width: 42,
        height: 42,
        borderRadius: '50%',
        border: 'none',
        backgroundColor: isOpen ? 'var(--bs-success)' : colors.buttonBg,
        color: isOpen ? 'white' : colors.text,
        boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        transition: 'all 0.3s ease',
        fontSize: '18px',
        flexShrink: 0,
        ...style,
      }}
    >
      {isOpen ? '▼' : '>_'}
    </button>
  );
}
