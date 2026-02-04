import React, { useEffect, useRef } from 'react';
import PropTypes from 'prop-types';
import './Offcanvas.css';

export function Offcanvas({
  isOpen = false,
  toggle,
  direction = 'end',
  backdrop = true,
  backdropClassName = '',
  className = '',
  style = {},
  children,
  autoFocus = true,
  keyboard = true,
  labelledBy,
  onClosed = () => {},
  onOpened = () => {},
  scrollable = false,
  unmountOnClose = true,
  zIndex = 1050,
  ...rest
}) {
  const offcanvasRef = useRef(null);

  useEffect(() => {
    if (isOpen) {
      onOpened();
      if (autoFocus && offcanvasRef.current) {
        offcanvasRef.current.focus();
      }
      if (keyboard) {
        const handleKeyDown = e => {
          if (e.key === 'Escape') {
            toggle && toggle();
          }
        };
        document.addEventListener('keydown', handleKeyDown);
        return () => document.removeEventListener('keydown', handleKeyDown);
      }
    } else {
      onClosed();
    }
  }, [isOpen, autoFocus, keyboard, onClosed, onOpened, toggle]);

  if (!isOpen && unmountOnClose) return null;

  return (
    <>
      {backdrop && isOpen && (
        <div
          className={`offcanvas-backdrop ${backdropClassName}`}
          style={{ zIndex: zIndex - 1 }}
          onClick={toggle}
        />
      )}
      <aside
        ref={offcanvasRef}
        className={`offcanvas offcanvas-${direction} ${isOpen ? 'show' : ''} ${className}`}
        style={{ zIndex, ...style, overflowY: scrollable ? 'auto' : 'hidden' }}
        tabIndex="-1"
        aria-labelledby={labelledBy}
        role="dialog"
        {...rest}
      >
        {children}
      </aside>
    </>
  );
}

Offcanvas.propTypes = {
  isOpen: PropTypes.bool,
  toggle: PropTypes.func,
  direction: PropTypes.oneOf(['start', 'end', 'top', 'bottom']),
  backdrop: PropTypes.bool,
  backdropClassName: PropTypes.string,
  className: PropTypes.string,
  style: PropTypes.object,
  children: PropTypes.node,
  autoFocus: PropTypes.bool,
  keyboard: PropTypes.bool,
  labelledBy: PropTypes.string,
  onClosed: PropTypes.func,
  onOpened: PropTypes.func,
  scrollable: PropTypes.bool,
  unmountOnClose: PropTypes.bool,
  zIndex: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
};

export function OffcanvasHeader({
  children,
  className = '',
  closeAriaLabel = 'Close',
  toggle,
  tag = 'h5',
  wrapTag = 'div',
  ...rest
}) {
  const TagComponent = tag;
  const WrapTagComponent = wrapTag;
  return (
    <WrapTagComponent className={`offcanvas-header ${className}`} {...rest}>
      <TagComponent className="offcanvas-title">{children}</TagComponent>
      {toggle && (
        <button
          type="button"
          className="offcanvas-close"
          aria-label={closeAriaLabel}
          onClick={toggle}
        >
          &times;
        </button>
      )}
    </WrapTagComponent>
  );
}

OffcanvasHeader.propTypes = {
  children: PropTypes.node,
  className: PropTypes.string,
  closeAriaLabel: PropTypes.string,
  toggle: PropTypes.func,
  tag: PropTypes.elementType,
  wrapTag: PropTypes.elementType,
};

export function OffcanvasBody({ children, className = '', tag = 'div', ...rest }) {
  const TagComponent = tag;
  return (
    <TagComponent className={`offcanvas-body ${className}`} {...rest}>
      {children}
    </TagComponent>
  );
}

OffcanvasBody.propTypes = {
  children: PropTypes.node,
  className: PropTypes.string,
  tag: PropTypes.elementType,
};
