import './SimulationCard.css';
import PropTypes from 'prop-types';
import { Card, Badge, Stack } from 'react-bootstrap';
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
  const { simulation_id, display_name, created_at } = simulation;
  const isFailed = statusData?.status === 'failed';
  const isRunning = statusData?.status === 'running';

  const handleCardClick = e => {
    if (e.target.closest('a') || e.target.closest('button') || e.target.closest('input')) {
      return;
    }
    onCardClick(simulation_id, e);
  };

  const cfg = simulation.config?.shared_settings || simulation.config || {};
  const dataset = cfg.dataset_keyword || 'Unknown';
  const modelType = cfg.model_type || 'Unknown';
  const rounds = cfg.num_of_rounds || 'N/A';
  const clients = cfg.num_of_clients || 'N/A';
  const origin = statusData?.origin || simulation.origin || 'unknown';
  const strategies = simulation.config?.simulation_strategies || [];
  const strategyNames =
    strategies.length > 0
      ? Array.from(new Set(strategies.map(s => s.aggregation_strategy_keyword))).filter(Boolean)
      : [cfg.aggregation_strategy_keyword].filter(Boolean);

  const attackNames =
    strategies.length > 0
      ? Array.from(
          new Set(strategies.flatMap(s => s.attack_schedule?.map(a => a.attack_type) || []))
        ).filter(Boolean)
      : (cfg.attack_schedule?.map(a => a.attack_type) || []).filter(Boolean);

  return (
    <Card
      onClick={handleCardClick}
      className={`simulation-card shadow-sm ${isSelected ? 'selected' : ''} ${isExiting ? 'exiting' : ''}`}
    >
      <Card.Body>
        <div className="card-content flex-grow-1 min-width-0">
          <div className="card-title-row d-flex justify-content-between align-items-start mb-1">
            <div className="card-title-name flex-grow-1 me-2">
              <EditableSimName
                simulationId={simulation_id}
                displayName={display_name}
                onRename={onRename}
              />
            </div>
            <div className="card-title-status d-flex align-items-center gap-2">
              <StatusBadge status={statusData?.status} errorMessage={statusData?.error} />
              {isRunning && (
                <button
                  className="btn btn-xs btn-outline-warning"
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
          <div className="card-meta text-muted xs mb-2 d-flex align-items-center flex-wrap gap-2">
            <span className="badge bg-secondary-subtle text-secondary border-0 fw-normal">
              ID: {simulation_id}
            </span>
            {created_at && (
              <span className="text-secondary opacity-75">
                <i className="bi bi-clock me-1"></i>
                {getRelativeTime(created_at)}
              </span>
            )}
            <Badge
              bg={origin === 'api' ? 'info' : 'primary'}
              className="rounded-pill opacity-75 fw-normal"
            >
              {origin.toUpperCase()}
            </Badge>
          </div>

          {/* Error alert for failed simulations */}
          {isFailed && statusData.error && (
            <div className="mb-2">
              <ExpandableError error={statusData.error} maxLines={2} />
            </div>
          )}

          {/* Facts Section */}
          <Stack direction="horizontal" gap={2} className="flex-wrap mb-3">
            <div className="fact-badge d-flex align-items-center gap-1 bg-light border rounded-pill px-2 py-1 small">
              <i className="bi bi-database text-primary"></i>
              <span className="fw-medium">{dataset}</span>
            </div>
            <div className="fact-badge d-flex align-items-center gap-1 bg-light border rounded-pill px-2 py-1 small">
              <i className="bi bi-cpu text-success"></i>
              <span className="fw-medium">{modelType}</span>
            </div>
            <div className="fact-badge d-flex align-items-center gap-1 bg-light border rounded-pill px-2 py-1 small">
              <i className="bi bi-arrow-repeat text-info"></i>
              <span className="fw-medium">{rounds} rounds</span>
            </div>
            <div className="fact-badge d-flex align-items-center gap-1 bg-light border rounded-pill px-2 py-1 small">
              <i className="bi bi-people text-warning"></i>
              <span className="fw-medium">{clients} clients</span>
            </div>

            {strategyNames.map(sn => (
              <div
                key={sn}
                className="fact-badge d-flex align-items-center gap-1 bg-primary-subtle text-primary border border-primary-subtle rounded-pill px-2 py-1 small"
              >
                <i className="bi bi-layers"></i>
                <span className="fw-medium">{sn}</span>
              </div>
            ))}

            {attackNames.map(an => (
              <div
                key={an}
                className="fact-badge d-flex align-items-center gap-1 bg-danger-subtle text-danger border border-danger-subtle rounded-pill px-2 py-1 small"
              >
                <i className="bi bi-shield-exclamation"></i>
                <span className="fw-medium">{an}</span>
              </div>
            ))}
            {attackNames.length === 0 && (
              <div className="fact-badge d-flex align-items-center gap-1 bg-success-subtle text-success border border-success-subtle rounded-pill px-2 py-1 small">
                <i className="bi bi-shield-check"></i>
                <span className="fw-medium">No Attacks</span>
              </div>
            )}
          </Stack>

          {/* Action link */}
          <div className="d-flex justify-content-end">
            <Link
              to={`/simulations/${simulation_id}`}
              className="btn btn-sm btn-outline-primary rounded-pill px-3 fw-medium"
              onClick={e => e.stopPropagation()}
            >
              View Details →
            </Link>
          </div>
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
    config: PropTypes.object,
    origin: PropTypes.string,
  }).isRequired,
  statusData: PropTypes.shape({
    status: PropTypes.string,
    error: PropTypes.string,
    origin: PropTypes.string,
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
