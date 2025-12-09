import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import 'bootstrap/dist/css/bootstrap.min.css';
import './index.css';
import App from './App.jsx';
import { ThemeProvider } from './contexts/ThemeContext';
import { TerminalProvider } from './contexts/TerminalContext';

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ThemeProvider>
      <TerminalProvider>
        <App />
      </TerminalProvider>
    </ThemeProvider>
  </StrictMode>
);
