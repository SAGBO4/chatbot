'use client';

import React, { useState, useEffect, useRef } from 'react';
import { api } from '@/lib/api';
import { TicketResponse } from '@/types';
import { useTranslation } from '@/lib/i18n/LanguageContext';
import { useTelegram } from '@/lib/telegram/TelegramContext';
import { useToast } from '@/components/ui/Toast';
import { StatusBadge } from './StatusBadge';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Alert } from '@/components/ui/Alert';
import { Dialog, DialogContent, DialogHeader, DialogFooter } from '@/components/ui/Dialog';
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
  Maximize2,
  FileImage,
  Filter,
  Copy,
  ChevronRight,
} from 'lucide-react';

interface ParsedQuestion {
  category: string | null;
  text: string;
  attachmentUrl: string | null;
}

function parseTicketContent(rawQuestion: string): ParsedQuestion {
  if (!rawQuestion) return { category: null, text: '', attachmentUrl: null };

  let category: string | null = null;
  let text = rawQuestion;
  let attachmentUrl: string | null = null;

  // Extract category if present
  const catMatch = text.match(/\[Catégorie:\s*([^\]]+)\]/i);
  if (catMatch) {
    category = catMatch[1].trim();
    text = text.replace(catMatch[0], '').trim();
  }

  // Extract attachment
  const match = text.match(/\[(?:Pièce jointe|Attachment|Capture):\s*(\S+)\]/i);
  if (match) {
    attachmentUrl = match[1];
    text = text.replace(match[0], '').trim();
  } else {
    const mdMatch = text.match(/!\[.*?\]\((https?:\/\/[^\s\)]+|\/uploads\/[^\s\)]+)\)/i);
    if (mdMatch) {
      attachmentUrl = mdMatch[1];
      text = text.replace(mdMatch[0], '').trim();
    }
  }

  return { category, text, attachmentUrl };
}

export const TicketList: React.FC = () => {
  const { t, locale } = useTranslation();
  const { user, isAdmin, triggerHaptic } = useTelegram();
  const { toast } = useToast();

  const [tickets, setTickets] = useState<TicketResponse[]>([]);
  const [userIdFilter, setUserIdFilter] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'OPEN' | 'RESOLVED'>('ALL');
  const [textSearch, setTextSearch] = useState('');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Ticket Detail Drawer / Modal
  const [detailTicket, setDetailTicket] = useState<TicketResponse | null>(null);

  // Attachment lightbox
  const [previewImage, setPreviewImage] = useState<{ url: string; ticketId: number } | null>(null);

  // Resolve Modal state (Admin only)
  const [resolveTarget, setResolveTarget] = useState<TicketResponse | null>(null);
  const [solutionText, setSolutionText] = useState('');
  const [agentName, setAgentName] = useState('Support Agent');
  const [addToKb, setAddToKb] = useState(true);
  const [isResolving, setIsResolving] = useState(false);
  const [resolveError, setResolveError] = useState<string | null>(null);

  const fetchTickets = async (userId?: number) => {
    setIsLoading(true);
    setError(null);
    try {
      const targetUserId = isAdmin ? userId : user?.id || undefined;
      const data = await api.getTickets(targetUserId);
      setTickets(data);
    } catch (err: unknown) {
      const msg = (err as { message?: string })?.message || t.errTicketsLoad;
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  };

  const loadErrorMessage = useRef(t.errTicketsLoad);
  useEffect(() => {
    loadErrorMessage.current = t.errTicketsLoad;
  }, [t.errTicketsLoad]);

  useEffect(() => {
    let ignore = false;
    const loadInitialTickets = async () => {
      try {
        const targetUserId = isAdmin ? undefined : user?.id || undefined;
        const data = await api.getTickets(targetUserId);
        if (!ignore) {
          setTickets(data);
          setIsLoading(false);
        }
      } catch (err: unknown) {
        if (!ignore) {
          const msg = (err as { message?: string })?.message || loadErrorMessage.current;
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
    setTextSearch('');
    setStatusFilter('ALL');
    fetchTickets();
  };

  const handleCopyTicketId = (ticketId: number, e?: React.MouseEvent) => {
    e?.stopPropagation();
    navigator.clipboard?.writeText(String(ticketId));
    triggerHaptic('light');
    toast({
      title: t.ticketCopied,
      description: `Ticket #${ticketId}`,
      variant: 'success',
    });
  };

  const handleOpenResolve = (ticket: TicketResponse, e?: React.MouseEvent) => {
    e?.stopPropagation();
    setResolveTarget(ticket);
    setSolutionText('');
    setResolveError(null);
  };

  const handleConfirmResolve = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!resolveTarget || !solutionText.trim()) return;

    setIsResolving(true);
    setResolveError(null);
    try {
      const resolved = await api.resolveTicket(resolveTarget.id, {
        solution: solutionText.trim(),
        resolved_by: agentName.trim() || 'Agent',
        resolution_channel: 'WEB_PORTAL',
        add_to_knowledge_base: addToKb,
      });

      setTickets((prev) =>
        prev.map((t) =>
          t.id === resolved.id
            ? {
                ...t,
                status: 'RESOLVED',
                solution: resolved.solution,
                resolved_by: resolved.resolved_by,
              }
            : t
        )
      );

      if (detailTicket && detailTicket.id === resolved.id) {
        setDetailTicket({
          ...detailTicket,
          status: 'RESOLVED',
          solution: resolved.solution,
          resolved_by: resolved.resolved_by,
        });
      }

      toast({
        title: locale === 'fr' ? 'Ticket résolu' : 'Ticket resolved',
        description: `Ticket #${resolved.id} clôturé avec succès`,
        variant: 'success',
      });
      setResolveTarget(null);
    } catch (err: unknown) {
      const msg = (err as { message?: string })?.message || t.errTicketResolve;
      setResolveError(msg);
    } finally {
      setIsResolving(false);
    }
  };

  // Filtered tickets
  const filteredTickets = tickets.filter((t) => {
    if (statusFilter === 'OPEN' && (t.status === 'RESOLVED' || t.status === 'CLOSED')) return false;
    if (statusFilter === 'RESOLVED' && t.status !== 'RESOLVED' && t.status !== 'CLOSED') return false;

    if (textSearch.trim()) {
      const q = textSearch.toLowerCase();
      const matchQ = t.question.toLowerCase().includes(q);
      const matchSol = (t.solution || '').toLowerCase().includes(q);
      const matchHandle = (t.user_handle || '').toLowerCase().includes(q);
      const matchId = String(t.id).includes(q) || String(t.user_id).includes(q);
      if (!matchQ && !matchSol && !matchHandle && !matchId) return false;
    }

    return true;
  });

  const countOpen = tickets.filter((t) => t.status !== 'RESOLVED' && t.status !== 'CLOSED').length;
  const countResolved = tickets.filter((t) => t.status === 'RESOLVED' || t.status === 'CLOSED').length;

  return (
    <div className="space-y-5">
      {/* Filters & Control Strip */}
      <div className="bg-[#0c0c0f] backdrop-blur-2xl border border-white/[0.08] p-4 rounded-2xl flex flex-col gap-4 shadow-xl">
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
          {/* Status Tabs */}
          <div className="flex items-center gap-1.5 p-1 bg-white/[0.04] border border-white/[0.08] rounded-xl self-start">
            <button
              type="button"
              onClick={() => {
                triggerHaptic('light');
                setStatusFilter('ALL');
              }}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all cursor-pointer ${
                statusFilter === 'ALL'
                  ? 'bg-white text-black font-semibold shadow-sm'
                  : 'text-zinc-400 hover:text-white'
              }`}
            >
              {t.tabAll} ({tickets.length})
            </button>
            <button
              type="button"
              onClick={() => {
                triggerHaptic('light');
                setStatusFilter('OPEN');
              }}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all cursor-pointer ${
                statusFilter === 'OPEN'
                  ? 'bg-white text-black font-semibold shadow-sm'
                  : 'text-zinc-400 hover:text-white'
              }`}
            >
              {t.tabOpen} ({countOpen})
            </button>
            <button
              type="button"
              onClick={() => {
                triggerHaptic('light');
                setStatusFilter('RESOLVED');
              }}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all cursor-pointer ${
                statusFilter === 'RESOLVED'
                  ? 'bg-white text-black font-semibold shadow-sm'
                  : 'text-zinc-400 hover:text-white'
              }`}
            >
              {t.tabResolved} ({countResolved})
            </button>
          </div>

          {/* Action buttons */}
          <div className="flex items-center gap-2 justify-end">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => {
                const parsedId =
                  isAdmin && userIdFilter.trim()
                    ? parseInt(userIdFilter.trim(), 10)
                    : isAdmin
                    ? undefined
                    : user?.id;
                fetchTickets(parsedId);
              }}
              isLoading={isLoading}
            >
              <RefreshCw className="h-3.5 w-3.5 mr-1" />
              {t.btnRefresh}
            </Button>
          </div>
        </div>

        {/* Search input bar */}
        <div className="flex flex-col sm:flex-row items-center gap-2">
          <div className="relative flex-1 w-full">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-400 pointer-events-none" />
            <input
              type="text"
              placeholder={locale === 'fr' ? 'Rechercher par mot-clé, ticket #, catégorie...' : 'Search by keyword, ticket #, category...'}
              value={textSearch}
              onChange={(e) => setTextSearch(e.target.value)}
              className="w-full rounded-xl bg-white/[0.04] backdrop-blur-md border border-white/[0.1] pl-10 pr-3 py-2 text-xs text-white placeholder-zinc-500 focus:border-white/40 focus:outline-none focus:ring-1 focus:ring-white/20"
            />
          </div>

          {isAdmin && (
            <form onSubmit={handleSearch} className="flex items-center gap-2 w-full sm:w-auto">
              <input
                type="text"
                placeholder={t.filterPlaceholder}
                value={userIdFilter}
                onChange={(e) => setUserIdFilter(e.target.value)}
                className="w-full sm:w-44 rounded-xl bg-white/[0.04] backdrop-blur-md border border-white/[0.1] px-3 py-2 text-xs text-white placeholder-zinc-500 focus:border-white/40 focus:outline-none focus:ring-1 focus:ring-white/20"
              />
              <Button type="submit" variant="secondary" size="sm">
                <Filter className="h-3.5 w-3.5 mr-1" />
                {t.btnFilter}
              </Button>
            </form>
          )}

          {(textSearch || userIdFilter) && (
            <Button type="button" variant="ghost" size="sm" onClick={handleReset}>
              {t.btnClear}
            </Button>
          )}
        </div>
      </div>

      {/* Error Banner */}
      {error && <Alert type="error">{error}</Alert>}

      {/* Tickets Feed */}
      {isLoading ? (
        <div className="flex flex-col items-center justify-center py-16 text-zinc-400">
          <RefreshCw className="h-6 w-6 animate-spin text-white mb-3" />
          <p className="text-xs">{t.searchSearching}</p>
        </div>
      ) : filteredTickets.length === 0 ? (
        <Card elevated className="p-12 text-center border-white/[0.08] bg-[#0c0c0f]">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-white/[0.06] text-white mb-3 border border-white/[0.12]">
            <Ticket className="h-6 w-6 text-zinc-300" />
          </div>
          <h3 className="text-sm font-semibold text-white">{t.noTicketsTitle}</h3>
          <p className="text-xs text-zinc-400 max-w-sm mx-auto mt-1 mb-4">{t.noTicketsDesc}</p>
        </Card>
      ) : (
        <div className="space-y-4">
          {filteredTickets.map((ticket) => {
            const { category, text, attachmentUrl } = parseTicketContent(ticket.question);

            return (
              <Card
                key={ticket.id}
                elevated
                hoverable
                onClick={() => setDetailTicket(ticket)}
                className="p-5 sm:p-6 border-white/[0.08] bg-[#0c0c0f] cursor-pointer transition-all"
              >
                {/* Ticket Card Header */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3.5 border-b border-white/[0.08]">
                  <div className="flex items-center gap-2.5 flex-wrap">
                    <button
                      type="button"
                      onClick={(e) => handleCopyTicketId(ticket.id, e)}
                      className="text-xs font-mono font-semibold text-white bg-white/10 hover:bg-white/20 px-2.5 py-1 rounded-lg border border-white/20 shadow-sm flex items-center gap-1.5 transition-colors cursor-pointer"
                      title="Copier le numéro"
                    >
                      <span>#{ticket.id}</span>
                      <Copy className="h-3 w-3 text-zinc-400" />
                    </button>

                    {category && (
                      <span className="text-[11px] font-medium text-zinc-300 bg-white/[0.05] border border-white/[0.08] px-2.5 py-0.5 rounded-md">
                        {category}
                      </span>
                    )}

                    <span className="text-xs text-zinc-400 flex items-center gap-1.5">
                      <User className="h-3.5 w-3.5 text-zinc-500" />
                      <span>ID {ticket.user_id}</span>
                    </span>
                    {ticket.user_handle && (
                      <span className="text-xs text-zinc-400">({ticket.user_handle})</span>
                    )}
                  </div>

                  <div className="flex items-center gap-3">
                    <div className="flex items-center gap-1.5 text-xs text-zinc-400">
                      <Calendar className="h-3.5 w-3.5 text-zinc-500" />
                      <span>{new Date(ticket.created_at).toLocaleDateString()}</span>
                    </div>
                    <StatusBadge status={ticket.status} />
                  </div>
                </div>

                {/* Ticket Message Body Preview */}
                <div className="mt-4">
                  <div className="flex items-start gap-3">
                    <MessageSquare className="h-4 w-4 text-zinc-400 shrink-0 mt-0.5" />
                    <p className="text-xs sm:text-sm text-zinc-200 leading-relaxed font-normal line-clamp-2">
                      {text}
                    </p>
                  </div>
                </div>

                {/* Attached Screenshot Preview if present */}
                {attachmentUrl && (
                  <div className="mt-4 pt-3 border-t border-white/[0.06] flex items-center gap-3">
                    <div
                      onClick={(e) => {
                        e.stopPropagation();
                        setPreviewImage({ url: attachmentUrl, ticketId: ticket.id });
                      }}
                      className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-white/[0.04] border border-white/[0.08] hover:border-white/20 transition-colors cursor-pointer text-xs text-zinc-300"
                    >
                      <FileImage className="h-3.5 w-3.5 text-zinc-400" />
                      <span>{t.ticketAttachedImage}</span>
                      <Maximize2 className="h-3 w-3 text-zinc-500 ml-1" />
                    </div>
                  </div>
                )}

                {/* Solution Box if resolved */}
                {ticket.solution && (
                  <div className="mt-4 rounded-xl bg-emerald-950/20 border border-emerald-500/25 p-4">
                    <div className="flex items-start gap-3">
                      <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0 mt-0.5" />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-xs font-semibold text-emerald-400 uppercase tracking-wider">
                            {t.agentSolutionHeader}
                          </span>
                          {ticket.resolved_by && (
                            <span className="text-[11px] text-zinc-400">
                              ({t.resolvedByLabel} {ticket.resolved_by})
                            </span>
                          )}
                        </div>
                        <p className="text-xs sm:text-sm text-emerald-100/90 leading-relaxed whitespace-pre-line line-clamp-2">
                          {ticket.solution}
                        </p>
                      </div>
                    </div>
                  </div>
                )}

                {/* Card Footer: View Details & Actions */}
                <div className="mt-4 pt-3 border-t border-white/[0.06] flex items-center justify-between text-xs text-zinc-400">
                  <div className="flex items-center gap-1.5 text-zinc-400 hover:text-white transition-colors">
                    <span>{t.ticketDetails}</span>
                    <ChevronRight className="h-3.5 w-3.5" />
                  </div>

                  {isAdmin && ticket.status !== 'RESOLVED' && ticket.status !== 'CLOSED' && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={(e) => handleOpenResolve(ticket, e)}
                    >
                      <Check className="h-3.5 w-3.5 mr-1 text-emerald-400" />
                      {t.btnResolveAction}
                    </Button>
                  )}
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {/* Full Ticket Detail Modal */}
      {detailTicket && (
        <Dialog open={Boolean(detailTicket)} onOpenChange={(open) => !open && setDetailTicket(null)}>
          <DialogContent onClose={() => setDetailTicket(null)} className="max-w-2xl bg-[#0a0e17]">
            <DialogHeader>
              <div className="flex items-center justify-between gap-3 pb-3 border-b border-white/[0.08]">
                <div className="flex items-center gap-2.5">
                  <span className="text-sm font-mono font-bold text-white bg-white/10 px-3 py-1 rounded-lg border border-white/20">
                    Ticket #{detailTicket.id}
                  </span>
                  <StatusBadge status={detailTicket.status} />
                </div>
                <button
                  type="button"
                  onClick={() => handleCopyTicketId(detailTicket.id)}
                  className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-white/[0.04] border border-white/[0.1] text-xs text-zinc-300 hover:text-white transition-colors"
                >
                  <Copy className="h-3 w-3" />
                  <span>{locale === 'fr' ? 'Copier réf.' : 'Copy ref.'}</span>
                </button>
              </div>

              <div className="flex items-center gap-4 text-xs text-zinc-400 pt-2">
                <span className="flex items-center gap-1.5">
                  <User className="h-3.5 w-3.5 text-zinc-500" />
                  <span>ID: {detailTicket.user_id}</span>
                  {detailTicket.user_handle && ` (${detailTicket.user_handle})`}
                </span>
                <span className="flex items-center gap-1.5">
                  <Calendar className="h-3.5 w-3.5 text-zinc-500" />
                  <span>{new Date(detailTicket.created_at).toLocaleString()}</span>
                </span>
              </div>
            </DialogHeader>

            {/* Modal Body */}
            <div className="space-y-5 pt-2">
              {/* Category pill if any */}
              {parseTicketContent(detailTicket.question).category && (
                <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-white/[0.04] border border-white/[0.08] text-xs text-zinc-300">
                  <span className="text-zinc-500">Catégorie :</span>
                  <span className="font-semibold text-white">
                    {parseTicketContent(detailTicket.question).category}
                  </span>
                </div>
              )}

              {/* Message */}
              <div>
                <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-2">
                  {locale === 'fr' ? 'Description de la demande' : 'Issue Description'}
                </h4>
                <div className="rounded-xl bg-white/[0.03] border border-white/[0.08] p-4 text-xs sm:text-sm text-zinc-100 leading-relaxed whitespace-pre-line font-normal">
                  {parseTicketContent(detailTicket.question).text}
                </div>
              </div>

              {/* Attachment */}
              {parseTicketContent(detailTicket.question).attachmentUrl && (
                <div>
                  <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-2">
                    {t.ticketAttachedImage}
                  </h4>
                  <div
                    onClick={() =>
                      setPreviewImage({
                        url: parseTicketContent(detailTicket.question).attachmentUrl!,
                        ticketId: detailTicket.id,
                      })
                    }
                    className="relative inline-block rounded-xl overflow-hidden border border-white/[0.15] bg-black/40 cursor-pointer max-w-sm group"
                  >
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={parseTicketContent(detailTicket.question).attachmentUrl!}
                      alt="Capture jointe"
                      className="max-h-48 w-auto object-cover group-hover:opacity-90 transition-opacity"
                    />
                    <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity">
                      <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-black/80 border border-white/20 text-xs font-medium text-white shadow-lg">
                        <Maximize2 className="h-3.5 w-3.5" />
                        <span>{t.ticketAttachmentView}</span>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Solution */}
              {detailTicket.solution && (
                <div className="rounded-xl bg-emerald-950/25 border border-emerald-500/30 p-4">
                  <div className="flex items-start gap-3">
                    <CheckCircle2 className="h-5 w-5 text-emerald-400 shrink-0 mt-0.5" />
                    <div>
                      <div className="flex items-center gap-2 mb-1.5">
                        <h4 className="text-xs font-semibold text-emerald-400 uppercase tracking-wider">
                          {t.agentSolutionHeader}
                        </h4>
                        {detailTicket.resolved_by && (
                          <span className="text-[11px] text-zinc-400">
                            ({t.resolvedByLabel} {detailTicket.resolved_by})
                          </span>
                        )}
                      </div>
                      <div className="text-xs sm:text-sm text-emerald-100/90 leading-relaxed whitespace-pre-line">
                        {detailTicket.solution}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>

            <DialogFooter>
              {isAdmin && detailTicket.status !== 'RESOLVED' && detailTicket.status !== 'CLOSED' && (
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => {
                    handleOpenResolve(detailTicket);
                  }}
                >
                  <Check className="h-3.5 w-3.5 mr-1" />
                  {t.btnResolveAction}
                </Button>
              )}
              <Button variant="secondary" size="sm" onClick={() => setDetailTicket(null)}>
                {locale === 'fr' ? 'Fermer' : 'Close'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}

      {/* Image Lightbox Modal */}
      {previewImage && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/90 backdrop-blur-md"
          onClick={() => setPreviewImage(null)}
        >
          <div
            className="relative max-w-4xl max-h-[90vh] flex flex-col items-center"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              onClick={() => setPreviewImage(null)}
              className="absolute -top-10 right-0 p-1.5 rounded-lg text-zinc-400 hover:text-white transition-colors cursor-pointer"
              title="Fermer"
            >
              <X className="h-6 w-6" />
            </button>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={previewImage.url}
              alt={`Capture ticket #${previewImage.ticketId}`}
              className="max-h-[80vh] max-w-full rounded-xl object-contain border border-white/[0.15] shadow-2xl"
            />
            <div className="mt-3 flex items-center justify-between w-full text-xs text-zinc-400">
              <span>Ticket #{previewImage.ticketId} • {t.ticketAttachedImage}</span>
              <a
                href={previewImage.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-white hover:underline ml-4"
              >
                Ouvrir en taille réelle
              </a>
            </div>
          </div>
        </div>
      )}

      {/* Resolve Modal (Admin only) */}
      {isAdmin && resolveTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-3.5 sm:p-4 bg-black/85 backdrop-blur-md">
          <div className="w-full max-w-lg max-h-[90vh] overflow-y-auto rounded-2xl bg-[#0a0e17] border border-white/[0.12] p-5 sm:p-6 shadow-2xl relative">
            <button
              onClick={() => setResolveTarget(null)}
              className="absolute right-4 top-4 text-zinc-400 hover:text-white cursor-pointer"
            >
              <X className="h-5 w-5" />
            </button>

            <h3 className="text-base font-semibold text-white mb-1 flex items-center gap-2">
              <Check className="h-4 w-4 text-emerald-400" />
              {t.resolveTitle} #{resolveTarget.id}
            </h3>
            <p className="text-xs text-zinc-400 mb-4">{t.resolveSubtitle}</p>

            <div className="rounded-xl bg-white/[0.04] border border-white/[0.08] p-3 mb-4 text-xs text-zinc-200">
              <span className="font-semibold text-zinc-400 block mb-1">
                {t.userQuestionLabel}
              </span>
              {parseTicketContent(resolveTarget.question).text}
            </div>

            {resolveError && (
              <Alert type="error" className="mb-4">
                {resolveError}
              </Alert>
            )}

            <form onSubmit={handleConfirmResolve} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1">
                  {t.agentNameLabel}
                </label>
                <input
                  type="text"
                  required
                  value={agentName}
                  onChange={(e) => setAgentName(e.target.value)}
                  className="w-full rounded-xl bg-white/[0.04] border border-white/[0.1] px-3 py-2 text-xs text-white placeholder-zinc-500 focus:border-white/40 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1">
                  {t.solutionLabel}
                </label>
                <textarea
                  rows={4}
                  required
                  value={solutionText}
                  onChange={(e) => setSolutionText(e.target.value)}
                  placeholder={t.solutionPlaceholder}
                  className="w-full rounded-xl bg-white/[0.04] border border-white/[0.1] px-3 py-2 text-xs text-white placeholder-zinc-500 focus:border-white/40 focus:outline-none"
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
                <label htmlFor="addToKb" className="text-xs text-zinc-300 cursor-pointer">
                  Indexer cette réponse dans la base de connaissances pour tous les utilisateurs
                </label>
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-white/[0.08]">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => setResolveTarget(null)}
                  disabled={isResolving}
                >
                  Annuler
                </Button>
                <Button type="submit" variant="primary" size="sm" isLoading={isResolving}>
                  {t.btnConfirmResolution}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
