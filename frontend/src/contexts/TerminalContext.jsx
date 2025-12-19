import { createContext, useContext, useState, useRef, useCallback } from 'react';

const TerminalContext = createContext();

// eslint-disable-next-line react-refresh/only-export-components
export function useTerminal() {
  const context = useContext(TerminalContext);
  if (!context) {
    throw new Error('useTerminal must be used within TerminalProvider');
  }
  return context;
}

export function TerminalProvider({ children }) {
  const [isOpen, setIsOpen] = useState(false);
  const terminalRef = useRef(null);

  const openTerminal = useCallback(() => {
    setIsOpen(true);
  }, []);

  const closeTerminal = useCallback(() => {
    setIsOpen(false);
  }, []);

  const toggleTerminal = useCallback(() => {
    setIsOpen(prev => !prev);
  }, []);

  const sendCommand = useCallback(command => {
    if (terminalRef.current?.sendCommand) {
      terminalRef.current.sendCommand(command);
    }
  }, []);

  const resetTerminal = useCallback(() => {
    if (terminalRef.current?.reset) {
      terminalRef.current.reset();
    }
  }, []);

  const interruptTerminal = useCallback(() => {
    if (terminalRef.current?.interrupt) {
      terminalRef.current.interrupt();
    }
  }, []);

  const interruptAndRun = useCallback(
    async command => {
      // Send Ctrl+C to stop any running process
      interruptTerminal();
      // Wait for interrupt to take effect
      await new Promise(resolve => setTimeout(resolve, 200));
      // Send the new command
      sendCommand(command);
    },
    [interruptTerminal, sendCommand]
  );

  return (
    <TerminalContext.Provider
      value={{
        isOpen,
        openTerminal,
        closeTerminal,
        toggleTerminal,
        sendCommand,
        resetTerminal,
        interruptTerminal,
        interruptAndRun,
        terminalRef,
        setIsOpen,
      }}
    >
      {children}
    </TerminalContext.Provider>
  );
}
