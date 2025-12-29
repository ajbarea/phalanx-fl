import { useState, useEffect } from 'react';
import { Card, Alert, Spinner, Badge, Row, Col, Form, Modal, Button } from 'react-bootstrap';
import { apiClient } from '@api/client';

export function AttackSnapshotsTab({ simulationId, status }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);
  const [selectedRound, setSelectedRound] = useState('all');
  const [selectedClient, setSelectedClient] = useState('all');
  const [modalImage, setModalImage] = useState(null);

  useEffect(() => {
    if (status !== 'completed') {
      setLoading(false);
      return;
    }

    const fetchSnapshots = async () => {
      try {
        const response = await apiClient.get(`/simulations/${simulationId}/attack-snapshots`);
        setData(response.data);
      } catch (err) {
        setError(err.response?.data?.detail || err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchSnapshots();
  }, [simulationId, status]);

  if (status !== 'completed') {
    return (
      <Card className="mt-3">
        <Card.Body>
          <Alert variant="info">
            Attack snapshots will be available once the simulation completes.
          </Alert>
        </Card.Body>
      </Card>
    );
  }

  if (loading) {
    return (
      <Card className="mt-3">
        <Card.Body className="text-center py-4">
          <Spinner animation="border" size="sm" className="me-2" />
          Loading attack snapshots...
        </Card.Body>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="mt-3">
        <Card.Body>
          <Alert variant="warning">Failed to load attack snapshots: {error}</Alert>
        </Card.Body>
      </Card>
    );
  }

  if (!data?.has_snapshots || !data.strategies?.length) {
    return (
      <Card className="mt-3">
        <Card.Body>
          <Alert variant="info">
            <strong>No attack snapshots available.</strong>
            <p className="mb-0 mt-2">
              Attack snapshots are generated when <code>save_attack_snapshots</code> is enabled and
              malicious clients are configured. Try running a simulation with attacks enabled.
            </p>
          </Alert>
        </Card.Body>
      </Card>
    );
  }

  // Combine all snapshots from all strategies for filtering
  const allSnapshots = data.strategies.flatMap(s => s.snapshots);
  const uniqueRounds = [...new Set(allSnapshots.map(s => s.round_num))].sort((a, b) => a - b);
  const uniqueClients = [...new Set(allSnapshots.map(s => s.client_id))].sort((a, b) => a - b);

  // Filter snapshots
  const filteredSnapshots = allSnapshots.filter(snapshot => {
    if (selectedRound !== 'all' && snapshot.round_num !== parseInt(selectedRound)) return false;
    if (selectedClient !== 'all' && snapshot.client_id !== parseInt(selectedClient)) return false;
    return true;
  });

  // Get summary from first strategy
  const summary = data.strategies[0]?.summary;

  return (
    <Card className="mt-3">
      <Card.Body>
        <h5 className="mb-3">Attack Snapshots</h5>

        {summary && (
          <Alert variant="light" className="mb-3 border">
            <div className="d-flex flex-wrap gap-3">
              <div>
                <strong>Total Snapshots:</strong> {summary.attack_summary?.total_snapshots || 0}
              </div>
              <div>
                <strong>Malicious Clients:</strong>{' '}
                {summary.attack_summary?.clients_attacked?.join(', ') || 'None'}
              </div>
              <div>
                <strong>Attack Types:</strong>{' '}
                {summary.attack_summary?.attack_types?.map(type => (
                  <Badge key={type} bg="danger" className="me-1">
                    {type.replace(/_/g, ' ')}
                  </Badge>
                ))}
              </div>
            </div>
          </Alert>
        )}

        <Row className="mb-3">
          <Col xs={12} md={4}>
            <Form.Group>
              <Form.Label className="small fw-semibold">Filter by Round</Form.Label>
              <Form.Select
                size="sm"
                value={selectedRound}
                onChange={e => setSelectedRound(e.target.value)}
              >
                <option value="all">All Rounds ({uniqueRounds.length})</option>
                {uniqueRounds.map(r => (
                  <option key={r} value={r}>
                    Round {r}
                  </option>
                ))}
              </Form.Select>
            </Form.Group>
          </Col>
          <Col xs={12} md={4}>
            <Form.Group>
              <Form.Label className="small fw-semibold">Filter by Client</Form.Label>
              <Form.Select
                size="sm"
                value={selectedClient}
                onChange={e => setSelectedClient(e.target.value)}
              >
                <option value="all">All Clients ({uniqueClients.length})</option>
                {uniqueClients.map(c => (
                  <option key={c} value={c}>
                    Client {c}
                  </option>
                ))}
              </Form.Select>
            </Form.Group>
          </Col>
          <Col xs={12} md={4} className="d-flex align-items-end">
            <small className="text-muted">
              Showing {filteredSnapshots.length} of {allSnapshots.length} snapshots
            </small>
          </Col>
        </Row>

        <Row className="g-3">
          {filteredSnapshots.map((snapshot, idx) => (
            <Col key={idx} xs={12} lg={6}>
              <Card
                className="h-100 shadow-sm"
                style={{ cursor: 'pointer' }}
                onClick={() => setModalImage(snapshot)}
              >
                <Card.Header className="py-2 d-flex justify-content-between align-items-center">
                  <div>
                    <Badge bg="primary" className="me-2">
                      Round {snapshot.round_num}
                    </Badge>
                    <Badge bg="secondary" className="me-2">
                      Client {snapshot.client_id}
                    </Badge>
                  </div>
                  <Badge bg="danger">{snapshot.attack_type.replace(/_/g, ' ')}</Badge>
                </Card.Header>
                <Card.Body className="p-2">
                  <img
                    src={`/api/simulations/${simulationId}/results/${snapshot.image_path}`}
                    alt={`${snapshot.attack_type} attack - Client ${snapshot.client_id} Round ${snapshot.round_num}`}
                    className="img-fluid rounded"
                    style={{ maxHeight: '300px', width: '100%', objectFit: 'contain' }}
                  />
                </Card.Body>
                {snapshot.metadata && (
                  <Card.Footer className="py-2 small text-muted">
                    <div className="d-flex justify-content-between">
                      <span>Samples: {snapshot.metadata.num_samples}</span>
                      {snapshot.metadata.data_shape && (
                        <span>Shape: {snapshot.metadata.data_shape.join(' x ')}</span>
                      )}
                    </div>
                  </Card.Footer>
                )}
              </Card>
            </Col>
          ))}
        </Row>

        {filteredSnapshots.length === 0 && (
          <Alert variant="info" className="mt-3">
            No snapshots match the current filters.
          </Alert>
        )}

        <div className="mt-4 small text-muted">
          <strong>Understanding Attack Snapshots:</strong>
          <ul className="mb-0 mt-2">
            <li>
              <strong>Before/After Comparisons:</strong> Images show original data (left) vs
              poisoned data (right)
            </li>
            <li>
              <strong>Label Flipping:</strong> Changes labels to wrong classes, causing model
              confusion
            </li>
            <li>
              <strong>Gaussian Noise:</strong> Adds random noise to training images, disrupting
              learning
            </li>
            <li>
              <strong>Model Poisoning:</strong> Manipulates model weights to extreme values,
              degrading performance
            </li>
            <li>
              <strong>Gradient Scaling:</strong> Multiplies weight updates by a factor, amplifying
              malicious changes
            </li>
            <li>
              <strong>Byzantine Perturbation:</strong> Injects random noise into model weights
            </li>
            <li>
              <strong>Token Replacement:</strong> Replaces tokens in text data with adversarial
              alternatives (NLP)
            </li>
          </ul>
        </div>
      </Card.Body>

      {/* Full-size image modal */}
      <Modal show={!!modalImage} onHide={() => setModalImage(null)} size="xl" centered>
        {modalImage && (
          <>
            <Modal.Header closeButton>
              <Modal.Title>
                {modalImage.attack_type.replace(/_/g, ' ')} - Client {modalImage.client_id}, Round{' '}
                {modalImage.round_num}
              </Modal.Title>
            </Modal.Header>
            <Modal.Body className="text-center p-0">
              <img
                src={`/api/simulations/${simulationId}/results/${modalImage.image_path}`}
                alt="Full size attack snapshot"
                style={{ maxWidth: '100%', maxHeight: '80vh' }}
              />
            </Modal.Body>
            <Modal.Footer>
              <Button variant="secondary" onClick={() => setModalImage(null)}>
                Close
              </Button>
            </Modal.Footer>
          </>
        )}
      </Modal>
    </Card>
  );
}
