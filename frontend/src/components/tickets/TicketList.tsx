'use client';

import React, { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import { TicketResponse } from '@/types';
import { useTranslation } from '@/lib/i18n/LanguageContext';
import { StatusBadge } from './StatusBadge';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Alert } from '@/components/ui/Alert';
import {
  RefreshCw,
  Search,
  Ticket,
  Calendar,
  MessageSquare,
  CheckCircle2,
  X,
  Check,
  User,
} from 'lucide-react';
import { useTelegram } from '@/lib/telegram/TelegramContext';

export const TicketList: React.FC = () => {
  const { t, locale } = useTranslation();
  const { user, isAdmin } = useTelegram();
  const [tickets, setTickets] = useState<TicketResponse[]>([]);
  const [userIdFilter, setUserIdFilter] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Resolve Modal state
  const [selectedTicket, setSelectedTicket] = useState<TicketResponse | null>(null);
  const [solutionText, setSolutionText] = useState('');
  const [agentName, setAgentName] = useState('Support Agent');
  const [addToKb, setAddToKb] = useState(true);
  const [isResolving, setIsResolving] = useState(false);
  const [resolveError, setResolveError] = useState<string | null>(null);

  const fetchTickets = async (userId?: number) => {
    setIsLoading(true);
    setError(null);
    try {
      const targetUserId = isAdmin ? userId : (user?.id || undefined);
      const data = await api.getTickets(targetUserId);
      setTickets(data);
    } catch (err: unknown) {
      const msg = (err as { message?: string })?.message || 'Erreur lors du chargement des tickets';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    let ignore = false;
    const loadInitialTickets = async () => {
      try {
        const targetUserId = isAdmin ? undefined : (user?.id || undefined);
        const data = await api.getTickets(targetUserId);
        if (!ignore) {
          setTickets(data);
          setIsLoading(false);
        }
      } catch (err: unknown) {
        if (!ignore) {
          const msg = (err as { message?: string })?.message || 'Erreur lors du chargement des tickets';
          setError(msg);
          setIsLoading(false);
        }
      }
    };
    loadInitialTickets();
    return () => {
      ignore = true;
    };
  }, [user, isAdmin]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    const parsedId = userIdFilter.trim() ? parseInt(userIdFilter.trim(), 10) : undefined;
    fetchTickets(parsedId);
  };

  const handleReset = () => {
    setUserIdFilter('');
    fetchTickets();
  };

  const handleOpenResolve = (ticket: TicketResponse) => {
    setSelectedTicket(ticket);
    setSolutionText('');
    setResolveError(null);
  };

  const handleConfirmResolve = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedTicket || !solutionText.trim()) return;

    setIsResolving(true);
    setResolveError(null);
    try {
      const resolved = await api.resolveTicket(selectedTicket.id, {
        solution: solutionText.trim(),
        resolved_by: agentName.trim() || 'Agent',
        resolution_channel: 'WEB_PORTAL',
        add_to_knowledge_base: addToKb,
      });

      // Update local state with resolved ticket
      setTickets((prev) =>
        prev.map((t) => (t.id === resolved.id ? { ...t, status: 'RESOLVED', solution: resolved.solution, resolved_by: resolved.resolved_by } : t))
      );
      setSelectedTicket(null);
    } catch (err: unknown) {
      const msg = (err as { message?: string })?.message || 'Erreur lors de la résolution du ticket';
      setResolveError(msg);
    } finally {
      setIsResolving(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Filter and Action Header */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4 bg-white/[0.03] backdrop-blur-2xl border border-white/[0.08] p-4 rounded-2xl">
        {isAdmin ? (
          <form onSubmit={handleSearch} className="flex flex-1 items-center gap-2 max-w-md">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-neutral-400 pointer-events-none" />
              <input
                type="text"
                placeholder={t.filterPlaceholder}
                value={userIdFilter}
                onChange={(e) => setUserIdFilter(e.target.value)}
                className="w-full rounded-xl bg-white/[0.04] backdrop-blur-md border border-white/[0.1] pl-9 pr-3 py-2 text-xs text-white placeholder-neutral-500 focus:border-white/40 focus:outline-none focus:ring-1 focus:ring-white/20"
              />
            </div>
            <Button type="submit" variant="primary" size="sm">
              {t.btnFilter}
            </Button>
            {userIdFilter && (
              <Button type="button" variant="ghost" size="sm" onClick={handleReset}>
                {t.btnClear}
              </Button>
            )}
          </form>
        ) : (
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-white">
              {locale === 'fr' ? 'Mes demandes d’assistance' : 'My Support Requests'}
            </span>
            {user && (
              <span className="text-[10px] text-neutral-400 bg-white/[0.06] border border-white/10 px-2 py-0.5 rounded-full">
                ID {user.id}
              </span>
            )}
          </div>
        )}

        <div className="flex items-center gap-2 justify-end">
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => {
              const parsedId = isAdmin && userIdFilter.trim() ? parseInt(userIdFilter.trim(), 10) : (isAdmin ? undefined : user?.id);
              fetchTickets(parsedId);
            }}
            isLoading={isLoading}
          >
            <RefreshCw className="h-3.5 w-3.5 mr-1" />
            {t.btnRefresh}
          </Button>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <Alert type="error">
          {error}
        </Alert>
      )}

      {/* Tickets Content */}
      {isLoading ? (
        <div className="flex flex-col items-center justify-center py-16 text-neutral-400">
          <RefreshCw className="h-6 w-6 animate-spin text-white mb-3" />
          <p className="text-xs">{t.searchSearching}</p>
        </div>
      ) : tickets.length === 0 ? (
        <Card elevated className="p-12 text-center border-white/[0.08]">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-white/[0.06] text-white mb-3 border border-white/[0.12]">
            <Ticket className="h-6 w-6 text-white" />
          </div>
          <h3 className="text-sm font-semibold text-white">{t.noTicketsTitle}</h3>
          <p className="text-xs text-neutral-400 max-w-sm mx-auto mt-1 mb-4">
            {t.noTicketsDesc}
          </p>
        </Card>
      ) : (
        <div className="space-y-3.5">
          {tickets.map((ticket) => (
            <Card key={ticket.id} elevated hoverable className="p-5 border-white/[0.08]">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-white/[0.08]">
                <div className="flex items-center gap-2.5">
                  <span className="text-xs font-mono font-medium text-white bg-white/10 px-2.5 py-0.5 rounded-lg border border-white/20">
                    Ticket #{ticket.id}
                  </span>
                  <span className="text-xs text-neutral-400 flex items-center gap-1">
                    <User className="h-3 w-3 text-neutral-400" />
                    ID {ticket.user_id}
                  </span>
                  {ticket.user_handle && (
                    <span className="text-xs text-neutral-500">({ticket.user_handle})</span>
                  )}
                </div>
                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-1 text-xs text-neutral-400">
                    <Calendar className="h-3 w-3" />
                    <span>{new Date(ticket.created_at).toLocaleDateString()}</span>
                  </div>
                  <StatusBadge status={ticket.status} />
                </div>
              </div>

              {/* Question */}
              <div className="mt-3.5">
                <div className="flex items-start gap-2.5">
                  <MessageSquare className="h-4 w-4 text-white shrink-0 mt-0.5" />
                  <p className="text-xs sm:text-sm text-neutral-200 leading-relaxed font-normal">
                    {ticket.question}
                  </p>
                </div>
              </div>

              {/* Solution if already resolved */}
              {ticket.solution && (
                <div className="mt-3.5 rounded-xl bg-emerald-950/20 border border-emerald-500/25 p-3.5">
                  <div className="flex items-start gap-2.5">
                    <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0 mt-0.5" />
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-[11px] font-semibold text-emerald-400 uppercase tracking-wider">
                          {t.agentSolutionHeader}
                        </span>
                        {ticket.resolved_by && (
                          <span className="text-[11px] text-neutral-400">({t.resolvedByLabel} {ticket.resolved_by})</span>
                        )}
                      </div>
                      <p className="text-xs text-emerald-100/90 leading-relaxed whitespace-pre-line">
                        {ticket.solution}
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* Agent Resolve Action button for Open/Pending tickets (Admin only) */}
              {isAdmin && ticket.status !== 'RESOLVED' && ticket.status !== 'CLOSED' && (
                <div className="mt-3.5 pt-3 border-t border-white/[0.08] flex justify-end">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleOpenResolve(ticket)}
                  >
                    <Check className="h-3.5 w-3.5 mr-1 text-white" />
                    {t.btnResolveAction}
                  </Button>
                </div>
              )}
            </Card>
          ))}
        </div>
      )}

      {/* Modal: Resolve Ticket as Support Agent (Admin only) */}
      {isAdmin && selectedTicket && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-3.5 sm:p-4 bg-black/80 backdrop-blur-md">
          <div className="w-full max-w-lg max-h-[90vh] overflow-y-auto rounded-2xl bg-black/95 border border-white/[0.12] p-5 sm:p-6 shadow-2xl relative">
            <button
              onClick={() => setSelectedTicket(null)}
              className="absolute right-4 top-4 text-neutral-400 hover:text-white"
            >
              <X className="h-5 w-5" />
            </button>

            <h3 className="text-base font-semibold text-white mb-1 flex items-center gap-2">
              <Check className="h-4 w-4 text-white" />
              Résolution du Ticket #{selectedTicket.id}
            </h3>
            <p className="text-xs text-neutral-400 mb-4">
              Transmettez la procédure de solution à l&apos;utilisateur.
            </p>

            <div className="rounded-xl bg-white/[0.04] border border-white/[0.08] p-3 mb-4 text-xs text-neutral-200">
              <span className="font-semibold text-neutral-400 block mb-1">Question de l&apos;utilisateur :</span>
              {selectedTicket.question}
            </div>

            {resolveError && (
              <Alert type="error" className="mb-4">
                {resolveError}
              </Alert>
            )}

            <form onSubmit={handleConfirmResolve} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-neutral-400 mb-1">
                  Nom ou Identifiant de l&apos;Agent *
                </label>
                <input
                  type="text"
                  required
                  value={agentName}
                  onChange={(e) => setAgentName(e.target.value)}
                  className="w-full rounded-xl bg-white/[0.04] border border-white/[0.1] px-3 py-2 text-xs text-white placeholder-neutral-500 focus:border-white/40 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-neutral-400 mb-1">
                  Procédure / Solution validée *
                </label>
                <textarea
                  rows={4}
                  required
                  value={solutionText}
                  onChange={(e) => setSolutionText(e.target.value)}
                  placeholder="Décrivez précisément les étapes de résolution..."
                  className="w-full rounded-xl bg-white/[0.04] border border-white/[0.1] px-3 py-2 text-xs text-white placeholder-neutral-500 focus:border-white/40 focus:outline-none"
                />
              </div>

              <div className="flex items-center gap-2 pt-1">
                <input
                  type="checkbox"
                  id="addToKb"
                  checked={addToKb}
                  onChange={(e) => setAddToKb(e.target.checked)}
                  className="rounded border-white/20 bg-white/[0.05] text-white focus:ring-white/20"
                />
                <label htmlFor="addToKb" className="text-xs text-neutral-300 cursor-pointer">
                  Indexer cette solution dans la base de connaissances pour tous les utilisateurs
                </label>
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-white/[0.08]">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => setSelectedTicket(null)}
                  disabled={isResolving}
                >
                  Annuler
                </Button>
                <Button
                  type="submit"
                  variant="primary"
                  size="sm"
                  isLoading={isResolving}
                >
                  Valider la résolution
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
