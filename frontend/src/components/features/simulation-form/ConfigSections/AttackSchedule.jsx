import { useState, useEffect } from 'react';
import { Form, Button, Card, Alert } from 'react-bootstrap';
import { SwitchField } from '../FormFields/SwitchField';
import { NumberField } from '../FormFields/NumberField';
import { SelectField } from '../FormFields/SelectField';
import { ATTACKS } from '@constants/attacks';

export function AttackSchedule({ config, onChange }) {
  const [schedule, setSchedule] = useState(config.attack_schedule || []);

  // Sync local schedule state when attack_schedule changes
  useEffect(() => {
    const configSchedule = config.attack_schedule || [];
    if (JSON.stringify(configSchedule) !== JSON.stringify(schedule)) {
      setSchedule(configSchedule);
    }
  }, [config.attack_schedule, schedule]);

  // Derive enabled state from whether schedule has items
  const isEnabled = schedule.length > 0;

  const emitChange = newSchedule => {
    setSchedule(newSchedule);
    onChange({
      target: {
        name: 'attack_schedule',
        value: newSchedule,
      },
    });
  };

  const handleEnabledChange = e => {
    const enabled = e.target.checked;
    if (enabled && schedule.length === 0) {
      // Add a default phase when enabling
      const defaultPhase = {
        start_round: 1,
        end_round: config.num_of_rounds || 10,
        selection_strategy: 'specific',
        malicious_client_ids: [0],
        attack_type: 'label_flipping',
      };
      emitChange([defaultPhase]);
    } else if (!enabled) {
      emitChange([]);
    }
  };

  const handleAddAttackPhase = () => {
    const newPhase = {
      start_round: 1,
      end_round: config.num_of_rounds || 10,
      selection_strategy: 'specific',
      malicious_client_ids: [0],
      attack_type: 'label_flipping',
    };
    emitChange([...schedule, newPhase]);
  };

  const handleRemovePhase = index => {
    emitChange(schedule.filter((_, i) => i !== index));
  };

  const handlePhaseChange = (index, field, value) => {
    const newSchedule = [...schedule];
    newSchedule[index] = { ...newSchedule[index], [field]: value };
    emitChange(newSchedule);
  };

  return (
    <>
      <SwitchField
        name="attack_schedule_enabled"
        label="Enable Attack Schedule"
        checked={isEnabled}
        onChange={handleEnabledChange}
        tooltip="Schedule attacks to occur during specific rounds (advanced feature)"
      />

      {isEnabled && (
        <>
          <Alert variant="info" className="small">
            Attack scheduling allows you to configure different attacks at different rounds. This is
            useful for testing defense adaptation over time.
          </Alert>

          {schedule.map((phase, index) => (
            <Card key={index} className="mb-3">
              <Card.Header className="d-flex justify-content-between align-items-center">
                <span>Attack Phase {index + 1}</span>
                <Button variant="danger" size="sm" onClick={() => handleRemovePhase(index)}>
                  Remove
                </Button>
              </Card.Header>
              <Card.Body>
                <NumberField
                  name={`phase_${index}_start_round`}
                  label="Start Round"
                  value={phase.start_round}
                  onChange={e => handlePhaseChange(index, 'start_round', parseInt(e.target.value))}
                  min={1}
                  max={config.num_of_rounds}
                />

                <NumberField
                  name={`phase_${index}_end_round`}
                  label="End Round"
                  value={phase.end_round}
                  onChange={e => handlePhaseChange(index, 'end_round', parseInt(e.target.value))}
                  min={1}
                  max={config.num_of_rounds}
                />

                <SelectField
                  name={`phase_${index}_selection_strategy`}
                  label="Client Selection Strategy"
                  value={phase.selection_strategy}
                  onChange={e => handlePhaseChange(index, 'selection_strategy', e.target.value)}
                  options={['specific', 'random', 'percentage']}
                />

                {phase.selection_strategy === 'specific' && (
                  <Form.Group className="mb-3">
                    <Form.Label>Client IDs (comma-separated)</Form.Label>
                    <Form.Control
                      type="text"
                      value={(phase.malicious_client_ids || phase.client_ids || []).join(', ')}
                      onChange={e =>
                        handlePhaseChange(
                          index,
                          'malicious_client_ids',
                          e.target.value.split(',').map(id => parseInt(id.trim()))
                        )
                      }
                      placeholder="e.g., 0, 1, 2"
                    />
                  </Form.Group>
                )}

                {phase.selection_strategy === 'random' && (
                  <NumberField
                    name={`phase_${index}_malicious_client_count`}
                    label="Number of Malicious Clients"
                    value={phase.malicious_client_count || 1}
                    onChange={e =>
                      handlePhaseChange(index, 'malicious_client_count', parseInt(e.target.value))
                    }
                    min={1}
                    max={config.num_of_clients}
                    tooltip="Number of clients to randomly select as malicious"
                  />
                )}

                {phase.selection_strategy === 'percentage' && (
                  <NumberField
                    name={`phase_${index}_malicious_percentage`}
                    label="Malicious Client Percentage"
                    value={phase.malicious_percentage || 0.2}
                    onChange={e =>
                      handlePhaseChange(index, 'malicious_percentage', parseFloat(e.target.value))
                    }
                    min={0}
                    max={1}
                    step={0.1}
                    tooltip="Fraction of clients to make malicious (0.0-1.0)"
                  />
                )}

                <SelectField
                  name={`phase_${index}_attack_type`}
                  label="Attack Type"
                  value={phase.attack_type || phase.attack_config?.type || 'label_flipping'}
                  onChange={e => handlePhaseChange(index, 'attack_type', e.target.value)}
                  options={ATTACKS}
                />
              </Card.Body>
            </Card>
          ))}

          <Button variant="outline-primary" onClick={handleAddAttackPhase} className="w-100">
            + Add Attack Phase
          </Button>
        </>
      )}
    </>
  );
}
