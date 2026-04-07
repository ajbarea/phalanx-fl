import { Table, Button, Form, Dropdown, Badge, OverlayTrigger, Tooltip } from 'react-bootstrap';
import {
  QUICK_PATTERNS,
  AGGREGATION_STRATEGIES,
  STRATEGY_DEFAULTS,
} from '@constants/strategyVariations';
import { ATTACKS } from '@constants/attacks';
import { formatAttackName } from '@constants/strategyLabels';
import { InfoTooltip } from '@components/common/Tooltip/InfoTooltip';
import { MaterialIcon } from '@components/common/Icon/MaterialIcon';

// Helper to check which parameters a strategy needs
const strategyNeeds = {
  krumSelections: s => ['krum', 'multi-krum', 'bulyan'].includes(s),
  trustParams: s => s === 'trust',
  pidParams: s => s === 'pid',
  trimRatio: s => s === 'trimmed_mean',
  removeFromRound: s => ['trust', 'pid', 'bulyan', 'trimmed_mean', 'rfa'].includes(s),
};

export function StrategyVariationList({
  variations,
  onChange,
  numOfClients,
  numOfRounds,
  onQuickPattern,
}) {
  // Calculate valid krum selections based on research constraints
  const getValidKrumSelections = (strategyType, maliciousCount) => {
    const honestClients = numOfClients - maliciousCount;
    const defaultK = STRATEGY_DEFAULTS[strategyType]?.num_krum_selections || 1;
    // Cap at honest clients to respect constraints
    return Math.max(1, Math.min(defaultK, honestClients));
  };

  // Apply strategy-specific defaults when switching strategies
  const applyStrategyDefaults = (strategy, previousStrategy = null) => {
    const strategyType = strategy.aggregation_strategy_keyword;
    const defaults = STRATEGY_DEFAULTS[strategyType] || {};

    // If switching strategies, apply new defaults with constraint validation
    if (previousStrategy && previousStrategy !== strategyType) {
      const result = {
        ...strategy,
        ...defaults,
      };
      // Ensure krum selections respect constraints for krum-based strategies
      if (['krum', 'multi-krum', 'bulyan'].includes(strategyType)) {
        result.num_krum_selections = getValidKrumSelections(
          strategyType,
          strategy.num_of_malicious_clients || 0
        );
      }
      return result;
    }

    // Just fill in missing values
    const result = { ...strategy };
    Object.entries(defaults).forEach(([key, value]) => {
      if (result[key] === undefined) {
        result[key] = value;
      }
    });
    return result;
  };

  const handleAddRow = () => {
    const nextNumber = variations.length + 1;

    const newVariation = applyStrategyDefaults({
      id: Date.now(),
      name: `strategy_${nextNumber}`,
      aggregation_strategy_keyword: 'fedavg',
      num_of_malicious_clients: 0,
      remove_clients: 'false',
    });
    onChange([...variations, newVariation]);
  };

  const handleDeleteRow = id => {
    onChange(variations.filter(v => v.id !== id));
  };

  const handleFieldChange = (id, field, value) => {
    onChange(
      variations.map(v => {
        if (v.id === id) {
          const updated = { ...v, [field]: value };

          // Auto-generate name from strategy + malicious count
          if (field === 'aggregation_strategy_keyword' || field === 'num_of_malicious_clients') {
            const strategy =
              field === 'aggregation_strategy_keyword' ? value : v.aggregation_strategy_keyword;
            const malCount =
              field === 'num_of_malicious_clients' ? value : v.num_of_malicious_clients;
            updated.name = `${strategy}_mal${malCount}`;
          }

          // Apply defaults when switching strategy
          if (field === 'aggregation_strategy_keyword') {
            return applyStrategyDefaults(updated, v.aggregation_strategy_keyword);
          }

          // Auto-adjust krum selections when malicious count changes
          if (field === 'num_of_malicious_clients') {
            const strategy = v.aggregation_strategy_keyword;
            if (['krum', 'multi-krum', 'bulyan'].includes(strategy)) {
              const honestClients = numOfClients - value;
              const currentK = v.num_krum_selections || 1;
              // Cap krum selections if they exceed honest clients
              if (currentK > honestClients) {
                updated.num_krum_selections = Math.max(1, honestClients);
              }
            }
          }

          return updated;
        }
        return v;
      })
    );
  };

  const handleQuickPattern = patternId => {
    const pattern = QUICK_PATTERNS[patternId];
    if (pattern) {
      const baseStrategy =
        variations.length > 0 ? variations[0].aggregation_strategy_keyword : 'fedavg';
      // Pass numOfClients to pattern generators for proper validation
      const generated = pattern.generate(baseStrategy, numOfClients, numOfRounds);
      const withDefaults = generated.map(v => applyStrategyDefaults(v));
      const withIds = withDefaults.map((v, i) => ({
        ...v,
        id: Date.now() + i,
      }));
      onChange(withIds);
      if (onQuickPattern) {
        onQuickPattern(pattern);
      }
    }
  };

  // Validation helpers based on research constraints
  // Krum: n > 2f + 2 (Blanchard et al., NeurIPS 2017)
  // Bulyan: n ≥ 4f + 3 (El Mhamdi et al., MLSys 2019)
  const getKrumValidation = variation => {
    if (!strategyNeeds.krumSelections(variation.aggregation_strategy_keyword)) return null;
    const honestClients = numOfClients - variation.num_of_malicious_clients;
    const selections = variation.num_krum_selections || 1;
    if (selections > honestClients) {
      return `Max: ${honestClients} (honest clients)`;
    }
    return null;
  };

  const getMaliciousValidation = variation => {
    const strategy = variation.aggregation_strategy_keyword;
    const mal = variation.num_of_malicious_clients;

    if (mal > numOfClients) {
      return `Max: ${numOfClients}`;
    }

    // Research-backed Byzantine fault tolerance constraints
    if (strategy === 'bulyan') {
      // Bulyan: n ≥ 4f + 3 → max f = floor((n-3)/4)
      const maxMal = Math.floor((numOfClients - 3) / 4);
      if (mal > maxMal) {
        return `Bulyan max: ${maxMal} (n ≥ 4f+3)`;
      }
    } else if (['krum', 'multi-krum'].includes(strategy)) {
      // Krum: n > 2f + 2 → max f = floor((n-2)/2)
      const maxMal = Math.floor((numOfClients - 2) / 2);
      if (mal > maxMal) {
        return `Krum max: ${maxMal} (n > 2f+2)`;
      }
    }

    return null;
  };

  // Render validation warning
  const ValidationBadge = ({ message }) =>
    message ? (
      <OverlayTrigger overlay={<Tooltip>{message}</Tooltip>}>
        <Badge bg="warning" className="ms-1" style={{ cursor: 'help' }}>
          !
        </Badge>
      </OverlayTrigger>
    ) : null;

  return (
    <div className="strategy-variation-list">
      <div className="d-flex justify-content-between align-items-center mb-3">
        <div>
          <h5 className="mb-1">Strategy Variations</h5>
          <p className="text-muted small mb-0">
            Define parameter variations to compare multiple strategies.
          </p>
        </div>
        <div className="d-flex gap-2">
          <Dropdown align="end">
            <Dropdown.Toggle variant="outline-secondary" size="sm">
              Quick Patterns
            </Dropdown.Toggle>
            <Dropdown.Menu>
              {Object.values(QUICK_PATTERNS).map(pattern => (
                <Dropdown.Item key={pattern.id} onClick={() => handleQuickPattern(pattern.id)}>
                  <div>
                    <strong>{pattern.name}</strong>
                    <div className="small text-muted">{pattern.description}</div>
                  </div>
                </Dropdown.Item>
              ))}
            </Dropdown.Menu>
          </Dropdown>
          <Button variant="primary" size="sm" onClick={handleAddRow}>
            Add Strategy
          </Button>
        </div>
      </div>

      {variations.length === 0 ? (
        <div className="text-center py-5 border rounded">
          <i className="bi bi-table empty-state-icon"></i>
          <p className="text-muted mt-3">
            No strategies yet. Click "Add Strategy" or choose a Quick Pattern to get started.
          </p>
        </div>
      ) : (
        <div className="table-responsive">
          <Table hover size="sm" className="variation-table" style={{ minWidth: '1100px' }}>
            <thead>
              <tr>
                <th style={{ width: '32px' }}>#</th>
                <th style={{ minWidth: '100px' }}>
                  <InfoTooltip text="Descriptive name for this strategy variation">
                    Name
                  </InfoTooltip>
                </th>
                <th style={{ minWidth: '140px' }}>
                  <InfoTooltip text="Federated learning aggregation method">Strategy</InfoTooltip>
                </th>
                <th style={{ width: '70px' }}>
                  <InfoTooltip text="Number of Byzantine/malicious clients">Mal.</InfoTooltip>
                </th>
                <th style={{ minWidth: '110px' }}>
                  <InfoTooltip text="Type of attack when malicious clients > 0">Attack</InfoTooltip>
                </th>
                <th style={{ width: '60px' }}>
                  <InfoTooltip text="Remove untrusted clients from aggregation">Rem.</InfoTooltip>
                </th>
                <th style={{ width: '70px' }}>
                  <InfoTooltip text="Round to begin removing clients (Trust/PID/Bulyan/TrimMean/RFA)">
                    Start
                  </InfoTooltip>
                </th>
                <th style={{ width: '70px' }}>
                  <InfoTooltip text="Krum selections (Krum/Multi-Krum/Bulyan) or Trim ratio (Trimmed Mean)">
                    K / Trim
                  </InfoTooltip>
                </th>
                <th style={{ width: '70px' }}>
                  <InfoTooltip text="Trust threshold (Trust) or Std Dev multiplier (PID)">
                    Thresh
                  </InfoTooltip>
                </th>
                <th style={{ width: '60px' }}>
                  <InfoTooltip text="Beta decay for trust scores (Trust strategy)">
                    Beta
                  </InfoTooltip>
                </th>
                <th style={{ width: '55px' }}>
                  <InfoTooltip text="Proportional gain (PID)">Kp</InfoTooltip>
                </th>
                <th style={{ width: '55px' }}>
                  <InfoTooltip text="Integral gain (PID)">Ki</InfoTooltip>
                </th>
                <th style={{ width: '55px' }}>
                  <InfoTooltip text="Derivative gain (PID)">Kd</InfoTooltip>
                </th>
              </tr>
            </thead>
            <tbody>
              {variations.map((variation, index) => {
                const strategy = variation.aggregation_strategy_keyword;
                const krumError = getKrumValidation(variation);
                const malError = getMaliciousValidation(variation);

                return (
                  <tr key={variation.id}>
                    {/* Row number and delete */}
                    <td>
                      <div className="d-flex align-items-center gap-1">
                        <Badge bg="secondary" className="me-1">
                          {index + 1}
                        </Badge>
                        <button
                          onClick={() => handleDeleteRow(variation.id)}
                          title="Delete strategy"
                          aria-label="Delete strategy"
                          className="strategy-delete-btn"
                        >
                          <MaterialIcon name="delete" size={16} />
                        </button>
                      </div>
                    </td>

                    {/* Name */}
                    <td>
                      <Form.Control
                        type="text"
                        size="sm"
                        value={variation.name}
                        title={variation.name}
                        onChange={e => handleFieldChange(variation.id, 'name', e.target.value)}
                      />
                    </td>

                    {/* Strategy */}
                    <td>
                      <Form.Select
                        size="sm"
                        value={strategy}
                        onChange={e =>
                          handleFieldChange(
                            variation.id,
                            'aggregation_strategy_keyword',
                            e.target.value
                          )
                        }
                      >
                        {AGGREGATION_STRATEGIES.map(s => (
                          <option key={s.value} value={s.value}>
                            {s.label}
                          </option>
                        ))}
                      </Form.Select>
                    </td>

                    {/* Malicious clients */}
                    <td>
                      <div className="d-flex align-items-center">
                        <Form.Control
                          type="number"
                          size="sm"
                          min="0"
                          max={numOfClients}
                          value={variation.num_of_malicious_clients}
                          isInvalid={!!malError}
                          onChange={e =>
                            handleFieldChange(
                              variation.id,
                              'num_of_malicious_clients',
                              parseInt(e.target.value) || 0
                            )
                          }
                          style={{ width: '60px' }}
                        />
                        <ValidationBadge message={malError} />
                      </div>
                    </td>

                    {/* Attack type */}
                    <td>
                      {variation.num_of_malicious_clients > 0 ? (
                        <Form.Select
                          size="sm"
                          value={variation.attack_type || 'gaussian_noise'}
                          onChange={e =>
                            handleFieldChange(variation.id, 'attack_type', e.target.value)
                          }
                        >
                          {ATTACKS.map(attack => (
                            <option key={attack} value={attack}>
                              {formatAttackName(attack)}
                            </option>
                          ))}
                        </Form.Select>
                      ) : (
                        <span className="text-muted">—</span>
                      )}
                    </td>

                    {/* Remove clients toggle */}
                    <td>
                      <Form.Check
                        type="switch"
                        checked={variation.remove_clients === 'true'}
                        onChange={e =>
                          handleFieldChange(
                            variation.id,
                            'remove_clients',
                            e.target.checked ? 'true' : 'false'
                          )
                        }
                      />
                    </td>

                    {/* Begin removing from round */}
                    <td>
                      {strategyNeeds.removeFromRound(strategy) &&
                      variation.remove_clients === 'true' ? (
                        <Form.Control
                          type="number"
                          size="sm"
                          min="1"
                          value={variation.begin_removing_from_round || 2}
                          onChange={e =>
                            handleFieldChange(
                              variation.id,
                              'begin_removing_from_round',
                              parseInt(e.target.value) || 1
                            )
                          }
                          style={{ width: '60px' }}
                        />
                      ) : (
                        <span className="text-muted">—</span>
                      )}
                    </td>

                    {/* Krum selections / Trim ratio */}
                    <td>
                      {strategyNeeds.krumSelections(strategy) ? (
                        <div className="d-flex align-items-center">
                          <Form.Control
                            type="number"
                            size="sm"
                            min="1"
                            max={numOfClients - variation.num_of_malicious_clients}
                            value={variation.num_krum_selections || 1}
                            isInvalid={!!krumError}
                            onChange={e =>
                              handleFieldChange(
                                variation.id,
                                'num_krum_selections',
                                parseInt(e.target.value) || 1
                              )
                            }
                            style={{ width: '55px' }}
                          />
                          <ValidationBadge message={krumError} />
                        </div>
                      ) : strategyNeeds.trimRatio(strategy) ? (
                        <Form.Control
                          type="number"
                          size="sm"
                          step="0.05"
                          min="0"
                          max="0.5"
                          value={variation.trim_ratio || 0.1}
                          onChange={e =>
                            handleFieldChange(
                              variation.id,
                              'trim_ratio',
                              parseFloat(e.target.value) || 0.1
                            )
                          }
                          style={{ width: '60px' }}
                        />
                      ) : (
                        <span className="text-muted">—</span>
                      )}
                    </td>

                    {/* Threshold (trust_threshold or num_std_dev) */}
                    <td>
                      {strategyNeeds.trustParams(strategy) ? (
                        <Form.Control
                          type="number"
                          size="sm"
                          step="0.01"
                          min="0"
                          max="1"
                          value={variation.trust_threshold ?? 0.15}
                          onChange={e =>
                            handleFieldChange(
                              variation.id,
                              'trust_threshold',
                              parseFloat(e.target.value)
                            )
                          }
                          style={{ width: '60px' }}
                        />
                      ) : strategyNeeds.pidParams(strategy) ? (
                        <Form.Control
                          type="number"
                          size="sm"
                          step="0.5"
                          min="0"
                          value={variation.num_std_dev ?? 2.0}
                          title="Standard deviation multiplier for removal threshold"
                          onChange={e =>
                            handleFieldChange(
                              variation.id,
                              'num_std_dev',
                              parseFloat(e.target.value)
                            )
                          }
                          style={{ width: '60px' }}
                        />
                      ) : (
                        <span className="text-muted">—</span>
                      )}
                    </td>

                    {/* Beta value (trust only) */}
                    <td>
                      {strategyNeeds.trustParams(strategy) ? (
                        <Form.Control
                          type="number"
                          size="sm"
                          step="0.05"
                          min="0"
                          max="1"
                          value={variation.beta_value ?? 0.75}
                          onChange={e =>
                            handleFieldChange(
                              variation.id,
                              'beta_value',
                              parseFloat(e.target.value)
                            )
                          }
                          style={{ width: '55px' }}
                        />
                      ) : (
                        <span className="text-muted">—</span>
                      )}
                    </td>

                    {/* Kp (PID only) */}
                    <td>
                      {strategyNeeds.pidParams(strategy) ? (
                        <Form.Control
                          type="number"
                          size="sm"
                          step="0.1"
                          min="0"
                          value={variation.Kp ?? 1.0}
                          onChange={e =>
                            handleFieldChange(variation.id, 'Kp', parseFloat(e.target.value))
                          }
                          style={{ width: '50px' }}
                        />
                      ) : (
                        <span className="text-muted">—</span>
                      )}
                    </td>

                    {/* Ki (PID only) */}
                    <td>
                      {strategyNeeds.pidParams(strategy) ? (
                        <Form.Control
                          type="number"
                          size="sm"
                          step="0.01"
                          min="0"
                          value={variation.Ki ?? 0.05}
                          onChange={e =>
                            handleFieldChange(variation.id, 'Ki', parseFloat(e.target.value))
                          }
                          style={{ width: '50px' }}
                        />
                      ) : (
                        <span className="text-muted">—</span>
                      )}
                    </td>

                    {/* Kd (PID only) */}
                    <td>
                      {strategyNeeds.pidParams(strategy) ? (
                        <Form.Control
                          type="number"
                          size="sm"
                          step="0.01"
                          min="0"
                          value={variation.Kd ?? 0.05}
                          onChange={e =>
                            handleFieldChange(variation.id, 'Kd', parseFloat(e.target.value))
                          }
                          style={{ width: '50px' }}
                        />
                      ) : (
                        <span className="text-muted">—</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </Table>
        </div>
      )}
    </div>
  );
}
