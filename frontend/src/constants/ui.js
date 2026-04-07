/**
 * UI Constants for consistent user experience across the application.
 *
 * Based on 2025 accessibility guidelines:
 * @see https://sheribyrnehaber.medium.com/designing-toast-messages-for-accessibility-fb610ac364be
 */

/**
 * Toast notification durations based on accessibility research.
 * Formula: 5 seconds base + 1 second per 120 words.
 * Short messages use 6000ms, longer messages should calculate accordingly.
 */
export const TOAST_DURATION = {
  /** Default duration for info/success toasts (6 seconds) */
  DEFAULT: 6000,
  /** Short duration for quick confirmations (4 seconds) */
  SHORT: 4000,
  /** Extended duration for important messages (8 seconds) */
  LONG: 8000,
  /** No auto-dismiss - user must close manually */
  PERSISTENT: 0,
};

/**
 * Cache durations for TanStack Query.
 */
export const CACHE_DURATION = {
  /** 5 minutes - for rarely changing data like device info */
  FIVE_MINUTES: 5 * 60 * 1000,
  /** 1 minute - for moderately changing data */
  ONE_MINUTE: 60 * 1000,
  /** 30 seconds - for frequently changing data */
  THIRTY_SECONDS: 30 * 1000,
};

/**
 * Polling intervals for real-time data fetching.
 */
export const POLLING_INTERVALS = {
  /** 5 seconds - Standard status polling for simulations */
  SIMULATIONS: 5000,
  /** 2 seconds - Fast polling for running simulation details */
  SIMULATION_DETAILS: 2000,
  /** 10 seconds - Check for any running simulations */
  RUNNING_CHECK: 10000,
  /** 1 second - Auto-save draft config */
  DRAFT_SAVE: 1000,
  /** 100ms - Delay before terminal operations */
  TERMINAL_CONNECT: 100,
};

/**
 * Tooltip timing configuration for consistent UX.
 */
export const TOOLTIP_DELAYS = {
  show: 250,
  hide: 400,
};

/** Terminal timing constants in milliseconds. */
export const TERMINAL_TIMING = {
  CONNECT_DELAY: 100,
  FIT_ADDON_DELAY: 150,
  DIMENSION_CHECK: 100,
  FOCUS_DELAY: 50,
  IMMEDIATE: 0,
};

/** Responsive breakpoints in pixels. */
export const BREAKPOINTS = {
  MOBILE: 768,
};

/** Chart dimensions in pixels. */
export const CHART_DIMENSIONS = {
  MOBILE_HEIGHT: 350,
  DESKTOP_HEIGHT: 500,
  MIN_WIDTH: 300,
};

/**
 * Colorblind-safe chart palettes (WCAG 2.1 AA compliant).
 * Extended to 12 colors for large federations. All colors tested for visibility,
 * white text readability on buttons, and colorblind accessibility.
 * @see https://jfly.uni-koeln.de/color/
 */
export const CHART_COLORS = {
  light: [
    '#0072B2',
    '#D55E00',
    '#009E73',
    '#CC79A7',
    '#E69F00',
    '#56B4E9',
    '#785EF0',
    '#404040',
    '#117733',
    '#882255',
    '#44AA99',
    '#999933',
  ],
  dark: [
    '#56B4E9',
    '#E69F00',
    '#00D084',
    '#CC79A7',
    '#FF7EB6',
    '#82CFFF',
    '#BE95FF',
    '#33B1FF',
    '#08BDBA',
    '#FF6F61',
    '#FFB000',
    '#6FDC8C',
  ],
};

/**
 * Malicious client highlight colors for charts.
 */
export const MALICIOUS_COLORS = {
  light: '#D32F2F',
  dark: '#FF6B6B',
};

/**
 * Chart UI element colors (grid, axis, text, brush).
 */
export const CHART_UI_COLORS = {
  light: {
    grid: '#e0e0e0',
    axis: '#666666',
    text: '#333333',
    brush: '#8884d8',
    brushFill: '#f5f5f5',
    tooltipBg: '#ffffff',
    line: '#6750A4',
  },
  dark: {
    grid: '#444444',
    axis: '#999999',
    text: '#cccccc',
    brush: '#666666',
    brushFill: '#1a1a1a',
    tooltipBg: '#2b2b2b',
    line: '#82ca9d',
  },
};

/**
 * Material Design 3 theme colors.
 * Used for surfaces, text, and UI elements.
 */
export const THEME_COLORS = {
  light: {
    surface: '#ffffff',
    surfaceVariant: '#f5f5f5',
    surfaceContainer: '#fafafa',
    primary: '#6750a4',
    primaryHover: '#7965af',
    onPrimary: '#ffffff',
    textPrimary: '#212529',
    textSecondary: '#6c757d',
    textMuted: '#adb5bd',
    border: '#dee2e6',
    borderStrong: '#ced4da',
  },
  dark: {
    surface: '#1c1b1f',
    surfaceVariant: '#2b2930',
    surfaceContainer: '#353239',
    surfaceContainerHigh: '#49454f',
    primary: '#d0bcff',
    primaryContainer: '#4f378b',
    primaryHover: '#6750a4',
    onPrimary: '#381e72',
    onPrimaryContainer: '#eaddff',
    textPrimary: '#e6e1e5',
    textSecondary: '#cac4d0',
    textMuted: '#938f99',
    border: '#49454f',
    borderStrong: '#938f99',
  },
};

/**
 * Status colors for simulation badges and indicators.
 * Each status has text color, background, and dot color.
 */
export const STATUS_COLORS = {
  light: {
    pending: {
      text: '#6c757d',
      bg: 'rgba(108, 117, 125, 0.1)',
      dot: '#6c757d',
    },
    running: {
      text: '#0d6efd',
      bg: 'rgba(13, 110, 253, 0.1)',
      dot: '#0d6efd',
    },
    completed: {
      text: '#198754',
      bg: 'rgba(25, 135, 84, 0.1)',
      dot: '#198754',
    },
    failed: {
      text: '#dc3545',
      bg: 'rgba(220, 53, 69, 0.1)',
      dot: '#dc3545',
    },
    stopped: {
      text: '#fd7e14',
      bg: 'rgba(253, 126, 20, 0.1)',
      dot: '#fd7e14',
    },
    loading: {
      text: '#6c757d',
      bg: 'rgba(108, 117, 125, 0.08)',
      dot: '#adb5bd',
    },
  },
  dark: {
    pending: {
      text: '#cac4d0',
      bg: 'rgba(202, 196, 208, 0.12)',
      dot: '#938f99',
    },
    running: {
      text: '#9dc6f0',
      bg: 'rgba(157, 198, 240, 0.12)',
      dot: '#5b9dd9',
    },
    completed: {
      text: '#9dd6b8',
      bg: 'rgba(157, 214, 184, 0.12)',
      dot: '#4caf50',
    },
    failed: {
      text: '#f2b8b5',
      bg: 'rgba(242, 184, 181, 0.12)',
      dot: '#e57373',
    },
    stopped: {
      text: '#ffd89e',
      bg: 'rgba(255, 216, 158, 0.12)',
      dot: '#ff9800',
    },
    loading: {
      text: '#cac4d0',
      bg: 'rgba(202, 196, 208, 0.08)',
      dot: '#938f99',
    },
  },
};

/**
 * Alert variant colors for success, danger, warning, info.
 */
export const ALERT_COLORS = {
  light: {
    success: {
      bg: 'rgba(25, 135, 84, 0.06)',
      border: 'rgba(25, 135, 84, 0.2)',
      text: '#198754',
    },
    danger: {
      bg: 'rgba(220, 53, 69, 0.06)',
      border: 'rgba(220, 53, 69, 0.2)',
      text: '#dc3545',
    },
    warning: {
      bg: 'rgba(255, 193, 7, 0.06)',
      border: 'rgba(255, 193, 7, 0.2)',
      text: '#b8860b', // Accessible warning (DarkGoldenrod - 5.3:1)
    },
    info: {
      bg: 'rgba(13, 110, 253, 0.06)',
      border: 'rgba(13, 110, 253, 0.2)',
      text: '#0d6efd',
    },
  },
  dark: {
    success: {
      bg: '#1d3a2d',
      border: '#2d5a45',
      text: '#9dd6b8',
    },
    danger: {
      bg: '#3a1d1d',
      border: '#5a2d2d',
      text: '#f2b8b5',
    },
    warning: {
      bg: '#3a341d',
      border: '#5a4f2d',
      text: '#ffb347', // Accessible warning (Pastel Orange - 4.7:1)
    },
    info: {
      bg: '#1d2a3a',
      border: '#2d3f5a',
      text: '#9dc6f0',
    },
  },
};

/**
 * Difficulty badge colors for preset cards.
 */
export const DIFFICULTY_COLORS = {
  light: {
    beginner: {
      bg: 'rgba(34, 197, 94, 0.15)',
      border: 'rgba(34, 197, 94, 0.3)',
      text: '#16a34a',
    },
    intermediate: {
      bg: 'rgba(59, 130, 246, 0.15)',
      border: 'rgba(59, 130, 246, 0.3)',
      text: '#2563eb',
    },
    advanced: {
      bg: 'rgba(168, 85, 247, 0.15)',
      border: 'rgba(168, 85, 247, 0.3)',
      text: '#9333ea',
    },
  },
  dark: {
    beginner: {
      bg: 'rgba(74, 222, 128, 0.2)',
      border: 'rgba(74, 222, 128, 0.4)',
      text: '#86efac',
    },
    intermediate: {
      bg: 'rgba(96, 165, 250, 0.2)',
      border: 'rgba(96, 165, 250, 0.4)',
      text: '#93c5fd',
    },
    advanced: {
      bg: 'rgba(192, 132, 252, 0.2)',
      border: 'rgba(192, 132, 252, 0.4)',
      text: '#d8b4fe',
    },
  },
};

/**
 * Attack type colors for visualization cards and icons.
 * Light mode uses vibrant colors, dark mode uses desaturated variants.
 */
export const ATTACK_TYPE_COLORS = {
  light: {
    label_flipping: '#e74c3c',
    gaussian_noise: '#9b59b6',
    model_poisoning: '#c0392b',
    gradient_scaling: '#d35400',
    byzantine_perturbation: '#8e44ad',
    token_replacement: '#2980b9',
  },
  dark: {
    label_flipping: '#ff8a80',
    gaussian_noise: '#ce93d8',
    model_poisoning: '#ef9a9a',
    gradient_scaling: '#ffcc80',
    byzantine_perturbation: '#b39ddb',
    token_replacement: '#90caf9',
  },
};

/**
 * Attack phase background colors for chart shading.
 * Semi-transparent backgrounds for visualizing attack phases on charts.
 */
export const ATTACK_PHASE_COLORS = {
  light: {
    label_flipping: 'rgba(220, 53, 69, 0.12)',
    gaussian_noise: 'rgba(255, 152, 0, 0.12)',
    model_poisoning: 'rgba(156, 39, 176, 0.12)',
    backdoor: 'rgba(63, 81, 181, 0.12)',
    free_rider: 'rgba(0, 150, 136, 0.12)',
    default: 'rgba(211, 47, 47, 0.10)',
  },
  dark: {
    label_flipping: 'rgba(244, 67, 54, 0.18)',
    gaussian_noise: 'rgba(255, 167, 38, 0.18)',
    model_poisoning: 'rgba(186, 104, 200, 0.18)',
    backdoor: 'rgba(121, 134, 203, 0.18)',
    free_rider: 'rgba(77, 182, 172, 0.18)',
    default: 'rgba(255, 107, 107, 0.15)',
  },
};

/**
 * Defense activation colors for reference lines on charts.
 */
export const DEFENSE_COLORS = {
  light: {
    threshold: '#2196F3',
    removalStart: '#4CAF50',
    warning: '#FF9800',
  },
  dark: {
    threshold: '#64B5F6',
    removalStart: '#81C784',
    warning: '#FFB74D',
  },
};

/**
 * Terminal/console colors for backgrounds and borders.
 */
export const TERMINAL_COLORS = {
  light: {
    bg: '#e9ecef',
    border: '#dee2e6',
    text: '#212529',
  },
  dark: {
    bg: '#2d2d2d',
    border: '#404040',
    text: '#e6e1e5',
  },
};

/**
 * Full xterm terminal theme palettes.
 * Used for xterm.js terminal emulator theming.
 */
export const TERMINAL_THEMES = {
  dark: {
    background: '#1e1e1e',
    foreground: '#d4d4d4',
    cursor: '#d4d4d4',
    cursorAccent: '#1e1e1e',
    selectionBackground: '#264f78',
    black: '#1e1e1e',
    red: '#f44747',
    green: '#6a9955',
    yellow: '#dcdcaa',
    blue: '#569cd6',
    magenta: '#c586c0',
    cyan: '#4ec9b0',
    white: '#d4d4d4',
    brightBlack: '#808080',
    brightRed: '#f44747',
    brightGreen: '#6a9955',
    brightYellow: '#dcdcaa',
    brightBlue: '#569cd6',
    brightMagenta: '#c586c0',
    brightCyan: '#4ec9b0',
    brightWhite: '#ffffff',
  },
  light: {
    background: '#ffffff',
    foreground: '#383a42',
    cursor: '#383a42',
    cursorAccent: '#ffffff',
    selectionBackground: '#b4d5fe',
    black: '#383a42',
    red: '#e45649',
    green: '#50a14f',
    yellow: '#c18401',
    blue: '#4078f2',
    magenta: '#a626a4',
    cyan: '#0184bc',
    white: '#fafafa',
    brightBlack: '#a0a1a7',
    brightRed: '#e45649',
    brightGreen: '#50a14f',
    brightYellow: '#c18401',
    brightBlue: '#4078f2',
    brightMagenta: '#a626a4',
    brightCyan: '#0184bc',
    brightWhite: '#ffffff',
  },
};

/**
 * Tooltip colors for chart tooltips and popovers.
 */
export const TOOLTIP_COLORS = {
  light: {
    bg: '#ffffff',
    border: '#e0e0e0',
    text: '#333333',
    muted: '#666666',
    danger: { border: '#dc3545', text: '#c62828' },
    success: { border: '#4caf50', text: '#2e7d32' },
  },
  dark: {
    bg: '#2b2b2b',
    border: '#444444',
    text: '#e0e0e0',
    muted: '#999999',
    danger: { border: '#f44336', text: '#ff8a80' },
    success: { border: '#81c784', text: '#a5d6a7' },
  },
};

/**
 * Helper to get theme-aware colors.
 * @param {string} theme - 'light' or 'dark'
 * @returns {Object} Colors for the specified theme
 */
export const getThemeColors = theme => ({
  chart: CHART_COLORS[theme] || CHART_COLORS.light,
  chartUI: CHART_UI_COLORS[theme] || CHART_UI_COLORS.light,
  malicious: MALICIOUS_COLORS[theme] || MALICIOUS_COLORS.light,
  theme: THEME_COLORS[theme] || THEME_COLORS.light,
  status: STATUS_COLORS[theme] || STATUS_COLORS.light,
  alert: ALERT_COLORS[theme] || ALERT_COLORS.light,
  difficulty: DIFFICULTY_COLORS[theme] || DIFFICULTY_COLORS.light,
  attackType: ATTACK_TYPE_COLORS[theme] || ATTACK_TYPE_COLORS.light,
  attackPhase: ATTACK_PHASE_COLORS[theme] || ATTACK_PHASE_COLORS.light,
  defense: DEFENSE_COLORS[theme] || DEFENSE_COLORS.light,
  terminal: TERMINAL_COLORS[theme] || TERMINAL_COLORS.light,
  terminalTheme: TERMINAL_THEMES[theme] || TERMINAL_THEMES.dark,
  tooltip: TOOLTIP_COLORS[theme] || TOOLTIP_COLORS.light,
});
