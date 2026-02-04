import { BrowserRouter as Router, Route, Routes, Link } from 'react-router-dom';
import { Navbar, Nav, Container } from 'react-bootstrap';
import { Dashboard } from './pages/Dashboard/Dashboard';
import { NewSimulation } from './pages/NewSimulation/NewSimulation';
import { SimulationDetails } from './pages/SimulationDetails/SimulationDetails';
import { ExperimentQueue } from './pages/ExperimentQueue/ExperimentQueue';
import { QueueStatus } from './pages/QueueStatus/QueueStatus';
import { NotFound } from './pages/NotFound/NotFound';
import AssistantPage from './pages/Assistant/AssistantPage';
import ComparisonView from './components/ComparisonView';
import TerminalPanel from './components/TerminalPanel';
import ErrorBoundary from './components/ErrorBoundary';
import ThemeToggle from './components/ThemeToggle';
import { DeviceIndicator } from './components/layout/DeviceIndicator';
import { AssistantRuntimeProvider, AssistantPanel } from './components/features/Assistant';
import { Toaster } from 'sonner';
import { useEffect, useState } from 'react';
import { useTerminal } from './contexts/TerminalContext';
import './App.css';

function App() {
  const { isOpen: isTerminalOpen } = useTerminal();
  const [isAssistantOpen, setIsAssistantOpen] = useState(false);
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem('theme') || 'light';
  });

  useEffect(() => {
    const handleThemeChange = () => {
      const currentTheme = localStorage.getItem('theme') || 'light';
      setTheme(currentTheme);
    };

    window.addEventListener('storage', handleThemeChange);

    // MutationObserver catches theme changes from ThemeToggle component
    const observer = new MutationObserver(() => {
      const htmlElement = document.documentElement;
      const isDark = htmlElement.getAttribute('data-bs-theme') === 'dark';
      setTheme(isDark ? 'dark' : 'light');
    });

    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-bs-theme'],
    });

    return () => {
      window.removeEventListener('storage', handleThemeChange);
      observer.disconnect();
    };
  }, []);

  return (
    <ErrorBoundary>
      <Toaster
        position="top-right"
        theme={theme}
        toastOptions={{
          duration: 4000,
          style: {
            fontFamily: 'var(--bs-body-font-family)',
          },
        }}
      />
      <Router>
        <AssistantRuntimeProvider>
          <Navbar expand="md" className="mb-3" bg="body-tertiary">
            <Container>
              <Navbar.Brand as={Link} to="/" className="d-flex align-items-center gap-2">
                <img
                  src="/intellifl.png"
                  alt="IntelliFL Logo"
                  height={56}
                  width={56}
                  style={{ objectFit: 'contain' }}
                />
                <span className="brand-text">
                  Intelli<span className="brand-text-fl">FL</span>
                </span>
              </Navbar.Brand>
              <Navbar.Toggle aria-controls="navbar-nav" />
              <Navbar.Collapse id="navbar-nav">
                <Nav className="me-auto">
                  <Nav.Link as={Link} to="/">
                    Dashboard
                  </Nav.Link>
                  <Nav.Link as={Link} to="/simulations/new">
                    New Simulation
                  </Nav.Link>
                  <Nav.Link as={Link} to="/experiments/queue">
                    Experiment Queue
                  </Nav.Link>
                  <Nav.Link as={Link} to="/assistant">
                    Assistant
                  </Nav.Link>
                </Nav>
                <Nav className="align-items-center">
                  <button
                    className="aui-navbar-btn"
                    onClick={() => setIsAssistantOpen(true)}
                    title="Open Assistant"
                    aria-label="Open IntelliFL Assistant"
                  >
                    <span className="material-symbols-outlined">chat</span>
                  </button>
                  <DeviceIndicator />
                  <ThemeToggle />
                </Nav>
              </Navbar.Collapse>
            </Container>
          </Navbar>
          <Container
            className="mt-4"
            style={{
              paddingBottom: isTerminalOpen ? '420px' : '60px',
              transition: 'padding-bottom 0.3s ease',
            }}
          >
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/simulations/new" element={<NewSimulation />} />
              <Route path="/experiments/queue" element={<ExperimentQueue />} />
              <Route path="/queue/:simulationId" element={<QueueStatus />} />
              <Route path="/simulations/:simulationId" element={<SimulationDetails />} />
              <Route path="/compare" element={<ComparisonView />} />
              <Route path="/assistant" element={<AssistantPage />} />
              {/* Catch-all 404 route - must be last */}
              <Route path="*" element={<NotFound />} />
            </Routes>
          </Container>
          <AssistantPanel isOpen={isAssistantOpen} onClose={() => setIsAssistantOpen(false)} />
          <TerminalPanel />
        </AssistantRuntimeProvider>
      </Router>
    </ErrorBoundary>
  );
}

export default App;
