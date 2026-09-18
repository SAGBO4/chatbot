'use client';

import React, { useState } from 'react';
import { api } from '@/lib/api';
import { TicketResponse } from '@/types';
import { useTranslation } from '@/lib/i18n/LanguageContext';
import { useTelegram } from '@/lib/telegram/TelegramContext';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Alert } from '@/components/ui/Alert';
import { Headphones, Send, CheckCircle2 } from 'lucide-react';

interface TicketFormProps {
  initialQuestion?: string;
  initialAutomatedAnswer?: string;
  onSuccess?: (ticket: TicketResponse) => void;
  onCancel?: () => void;
}

export const TicketForm: React.FC<TicketFormProps> = ({
  initialQuestion = '',
  initialAutomatedAnswer = '',
  onSuccess,
  onCancel,
}) => {
  const { t } = useTranslation();
  const { user: tgUser, triggerHaptic } = useTelegram();

  const [userId, setUserId] = useState<string>(() => tgUser?.id ? String(tgUser.id) : '10001');
  const [userHandle, setUserHandle] = useState<string>(() => 
    tgUser?.username ? `@${tgUser.username}` : (tgUser?.first_name || '')
  );
  const [question, setQuestion] = useState<string>(initialQuestion);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [createdTicket, setCreatedTicket] = useState<TicketResponse | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const parsedUserId = parseInt(userId, 10);
    if (isNaN(parsedUserId) || parsedUserId <= 0) {
      setError('Identifiant utilisateur numérique invalide (ex: Telegram ID).');
      return;
    }

    if (!question.trim()) {
      setError('Veuillez renseigner le contenu de votre demande.');
      return;
    }

    setIsLoading(true);
    triggerHaptic('medium');
    try {
      const ticket = await api.createTicket({
        user_id: parsedUserId,
        user_handle: userHandle.trim() || undefined,
        question: question.trim(),
        automated_answer: initialAutomatedAnswer || undefined,
      });
      triggerHaptic('heavy');
      setCreatedTicket(ticket);
      if (onSuccess) {
        onSuccess(ticket);
      }
    } catch (err: unknown) {
      const msg = (err as { message?: string })?.message || 'Erreur lors de l’enregistrement du ticket';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  };

  if (createdTicket) {
    return (
      <Card elevated className="p-5 sm:p-6 border-emerald-500/30 bg-emerald-950/20 backdrop-blur-xl">
        <div className="flex items-start gap-3.5">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-emerald-500/20 text-emerald-400">
            <CheckCircle2 className="h-5 w-5" />
          </div>
          <div className="space-y-1.5">
            <h3 className="text-sm sm:text-base font-semibold text-white">
              {t.ticketCreatedSuccess} (#{createdTicket.id})
            </h3>
            <p className="text-xs sm:text-sm text-slate-300">
              {t.ticketCreatedTrack}
            </p>
            <div className="pt-2 flex items-center gap-3">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => {
                  setCreatedTicket(null);
                  setQuestion('');
                }}
              >
                {t.btnNewTicket}
              </Button>
            </div>
          </div>
        </div>
      </Card>
    );
  }

  return (
    <Card elevated className="p-5 sm:p-6 shadow-2xl">
      <div className="flex items-center gap-3 mb-5 pb-4 border-b border-white/[0.08]">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-white/[0.08] text-white border border-white/[0.15] shadow-sm">
          <Headphones className="h-4 w-4" />
        </div>
        <div>
          <h3 className="text-sm sm:text-base font-semibold text-white">{t.ticketFormTitle}</h3>
          <p className="text-xs text-neutral-400">{t.ticketFormSub}</p>
        </div>
      </div>

      {error && (
        <Alert type="error" className="mb-4">
          {error}
        </Alert>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2">
          <Input
            label={t.userIdLabel}
            type="number"
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            required
            helperText="Telegram User ID (numérique)"
          />
          <Input
            label={t.userHandleLabel}
            placeholder="@pseudo_telegram ou contact@exemple.com"
            value={userHandle}
            onChange={(e) => setUserHandle(e.target.value)}
            helperText="Optionnel"
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-neutral-400 mb-1.5 uppercase tracking-wider">
            {t.issueDescLabel}
          </label>
          <textarea
            rows={4}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            required
            placeholder="Détaillez votre question, le modèle de portefeuille, le nœud utilisé ou le comportement inattendu..."
            className="w-full rounded-xl bg-white/[0.04] backdrop-blur-md border border-white/[0.1] px-3.5 py-2.5 text-xs sm:text-sm text-white placeholder-neutral-500 transition-colors focus:border-white/40 focus:outline-none focus:ring-1 focus:ring-white/20"
          />
        </div>

        <div className="flex items-center justify-end gap-3 pt-2">
          {onCancel && (
            <Button type="button" variant="ghost" onClick={onCancel} disabled={isLoading}>
              {t.btnCancel}
            </Button>
          )}
          <Button type="submit" variant="primary" isLoading={isLoading}>
            <Send className="h-3.5 w-3.5 mr-1.5" />
            {t.btnSubmitTicket}
          </Button>
        </div>
      </form>
    </Card>
  );
};
