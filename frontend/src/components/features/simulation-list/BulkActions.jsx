import PropTypes from 'prop-types';
import { Button } from 'react-bootstrap';
import { MaterialIcon } from '@components/common/Icon/MaterialIcon';

export function BulkActions({
  selectedCount,
  totalCount,
  onDeleteSelected,
  onCompare,
  onClearAll,
  deleting,
}) {
  return (
    <div className="d-flex flex-wrap gap-2 w-100 w-md-auto">
      {selectedCount > 0 && (
        <>
          <Button
            variant="danger"
            size="sm"
            onClick={onDeleteSelected}
            disabled={deleting}
            className="flex-grow-1 flex-md-grow-0"
            aria-label={`Delete ${selectedCount} selected simulation${selectedCount > 1 ? 's' : ''}`}
          >
            <span aria-hidden="true">🗑️</span> Delete ({selectedCount})
          </Button>
          <Button
            variant="info"
            size="sm"
            onClick={onCompare}
            className="flex-grow-1 flex-md-grow-0"
            aria-label={`Compare ${selectedCount} selected simulation${selectedCount > 1 ? 's' : ''}`}
          >
            <span aria-hidden="true">📊</span> Compare ({selectedCount})
          </Button>
        </>
      )}
      {totalCount > 0 && (
        <Button
          variant="outline-danger"
          size="sm"
          onClick={onClearAll}
          disabled={deleting}
          className="flex-grow-1 flex-md-grow-0"
          aria-label={`Clear all ${totalCount} simulation${totalCount > 1 ? 's' : ''}`}
        >
          <div className="d-flex align-items-center gap-1">
            <MaterialIcon name="delete" size={20} aria-hidden="true" />
            <span>Clear All</span>
          </div>
        </Button>
      )}
    </div>
  );
}

BulkActions.propTypes = {
  selectedCount: PropTypes.number.isRequired,
  totalCount: PropTypes.number.isRequired,
  onDeleteSelected: PropTypes.func.isRequired,
  onCompare: PropTypes.func.isRequired,
  onClearAll: PropTypes.func.isRequired,
  deleting: PropTypes.bool,
};

BulkActions.defaultProps = {
  deleting: false,
};
