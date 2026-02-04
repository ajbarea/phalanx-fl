import { useState, useEffect, useMemo } from 'react';
import { Card, Alert, Spinner, Badge, Row, Col, Form, Modal, Button, Nav } from 'react-bootstrap';
import { apiClient } from '@api/client';
import { ImageLightbox } from '@components/common/ImageLightbox';

const VIZ_TYPES = {
  primary: { label: 'Samples', icon: '🖼️' },
  comparison: { label: 'Comparison', icon: '🔄' },
  confusion_matrix: { label: 'Confusion Matrix', icon: '📊' },
  difference_heatmap: { label: 'Difference Heatmap', icon: '🌡️' },
  weight_histogram: { label: 'Weight Distribution', icon: '📈' },
  prediction_grid: { label: 'Prediction Impact', icon: '🎯' },
  html_diff: { label: 'Token Diff', icon: '📝' },
};

const ATTACK_VIZ_OVERRIDES = {
  model_poisoning: {
    primary: { label: 'Prediction Comparison', icon: '🎯' },
  },
  gradient_scaling: {
    primary: { label: 'Prediction Comparison', icon: '🎯' },
  },
  byzantine_perturbation: {
    primary: { label: 'Prediction Comparison', icon: '🎯' },
  },
};

const getVizConfig = (vizType, attackType) => {
  const override = ATTACK_VIZ_OVERRIDES[attackType]?.[vizType];
  return override || VIZ_TYPES[vizType] || { label: vizType, icon: '📄' };
};

const ATTACK_DESCRIPTIONS = {
  label_flipping: {
    title: 'Label Flipping Attack',
    description:
      'Changes training labels to wrong classes without modifying the actual images. The visual comparison shows identical images with different labels.',
    tip: 'Check the Confusion Matrix tab to see label remapping patterns.',
  },
  gaussian_noise: {
    title: 'Gaussian Noise Attack',
    description: 'Adds random noise to training images, disrupting the learning process.',
    tip: 'Check the Difference Heatmap tab to see pixel-level noise patterns.',
  },
  model_poisoning: {
    title: 'Model Poisoning Attack',
    description: 'Manipulates model weights to extreme values, degrading performance.',
    tip: 'Compare predictions before/after poisoning and check Weight Distribution.',
  },
  gradient_scaling: {
    title: 'Gradient Scaling Attack',
    description: 'Multiplies weight updates by a factor, amplifying malicious changes.',
    tip: 'Check the Weight Distribution tab to see the scale of modifications.',
  },
  byzantine_perturbation: {
    title: 'Byzantine Perturbation Attack',
    description: 'Injects random noise into model weights during training.',
    tip: 'Check the Weight Distribution tab to see noise patterns.',
  },
  token_replacement: {
    title: 'Token Replacement Attack',
    description: 'Replaces tokens in text data with adversarial alternatives.',
    tip: 'Check the Token Diff tab for detailed before/after comparison.',
  },
};

function AttackSnapshotCard({ snapshot, simulationId, onImageClick }) {
  const [activeTab, setActiveTab] = useState('primary');

  const visualizations = useMemo(
    () => snapshot.visualizations || { primary: snapshot.image_path },
    [snapshot.visualizations, snapshot.image_path]
  );

  const availableViz = useMemo(() => {
    return Object.keys(VIZ_TYPES)
      .filter(key => visualizations[key])
      .map(key => ({ key, ...getVizConfig(key, snapshot.attack_type) }));
  }, [visualizations, snapshot.attack_type]);

  const attackInfo = ATTACK_DESCRIPTIONS[snapshot.attack_type] || null;

  useEffect(() => {
    if (!visualizations[activeTab]) {
      const firstAvailable = availableViz[0]?.key || 'primary';
      setActiveTab(firstAvailable);
    }
  }, [activeTab, visualizations, availableViz]);

  const renderVisualization = () => {
    const vizPath = visualizations[activeTab];
    if (!vizPath) return null;

    const isHtmlViz = activeTab === 'html_diff' || vizPath.endsWith('.html');

    if (isHtmlViz) {
      return (
        <iframe
          src={`/api/simulations/${simulationId}/results/${vizPath}`}
          title="Token Replacement Visualization"
          className="w-100 rounded border-0"
          style={{ height: '500px', backgroundColor: '#1e1e1e' }}
        />
      );
    }

    return (
      <img
        src={`/api/simulations/${simulationId}/results/${vizPath}`}
        alt={`${snapshot.attack_type} - ${getVizConfig(activeTab, snapshot.attack_type).label}`}
        className="img-fluid rounded"
        style={{ maxHeight: '400px', width: '100%', objectFit: 'contain', cursor: 'pointer' }}
        onClick={() => onImageClick({ ...snapshot, currentViz: activeTab })}
      />
    );
  };

  return (
    <Card className="h-100 shadow-sm">
      <Card.Header className="py-2">
        <div className="d-flex justify-content-between align-items-center flex-wrap gap-2">
          <div>
            <Badge bg="primary" className="me-2">
              Round {snapshot.round_num}
            </Badge>
            <Badge bg="secondary" className="me-2">
              Client {snapshot.client_id}
            </Badge>
          </div>
          <Badge bg="danger">{snapshot.attack_type.replace(/_/g, ' ')}</Badge>
        </div>
      </Card.Header>

      {availableViz.length > 1 && (
        <Card.Body className="py-2 px-3 border-bottom">
          <Nav variant="pills" className="flex-row flex-wrap gap-1" activeKey={activeTab}>
            {availableViz.map(viz => (
              <Nav.Item key={viz.key}>
                <Nav.Link
                  eventKey={viz.key}
                  onClick={() => setActiveTab(viz.key)}
                  className="py-1 px-2 small"
                  style={{ fontSize: '0.75rem' }}
                >
                  {viz.icon} {viz.label}
                </Nav.Link>
              </Nav.Item>
            ))}
          </Nav>
        </Card.Body>
      )}

      <Card.Body className="p-2">{renderVisualization()}</Card.Body>

      {snapshot.metadata && (
        <Card.Footer className="py-2 small text-muted">
          <div className="d-flex justify-content-between flex-wrap gap-1">
            {snapshot.metadata.num_samples && <span>Samples: {snapshot.metadata.num_samples}</span>}
            {snapshot.metadata.data_shape && (
              <span>Shape: {snapshot.metadata.data_shape.join(' × ')}</span>
            )}
            {/* Weight attack statistics */}
            {snapshot.metadata.statistics?.difference && (
              <>
                <span>
                  Changed: {snapshot.metadata.statistics.difference.pct_changed?.toFixed(1)}%
                </span>
                <span>
                  L2 Norm: {snapshot.metadata.statistics.difference.diff_l2_norm?.toFixed(2)}
                </span>
              </>
            )}
          </div>
        </Card.Footer>
      )}

      {/* Label Flipping Summary Stats */}
      {snapshot.flip_summary && snapshot.attack_type === 'label_flipping' && (
        <Card.Footer className="py-2 small border-top" style={{ backgroundColor: '#fff3cd' }}>
          <div className="d-flex flex-wrap gap-2 align-items-center">
            <Badge bg="danger">
              {snapshot.flip_summary.flipped_samples}/{snapshot.flip_summary.total_samples} flipped
              ({snapshot.flip_summary.flip_rate}%)
            </Badge>
            {snapshot.flip_summary.top_flip_patterns?.slice(0, 2).map((pattern, i) => (
              <Badge key={i} bg="secondary">
                {pattern.from} → {pattern.to} ({pattern.count})
              </Badge>
            ))}
          </div>
        </Card.Footer>
      )}

      {attackInfo && activeTab === 'primary' && (
        <Card.Footer className="py-2 small border-top bg-light">
          <div className="text-muted">
            <strong className="d-block mb-1">{attackInfo.title}</strong>
            <p className="mb-1" style={{ fontSize: '0.75rem' }}>
              {attackInfo.description}
            </p>
            {availableViz.length > 1 && (
              <p className="mb-0 fst-italic" style={{ fontSize: '0.7rem' }}>
                💡 {attackInfo.tip}
              </p>
            )}
          </div>
        </Card.Footer>
      )}
    </Card>
  );
}

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

  const allSnapshots = data.strategies.flatMap(s => s.snapshots);
  const uniqueRounds = [...new Set(allSnapshots.map(s => s.round_num))].sort((a, b) => a - b);
  const uniqueClients = [...new Set(allSnapshots.map(s => s.client_id))].sort((a, b) => a - b);

  const filteredSnapshots = allSnapshots.filter(snapshot => {
    if (selectedRound !== 'all' && snapshot.round_num !== parseInt(selectedRound)) return false;
    if (selectedClient !== 'all' && snapshot.client_id !== parseInt(selectedClient)) return false;
    return true;
  });

  const summary = data.strategies[0]?.summary;

  const vizTypeCounts = {};
  allSnapshots.forEach(s => {
    if (s.visualizations) {
      Object.keys(s.visualizations).forEach(vt => {
        vizTypeCounts[vt] = (vizTypeCounts[vt] || 0) + 1;
      });
    }
  });

  return (
    <Card className="mt-3">
      <Card.Body>
        <h5 className="mb-3">Attack Snapshots</h5>

        {summary && (
          <Alert
            variant="secondary"
            className="mb-3"
            style={{
              backgroundColor: 'var(--color-surface-variant)',
              border: '1px solid var(--color-border)',
              color: 'var(--color-text-primary)',
            }}
          >
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
            {Object.keys(vizTypeCounts).length > 1 && (
              <div className="mt-2 small text-muted">
                <strong>Available Visualizations:</strong>{' '}
                {Object.entries(VIZ_TYPES)
                  .filter(([key]) => vizTypeCounts[key])
                  .map(([key, config]) => (
                    <Badge key={key} bg="secondary" className="me-1">
                      {config.icon} {config.label}
                    </Badge>
                  ))}
              </div>
            )}
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
            <Col key={idx} xs={12} lg={snapshot.is_text_attack ? 12 : 6}>
              <AttackSnapshotCard
                snapshot={snapshot}
                simulationId={simulationId}
                onImageClick={setModalImage}
              />
            </Col>
          ))}
        </Row>

        {filteredSnapshots.length === 0 && (
          <Alert variant="info" className="mt-3">
            No snapshots match the current filters.
          </Alert>
        )}
      </Card.Body>

      {/* Full-size image lightbox with zoom */}
      {modalImage && modalImage.currentViz !== 'html_diff' && (
        <ImageLightbox
          show={!!modalImage}
          onHide={() => setModalImage(null)}
          src={`/api/simulations/${simulationId}/results/${
            modalImage.visualizations?.[modalImage.currentViz] || modalImage.image_path
          }`}
          alt={`${modalImage.attack_type} visualization`}
          title={
            `${modalImage.attack_type.replace(/_/g, ' ')} - Client ${modalImage.client_id}, Round ${modalImage.round_num}` +
            (modalImage.currentViz && modalImage.currentViz !== 'primary'
              ? ` - ${getVizConfig(modalImage.currentViz, modalImage.attack_type).label}`
              : '')
          }
          footerContent={
            modalImage.visualizations &&
            Object.keys(modalImage.visualizations).length > 1 && (
              <small className="text-muted">
                Views:{' '}
                {Object.keys(VIZ_TYPES)
                  .filter(key => modalImage.visualizations[key])
                  .map(key => {
                    const config = getVizConfig(key, modalImage.attack_type);
                    return (
                      <Badge key={key} bg="secondary" className="me-1">
                        {config.icon} {config.label}
                      </Badge>
                    );
                  })}
              </small>
            )
          }
        />
      )}

      {/* HTML diff modal (for text-based attacks like token replacement) */}
      {modalImage && modalImage.currentViz === 'html_diff' && (
        <Modal show={true} onHide={() => setModalImage(null)} size="xl" centered>
          <Modal.Header closeButton>
            <Modal.Title>
              {modalImage.attack_type.replace(/_/g, ' ')} - Client {modalImage.client_id}, Round{' '}
              {modalImage.round_num} - Token Diff
            </Modal.Title>
          </Modal.Header>
          <Modal.Body className="p-0">
            <iframe
              src={`/api/simulations/${simulationId}/results/${modalImage.visualizations?.html_diff}`}
              title="Token Replacement Visualization"
              className="w-100 border-0"
              style={{ height: '80vh' }}
            />
          </Modal.Body>
          <Modal.Footer>
            <Button variant="secondary" onClick={() => setModalImage(null)}>
              Close
            </Button>
          </Modal.Footer>
        </Modal>
      )}
    </Card>
  );
}
