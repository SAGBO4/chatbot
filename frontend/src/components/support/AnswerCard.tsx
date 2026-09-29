'use client';

import React, { useState } from 'react';
import { QueryResponse } from '@/types';
import { useTranslation } from '@/lib/i18n/LanguageContext';
import { useToast } from '@/components/ui/Toast';
import { useTelegram } from '@/lib/telegram/TelegramContext';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import {
  FileCheck2,
  BookOpen,
  CheckCircle2,
  HelpCircle,
  ThumbsUp,
  ArrowRight,
} from 'lucide-react';

interface AnswerCardProps {
  result: QueryResponse;
  onEscalate: () => void;
}

export const AnswerCard: React.FC<AnswerCardProps> = ({ result, onEscalate }) => {
  const { t } = useTranslation();
  const { triggerHaptic } = useTelegram();
  const { toast } = useToast();
  const [resolutionStatus, setResolutionStatus] = useState<'unconfirmed' | 'resolved' | 'escalating'>('unconfirmed');

  const handleResolved = () => {
    triggerHaptic('medium');
    setResolutionStatus('resolved');
    toast({
      title: t.feedbackThanks,
      description: t.feedbackThanksSub,
      variant: 'success',
    });
  };

  const handleUnresolved = () => {
    triggerHaptic('medium');
    setResolutionStatus('escalating');
    onEscalate();
  };

  return (
    <Card elevated className="border-white/[0.09] shadow-2xl overflow-hidden bg-[#121216] backdrop-blur-2xl">
      {/* Header Info */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-5 border-b border-white/[0.08] bg-zinc-900/40">
        <div className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-white/10 text-white border border-white/15 shadow-sm">
            <FileCheck2 className="h-4 w-4" />
          </div>
          <div>
            <span className="text-sm font-semibold text-white tracking-tight">{t.technicalSolution}</span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {result.article_id && (
            <Badge variant="neutral" size="sm">
              <BookOpen className="h-3 w-3 text-zinc-300" />
              {t.kbArticle} #{result.article_id}
            </Badge>
          )}
          <Badge variant="neutral" size="sm">
            <CheckCircle2 className="h-3 w-3 text-zinc-300" />
            {t.verifiedDoc}
          </Badge>
        </div>
      </div>

      {/* Answer Body */}
      <div className="p-6">
        <div className="rounded-xl bg-black/40 border border-white/[0.08] p-5 text-xs sm:text-sm leading-relaxed text-zinc-100 whitespace-pre-line font-normal">
          {result.answer}
        </div>
      </div>

      {/* Interactive Resolution Confirmation */}
      <div className="px-6 py-4 border-t border-white/[0.08] bg-white/[0.01]">
        {resolutionStatus === 'unconfirmed' && (
          <div>
            <p className="text-xs font-medium text-zinc-300 mb-3 flex items-center gap-1.5">
              <HelpCircle className="h-3.5 w-3.5 text-zinc-400" />
              {t.resolutionQuestion}
            </p>
            <div className="flex flex-wrap items-center gap-3">
              <Button
                variant="secondary"
                size="sm"
                onClick={handleResolved}
                className="hover:border-white/40 hover:text-white"
              >
                <CheckCircle2 className="h-3.5 w-3.5 text-zinc-300 mr-1.5" />
                {t.btnResolved}
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={handleUnresolved}
                className="hover:border-white/40 hover:text-white"
              >
                <HelpCircle className="h-3.5 w-3.5 text-zinc-400 mr-1.5" />
                {t.btnEscalate}
              </Button>
            </div>
          </div>
        )}

        {resolutionStatus === 'resolved' && (
          <div className="flex items-center gap-2.5 text-zinc-200 py-1">
            <ThumbsUp className="h-4 w-4" />
            <div>
              <p className="text-xs font-semibold">{t.feedbackThanks}</p>
              <p className="text-[11px] text-zinc-400">{t.feedbackThanksSub}</p>
            </div>
          </div>
        )}

        {resolutionStatus === 'escalating' && (
          <div className="flex items-center justify-between gap-3 text-amber-400 py-1">
            <div>
              <p className="text-xs font-semibold">{t.escalatingNotice}</p>
              <p className="text-[11px] text-zinc-400">{t.escalatingNoticeSub}</p>
            </div>
            <ArrowRight className="h-4 w-4 text-amber-400" />
          </div>
        )}
      </div>
    </Card>
  );
};
