import { useState, useEffect } from 'react';
import { BREAKPOINTS, CHART_DIMENSIONS } from '@constants/ui';

/**
 * Hook for responsive chart height based on viewport width.
 * Returns appropriate chart height for mobile vs desktop.
 *
 * @param {number} [mobileHeight=CHART_DIMENSIONS.MOBILE_HEIGHT] - Height on mobile
 * @param {number} [desktopHeight=CHART_DIMENSIONS.DESKTOP_HEIGHT] - Height on desktop
 * @returns {number} Current chart height based on viewport
 */
export function useResponsiveChartHeight(
  mobileHeight = CHART_DIMENSIONS.MOBILE_HEIGHT,
  desktopHeight = CHART_DIMENSIONS.DESKTOP_HEIGHT
) {
  const [chartHeight, setChartHeight] = useState(() =>
    window.innerWidth < BREAKPOINTS.MOBILE ? mobileHeight : desktopHeight
  );

  useEffect(() => {
    const updateDimensions = () => {
      const isMobile = window.innerWidth < BREAKPOINTS.MOBILE;
      setChartHeight(isMobile ? mobileHeight : desktopHeight);
    };

    updateDimensions();
    window.addEventListener('resize', updateDimensions);
    return () => window.removeEventListener('resize', updateDimensions);
  }, [mobileHeight, desktopHeight]);

  return chartHeight;
}
