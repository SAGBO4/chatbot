import React from 'react';
import { AlertCircle, CheckCircle2, Info, AlertTriangle, Shield } from 'lucide-react';

type AlertType = 'info' | 'success' | 'warning' | 'error' | 'security';

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
  const styles: Record<AlertType, { border: string; bg: string; text: string; icon: React.ReactNode }> = {
    info: {
      border: 'border-white/[0.12]',
      bg: 'bg-zinc-900/90',
      text: 'text-zinc-200',
      icon: <Info className="h-4 w-4 text-zinc-400 shrink-0 mt-0.5" />,
    },
    success: {
      border: 'border-emerald-500/25',
      bg: 'bg-emerald-950/20',
      text: 'text-emerald-200',
      icon: <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0 mt-0.5" />,
    },
    warning: {
      border: 'border-amber-500/25',
      bg: 'bg-amber-950/20',
      text: 'text-amber-200',
      icon: <AlertTriangle className="h-4 w-4 text-amber-400 shrink-0 mt-0.5" />,
    },
    error: {
      border: 'border-rose-500/25',
      bg: 'bg-rose-950/20',
      text: 'text-rose-200',
      icon: <AlertCircle className="h-4 w-4 text-rose-400 shrink-0 mt-0.5" />,
    },
    security: {
      border: 'border-white/[0.15]',
      bg: 'bg-zinc-900/90',
      text: 'text-zinc-200',
      icon: <Shield className="h-4 w-4 text-zinc-300 shrink-0 mt-0.5" />,
    },
  };

  const current = styles[type] || styles.info;

  return (
    <div className={`rounded-xl border p-4 ${current.border} ${current.bg} ${className} flex items-start gap-3`}>
      {current.icon}
      <div className="space-y-1 text-xs">
        {title && <h4 className={`font-semibold text-xs leading-none ${current.text}`}>{title}</h4>}
        <div className={`${current.text} leading-relaxed opacity-90 font-normal`}>{children}</div>
      </div>
    </div>
  );
};
