import { useState, useCallback } from 'react';
import { Modal, Button, Spinner, Badge } from 'react-bootstrap';
import { useImageZoom } from './useImageZoom';
import './ImageLightbox.css';

const ZOOM_PRESETS = [
  { value: 0.5, label: '50%' },
  { value: 0.75, label: '75%' },
  { value: 1, label: '100%' },
  { value: 1.25, label: '125%' },
  { value: 1.5, label: '150%' },
  { value: 2, label: '200%' },
  { value: 3, label: '300%' },
  { value: 4, label: '400%' },
];

/**
 * ImageLightbox - A zoom-enabled image modal component
 *
 * Features:
 * - Zoom in/out with buttons, mouse wheel, or double-click
 * - Pan by dragging when zoomed
 * - Keyboard shortcuts (Esc, +/-, 0, arrows)
 * - Touch support for mobile
 * - Theme-aware (uses CSS variables)
 *
 * @param {Object} props
 * @param {boolean} props.show - Whether the modal is visible
 * @param {Function} props.onHide - Callback when modal should close
 * @param {string} props.src - Image source URL
 * @param {string} props.alt - Image alt text
 * @param {string} props.title - Modal title
 * @param {React.ReactNode} props.footerContent - Optional content for the footer
 * @param {React.ReactNode} props.headerExtra - Optional extra content for header
 */
export function ImageLightbox({
  show,
  onHide,
  src,
  alt = 'Image',
  title,
  footerContent,
  headerExtra,
}) {
  const [isLoading, setIsLoading] = useState(true);
  const [hasError, setHasError] = useState(false);

  const {
    zoom,
    zoomPercent,
    isZoomed,
    canZoomIn,
    canZoomOut,
    containerRef,
    imageRef,
    zoomIn,
    zoomOut,
    reset,
    fitToScreen,
    setZoomLevel,
    handlers,
    imageStyle,
    isDragging,
  } = useImageZoom({ enabled: show, onClose: onHide });

  const handleImageLoad = useCallback(() => {
    setIsLoading(false);
    setHasError(false);
  }, []);

  const handleImageError = useCallback(() => {
    setIsLoading(false);
    setHasError(true);
  }, []);

  // Reset state when modal opens/closes or src changes
  const handleEnter = useCallback(() => {
    setIsLoading(true);
    setHasError(false);
    reset();
  }, [reset]);

  const handleZoomPresetChange = useCallback(
    e => {
      const value = parseFloat(e.target.value);
      setZoomLevel(value);
    },
    [setZoomLevel]
  );

  return (
    <Modal
      show={show}
      onHide={onHide}
      onEnter={handleEnter}
      dialogClassName="image-lightbox-modal"
      centered
      size="xl"
    >
      <Modal.Header closeButton>
        <Modal.Title>{title || alt}</Modal.Title>
        {headerExtra}
      </Modal.Header>

      <Modal.Body>
        {/* Zoom Toolbar */}
        <div className="lightbox-toolbar">
          <div className="lightbox-toolbar-group">
            <button
              className="lightbox-btn"
              onClick={zoomOut}
              disabled={!canZoomOut}
              title="Zoom out (-)"
            >
              <span className="lightbox-btn-icon">−</span>
            </button>

            <select
              className="lightbox-zoom-select"
              value={zoom}
              onChange={handleZoomPresetChange}
              title="Zoom level"
            >
              {ZOOM_PRESETS.map(preset => (
                <option key={preset.value} value={preset.value}>
                  {preset.label}
                </option>
              ))}
            </select>

            <button
              className="lightbox-btn"
              onClick={zoomIn}
              disabled={!canZoomIn}
              title="Zoom in (+)"
            >
              <span className="lightbox-btn-icon">+</span>
            </button>
          </div>

          <div className="lightbox-toolbar-divider" />

          <div className="lightbox-toolbar-group">
            <button
              className="lightbox-btn"
              onClick={fitToScreen}
              disabled={!isZoomed}
              title="Fit to screen (0)"
            >
              <span className="lightbox-btn-icon">⊡</span>
            </button>
          </div>

          <div className="lightbox-toolbar-divider" />

          <div className="lightbox-hints">
            <span className="lightbox-hint">
              <kbd className="lightbox-kbd">Scroll</kbd> zoom
            </span>
            <span className="lightbox-hint">
              <kbd className="lightbox-kbd">Double-click</kbd> toggle
            </span>
            {isZoomed && (
              <span className="lightbox-hint">
                <kbd className="lightbox-kbd">Drag</kbd> pan
              </span>
            )}
          </div>
        </div>

        {/* Image Container */}
        <div ref={containerRef} className="lightbox-image-container" {...handlers}>
          {isLoading && !hasError && (
            <div className="lightbox-loading">
              <Spinner animation="border" variant="primary" />
              <span>Loading image...</span>
            </div>
          )}

          {hasError && (
            <div className="lightbox-error">
              <span style={{ fontSize: '2rem' }}>⚠️</span>
              <span>Failed to load image</span>
              <Button
                variant="outline-secondary"
                size="sm"
                onClick={() => {
                  setIsLoading(true);
                  setHasError(false);
                }}
              >
                Retry
              </Button>
            </div>
          )}

          <div className="lightbox-image-wrapper">
            <img
              ref={imageRef}
              src={src}
              alt={alt}
              className={`lightbox-image ${isDragging ? 'dragging' : ''}`}
              style={{
                ...imageStyle,
                display: isLoading || hasError ? 'none' : 'block',
              }}
              onLoad={handleImageLoad}
              onError={handleImageError}
              draggable={false}
            />
          </div>
        </div>
      </Modal.Body>

      <Modal.Footer>
        <div className="lightbox-footer-content">
          <div className="lightbox-footer-info">
            {footerContent}
            {isZoomed && <Badge bg="secondary">{zoomPercent}% zoom</Badge>}
          </div>
          <div className="lightbox-footer-actions">
            <Button variant="secondary" onClick={onHide}>
              Close
            </Button>
          </div>
        </div>
      </Modal.Footer>
    </Modal>
  );
}

export default ImageLightbox;
