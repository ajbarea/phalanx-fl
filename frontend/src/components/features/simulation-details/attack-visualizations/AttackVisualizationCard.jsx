import { useState, useEffect, useMemo } from 'react';
import { Card, Badge, Nav } from 'react-bootstrap';
import { VIZ_TYPES, ATTACK_TYPES, getVisualizationComponent } from './index';

/**
 * Main wrapper component for attack visualizations.
 * Automatically selects the appropriate visualization component based on attack type.
 */
export function AttackVisualizationCard({ snapshot, simulationId, onImageClick }) {
  const [activeTab, setActiveTab] = useState('primary');

  // Memoize visualizations to prevent dependency changes on every render
  const visualizations = useMemo(
    () => snapshot.visualizations || { primary: snapshot.image_path },
    [snapshot.visualizations, snapshot.image_path]
  );

  // Get attack metadata
  const attackInfo = ATTACK_TYPES[snapshot.attack_type] || null;
  const { Component: VisualizationComponent } = getVisualizationComponent(snapshot.attack_type);

  // Get available visualization types for this snapshot, sorted by priority
  const availableViz = useMemo(() => {
    return Object.entries(VIZ_TYPES)
      .filter(([key]) => visualizations[key])
      .sort((a, b) => a[1].priority - b[1].priority)
      .map(([key, config]) => ({ key, ...config }));
  }, [visualizations]);

  // Ensure active tab is valid
  useEffect(() => {
    if (!visualizations[activeTab]) {
      const firstAvailable = availableViz[0]?.key || 'primary';
      setActiveTab(firstAvailable);
    }
  }, [activeTab, visualizations, availableViz]);

  const renderVisualization = () => {
    const vizPath = visualizations[activeTab];
    if (!vizPath) return null;

    if (activeTab === 'html_diff') {
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
        alt={`${snapshot.attack_type} - ${VIZ_TYPES[activeTab]?.label || activeTab}`}
        className="img-fluid rounded"
        style={{ maxHeight: '400px', width: '100%', objectFit: 'contain', cursor: 'pointer' }}
        onClick={() => onImageClick?.({ ...snapshot, currentViz: activeTab })}
      />
    );
  };

  return (
    <Card className="h-100 shadow-sm">
      {/* Header */}
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
          <Badge
            bg="danger"
            style={attackInfo ? { backgroundColor: attackInfo.color } : {}}
            className="text-white"
          >
            {attackInfo?.icon || '⚠️'} {snapshot.attack_type.replace(/_/g, ' ')}
          </Badge>
        </div>
      </Card.Header>

      {/* Visualization Tabs */}
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

      {/* Main Visualization */}
      <Card.Body className="p-2">{renderVisualization()}</Card.Body>

      {/* Delegate to specialized component for stats/footer */}
      <VisualizationComponent
        snapshot={snapshot}
        simulationId={simulationId}
        activeTab={activeTab}
        attackInfo={attackInfo}
        availableViz={availableViz}
      />
    </Card>
  );
}
