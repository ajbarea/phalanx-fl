import { useState, useEffect, useRef } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Alert } from 'react-bootstrap';
import { PageContainer } from '@components/layout/PageContainer';
import { PageHeader } from '@components/layout/PageHeader';
import { SimulationForm } from '@components/features/simulation-form/SimulationForm';
import { OutlineButton } from '@components/common/Button/OutlineButton';
import { ConfirmModal } from '@components/common/Modal/ConfirmModal';
import { QueueChoiceModal } from '@components/common/Modal/QueueChoiceModal';
import { createSimulation, prepareSimulation } from '@api';
import { getErrorMessage } from '@utils/errorMessages';
import { useConfigValidation } from '@hooks/useConfigValidation';
import { useRunningSimulation } from '@hooks/useRunningSimulation';
import { useDeviceInfo } from '@hooks/useDeviceInfo';
import { useTerminal } from '@contexts/TerminalContext';
import { initialConfig } from '@constants/initialConfig';
import { PRESETS } from '@constants/presets';
import { TOAST_DURATION, POLLING_INTERVALS } from '@constants/ui';
import { STORAGE_KEYS } from '@constants/storage';
import { toast } from 'sonner';

export function NewSimulation() {
  const [config, setConfig] = useState(() => {
    const savedDraft = localStorage.getItem(STORAGE_KEYS.SIMULATION_DRAFT);
    if (savedDraft) {
      try {
        return JSON.parse(savedDraft);
      } catch {
        return initialConfig;
      }
    }
    return initialConfig;
  });

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [selectedPreset, setSelectedPreset] = useState(null);
  const [showClearModal, setShowClearModal] = useState(false);
  const [showQueueChoiceModal, setShowQueueChoiceModal] = useState(false);
  const [pendingConfig, setPendingConfig] = useState(null);
  const navigate = useNavigate();

  const validation = useConfigValidation(config);
  const { hasRunning, runningSimIds } = useRunningSimulation();
  const { openTerminal, interruptAndRun } = useTerminal();
  const {
    gpuAvailable,
    gpuInfo,
    recommendedDevice,
    loading: deviceLoading,
    hasBeenNotified,
    markNotified,
  } = useDeviceInfo();

  const hasAppliedDevice = useRef(false);

  useEffect(() => {
    const timeoutId = setTimeout(() => {
      localStorage.setItem(STORAGE_KEYS.SIMULATION_DRAFT, JSON.stringify(config));
    }, POLLING_INTERVALS.DRAFT_SAVE);

    return () => clearTimeout(timeoutId);
  }, [config]);

  useEffect(() => {
    if (!deviceLoading && gpuAvailable && gpuInfo && !hasBeenNotified()) {
      toast.info(`GPU detected! Using ${gpuInfo.name} for training`, {
        duration: TOAST_DURATION.DEFAULT,
      });
      markNotified();
    }
  }, [deviceLoading, gpuAvailable, gpuInfo, hasBeenNotified, markNotified]);

  useEffect(() => {
    if (!deviceLoading && recommendedDevice && !hasAppliedDevice.current) {
      // Only update if current device is 'cpu' (don't override user's choice from draft)
      if (config.training_device === 'cpu' && recommendedDevice === 'gpu') {
        setConfig(prev => ({ ...prev, training_device: recommendedDevice }));
      }
      hasAppliedDevice.current = true;
    }
  }, [deviceLoading, recommendedDevice, config.training_device]);

  const handleConfigChange = e => {
    const { name, value, type } = e.target;
    let finalValue = value;

    if (type === 'number') {
      finalValue = value.includes('.') ? parseFloat(value) : parseInt(value, 10);
    }

    setConfig(prev => ({ ...prev, [name]: finalValue }));
  };

  const handlePresetChange = presetKey => {
    setSelectedPreset(presetKey);
    if (presetKey && PRESETS[presetKey]) {
      const preset = PRESETS[presetKey];
      const newConfig = {
        ...config,
        ...preset.config,
        display_name: preset.name,
        // Override preset's training_device with recommended device (GPU if available)
        training_device: recommendedDevice || preset.config.training_device || 'cpu',
      };

      // Sync attack_schedule to dynamic_attacks for UI
      if (preset.config.attack_schedule?.length > 0) {
        newConfig.dynamic_attacks = {
          enabled: true,
          schedule: preset.config.attack_schedule,
        };
      }

      setConfig(newConfig);
    }
  };

  /**
   * Sanitize config by removing incompatible fields based on dataset_source.
   * Prevents HuggingFace configs from including local dataset fields and vice versa.
   */
  const sanitizeConfig = config => {
    const sanitized = { ...config };

    // Local datasets that use transformers/LLM (not CNN)
    const llmDatasets = ['financial_phrasebank', 'lexglue', 'medal', 'medquad'];
    const isLlmDataset = llmDatasets.includes(config.dataset_keyword);

    if (config.dataset_source === 'huggingface') {
      delete sanitized.dataset_keyword;
    } else {
      delete sanitized.hf_dataset_name;
      delete sanitized.transformer_model;
      delete sanitized.max_seq_length;
      delete sanitized.text_column;
      delete sanitized.text2_column;
      delete sanitized.label_column;
      delete sanitized.partitioning_strategy;
      delete sanitized.partitioning_params;

      // Only delete LoRA params for non-LLM local datasets
      if (!isLlmDataset) {
        delete sanitized.use_lora;
        delete sanitized.lora_rank;
      }

      // Only reset to CNN for non-LLM local datasets
      if (sanitized.model_type === 'transformer' && !isLlmDataset) {
        sanitized.model_type = 'cnn';
      }
    }

    return sanitized;
  };

  const handleSubmit = async e => {
    e.preventDefault();

    if (hasRunning) {
      const sanitizedConfig = sanitizeConfig(config);
      setPendingConfig(sanitizedConfig);
      setShowQueueChoiceModal(true);
      return;
    }

    await submitSimulation(null);
  };

  const submitSimulation = async (addToQueue = null) => {
    setSubmitting(true);
    setError(null);
    setShowQueueChoiceModal(false);

    try {
      const configToSubmit = pendingConfig || sanitizeConfig(config);

      if (addToQueue === true) {
        const response = await createSimulation(configToSubmit, addToQueue);
        const { simulation_id } = response.data;
        localStorage.removeItem(STORAGE_KEYS.SIMULATION_DRAFT);
        setPendingConfig(null);
        toast.success('Added to experiment queue!');
        navigate(`/queue/${simulation_id}`);
      } else {
        const response = await prepareSimulation(configToSubmit);
        const { simulation_id, command } = response.data;
        localStorage.removeItem(STORAGE_KEYS.SIMULATION_DRAFT);
        setPendingConfig(null);

        toast.success('Simulation started!');
        openTerminal();

        // Give terminal time to open, then interrupt any running process and run the command
        setTimeout(() => {
          interruptAndRun(`${command}\n`);
        }, 100);

        navigate(`/simulations/${simulation_id}`);
      }
    } catch (err) {
      // API interceptor shows toast; just update UI state
      setError(getErrorMessage(err));
      setSubmitting(false);
    }
  };

  const handleResetConfig = () => {
    setShowClearModal(true);
  };

  const confirmResetConfig = () => {
    localStorage.removeItem(STORAGE_KEYS.SIMULATION_DRAFT);
    setConfig(initialConfig);
    setSelectedPreset(null);
    setShowClearModal(false);
    toast.success('Configuration reset to defaults');
  };

  const handleDownloadJSON = () => {
    const sanitizedConfig = sanitizeConfig(config);
    const dataStr = JSON.stringify(sanitizedConfig, null, 2);
    const dataBlob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(dataBlob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${config.display_name || 'simulation'}-config.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    toast.success('Configuration downloaded');
  };

  const handleUploadJSON = e => {
    const file = e.target.files[0];
    if (!file) return;

    const MAX_FILE_SIZE = 1024 * 1024;
    if (file.size > MAX_FILE_SIZE) {
      toast.error('File too large. Maximum size is 1MB.');
      e.target.value = '';
      return;
    }

    const reader = new FileReader();
    reader.onload = event => {
      try {
        const uploadedConfig = JSON.parse(event.target.result);
        setConfig(prev => ({ ...prev, ...uploadedConfig }));
        setSelectedPreset(null);
        toast.success('Configuration loaded from file');
      } catch {
        toast.error('Invalid JSON file');
      }
    };
    reader.readAsText(file);
    e.target.value = '';
  };

  return (
    <PageContainer>
      <PageHeader title="New Simulation">
        <div className="d-flex gap-2">
          <input
            type="file"
            accept=".json"
            onChange={handleUploadJSON}
            style={{ display: 'none' }}
            id="upload-json-input"
          />
          <OutlineButton
            onClick={() => document.getElementById('upload-json-input').click()}
            variant="outline-secondary"
            aria-label="Upload simulation configuration from JSON file"
          >
            Upload JSON
          </OutlineButton>
          <OutlineButton onClick={handleDownloadJSON} variant="outline-secondary">
            Download JSON
          </OutlineButton>
          <OutlineButton onClick={handleResetConfig} variant="outline-secondary">
            Reset Configuration
          </OutlineButton>
        </div>
      </PageHeader>

      {hasRunning && (
        <Alert variant="warning" className="mb-4">
          <div className="d-flex justify-content-between align-items-center">
            <div>
              <i className="bi bi-exclamation-triangle me-2"></i>
              <strong>Simulation in progress</strong> - New simulations will queue automatically
            </div>
            <OutlineButton
              as={Link}
              to={`/queue/${runningSimIds[0]}`}
              className="btn-warning-action"
              size="sm"
            >
              View Queue Status
            </OutlineButton>
          </div>
        </Alert>
      )}

      <SimulationForm
        config={config}
        onConfigChange={handleConfigChange}
        selectedPreset={selectedPreset}
        onPresetChange={handlePresetChange}
        onSubmit={handleSubmit}
        isSubmitting={submitting}
        validation={validation}
        error={error}
        gpuInfo={gpuInfo}
      />

      <ConfirmModal
        show={showClearModal}
        title="Reset Configuration"
        message="This will reset all fields to default values. Continue?"
        variant="warning"
        onConfirm={confirmResetConfig}
        onCancel={() => setShowClearModal(false)}
      />

      <QueueChoiceModal
        show={showQueueChoiceModal}
        onHide={() => {
          setShowQueueChoiceModal(false);
          setPendingConfig(null);
        }}
        onAddToQueue={() => submitSimulation(true)}
        onCreateSeparate={() => submitSimulation(false)}
      />
    </PageContainer>
  );
}
