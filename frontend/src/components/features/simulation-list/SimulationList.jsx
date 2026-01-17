import { Row, Col, Card, Button } from 'react-bootstrap';
import { Link } from 'react-router-dom';
import PropTypes from 'prop-types';
import { SimulationCard } from './SimulationCard';
import { MaterialIcon } from '@components/common/Icon/MaterialIcon';

export function SimulationList({
  simulations,
  statuses,
  selectedSims,
  exitingCards,
  onCardClick,
  onRename,
  onStop,
  stopping,
}) {
  if (!simulations || simulations.length === 0) {
    return (
      <Card className="text-center py-5 border-dashed">
        <Card.Body>
          <div className="mb-3">
            <MaterialIcon name="science" size={48} className="text-muted" aria-hidden="true" />
          </div>
          <h5 className="mb-2">No Simulations Yet</h5>
          <p className="text-muted mb-4">
            Start your first federated learning experiment to see results here.
            <br />
            <small>
              Simulations let you test different aggregation strategies and attack scenarios.
            </small>
          </p>
          <Button as={Link} to="/simulations/new" variant="primary" className="d-inline-flex align-items-center">
            <MaterialIcon name="add" size={18} className="me-1" aria-hidden="true" />
            Create First Simulation
          </Button>
        </Card.Body>
      </Card>
    );
  }

  return (
    <Row xs={1} md={2} lg={3} className="g-4">
      {simulations.map((sim, index) => (
        <Col key={sim.simulation_id} style={{ '--card-index': index }}>
          <SimulationCard
            simulation={sim}
            statusData={statuses[sim.simulation_id]}
            isSelected={selectedSims.includes(sim.simulation_id)}
            isExiting={exitingCards?.includes(sim.simulation_id)}
            onCardClick={onCardClick}
            onRename={onRename}
            onStop={onStop}
            stopping={stopping}
          />
        </Col>
      ))}
    </Row>
  );
}

SimulationList.propTypes = {
  simulations: PropTypes.arrayOf(
    PropTypes.shape({
      simulation_id: PropTypes.string.isRequired,
      display_name: PropTypes.string,
      strategy_name: PropTypes.string,
      num_of_rounds: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
      num_of_clients: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
    })
  ),
  statuses: PropTypes.objectOf(
    PropTypes.shape({
      status: PropTypes.string,
      progress: PropTypes.number,
    })
  ),
  selectedSims: PropTypes.arrayOf(PropTypes.string),
  exitingCards: PropTypes.arrayOf(PropTypes.string),
  onCardClick: PropTypes.func,
  onRename: PropTypes.func,
  onStop: PropTypes.func,
  stopping: PropTypes.objectOf(PropTypes.bool),
};

SimulationList.defaultProps = {
  simulations: [],
  statuses: {},
  selectedSims: [],
  exitingCards: [],
  onCardClick: () => {},
  onRename: () => {},
  onStop: () => {},
  stopping: {},
};
