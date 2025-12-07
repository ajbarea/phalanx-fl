import { Card } from 'react-bootstrap';
import Terminal from '../../components/Terminal';

export function TerminalPage() {
  return (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h1>Terminal</h1>
      </div>

      <Card>
        <Card.Body className="p-0">
          <Terminal height={500} showQuickCommands={true} />
        </Card.Body>
      </Card>

      <div className="mt-3 text-muted">
        <small>
          <strong>Tips:</strong> Use the quick command buttons or type commands directly.
          Common commands: <code>./run_simulation.sh</code>, <code>bash clean.sh</code>,{' '}
          <code>git status</code>
        </small>
      </div>
    </div>
  );
}

export default TerminalPage;
