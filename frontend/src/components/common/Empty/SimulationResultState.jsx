import PropTypes from 'prop-types';
import { Alert, Spinner } from 'react-bootstrap';

const PENDING_STATUSES = new Set(['running', 'pending', 'queued', 'loading']);
const FAILED_STATUSES = new Set(['failed', 'stopped']);

/**
 * Consistent placeholder for a simulation result tab (Insights, Plots, Attacks,
 * Metrics) when there is no data to show yet. One component + one copy template
 * so the tabs no longer diverge (spinner here, badge there, plaintext elsewhere).
 *
 * A simulation is a long-running async job, so the in-progress case gets a busy
 * indicator plus an explicit "what's coming" message (per 2026 pending-UI
 * guidance) rather than a skeleton, which would imply imminent content.
 *
 * @param {string} noun - Capitalized tab subject, e.g. "Insights", "Plots".
 */
export function SimulationResultState({ noun, status, className = 'mt-3' }) {
  const lower = noun.toLowerCase();

  if (PENDING_STATUSES.has(status)) {
    return (
      <div className={`text-center p-4 ${className}`}>
        <Spinner animation="border" role="status" variant="primary" size="sm" className="mb-2">
          <span className="visually-hidden">Simulation in progress</span>
        </Spinner>
        <p className="text-muted mb-0">{noun} will appear here once the simulation finishes.</p>
      </div>
    );
  }

  if (FAILED_STATUSES.has(status)) {
    return (
      <Alert variant="warning" className={className}>
        Simulation {status} — no {lower} to show.
      </Alert>
    );
  }

  return (
    <Alert variant="info" className={className}>
      No {lower} available for this simulation.
    </Alert>
  );
}

SimulationResultState.propTypes = {
  /** Capitalized subject of the tab, e.g. "Insights", "Attack snapshots". */
  noun: PropTypes.string.isRequired,
  /** Simulation status string from the API. */
  status: PropTypes.string,
  /** Wrapper classes (defaults to top margin). */
  className: PropTypes.string,
};
