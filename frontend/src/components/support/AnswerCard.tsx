'use client';

import React, { useState } from 'react';
import { QueryResponse } from '@/types';
import { useTranslation } from '@/lib/i18n/LanguageContext';
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
  ShieldCheck,
} from 'lucide-react';

interface AnswerCardProps {
  result: QueryResponse;
  onEscalate: () => void;
}

export const AnswerCard: React.FC<AnswerCardProps> = ({ result, onEscalate }) => {
  const { t } = useTranslation();
  const [resolutionStatus, setResolutionStatus] = useState<'unconfirmed' | 'resolved' | 'escalating'>('unconfirmed');

  const handleResolved = () => {
    setResolutionStatus('resolved');
  };

  const handleUnresolved = () => {
    setResolutionStatus('escalating');
    onEscalate();
  };

  return (
    <Card elevated className="border-white/[0.1] shadow-2xl overflow-hidden">
      {/* Header Info */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-5 border-b border-white/[0.08] bg-white/[0.02]">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-white/10 text-white border border-white/15">
            <FileCheck2 className="h-4 w-4" />
          </div>
          <div>
            <span className="text-sm font-semibold text-white">{t.automatedSolution}</span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {result.article_id && (
            <Badge variant="neutral" size="sm">
              <BookOpen className="h-3 w-3 text-neutral-300" />
              {t.kbArticle} #{result.article_id}
            </Badge>
          )}
          <Badge variant="success" size="sm">
            <ShieldCheck className="h-3 w-3" />
            {t.confidenceScore}
          </Badge>
        </div>
      </div>

      {/* Answer Body */}
      <div className="p-6">
        <div className="rounded-xl bg-black/50 border border-white/[0.08] p-5 text-sm leading-relaxed text-neutral-100 whitespace-pre-line font-normal">
          {result.answer}
        </div>
      </div>

      {/* Interactive Resolution Confirmation */}
      <div className="px-6 py-4 border-t border-white/[0.08] bg-white/[0.01]">
        {resolutionStatus === 'unconfirmed' && (
          <div>
            <p className="text-xs font-medium text-neutral-400 mb-3 flex items-center gap-1.5">
              <HelpCircle className="h-3.5 w-3.5 text-neutral-300" />
              {t.resolutionQuestion}
            </p>
            <div className="flex flex-wrap items-center gap-3">
              <Button
                variant="secondary"
                size="sm"
                onClick={handleResolved}
                className="hover:border-emerald-500/50 hover:text-emerald-400"
              >
                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                {t.btnResolved}
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={handleUnresolved}
                className="hover:border-white/40 hover:text-white"
              >
                <HelpCircle className="h-3.5 w-3.5 text-neutral-300" />
                {t.btnEscalate}
              </Button>
            </div>
          </div>
        )}

        {resolutionStatus === 'resolved' && (
          <div className="flex items-center gap-2.5 text-emerald-400 py-1">
            <ThumbsUp className="h-4 w-4" />
            <div>
              <p className="text-xs font-semibold">{t.feedbackThanks}</p>
              <p className="text-[11px] text-slate-400">{t.feedbackThanksSub}</p>
            </div>
          </div>
        )}

        {resolutionStatus === 'escalating' && (
          <div className="flex items-center justify-between gap-3 text-amber-400 py-1">
            <div>
              <p className="text-xs font-semibold">{t.escalatingNotice}</p>
              <p className="text-[11px] text-slate-400">{t.escalatingNoticeSub}</p>
            </div>
            <ArrowRight className="h-4 w-4 text-amber-400" />
          </div>
        )}
      </div>
    </Card>
  );
};
