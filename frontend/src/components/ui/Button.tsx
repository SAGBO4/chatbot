'use client';

import React from 'react';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'danger' | 'ghost' | 'shiny' | 'gradient';
  size?: 'xs' | 'sm' | 'md' | 'lg';
  isLoading?: boolean;
}

export const Button: React.FC<ButtonProps> = ({
  children,
  variant = 'primary',
  size = 'md',
  isLoading = false,
  className = '',
  disabled,
  ...props
}) => {
  const baseStyles =
    'relative inline-flex items-center justify-center font-medium rounded-xl transition-all duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-zinc-400 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer select-none';

  const sizeStyles = {
    xs: 'px-2.5 py-1 text-[11px] gap-1.5',
    sm: 'px-3.5 py-1.5 text-xs gap-1.5',
    md: 'px-4 py-2 text-sm gap-2',
    lg: 'px-5 py-2.5 text-base gap-2.5',
  };

  const variantStyles = {
    primary:
      'bg-white hover:bg-zinc-200 text-black font-semibold shadow-lg shadow-white/10 border border-white active:scale-[0.98]',
    secondary:
      'bg-[#121216] hover:bg-[#1a1a20] text-zinc-100 border border-white/[0.1] hover:border-white/[0.2] shadow-sm active:scale-[0.98]',
    outline:
      'border border-white/[0.12] hover:border-white/[0.25] text-zinc-300 hover:text-white bg-transparent hover:bg-white/[0.05] active:scale-[0.98]',
    ghost:
      'text-zinc-400 hover:text-white hover:bg-white/[0.05] bg-transparent active:scale-[0.98]',
    danger:
      'bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/30 text-rose-300 active:scale-[0.98]',
    shiny:
      'shiny-badge text-zinc-100 hover:text-white border border-white/20 active:scale-[0.98]',
    gradient:
      'bg-gradient-to-b from-white to-zinc-200 hover:from-zinc-100 hover:to-zinc-300 text-black font-semibold shadow-md active:scale-[0.98]',
  };

  return (
    <button
      className={`${baseStyles} ${sizeStyles[size]} ${variantStyles[variant]} ${className}`}
      disabled={disabled || isLoading}
      {...props}
    >
      {isLoading ? (
        <span className="flex items-center gap-2">
          <svg className="animate-spin h-3.5 w-3.5 text-current" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
          </svg>
          <span className="text-xs">Chargement...</span>
        </span>
      ) : (
        children
      )}
    </button>
  );
};
