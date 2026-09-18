import React from 'react';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'danger' | 'ghost' | 'gradient';
  size?: 'sm' | 'md' | 'lg';
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
  const baseStyles = 'inline-flex items-center justify-center font-medium rounded-lg transition-all duration-150 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-[#0a0e17] disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer select-none';

  const sizeStyles = {
    sm: 'px-3 py-1.5 text-xs gap-1.5',
    md: 'px-4 py-2 text-sm gap-2',
    lg: 'px-5 py-2.5 text-base gap-2.5',
  };

  const variantStyles = {
    primary: 'bg-white hover:bg-neutral-200 active:bg-neutral-300 text-black font-semibold shadow-lg shadow-white/10 focus:ring-white active:scale-95',
    gradient: 'bg-white hover:bg-neutral-200 text-black font-semibold shadow-lg shadow-white/10 focus:ring-white active:scale-95',
    secondary: 'bg-white/[0.06] hover:bg-white/[0.12] text-white border border-white/[0.12] hover:border-white/[0.25] backdrop-blur-md shadow-sm focus:ring-white/40 active:scale-95',
    outline: 'border border-white/[0.15] hover:border-white/40 text-neutral-200 hover:text-white bg-white/[0.02] hover:bg-white/[0.06] backdrop-blur-sm focus:ring-white/30 active:scale-95',
    danger: 'bg-rose-600/15 hover:bg-rose-600/25 border border-rose-500/30 text-rose-300 focus:ring-rose-500 active:scale-95',
    ghost: 'text-neutral-400 hover:text-white hover:bg-white/[0.06] bg-transparent focus:ring-white/20 active:scale-95',
  };

  return (
    <button
      className={`${baseStyles} ${sizeStyles[size]} ${variantStyles[variant]} ${className}`}
      disabled={disabled || isLoading}
      {...props}
    >
      {isLoading ? (
        <span className="flex items-center gap-2">
          <svg className="animate-spin h-4 w-4 text-current" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
          </svg>
          <span>...</span>
        </span>
      ) : (
        children
      )}
    </button>
  );
};
