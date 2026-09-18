import React from 'react';

export type BadgeVariant = 'success' | 'warning' | 'error' | 'info' | 'neutral' | 'crimson' | 'gradient';

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
  size?: 'sm' | 'md';
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'neutral',
  size = 'md',
  className = '',
  ...props
}) => {
  const sizeStyles = {
    sm: 'px-2 py-0.5 text-[11px]',
    md: 'px-2.5 py-1 text-xs font-medium',
  };

  const variantStyles: Record<BadgeVariant, string> = {
    crimson: 'bg-white/[0.08] text-white border border-white/[0.18]',
    gradient: 'bg-white/10 text-white border border-white/20 shadow-sm shadow-white/5',
    success: 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/25',
    warning: 'bg-amber-500/10 text-amber-400 border border-amber-500/25',
    error: 'bg-rose-500/10 text-rose-400 border border-rose-500/25',
    info: 'bg-white/[0.08] text-neutral-200 border border-white/[0.15]',
    neutral: 'bg-white/[0.05] text-neutral-300 border border-white/[0.1]',
  };

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-md font-medium tracking-wide ${sizeStyles[size]} ${variantStyles[variant]} ${className}`}
      {...props}
    >
      {children}
    </span>
  );
};
