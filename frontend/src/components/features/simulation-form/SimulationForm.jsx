import { useState } from 'react';
import { Form, Accordion, OverlayTrigger, Tooltip } from 'react-bootstrap';
import { PresetSelector } from './PresetSelector';
import { CommonSettings } from './ConfigSections/CommonSettings';
import { AttackSettings } from './ConfigSections/AttackSettings';
import { DefenseSettings } from './ConfigSections/DefenseSettings';
import { TrainingSettings } from './ConfigSections/TrainingSettings';
import { FlowerSettings } from './ConfigSections/FlowerSettings';
import { TransformerSettings } from './ConfigSections/TransformerSettings';
import { LLMSettings } from './ConfigSections/LLMSettings';
import { OutputSettings } from './ConfigSections/OutputSettings';
import { AttackSchedule } from './ConfigSections/AttackSchedule';
import ValidationSummary from '@components/ValidationSummary';
import { StickyFormFooter } from '@components/common/StickyFormFooter';
import { TOOLTIP_DELAYS } from '@constants/ui';

// Map field names to accordion section keys for error navigation
const FIELD_TO_SECTION = {
  aggregation_strategy_keyword: '0',
  dataset_keyword: '0',
  dataset_source: '0',
  num_of_rounds: '0',
  num_of_clients: '0',
  num_of_malicious_clients: '1',
  attack_type: '1',
  poison_rate: '1',
  scale_factor: '1',
  Kp: '2',
  Ki: '2',
  Kd: '2',
  num_of_client_epochs: '3',
  batch_size: '3',
  learning_rate: '3',
  training_device: '3',
  training_subset_fraction: '3',
  min_fit_clients: '4',
  min_evaluate_clients: '4',
  fraction_fit: '4',
  fraction_evaluate: '4',
  use_llm: '6',
  llm_model: '6',
  llm_task: '6',
  preserve_dataset: '7',
  save_csv: '7',
  save_plots: '7',
  attack_schedule: '8',
};

export function SimulationForm({
  config,
  onConfigChange,
  selectedPreset,
  onPresetChange,
  onSubmit,
  isSubmitting,
  validation,
  error,
}) {
  const [activeSection, setActiveSection] = useState(['0']);

  const getSectionPreview = section => {
    switch (section) {
      case 'common':
        return `${config.aggregation_strategy_keyword || 'fedavg'} • ${config.num_of_rounds || 0}r • ${config.num_of_clients || 0}c`;
      case 'attack':
        return `${config.num_of_malicious_clients || 0} malicious • ${config.attack_type || 'none'}`;
      case 'defense':
        return config.aggregation_strategy_keyword?.includes('pid')
          ? `Kp: ${config.Kp || 0} • Ki: ${config.Ki || 0} • Kd: ${config.Kd || 0}`
          : `Strategy: ${config.aggregation_strategy_keyword || 'fedavg'}`;
      case 'training':
        return `${config.num_of_client_epochs || 0} epochs • batch ${config.batch_size || 32}`;
      case 'flower':
        return `min_fit: ${config.min_fit_clients || 0} • min_eval: ${config.min_evaluate_clients || 0}`;
      case 'llm':
        return config.use_llm === 'true'
          ? `${config.llm_task?.toUpperCase() || 'MLM'} • ${config.llm_finetuning || 'LoRA'}`
          : 'Disabled';
      case 'output':
        return `${config.preserve_dataset === 'true' ? 'Preserve dataset' : 'Clean after run'}`;
      case 'dynamic':
        return config.attack_schedule?.length > 0
          ? `${config.attack_schedule.length} attack phases`
          : 'Disabled';
      default:
        return '';
    }
  };

  const getSectionPreviewTooltip = section => {
    switch (section) {
      case 'common':
        return (
          <div style={{ textAlign: 'left' }}>
            <div>
              <strong>{config.aggregation_strategy_keyword || 'fedavg'}</strong> - Aggregation
              strategy
            </div>
            <div>
              <strong>{config.num_of_rounds || 0}r</strong> - Number of training rounds
            </div>
            <div>
              <strong>{config.num_of_clients || 0}c</strong> - Total number of clients
            </div>
          </div>
        );
      case 'attack':
        return (
          <div style={{ textAlign: 'left' }}>
            <div>
              <strong>{config.num_of_malicious_clients || 0} malicious</strong> - Number of
              malicious clients
            </div>
            <div>
              <strong>{config.attack_type || 'none'}</strong> - Type of attack being simulated
            </div>
          </div>
        );
      case 'defense':
        return config.aggregation_strategy_keyword?.includes('pid') ? (
          <div style={{ textAlign: 'left' }}>
            <div>
              <strong>PID Controller Gains:</strong>
            </div>
            <div>
              <strong>Kp: {config.Kp || 0}</strong> - Proportional gain (immediate response)
            </div>
            <div>
              <strong>Ki: {config.Ki || 0}</strong> - Integral gain (accumulated error)
            </div>
            <div>
              <strong>Kd: {config.Kd || 0}</strong> - Derivative gain (rate of change)
            </div>
          </div>
        ) : (
          <div style={{ textAlign: 'left' }}>
            <div>
              <strong>{config.aggregation_strategy_keyword || 'fedavg'}</strong> - Defense
              aggregation strategy
            </div>
          </div>
        );
      case 'training':
        return (
          <div style={{ textAlign: 'left' }}>
            <div>
              <strong>{config.num_of_client_epochs || 0} epochs</strong> - Training epochs per
              client
            </div>
            <div>
              <strong>batch {config.batch_size || 32}</strong> - Training batch size
            </div>
          </div>
        );
      case 'flower':
        return (
          <div style={{ textAlign: 'left' }}>
            <div>
              <strong>min_fit: {config.min_fit_clients || 0}</strong> - Minimum clients for training
            </div>
            <div>
              <strong>min_eval: {config.min_evaluate_clients || 0}</strong> - Minimum clients for
              evaluation
            </div>
          </div>
        );
      case 'llm':
        return config.use_llm === 'true' ? (
          <div style={{ textAlign: 'left' }}>
            <div>
              <strong>Enabled</strong> - LLM/Transformer training is active
            </div>
            <div>
              <strong>Task:</strong> {config.llm_task?.toUpperCase() || 'MLM'} •{' '}
              <strong>Fine-tuning:</strong> {config.llm_finetuning || 'LoRA'}
            </div>
            <div>
              <strong>Model:</strong> {config.llm_model?.split('/').pop() || 'BiomedBERT'}
            </div>
          </div>
        ) : (
          <div style={{ textAlign: 'left' }}>
            <div>
              <strong>Disabled</strong> - LLM integration is turned off
            </div>
          </div>
        );
      case 'output':
        return (
          <div style={{ textAlign: 'left' }}>
            {config.preserve_dataset === 'true' ? (
              <div>
                <strong>Preserve dataset</strong> - Keep dataset files after simulation
              </div>
            ) : (
              <div>
                <strong>Clean after run</strong> - Remove dataset files after simulation
              </div>
            )}
          </div>
        );
      case 'dynamic':
        return config.attack_schedule?.length > 0 ? (
          <div style={{ textAlign: 'left' }}>
            <div>
              <strong>{config.attack_schedule.length} attack phases</strong> - Number of scheduled
              attack phases
            </div>
            <div>Attacks that change during training rounds</div>
          </div>
        ) : (
          <div style={{ textAlign: 'left' }}>
            <div>
              <strong>Disabled</strong> - No attack schedule configured
            </div>
          </div>
        );
      default:
        return '';
    }
  };

  // Handle clicking on error in sticky footer - scroll to and open the relevant section
  const handleErrorClick = error => {
    const sectionKey = FIELD_TO_SECTION[error.field];
    if (sectionKey) {
      // Open the accordion section if not already open
      if (!activeSection.includes(sectionKey)) {
        setActiveSection([...activeSection, sectionKey]);
      }
      // Scroll to the section after a brief delay for accordion animation
      setTimeout(() => {
        const element = document.querySelector(`[data-section-key="${sectionKey}"]`);
        element?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 100);
    }
  };

  return (
    <Form onSubmit={onSubmit} className="simulation-form-container">
      <PresetSelector selectedPreset={selectedPreset} onPresetChange={onPresetChange} />

      <Form.Group className="mb-4">
        <Form.Label>Simulation Name (Optional)</Form.Label>
        <Form.Control
          type="text"
          name="display_name"
          value={config.display_name || ''}
          onChange={onConfigChange}
          placeholder="Leave empty to use auto-generated ID"
        />
        <Form.Text className="text-muted">
          Give your simulation a memorable name, or use the auto-generated ID
        </Form.Text>
      </Form.Group>

      {validation && <ValidationSummary validation={validation} />}

      {error && (
        <div className="alert alert-danger" role="alert">
          <strong>Error:</strong> {error}
        </div>
      )}

      <div className="section-nav-menu mb-4">
        <div className="small text-muted mb-2">Jump to section:</div>
        <div className="d-flex flex-wrap gap-2">
          {[
            { key: '0', label: 'Common', section: 'common' },
            { key: '1', label: 'Attack', section: 'attack' },
            { key: '2', label: 'Defense', section: 'defense' },
            { key: '3', label: 'Training', section: 'training' },
            { key: '4', label: 'Flower', section: 'flower' },
            { key: '6', label: 'LLM', section: 'llm' },
            { key: '7', label: 'Output', section: 'output' },
            { key: '8', label: 'Dynamic', section: 'dynamic' },
          ].map(item => {
            const isActive = activeSection.includes(item.key);
            return (
              <button
                key={item.key}
                type="button"
                className={`btn btn-sm ${isActive ? 'btn-primary' : 'btn-outline-secondary'}`}
                onClick={() => {
                  if (activeSection.includes(item.key)) {
                    setActiveSection(activeSection.filter(key => key !== item.key));
                  } else {
                    setActiveSection([...activeSection, item.key]);
                    // Delay to allow accordion animation to start before scrolling
                    setTimeout(() => {
                      const element = document.querySelector(`[data-section-key="${item.key}"]`);
                      element?.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    }, 50);
                  }
                }}
              >
                {item.label}
              </button>
            );
          })}
        </div>
      </div>

      <Accordion
        defaultActiveKey={['0']}
        alwaysOpen
        className="mb-4"
        activeKey={activeSection}
        onSelect={setActiveSection}
      >
        <Accordion.Item eventKey="0" data-section-key="0">
          <Accordion.Header>
            <div className="d-flex align-items-center justify-content-between w-100 me-3">
              <span>Common Settings</span>
              {!activeSection.includes('0') && (
                <OverlayTrigger
                  placement="left"
                  delay={TOOLTIP_DELAYS}
                  overlay={
                    <Tooltip id="tooltip-common" className="config-preview-tooltip">
                      {getSectionPreviewTooltip('common')}
                    </Tooltip>
                  }
                >
                  <span className="text-muted small section-preview">
                    {getSectionPreview('common')}
                  </span>
                </OverlayTrigger>
              )}
            </div>
          </Accordion.Header>
          <Accordion.Body>
            <CommonSettings config={config} onChange={onConfigChange} />
          </Accordion.Body>
        </Accordion.Item>

        <Accordion.Item eventKey="1" data-section-key="1">
          <Accordion.Header>
            <div className="d-flex align-items-center justify-content-between w-100 me-3">
              <span>Attack Configuration</span>
              {!activeSection.includes('1') && (
                <OverlayTrigger
                  placement="left"
                  delay={TOOLTIP_DELAYS}
                  overlay={
                    <Tooltip id="tooltip-attack" className="config-preview-tooltip">
                      {getSectionPreviewTooltip('attack')}
                    </Tooltip>
                  }
                >
                  <span className="text-muted small section-preview">
                    {getSectionPreview('attack')}
                  </span>
                </OverlayTrigger>
              )}
            </div>
          </Accordion.Header>
          <Accordion.Body>
            <AttackSettings config={config} onChange={onConfigChange} />
          </Accordion.Body>
        </Accordion.Item>

        <Accordion.Item eventKey="2" data-section-key="2">
          <Accordion.Header>
            <div className="d-flex align-items-center justify-content-between w-100 me-3">
              <span>Defense Strategy Parameters</span>
              {!activeSection.includes('2') && (
                <OverlayTrigger
                  placement="left"
                  delay={TOOLTIP_DELAYS}
                  overlay={
                    <Tooltip id="tooltip-defense" className="config-preview-tooltip">
                      {getSectionPreviewTooltip('defense')}
                    </Tooltip>
                  }
                >
                  <span className="text-muted small section-preview">
                    {getSectionPreview('defense')}
                  </span>
                </OverlayTrigger>
              )}
            </div>
          </Accordion.Header>
          <Accordion.Body>
            <DefenseSettings config={config} onChange={onConfigChange} />
          </Accordion.Body>
        </Accordion.Item>

        <Accordion.Item eventKey="3" data-section-key="3">
          <Accordion.Header>
            <div className="d-flex align-items-center justify-content-between w-100 me-3">
              <span>Training Configuration</span>
              {!activeSection.includes('3') && (
                <OverlayTrigger
                  placement="left"
                  delay={TOOLTIP_DELAYS}
                  overlay={
                    <Tooltip id="tooltip-training" className="config-preview-tooltip">
                      {getSectionPreviewTooltip('training')}
                    </Tooltip>
                  }
                >
                  <span className="text-muted small section-preview">
                    {getSectionPreview('training')}
                  </span>
                </OverlayTrigger>
              )}
            </div>
          </Accordion.Header>
          <Accordion.Body>
            <TrainingSettings config={config} onChange={onConfigChange} />
          </Accordion.Body>
        </Accordion.Item>

        <Accordion.Item eventKey="4" data-section-key="4">
          <Accordion.Header>
            <div className="d-flex align-items-center justify-content-between w-100 me-3">
              <span>Flower Framework Settings</span>
              {!activeSection.includes('4') && (
                <OverlayTrigger
                  placement="left"
                  delay={TOOLTIP_DELAYS}
                  overlay={
                    <Tooltip id="tooltip-flower" className="config-preview-tooltip">
                      {getSectionPreviewTooltip('flower')}
                    </Tooltip>
                  }
                >
                  <span className="text-muted small section-preview">
                    {getSectionPreview('flower')}
                  </span>
                </OverlayTrigger>
              )}
            </div>
          </Accordion.Header>
          <Accordion.Body>
            <FlowerSettings config={config} onChange={onConfigChange} />
          </Accordion.Body>
        </Accordion.Item>

        {config.model_type === 'transformer' && (
          <Accordion.Item eventKey="5" data-section-key="5">
            <Accordion.Header>Transformer Configuration</Accordion.Header>
            <Accordion.Body>
              <TransformerSettings config={config} onChange={onConfigChange} />
            </Accordion.Body>
          </Accordion.Item>
        )}

        <Accordion.Item eventKey="6" data-section-key="6">
          <Accordion.Header>
            <div className="d-flex align-items-center justify-content-between w-100 me-3">
              <span>LLM Settings</span>
              {!activeSection.includes('6') && (
                <OverlayTrigger
                  placement="left"
                  delay={TOOLTIP_DELAYS}
                  overlay={
                    <Tooltip id="tooltip-llm" className="config-preview-tooltip">
                      {getSectionPreviewTooltip('llm')}
                    </Tooltip>
                  }
                >
                  <span className="text-muted small section-preview">
                    {getSectionPreview('llm')}
                  </span>
                </OverlayTrigger>
              )}
            </div>
          </Accordion.Header>
          <Accordion.Body>
            <LLMSettings config={config} onChange={onConfigChange} />
          </Accordion.Body>
        </Accordion.Item>

        <Accordion.Item eventKey="7" data-section-key="7">
          <Accordion.Header>
            <div className="d-flex align-items-center justify-content-between w-100 me-3">
              <span>Output Settings</span>
              {!activeSection.includes('7') && (
                <OverlayTrigger
                  placement="left"
                  delay={TOOLTIP_DELAYS}
                  overlay={
                    <Tooltip id="tooltip-output" className="config-preview-tooltip">
                      {getSectionPreviewTooltip('output')}
                    </Tooltip>
                  }
                >
                  <span className="text-muted small section-preview">
                    {getSectionPreview('output')}
                  </span>
                </OverlayTrigger>
              )}
            </div>
          </Accordion.Header>
          <Accordion.Body>
            <OutputSettings config={config} onChange={onConfigChange} />
          </Accordion.Body>
        </Accordion.Item>

        <Accordion.Item eventKey="8" data-section-key="8">
          <Accordion.Header>
            <div className="d-flex align-items-center justify-content-between w-100 me-3">
              <span>Attack Schedule (Advanced)</span>
              {!activeSection.includes('8') && (
                <OverlayTrigger
                  placement="left"
                  delay={TOOLTIP_DELAYS}
                  overlay={
                    <Tooltip id="tooltip-dynamic" className="config-preview-tooltip">
                      {getSectionPreviewTooltip('dynamic')}
                    </Tooltip>
                  }
                >
                  <span className="text-muted small section-preview">
                    {getSectionPreview('dynamic')}
                  </span>
                </OverlayTrigger>
              )}
            </div>
          </Accordion.Header>
          <Accordion.Body>
            <AttackSchedule config={config} onChange={onConfigChange} />
          </Accordion.Body>
        </Accordion.Item>
      </Accordion>

      <StickyFormFooter
        validation={validation}
        isSubmitting={isSubmitting}
        onErrorClick={handleErrorClick}
      />
    </Form>
  );
}
