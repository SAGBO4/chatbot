import React from 'react';

type AlertType = 'info' | 'success' | 'warning' | 'error' | 'crimson';

interface AlertProps {
  type?: AlertType;
  title?: string;
  children: React.ReactNode;
  className?: string;
}

export const Alert: React.FC<AlertProps> = ({
  type = 'info',
  title,
  children,
  className = '',
}) => {
  const styles: Record<AlertType, { border: string; bg: string; text: string }> = {
    crimson: {
      border: 'border-blue-500/30',
      bg: 'bg-blue-500/10',
      text: 'text-blue-200',
    },
    info: {
      border: 'border-sky-500/30',
      bg: 'bg-sky-500/10',
      text: 'text-sky-200',
    },
    success: {
      border: 'border-emerald-500/30',
      bg: 'bg-emerald-500/10',
      text: 'text-emerald-200',
    },
    warning: {
      border: 'border-amber-500/30',
      bg: 'bg-amber-500/10',
      text: 'text-amber-200',
    },
    error: {
      border: 'border-rose-500/30',
      bg: 'bg-rose-500/10',
      text: 'text-rose-200',
    },
  };

  const current = styles[type];

  return (
    <div className={`rounded-lg border p-4 ${current.border} ${current.bg} ${className}`}>
      {title && <h4 className={`text-sm font-semibold mb-1 ${current.text}`}>{title}</h4>}
      <div className={`text-sm ${current.text} opacity-95`}>{children}</div>
    </div>
  );
};
