import PropTypes from 'prop-types';

export function FilterBar({
  search,
  onSearchChange,
  status,
  onStatusChange,
  origin,
  onOriginChange,
  dataset,
  onDatasetChange,
  modelType,
  onModelTypeChange,
  strategy,
  onStrategyChange,
  attack,
  onAttackChange,
  originOptions,
  datasetOptions,
  modelTypeOptions,
  strategyOptions,
  attackOptions,
}) {
  return (
    <div className="filter-bar d-flex align-items-center gap-3 flex-wrap p-3 bg-body-tertiary rounded-3 mb-4 shadow-sm">
      {/* Search Bar */}
      <div className="flex-grow-1 min-width-200">
        <label htmlFor="search-filter" className="form-label small fw-semibold text-muted mb-1">
          Search
        </label>
        <div className="input-group input-group-sm">
          <span className="input-group-text bg-transparent border-end-0">
            <i className="bi bi-search text-muted"></i>
          </span>
          <input
            id="search-filter"
            type="text"
            className="form-control border-start-0 ps-0"
            placeholder="Search name or ID..."
            value={search}
            onChange={e => onSearchChange(e.target.value)}
          />
        </div>
      </div>

      {/* Status Filter */}
      <div style={{ minWidth: 120 }}>
        <label htmlFor="status-filter" className="form-label small fw-semibold text-muted mb-1">
          Status
        </label>
        <select
          id="status-filter"
          className="form-select form-select-sm"
          value={status}
          onChange={e => onStatusChange(e.target.value)}
        >
          <option value="all">All Statuses</option>
          <option value="queued">Queued</option>
          <option value="running">Running</option>
          <option value="completed">Completed</option>
          <option value="failed">Failed</option>
          <option value="stopped">Stopped</option>
        </select>
      </div>

      {/* Origin Filter */}
      <div style={{ minWidth: 120 }}>
        <label htmlFor="origin-filter" className="form-label small fw-semibold text-muted mb-1">
          Origin
        </label>
        <select
          id="origin-filter"
          className="form-select form-select-sm"
          value={origin}
          onChange={e => onOriginChange(e.target.value)}
        >
          {originOptions.map(opt => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {/* Strategy Filter */}
      <div style={{ minWidth: 140 }}>
        <label htmlFor="strategy-filter" className="form-label small fw-semibold text-muted mb-1">
          Strategy
        </label>
        <select
          id="strategy-filter"
          className="form-select form-select-sm"
          value={strategy}
          onChange={e => onStrategyChange(e.target.value)}
        >
          <option value="all">All Strategies</option>
          {strategyOptions.map(opt => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {/* Attack Filter */}
      <div style={{ minWidth: 140 }}>
        <label htmlFor="attack-filter" className="form-label small fw-semibold text-muted mb-1">
          Attack
        </label>
        <select
          id="attack-filter"
          className="form-select form-select-sm"
          value={attack}
          onChange={e => onAttackChange(e.target.value)}
        >
          <option value="all">All Attacks</option>
          <option value="none">None</option>
          {attackOptions.map(opt => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {/* Dataset Filter */}
      <div style={{ minWidth: 150 }}>
        <label htmlFor="dataset-filter" className="form-label small fw-semibold text-muted mb-1">
          Dataset
        </label>
        <select
          id="dataset-filter"
          className="form-select form-select-sm"
          value={dataset}
          onChange={e => onDatasetChange(e.target.value)}
        >
          {datasetOptions.map(opt => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {/* Model Type Filter */}
      <div style={{ minWidth: 130 }}>
        <label htmlFor="model-type-filter" className="form-label small fw-semibold text-muted mb-1">
          Model
        </label>
        <select
          id="model-type-filter"
          className="form-select form-select-sm"
          value={modelType}
          onChange={e => onModelTypeChange(e.target.value)}
        >
          {modelTypeOptions.map(opt => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}

FilterBar.propTypes = {
  search: PropTypes.string.isRequired,
  onSearchChange: PropTypes.func.isRequired,
  status: PropTypes.string.isRequired,
  onStatusChange: PropTypes.func.isRequired,
  origin: PropTypes.string.isRequired,
  onOriginChange: PropTypes.func.isRequired,
  dataset: PropTypes.string.isRequired,
  onDatasetChange: PropTypes.func.isRequired,
  modelType: PropTypes.string.isRequired,
  onModelTypeChange: PropTypes.func.isRequired,
  strategy: PropTypes.string.isRequired,
  onStrategyChange: PropTypes.func.isRequired,
  attack: PropTypes.string.isRequired,
  onAttackChange: PropTypes.func.isRequired,
  originOptions: PropTypes.array.isRequired,
  datasetOptions: PropTypes.array.isRequired,
  modelTypeOptions: PropTypes.array.isRequired,
  strategyOptions: PropTypes.array.isRequired,
  attackOptions: PropTypes.array.isRequired,
};
