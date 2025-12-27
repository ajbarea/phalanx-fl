import { BrowserRouter as Router, Route, Routes, Link } from 'react-router-dom';
import { Navbar, Nav, Container } from 'react-bootstrap';
import { Dashboard } from './pages/Dashboard/Dashboard';
import { SimulationDetails } from './pages/SimulationDetails/SimulationDetails';
import { NewSimulation } from './pages/NewSimulation/NewSimulation';
import { ExperimentQueue } from './pages/ExperimentQueue/ExperimentQueue';
import { QueueStatus } from './pages/QueueStatus/QueueStatus';
import { NotFound } from './pages/NotFound/NotFound';
import ComparisonView from './components/ComparisonView';
import TerminalPanel from './components/TerminalPanel';
import ErrorBoundary from './components/ErrorBoundary';
import ThemeToggle from './components/ThemeToggle';
import { Toaster } from 'sonner';
import { useEffect, useState } from 'react';
import { useTerminal } from './contexts/TerminalContext';
import './App.css';

function App() {
  const { isOpen: isTerminalOpen } = useTerminal();
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
        <Navbar
          expand="md"
          className="mb-3"
          style={{ backgroundColor: 'var(--color-surface-variant)' }}
        >
          <Container>
            <Navbar.Brand as={Link} to="/">
              IntelliFL
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
              </Nav>
              <Nav>
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
            {/* Catch-all 404 route - must be last */}
            <Route path="*" element={<NotFound />} />
          </Routes>
        </Container>
        <TerminalPanel />
      </Router>
    </ErrorBoundary>
  );
}

export default App;
