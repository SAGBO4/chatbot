import React from 'react';

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  helperText?: string;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, helperText, className = '', id, ...props }, ref) => {
    const inputId = id || (label ? label.toLowerCase().replace(/\s+/g, '-') : undefined);

    return (
      <div className="w-full">
        {label && (
          <label htmlFor={inputId} className="block text-xs font-medium text-zinc-400 mb-1.5 uppercase tracking-wider">
            {label}
          </label>
        )}
        <input
          ref={ref}
          id={inputId}
          className={`w-full rounded-xl bg-[#121216] border ${
            error ? 'border-rose-500/50 focus:border-rose-500 focus:ring-rose-500/20' : 'border-white/[0.1] focus:border-zinc-300 focus:ring-1 focus:ring-zinc-300/30'
          } px-3.5 py-2.5 text-sm text-zinc-100 placeholder-zinc-500 transition-all focus:outline-none ${className}`}
          {...props}
        />
        {error && <p className="mt-1.5 text-xs text-rose-400">{error}</p>}
        {helperText && !error && <p className="mt-1.5 text-xs text-zinc-500">{helperText}</p>}
      </div>
    );
  }
);

Input.displayName = 'Input';
