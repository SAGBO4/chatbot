import React from 'react';

export type BadgeVariant =
  | 'success'
  | 'warning'
  | 'error'
  | 'info'
  | 'neutral'
  | 'crimson'
  | 'gradient'
  | 'shiny'
  | 'brand'
  | 'outline';

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
  size?: 'xs' | 'sm' | 'md';
  dot?: boolean;
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'neutral',
  size = 'md',
  dot = false,
  className = '',
  ...props
}) => {
  const sizeStyles = {
    xs: 'px-1.5 py-0.5 text-[10px] gap-1',
    sm: 'px-2 py-0.5 text-[11px] gap-1.5',
    md: 'px-2.5 py-1 text-xs gap-1.5 font-medium',
  };

  const variantStyles: Record<BadgeVariant, string> = {
    shiny: 'shiny-badge text-zinc-200 border-white/[0.14] shadow-sm',
    neutral: 'bg-zinc-850/80 text-zinc-300 border border-white/[0.08]',
    outline: 'bg-transparent text-zinc-400 border border-white/[0.12]',
    success: 'bg-white/[0.08] text-zinc-200 border border-white/[0.15]',
    warning: 'bg-amber-500/10 text-amber-400 border border-amber-500/25',
    error: 'bg-rose-500/10 text-rose-400 border border-rose-500/25',
    info: 'bg-sky-500/10 text-sky-400 border border-sky-500/25',
    crimson: 'bg-white/[0.08] text-white border border-white/[0.18]',
    gradient: 'bg-gradient-to-r from-zinc-800 to-zinc-700 text-zinc-100 border border-white/15',
    brand: 'bg-white/10 text-white border border-white/20 font-medium shadow-sm shadow-white/5',
  };

  const dotColors: Record<BadgeVariant, string> = {
    shiny: 'bg-zinc-200',
    neutral: 'bg-zinc-400',
    outline: 'bg-zinc-400',
    success: 'bg-zinc-300',
    warning: 'bg-amber-400',
    error: 'bg-rose-400',
    info: 'bg-sky-400',
    crimson: 'bg-white',
    gradient: 'bg-zinc-200',
    brand: 'bg-white',
  };

  return (
    <span
      className={`inline-flex items-center rounded-lg tracking-normal ${sizeStyles[size]} ${variantStyles[variant]} ${className}`}
      {...props}
    >
      {dot && (
        <span
          className={`h-1.5 w-1.5 rounded-full ${dotColors[variant]} ${
            variant === 'success' ? 'animate-pulse' : ''
          }`}
        />
      )}
      {children}
    </span>
  );
};
