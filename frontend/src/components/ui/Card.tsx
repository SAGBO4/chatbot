'use client';

import React, { useRef, useCallback } from 'react';

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  elevated?: boolean;
  hoverable?: boolean;
  spotlight?: boolean;
  spotlightColor?: string;
  bento?: boolean;
}

export const Card: React.FC<CardProps> = ({
  children,
  elevated = false,
  hoverable = false,
  spotlight = true,
  spotlightColor = 'rgba(255, 255, 255, 0.08)',
  bento = false,
  className = '',
  onMouseMove,
  ...props
}) => {
  const cardRef = useRef<HTMLDivElement>(null);

  const handleMouseMove = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (spotlight && cardRef.current) {
        const rect = cardRef.current.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        cardRef.current.style.setProperty('--mouse-x', `${x}px`);
        cardRef.current.style.setProperty('--mouse-y', `${y}px`);
      }
      onMouseMove?.(e);
    },
    [spotlight, onMouseMove]
  );

  const baseStyles = 'relative rounded-2xl transition-all duration-200';
  const surfaceStyles = elevated
    ? 'bg-[#121216] border border-white/[0.09] shadow-xl shadow-black/60'
    : 'bg-[#101014] border border-white/[0.07] shadow-md shadow-black/40';

  const hoverStyles = hoverable
    ? 'hover:border-white/[0.18] hover:bg-[#14141a] hover:-translate-y-0.5'
    : '';

  const spotlightStyles = spotlight ? 'spotlight-card' : '';
  const bentoStyles = bento ? 'bento-highlight' : '';

  return (
    <div
      ref={cardRef}
      onMouseMove={handleMouseMove}
      style={{
        ...props.style,
        ...(spotlight ? { '--spotlight-color': spotlightColor } : {}),
      } as React.CSSProperties}
      className={`${baseStyles} ${surfaceStyles} ${spotlightStyles} ${bentoStyles} ${hoverStyles} ${className}`}
      {...props}
    >
      {children}
    </div>
  );
};

export const CardHeader: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({
  className = '',
  children,
  ...props
}) => (
  <div className={`flex flex-col space-y-1.5 p-6 ${className}`} {...props}>
    {children}
  </div>
);

export const CardTitle: React.FC<React.HTMLAttributes<HTMLHeadingElement>> = ({
  className = '',
  children,
  ...props
}) => (
  <h3 className={`text-sm sm:text-base font-semibold leading-none tracking-tight text-zinc-100 ${className}`} {...props}>
    {children}
  </h3>
);

export const CardDescription: React.FC<React.HTMLAttributes<HTMLParagraphElement>> = ({
  className = '',
  children,
  ...props
}) => (
  <p className={`text-xs text-zinc-400 leading-relaxed ${className}`} {...props}>
    {children}
  </p>
);

export const CardContent: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({
  className = '',
  children,
  ...props
}) => (
  <div className={`p-6 pt-0 ${className}`} {...props}>
    {children}
  </div>
);

export const CardFooter: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({
  className = '',
  children,
  ...props
}) => (
  <div className={`flex items-center p-6 pt-0 ${className}`} {...props}>
    {children}
  </div>
);
