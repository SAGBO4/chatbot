'use client';

import * as React from 'react';

interface TooltipProps {
  content: React.ReactNode;
  children: React.ReactElement;
  side?: 'top' | 'bottom' | 'left' | 'right';
  className?: string;
}

export const Tooltip: React.FC<TooltipProps> = ({
  content,
  children,
  side = 'top',
  className = '',
}) => {
  const [isVisible, setIsVisible] = React.useState(false);

  const sideStyles = {
    top: 'bottom-full left-1/2 -translate-x-1/2 mb-2',
    bottom: 'top-full left-1/2 -translate-x-1/2 mt-2',
    left: 'right-full top-1/2 -translate-y-1/2 mr-2',
    right: 'left-full top-1/2 -translate-y-1/2 ml-2',
  };

  return (
    <div
      className="relative inline-flex"
      onMouseEnter={() => setIsVisible(true)}
      onMouseLeave={() => setIsVisible(false)}
      onFocus={() => setIsVisible(true)}
      onBlur={() => setIsVisible(false)}
    >
      {children}
      {isVisible && (
        <div
          role="tooltip"
          className={`absolute ${sideStyles[side]} z-50 whitespace-nowrap rounded-lg bg-zinc-900 border border-white/[0.12] px-2.5 py-1 text-[11px] font-medium text-white shadow-xl pointer-events-none animate-in fade-in zoom-in-95 duration-100 ${className}`}
        >
          {content}
        </div>
      )}
    </div>
  );
};
