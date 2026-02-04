import { useState, useEffect, useRef, useCallback, useMemo, useDeferredValue } from 'react';
import { FilterBar } from './FilterBar';
import { useNavigate, Link } from 'react-router-dom';
import { Alert, Button } from 'react-bootstrap';
import { PageContainer } from '@components/layout/PageContainer';
import { PageHeader } from '@components/layout/PageHeader';
import { LoadingPage } from '@components/common/Loading/LoadingPage';
import { SimulationList } from '@components/features/simulation-list/SimulationList';
import { BulkActions } from '@components/features/simulation-list/BulkActions';
import { ConfirmModal } from '@components/common/Modal/ConfirmModal';
import { useSimulations } from '@hooks/useSimulations';
import { useSimulationStatus } from '@hooks/useSimulationStatus';
import { useRunningSimulation } from '@hooks/useRunningSimulation';
import { deleteMultipleSimulations, stopSimulation } from '@api/endpoints/simulations';
import { toast } from 'sonner';

export function Dashboard() {
  const { simulations, loading, error, refetch } = useSimulations();
  const { statuses } = useSimulationStatus(simulations);
  const { hasRunning } = useRunningSimulation();
  const [selectedSims, setSelectedSims] = useState([]);
  const [exitingCards, setExitingCards] = useState([]);
  const [deleting, setDeleting] = useState(false);
  const [stopping, setStopping] = useState(false);
  const navigate = useNavigate();
  const lastClickedIndexRef = useRef(null);

  // Filter state
  const [searchFilter, setSearchFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [originFilter, setOriginFilter] = useState('all');
  const [datasetFilter, setDatasetFilter] = useState('all');
  const [modelTypeFilter, setModelTypeFilter] = useState('all');
  const [strategyFilter, setStrategyFilter] = useState('all');
  const [attackFilter, setAttackFilter] = useState('all');

  // Deferred values for performance
  const deferredSearch = useDeferredValue(searchFilter);
  const deferredStatus = useDeferredValue(statusFilter);
  const deferredOrigin = useDeferredValue(originFilter);
  const deferredDataset = useDeferredValue(datasetFilter);
  const deferredModelType = useDeferredValue(modelTypeFilter);
  const deferredStrategy = useDeferredValue(strategyFilter);
  const deferredAttack = useDeferredValue(attackFilter);

  // Memoized extraction of config fields for filter options
  const { datasetKeywords, modelTypes, strategyNames, attackTypes } = useMemo(() => {
    const datasetSet = new Set();
    const modelTypeSet = new Set();
    const strategySet = new Set();
    const attackSet = new Set();

    simulations.forEach(sim => {
      // Try shared_settings, then root
      const cfg = sim.config?.shared_settings || sim.config || {};
      if (cfg.dataset_keyword) datasetSet.add(cfg.dataset_keyword);
      if (cfg.model_type) modelTypeSet.add(cfg.model_type);

      // Extract strategies
      if (sim.config?.simulation_strategies) {
        sim.config.simulation_strategies.forEach(s => {
          if (s.aggregation_strategy_keyword) strategySet.add(s.aggregation_strategy_keyword);
          if (s.attack_schedule) {
            s.attack_schedule.forEach(a => {
              if (a.attack_type) attackSet.add(a.attack_type);
            });
          }
        });
      } else if (cfg.aggregation_strategy_keyword) {
        strategySet.add(cfg.aggregation_strategy_keyword);
        if (cfg.attack_schedule) {
          cfg.attack_schedule.forEach(a => {
            if (a.attack_type) attackSet.add(a.attack_type);
          });
        }
      }
    });

    return {
      datasetKeywords: Array.from(datasetSet).sort(),
      modelTypes: Array.from(modelTypeSet).sort(),
      strategyNames: Array.from(strategySet).sort(),
      attackTypes: Array.from(attackSet).sort(),
    };
  }, [simulations]);

  const ORIGIN_OPTIONS = [
    { value: 'all', label: 'All Origins' },
    { value: 'api', label: 'API' },
    { value: 'cli', label: 'CLI' },
    { value: 'unknown', label: 'Unknown' },
  ];
  const DATASET_OPTIONS = [
    { value: 'all', label: 'All Datasets' },
    ...datasetKeywords.map(dk => ({ value: dk, label: dk })),
  ];
  const MODEL_TYPE_OPTIONS = [
    { value: 'all', label: 'All Model Types' },
    ...modelTypes.map(mt => ({ value: mt, label: mt })),
  ];
  const STRATEGY_OPTIONS = strategyNames.map(sn => ({ value: sn, label: sn }));
  const ATTACK_OPTIONS = attackTypes.map(at => ({ value: at, label: at }));

  // Memoized filtered simulations
  const filteredSimulations = useMemo(() => {
    return simulations.filter(sim => {
      const statusObj = statuses[sim.simulation_id] || {};
      const statusValue = statusObj.status || 'pending';
      const originValue = statusObj.origin || 'unknown';
      const cfg = sim.config?.shared_settings || sim.config || {};

      // Search (Name or ID)
      if (deferredSearch) {
        const query = deferredSearch.toLowerCase();
        const nameMatch = sim.display_name?.toLowerCase().includes(query);
        const idMatch = sim.simulation_id.toLowerCase().includes(query);
        if (!nameMatch && !idMatch) return false;
      }

      // Status
      if (deferredStatus !== 'all' && deferredStatus !== statusValue) return false;

      // Origin
      if (deferredOrigin !== 'all' && deferredOrigin !== originValue) return false;

      // Dataset
      if (deferredDataset !== 'all' && cfg.dataset_keyword !== deferredDataset) return false;

      // Model type
      if (deferredModelType !== 'all' && cfg.model_type !== deferredModelType) return false;

      // Strategy
      if (deferredStrategy !== 'all') {
        const strategies = sim.config?.simulation_strategies || [cfg];
        const hasStrategy = strategies.some(
          s => s.aggregation_strategy_keyword === deferredStrategy
        );
        if (!hasStrategy) return false;
      }

      // Attack
      if (deferredAttack !== 'all') {
        const strategies = sim.config?.simulation_strategies || [cfg];
        const hasAttack = strategies.some(s =>
          s.attack_schedule?.some(a => a.attack_type === deferredAttack)
        );
        if (deferredAttack === 'none') {
          if (hasAttack) return false;
        } else if (!hasAttack) {
          return false;
        }
      }

      return true;
    });
  }, [
    simulations,
    statuses,
    deferredSearch,
    deferredStatus,
    deferredOrigin,
    deferredDataset,
    deferredModelType,
    deferredStrategy,
    deferredAttack,
  ]);

  const [confirmModal, setConfirmModal] = useState({
    show: false,
    title: '',
    message: '',
    onConfirm: () => {},
    variant: 'danger',
  });

  const handleSelectAll = useCallback(() => {
    if (!simulations || simulations.length === 0) return;

    // If any items are selected, clear the selection
    if (selectedSims.length > 0) {
      setSelectedSims([]);
      lastClickedIndexRef.current = null;
    } else {
      setSelectedSims(simulations.map(sim => sim.simulation_id));
      lastClickedIndexRef.current = simulations.length - 1;
    }
  }, [simulations, selectedSims, setSelectedSims]);

  // Keyboard shortcut: Ctrl+A to select all
  useEffect(() => {
    const handleKeyDown = e => {
      // Only handle Ctrl+A if not in an input/textarea/contenteditable
      if (
        (e.ctrlKey || e.metaKey) &&
        e.key === 'a' &&
        !e.target.closest('input') &&
        !e.target.closest('textarea') &&
        !e.target.isContentEditable
      ) {
        e.preventDefault();
        handleSelectAll();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleSelectAll]);

  const handleCardClick = useCallback(
    (simId, e) => {
      if (
        e.target.closest('a') ||
        e.target.closest('button') ||
        e.target.closest('.editable-sim-name')
      ) {
        return;
      }

      const inputEl = e.target.closest('input');
      if (inputEl && inputEl.type !== 'checkbox') {
        return;
      }

      const clickedIndex = simulations.findIndex(sim => sim.simulation_id === simId);

      // Shift+click for range selection
      if (e.shiftKey && lastClickedIndexRef.current !== null) {
        // Prevent default text selection behavior
        e.preventDefault();

        // Clear any existing text selection
        if (window.getSelection) {
          window.getSelection().removeAllRanges();
        }

        const start = Math.min(lastClickedIndexRef.current, clickedIndex);
        const end = Math.max(lastClickedIndexRef.current, clickedIndex);
        const rangeIds = simulations.slice(start, end + 1).map(sim => sim.simulation_id);

        setSelectedSims(prev => {
          const newSelection = new Set(prev);
          rangeIds.forEach(id => newSelection.add(id));
          return Array.from(newSelection);
        });
      } else {
        // Normal click: toggle selection
        setSelectedSims(prev =>
          prev.includes(simId) ? prev.filter(id => id !== simId) : [...prev, simId]
        );
      }

      lastClickedIndexRef.current = clickedIndex;
    },
    [simulations, setSelectedSims]
  );

  const handleCompare = () => {
    if (selectedSims.length < 2) {
      toast.warning('Please select at least 2 simulations to compare');
      return;
    }
    navigate(`/compare?ids=${selectedSims.join(',')}`);
  };

  const handleStop = useCallback(
    async simId => {
      setConfirmModal({
        show: true,
        title: 'Stop Simulation',
        message: `Stop running simulation "${simId}"? This action cannot be undone.`,
        variant: 'warning',
        onConfirm: async () => {
          setConfirmModal({ ...confirmModal, show: false });
          setStopping(true);
          try {
            await stopSimulation(simId);
            await refetch();
            toast.success('Simulation stopped successfully');
          } catch (err) {
            toast.error(`Failed to stop: ${err.response?.data?.detail || err.message}`);
          } finally {
            setStopping(false);
          }
        },
      });
    },
    [setConfirmModal, setStopping, refetch, confirmModal]
  );

  const handleDeleteSelected = useCallback(async () => {
    if (selectedSims.length === 0) {
      toast.warning('No simulations selected');
      return;
    }

    const runningSimulations = selectedSims.filter(simId => statuses[simId]?.status === 'running');
    if (runningSimulations.length > 0) {
      toast.error(`Cannot delete running simulations: ${runningSimulations.join(', ')}`);
      return;
    }

    setConfirmModal({
      show: true,
      title: 'Delete Simulations',
      message: `Delete ${selectedSims.length} simulation(s)?`,
      variant: 'danger',
      onConfirm: async () => {
        setConfirmModal({ ...confirmModal, show: false });
        // Animate cards out first
        setExitingCards(selectedSims);
        setDeleting(true);
        // Wait for exit animation to complete
        await new Promise(resolve => setTimeout(resolve, 300));
        try {
          const response = await deleteMultipleSimulations(selectedSims);
          const { deleted, failed } = response.data;

          if (failed.length > 0) {
            const failedList = failed.map(f => `${f.simulation_id}: ${f.error}`).join('\n');
            toast.warning(`Some deletions failed:\n${failedList}`);
          }

          if (deleted.length > 0) {
            setSelectedSims([]);
            await refetch();
            toast.success(`Successfully deleted ${deleted.length} simulation(s)`);
          }
        } catch (err) {
          toast.error(`Failed to delete: ${err.response?.data?.detail || err.message}`);
        } finally {
          setExitingCards([]);
          setDeleting(false);
        }
      },
    });
  }, [
    selectedSims,
    statuses,
    setConfirmModal,
    confirmModal,
    setExitingCards,
    setDeleting,
    setSelectedSims,
    refetch,
  ]);

  const handleClearAll = useCallback(async () => {
    if (!simulations || simulations.length === 0) {
      toast.warning('No simulations to clear');
      return;
    }

    const runningSimulations = simulations.filter(
      sim => statuses[sim.simulation_id]?.status === 'running'
    );
    if (runningSimulations.length > 0) {
      toast.error(
        `Cannot clear all: ${runningSimulations.length} simulation(s) still running. Please wait for them to complete or fail first.`
      );
      return;
    }

    setConfirmModal({
      show: true,
      title: 'Clear All Simulations',
      message: `Clear ALL ${simulations.length} simulation(s)?\n\nThis will permanently delete all simulation data and cannot be undone.`,
      variant: 'danger',
      onConfirm: async () => {
        setConfirmModal({ ...confirmModal, show: false });
        setDeleting(true);
        try {
          const allSimIds = simulations.map(sim => sim.simulation_id);
          const response = await deleteMultipleSimulations(allSimIds);
          const { deleted, failed } = response.data;

          if (failed.length > 0) {
            const failedList = failed.map(f => `${f.simulation_id}: ${f.error}`).join('\n');
            toast.warning(`Some deletions failed:\n${failedList}`);
          }

          if (deleted.length > 0) {
            setSelectedSims([]);
            await refetch();
            toast.success(`Successfully cleared ${deleted.length} simulation(s)`);
          }
        } catch (err) {
          toast.error(`Failed to clear simulations: ${err.response?.data?.detail || err.message}`);
        } finally {
          setDeleting(false);
        }
      },
    });
  }, [simulations, statuses, setConfirmModal, confirmModal, setDeleting, setSelectedSims, refetch]);

  if (loading) {
    return <LoadingPage title="🏠 Simulation Dashboard" />;
  }

  if (error) {
    return (
      <PageContainer>
        <PageHeader title="🏠 Simulation Dashboard" />
        <div className="alert alert-danger">{error}</div>
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      <PageHeader title="🏠 Simulation Dashboard">
        <BulkActions
          selectedCount={selectedSims.length}
          totalCount={simulations?.length || 0}
          onDeleteSelected={handleDeleteSelected}
          onCompare={handleCompare}
          onClearAll={handleClearAll}
          onSelectAll={handleSelectAll}
          deleting={deleting}
        />
      </PageHeader>

      <FilterBar
        search={searchFilter}
        onSearchChange={setSearchFilter}
        status={statusFilter}
        onStatusChange={setStatusFilter}
        origin={originFilter}
        onOriginChange={setOriginFilter}
        dataset={datasetFilter}
        onDatasetChange={setDatasetFilter}
        modelType={modelTypeFilter}
        onModelTypeChange={setModelTypeFilter}
        strategy={strategyFilter}
        onStrategyChange={setStrategyFilter}
        attack={attackFilter}
        onAttackChange={setAttackFilter}
        originOptions={ORIGIN_OPTIONS}
        datasetOptions={DATASET_OPTIONS}
        modelTypeOptions={MODEL_TYPE_OPTIONS}
        strategyOptions={STRATEGY_OPTIONS}
        attackOptions={ATTACK_OPTIONS}
      />

      {hasRunning && (
        <Alert variant="warning" className="mb-4 shadow-sm border-0 bg-warning-subtle">
          <div className="d-flex justify-content-between align-items-center">
            <div>
              <i className="bi bi-exclamation-triangle-fill me-2 text-warning"></i>
              <strong>Simulation in progress</strong> - New simulations will queue automatically
            </div>
            <Button as={Link} to="/experiments/queue" className="btn-warning-action" size="sm">
              View Global Queue
            </Button>
          </div>
        </Alert>
      )}

      <SimulationList
        simulations={filteredSimulations}
        statuses={statuses}
        selectedSims={selectedSims}
        exitingCards={exitingCards}
        onCardClick={handleCardClick}
        onRename={refetch}
        onStop={handleStop}
        stopping={stopping}
      />

      <ConfirmModal
        show={confirmModal.show}
        title={confirmModal.title}
        message={confirmModal.message}
        variant={confirmModal.variant}
        onConfirm={confirmModal.onConfirm}
        onCancel={() => setConfirmModal({ ...confirmModal, show: false })}
      />
    </PageContainer>
  );
}
