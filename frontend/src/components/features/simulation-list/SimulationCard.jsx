import PropTypes from 'prop-types';
import { Card, Form } from 'react-bootstrap';
import { Link } from 'react-router-dom';
import { StatusBadge } from '@components/common/Badge/StatusBadge';
import { ExpandableError } from '@components/common/ExpandableError';
import EditableSimName from '@components/EditableSimName';
import { getRelativeTime } from '@utils/formatters';

export function SimulationCard({
  simulation,
  statusData,
  isSelected,
  isExiting,
  onCardClick,
  onRename,
  onStop,
  stopping,
}) {
  const { simulation_id, display_name, created_at, num_of_rounds, num_of_clients } = simulation;
  const isFailed = statusData?.status === 'failed';
  const isRunning = statusData?.status === 'running';

  const handleCheckboxChange = e => {
    e.stopPropagation();
    onCardClick(simulation_id, e);
  };

  const handleCardClick = e => {
    // Don't select if clicking on links or buttons
    if (e.target.closest('a') || e.target.closest('button') || e.target.closest('input')) {
      return;
    }
    onCardClick(simulation_id, e);
  };

  return (
    <Card
      onClick={handleCardClick}
      className={`simulation-card ${isSelected ? 'selected' : ''} ${isExiting ? 'exiting' : ''}`}
    >
      <Card.Body className="d-flex gap-3">
        {/* Selection checkbox - LEFT side, always visible */}
        <div className="card-checkbox">
          <Form.Check
            type="checkbox"
            checked={isSelected}
            onChange={handleCheckboxChange}
            aria-label={`Select ${display_name || simulation_id}`}
            className="simulation-checkbox"
          />
        </div>

        {/* Main content area */}
        <div className="card-content flex-grow-1 min-width-0">
          {/* Title row with name and status */}
          <div className="card-title-row">
            <div className="card-title-name">
              <EditableSimName
                simulationId={simulation_id}
                displayName={display_name}
                onRename={onRename}
              />
            </div>
            <div className="card-title-status">
              <StatusBadge status={statusData?.status} error={statusData?.error} />
              {/* Stop button - only for running simulations */}
              {isRunning && (
                <button
                  className="btn btn-sm btn-outline-warning ms-2"
                  onClick={e => {
                    e.stopPropagation();
                    onStop(simulation_id);
                  }}
                  disabled={stopping}
                  title="Stop simulation"
                  aria-label="Stop simulation"
                >
                  Stop
                </button>
              )}
            </div>
          </div>

          {/* Metadata row */}
          <div className="card-meta text-muted small mb-2">
            ID: <code>{simulation_id}</code>
            {created_at && (
              <>
                <span className="mx-2">•</span>
                {getRelativeTime(created_at)}
              </>
            )}
          </div>

          {/* Error alert for failed simulations */}
          {isFailed && statusData.error && (
            <ExpandableError error={statusData.error} maxLines={2} />
          )}

          {/* Stats row */}
          <div className="card-stats small text-muted mb-2">
            {num_of_rounds} rounds • {num_of_clients} clients
          </div>

          {/* Action link */}
          <Link
            to={`/simulations/${simulation_id}`}
            className="btn btn-sm btn-outline-primary"
            onClick={e => e.stopPropagation()}
          >
            View Details →
          </Link>
        </div>
      </Card.Body>
    </Card>
  );
}

SimulationCard.propTypes = {
  simulation: PropTypes.shape({
    simulation_id: PropTypes.string.isRequired,
    display_name: PropTypes.string,
    created_at: PropTypes.string,
    num_of_rounds: PropTypes.number,
    num_of_clients: PropTypes.number,
  }).isRequired,
  statusData: PropTypes.shape({
    status: PropTypes.string,
    error: PropTypes.string,
  }),
  isSelected: PropTypes.bool,
  isExiting: PropTypes.bool,
  onCardClick: PropTypes.func.isRequired,
  onRename: PropTypes.func.isRequired,
  onStop: PropTypes.func.isRequired,
  stopping: PropTypes.bool,
};

SimulationCard.defaultProps = {
  isSelected: false,
  isExiting: false,
  stopping: false,
};
