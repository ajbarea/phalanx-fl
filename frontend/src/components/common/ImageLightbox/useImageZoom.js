import { useState, useCallback, useRef, useEffect } from 'react';

const ZOOM_LEVELS = [0.5, 0.75, 1, 1.25, 1.5, 2, 3, 4];
const DEFAULT_ZOOM_INDEX = 2; // 1x (100%)
const WHEEL_ZOOM_SENSITIVITY = 0.002;

/**
 * Custom hook for image zoom and pan functionality
 * @param {Object} options - Configuration options
 * @param {boolean} options.enabled - Whether zoom is enabled
 * @param {Function} options.onClose - Callback when escape is pressed
 * @returns {Object} Zoom state and handlers
 */
export function useImageZoom({ enabled = true, onClose } = {}) {
  const [zoomIndex, setZoomIndex] = useState(DEFAULT_ZOOM_INDEX);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });

  const containerRef = useRef(null);
  const imageRef = useRef(null);

  const zoom = ZOOM_LEVELS[zoomIndex];
  const canZoomIn = zoomIndex < ZOOM_LEVELS.length - 1;
  const canZoomOut = zoomIndex > 0;
  const isZoomed = zoom > 1;

  // Reset zoom and position
  const reset = useCallback(() => {
    setZoomIndex(DEFAULT_ZOOM_INDEX);
    setPosition({ x: 0, y: 0 });
  }, []);

  // Zoom in one level
  const zoomIn = useCallback(() => {
    if (canZoomIn) {
      setZoomIndex(prev => prev + 1);
    }
  }, [canZoomIn]);

  // Zoom out one level
  const zoomOut = useCallback(() => {
    if (canZoomOut) {
      setZoomIndex(prev => {
        const newIndex = prev - 1;
        // Reset position when zooming out to 1x or below
        if (ZOOM_LEVELS[newIndex] <= 1) {
          setPosition({ x: 0, y: 0 });
        }
        return newIndex;
      });
    }
  }, [canZoomOut]);

  // Fit image to screen (reset to 1x)
  const fitToScreen = useCallback(() => {
    reset();
  }, [reset]);

  // Set zoom to specific level
  const setZoomLevel = useCallback(level => {
    const index = ZOOM_LEVELS.indexOf(level);
    if (index !== -1) {
      setZoomIndex(index);
      if (level <= 1) {
        setPosition({ x: 0, y: 0 });
      }
    }
  }, []);

  // Handle mouse wheel zoom
  const handleWheel = useCallback(
    e => {
      if (!enabled) return;
      e.preventDefault();

      const delta = -e.deltaY * WHEEL_ZOOM_SENSITIVITY;

      setZoomIndex(prev => {
        const newIndex = Math.max(0, Math.min(ZOOM_LEVELS.length - 1, prev + (delta > 0 ? 1 : -1)));

        // Reset position when zooming to 1x or below
        if (ZOOM_LEVELS[newIndex] <= 1) {
          setPosition({ x: 0, y: 0 });
        }

        return newIndex;
      });
    },
    [enabled]
  );

  // Handle double-click to toggle zoom
  const handleDoubleClick = useCallback(
    e => {
      if (!enabled) return;
      e.preventDefault();

      if (zoom > 1) {
        // Zoom out to fit
        reset();
      } else {
        // Zoom in to 2x
        setZoomLevel(2);
      }
    },
    [enabled, zoom, reset, setZoomLevel]
  );

  // Handle drag start
  const handleMouseDown = useCallback(
    e => {
      if (!enabled || !isZoomed) return;
      if (e.button !== 0) return; // Only left click

      e.preventDefault();
      setIsDragging(true);
      setDragStart({
        x: e.clientX - position.x,
        y: e.clientY - position.y,
      });
    },
    [enabled, isZoomed, position]
  );

  // Handle drag move
  const handleMouseMove = useCallback(
    e => {
      if (!isDragging || !isZoomed) return;

      const newX = e.clientX - dragStart.x;
      const newY = e.clientY - dragStart.y;

      // Calculate bounds based on zoom level and container size
      const container = containerRef.current;
      const image = imageRef.current;

      if (container && image) {
        const containerRect = container.getBoundingClientRect();
        const scaledWidth = image.naturalWidth * zoom * 0.5; // Approximate scaled size
        const scaledHeight = image.naturalHeight * zoom * 0.5;

        const maxX = Math.max(0, (scaledWidth - containerRect.width) / 2);
        const maxY = Math.max(0, (scaledHeight - containerRect.height) / 2);

        setPosition({
          x: Math.max(-maxX, Math.min(maxX, newX)),
          y: Math.max(-maxY, Math.min(maxY, newY)),
        });
      } else {
        setPosition({ x: newX, y: newY });
      }
    },
    [isDragging, isZoomed, dragStart, zoom]
  );

  // Handle drag end
  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  // Handle touch events for mobile
  const handleTouchStart = useCallback(
    e => {
      if (!enabled || !isZoomed || e.touches.length !== 1) return;

      const touch = e.touches[0];
      setIsDragging(true);
      setDragStart({
        x: touch.clientX - position.x,
        y: touch.clientY - position.y,
      });
    },
    [enabled, isZoomed, position]
  );

  const handleTouchMove = useCallback(
    e => {
      if (!isDragging || !isZoomed || e.touches.length !== 1) return;

      const touch = e.touches[0];
      const newX = touch.clientX - dragStart.x;
      const newY = touch.clientY - dragStart.y;

      setPosition({ x: newX, y: newY });
    },
    [isDragging, isZoomed, dragStart]
  );

  const handleTouchEnd = useCallback(() => {
    setIsDragging(false);
  }, []);

  // Keyboard shortcuts
  useEffect(() => {
    if (!enabled) return;

    const handleKeyDown = e => {
      switch (e.key) {
        case 'Escape':
          if (isZoomed) {
            reset();
          } else if (onClose) {
            onClose();
          }
          break;
        case '+':
        case '=':
          e.preventDefault();
          zoomIn();
          break;
        case '-':
        case '_':
          e.preventDefault();
          zoomOut();
          break;
        case '0':
          e.preventDefault();
          fitToScreen();
          break;
        case 'ArrowUp':
          if (isZoomed) {
            e.preventDefault();
            setPosition(p => ({ ...p, y: p.y + 50 }));
          }
          break;
        case 'ArrowDown':
          if (isZoomed) {
            e.preventDefault();
            setPosition(p => ({ ...p, y: p.y - 50 }));
          }
          break;
        case 'ArrowLeft':
          if (isZoomed) {
            e.preventDefault();
            setPosition(p => ({ ...p, x: p.x + 50 }));
          }
          break;
        case 'ArrowRight':
          if (isZoomed) {
            e.preventDefault();
            setPosition(p => ({ ...p, x: p.x - 50 }));
          }
          break;
        default:
          break;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [enabled, isZoomed, onClose, reset, zoomIn, zoomOut, fitToScreen]);

  // Global mouse up listener to handle drag end outside container
  useEffect(() => {
    if (!isDragging) return;

    window.addEventListener('mouseup', handleMouseUp);
    window.addEventListener('mousemove', handleMouseMove);

    return () => {
      window.removeEventListener('mouseup', handleMouseUp);
      window.removeEventListener('mousemove', handleMouseMove);
    };
  }, [isDragging, handleMouseUp, handleMouseMove]);

  return {
    // State
    zoom,
    zoomPercent: Math.round(zoom * 100),
    position,
    isDragging,
    isZoomed,
    canZoomIn,
    canZoomOut,

    // Refs
    containerRef,
    imageRef,

    // Actions
    zoomIn,
    zoomOut,
    reset,
    fitToScreen,
    setZoomLevel,

    // Event handlers
    handlers: {
      onWheel: handleWheel,
      onDoubleClick: handleDoubleClick,
      onMouseDown: handleMouseDown,
      onTouchStart: handleTouchStart,
      onTouchMove: handleTouchMove,
      onTouchEnd: handleTouchEnd,
    },

    // Style for the image
    imageStyle: {
      transform: `translate(${position.x}px, ${position.y}px) scale(${zoom})`,
      cursor: isZoomed ? (isDragging ? 'grabbing' : 'grab') : 'zoom-in',
      transition: isDragging ? 'none' : 'transform 0.2s ease-out',
    },
  };
}

export default useImageZoom;
