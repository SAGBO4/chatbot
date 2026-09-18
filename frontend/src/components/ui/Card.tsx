import React from 'react';

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  elevated?: boolean;
  hoverable?: boolean;
  glowing?: boolean;
}

export const Card: React.FC<CardProps> = ({
  children,
  elevated = false,
  hoverable = false,
  glowing = false,
  className = '',
  ...props
}) => {
  const baseStyles = 'rounded-2xl transition-all duration-200';
  const glassStyles = elevated
    ? 'bg-white/[0.04] backdrop-blur-2xl border border-white/[0.1] shadow-2xl shadow-black/80'
    : 'bg-white/[0.02] backdrop-blur-xl border border-white/[0.07] shadow-lg shadow-black/40';
  const glowStyles = glowing
    ? 'border-white/30 shadow-2xl shadow-white/5'
    : '';
  const hoverStyles = hoverable
    ? 'hover:border-white/25 hover:bg-white/[0.06] hover:shadow-2xl hover:shadow-white/5 hover:-translate-y-0.5'
    : '';

  return (
    <div
      className={`${baseStyles} ${glassStyles} ${glowStyles} ${hoverStyles} ${className}`}
      {...props}
    >
      {children}
    </div>
  );
};
