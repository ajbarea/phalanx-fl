import { PageContainer } from '@components/layout/PageContainer';
import { PageHeader } from '@components/layout/PageHeader';
import { QueueBuilder } from '@components/features/experiment-queue/QueueBuilder';
import { useSimulations } from '@hooks/useSimulations';
import { SimulationList } from '@components/features/simulation-list/SimulationList';

export function ExperimentQueue() {
  const { simulations, statuses, refetch } = useSimulations();

  const activeSimulations = simulations.filter(
    sim =>
      statuses[sim.simulation_id]?.status === 'running' ||
      statuses[sim.simulation_id]?.status === 'queued'
  );

  return (
    <PageContainer>
      <PageHeader title="🧪 Experiment Queue" />

      {activeSimulations.length > 0 && (
        <div className="mb-5">
          <h4 className="mb-3 d-flex align-items-center gap-2">
            <i className="bi bi-clock-history text-warning"></i>
            Active & Pending Simulations
          </h4>
          <SimulationList
            simulations={activeSimulations}
            statuses={statuses}
            selectedSims={[]}
            exitingCards={[]}
            onCardClick={() => {}}
            onRename={refetch}
            onStop={() => {}}
            stopping={false}
          />
        </div>
      )}

      <hr className="my-5" />

      <h4 className="mb-3">
        <i className="bi bi-plus-circle text-primary me-2"></i>
        Build New Experiment
      </h4>
      <QueueBuilder />
    </PageContainer>
  );
}
