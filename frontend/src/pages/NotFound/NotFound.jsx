import { Link } from 'react-router-dom';
import { Container, Row, Col, Button, Card } from 'react-bootstrap';

/** 404 page with navigation links to help users find their way back. */
export function NotFound() {
  const popularLinks = [
    { to: '/', label: 'Dashboard', description: 'View all simulations' },
    { to: '/simulations/new', label: 'New Simulation', description: 'Create a new experiment' },
    { to: '/experiments/queue', label: 'Experiment Queue', description: 'Run multiple strategies' },
  ];

  return (
    <Container className="py-5">
      <Row className="justify-content-center">
        <Col xs={12} md={8} lg={6}>
          <Card className="text-center shadow-sm">
            <Card.Body className="py-5">
              <div
                className="display-1 fw-bold text-muted mb-2"
                style={{ fontSize: '6rem', lineHeight: 1 }}
              >
                404
              </div>

              <h1 className="h3 mb-3">Page Not Found</h1>

              <p className="text-muted mb-4">
                The page you&apos;re looking for doesn&apos;t exist or has been moved. This may
                happen if a simulation was deleted or the URL was entered incorrectly.
              </p>

              <Button as={Link} to="/" variant="primary" size="lg" className="mb-4">
                Return to Dashboard
              </Button>

              <hr className="my-4" />
              <p className="text-muted small mb-3">Or navigate to:</p>
              <div className="d-flex flex-wrap justify-content-center gap-2">
                {popularLinks.map(link => (
                  <Button
                    key={link.to}
                    as={Link}
                    to={link.to}
                    variant="outline-secondary"
                    size="sm"
                    title={link.description}
                  >
                    {link.label}
                  </Button>
                ))}
              </div>
            </Card.Body>

            <Card.Footer className="text-muted small">
              <strong>Tip:</strong> If you followed a link to get here, the simulation may have been
              deleted. Check the Dashboard for available simulations.
            </Card.Footer>
          </Card>
        </Col>
      </Row>
    </Container>
  );
}

export default NotFound;
