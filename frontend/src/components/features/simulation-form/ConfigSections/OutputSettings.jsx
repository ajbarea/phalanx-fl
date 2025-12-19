import { SwitchField } from '../FormFields/SwitchField';
import { SelectField } from '../FormFields/SelectField';
import { NumberField } from '../FormFields/NumberField';

const SNAPSHOT_FORMAT_OPTIONS = [
  { value: 'pickle', label: 'Pickle (Data only)' },
  { value: 'visual', label: 'Visual (Images only)' },
  { value: 'pickle_and_visual', label: 'Both (Pickle + Visual)' },
];

export function OutputSettings({ config, onChange }) {
  const snapshotsEnabled = config.save_attack_snapshots === 'true';

  return (
    <>
      <SwitchField
        name="show_plots"
        label="Show Plots"
        checked={config.show_plots === 'true'}
        onChange={e =>
          onChange({ target: { name: 'show_plots', value: e.target.checked ? 'true' : 'false' } })
        }
        tooltip="Display plots during simulation (may slow down execution)"
      />

      <SwitchField
        name="save_plots"
        label="Save Plots"
        checked={config.save_plots === 'true'}
        onChange={e =>
          onChange({ target: { name: 'save_plots', value: e.target.checked ? 'true' : 'false' } })
        }
        tooltip="Save plot images to disk after simulation completes"
      />

      <SwitchField
        name="save_csv"
        label="Save CSV"
        checked={config.save_csv === 'true'}
        onChange={e =>
          onChange({ target: { name: 'save_csv', value: e.target.checked ? 'true' : 'false' } })
        }
        tooltip="Export metrics to CSV files for further analysis"
      />

      <SwitchField
        name="save_attack_snapshots"
        label="Save Attack Snapshots"
        checked={snapshotsEnabled}
        onChange={e =>
          onChange({
            target: { name: 'save_attack_snapshots', value: e.target.checked ? 'true' : 'false' },
          })
        }
        tooltip="Save snapshots of data before and after attacks for analysis and visualization"
      />

      {snapshotsEnabled && (
        <>
          <SelectField
            name="attack_snapshot_format"
            label="Snapshot Format"
            value={config.attack_snapshot_format || 'pickle_and_visual'}
            onChange={onChange}
            options={SNAPSHOT_FORMAT_OPTIONS}
            tooltip="Format for saving attack snapshots: pickle for data analysis, visual for images"
          />

          <NumberField
            name="snapshot_max_samples"
            label="Max Snapshot Samples"
            value={config.snapshot_max_samples || 5}
            onChange={onChange}
            min={1}
            max={50}
            tooltip="Maximum number of samples to include in each snapshot (1-50)"
          />
        </>
      )}

      <SwitchField
        name="preserve_dataset"
        label="Preserve Dataset"
        checked={config.preserve_dataset === 'true'}
        onChange={e =>
          onChange({
            target: { name: 'preserve_dataset', value: e.target.checked ? 'true' : 'false' },
          })
        }
        tooltip="Keep partitioned dataset files after simulation (useful for reproducibility)"
      />

      <SwitchField
        name="strict_mode"
        label="Strict Mode"
        checked={config.strict_mode === 'true'}
        onChange={e =>
          onChange({ target: { name: 'strict_mode', value: e.target.checked ? 'true' : 'false' } })
        }
        tooltip="Enable strict validation of configuration parameters"
      />

      <SwitchField
        name="remove_clients"
        label="Remove Clients"
        checked={config.remove_clients === 'true'}
        onChange={e =>
          onChange({
            target: { name: 'remove_clients', value: e.target.checked ? 'true' : 'false' },
          })
        }
        tooltip="Enable client removal based on defense strategy (required for some strategies)"
      />
    </>
  );
}
