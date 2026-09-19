'use client';

import React from 'react';
import { useTranslation } from '@/lib/i18n/LanguageContext';
import { Badge, BadgeVariant } from '@/components/ui/Badge';
import { Clock, CheckCircle2, AlertCircle, XCircle } from 'lucide-react';

interface StatusBadgeProps {
  status: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status }) => {
  const { t } = useTranslation();
  const normalized = status.toUpperCase();

  let variant: BadgeVariant = 'neutral';
  let icon = <Clock className="h-3 w-3" />;
  let label = normalized;

  switch (normalized) {
    case 'OPEN':
      variant = 'info';
      icon = <AlertCircle className="h-3 w-3" />;
      label = t.statusOpen;
      break;
    case 'PENDING':
      variant = 'warning';
      icon = <Clock className="h-3 w-3" />;
      label = t.statusPending;
      break;
    case 'RESOLVED':
      variant = 'success';
      icon = <CheckCircle2 className="h-3 w-3" />;
      label = t.statusResolved;
      break;
    case 'CLOSED':
      variant = 'neutral';
      icon = <XCircle className="h-3 w-3" />;
      label = t.statusClosed;
      break;
    default:
      variant = 'neutral';
      label = status;
  }

  return (
    <Badge variant={variant} size="sm">
      {icon}
      <span>{label}</span>
    </Badge>
  );
};
