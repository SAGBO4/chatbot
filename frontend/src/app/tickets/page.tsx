'use client';

import React, { useState } from 'react';
import { TicketList } from '@/components/tickets/TicketList';
import { TicketForm } from '@/components/tickets/TicketForm';
import { Button } from '@/components/ui/Button';
import { useTranslation } from '@/lib/i18n/LanguageContext';
import { useToast } from '@/components/ui/Toast';
import {
  Ticket,
  Plus,
  ArrowLeft,
  Headphones,
  ShieldCheck,
  Send,
  Clock,
  ExternalLink,
} from 'lucide-react';
import Link from 'next/link';

export default function TicketsPage() {
  const { t, locale } = useTranslation();
  const { toast } = useToast();
  const [mobileTab, setMobileTab] = useState<'list' | 'create'>('list');

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8 lg:py-12">
      {/* Top Header & Breadcrumb */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
        <div>
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 text-xs text-zinc-400 hover:text-white mb-2.5 transition-colors"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            <span>{t.navSupport}</span>
          </Link>
          <div className="flex items-center gap-2.5 flex-wrap">
            <h1 className="text-xl sm:text-2xl lg:text-3xl font-bold tracking-tight text-white">
              {t.ticketsTitle}
            </h1>
            <span className="rounded-full bg-white/10 border border-white/20 px-2.5 py-0.5 text-[11px] font-medium text-white shadow-sm">
              Support Desk Pro
            </span>
          </div>
          <p className="text-xs sm:text-sm text-zinc-400 mt-1 max-w-xl font-normal leading-relaxed">{t.ticketsSub}</p>
        </div>

        {/* Mobile Tab Switcher (< lg) */}
        <div className="flex lg:hidden items-center gap-2 p-1 bg-white/[0.04] border border-white/[0.08] rounded-xl self-start w-full sm:w-auto">
          <Button
            variant={mobileTab === 'list' ? 'primary' : 'ghost'}
            size="sm"
            onClick={() => setMobileTab('list')}
            className="flex-1 sm:flex-none justify-center"
          >
            <Ticket className="h-3.5 w-3.5 mr-1.5" />
            {t.navTickets}
          </Button>
          <Button
            variant={mobileTab === 'create' ? 'primary' : 'ghost'}
            size="sm"
            onClick={() => setMobileTab('create')}
            className="flex-1 sm:flex-none justify-center"
          >
            <Plus className="h-3.5 w-3.5 mr-1.5" />
            {t.btnNewTicket}
          </Button>
        </div>
      </div>

      {/* Main Responsive Layout: 2-column on desktop (lg:grid), Tabbed on mobile */}
      <div className="hidden lg:grid lg:grid-cols-12 gap-8 items-start">
        {/* Left Column: New Ticket Form + Helpful Support Cards (lg:col-span-5) */}
        <div className="lg:col-span-5 space-y-6 sticky top-20">
          <TicketForm
            onSuccess={() => {
              toast({
                title: t.ticketCreatedSuccess,
                description: locale === 'fr' ? 'Consultez la liste de vos tickets à droite.' : 'Check your tickets list on the right.',
                variant: 'success',
              });
            }}
          />

          {/* Quick Help Card */}
          <div className="rounded-2xl bg-[#0c0c0f] border border-white/[0.08] p-5 space-y-4">
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-white/[0.06] text-white border border-white/[0.1]">
                <Clock className="h-4 w-4" />
              </div>
              <div>
                <h4 className="text-xs font-semibold text-white">
                  {t.kpiResponseTime}
                </h4>
                <p className="text-[11px] text-zinc-400">
                  {locale === 'fr' ? 'Généralement sous 15 à 30 minutes (24/7)' : 'Typically within 15–30 minutes (24/7)'}
                </p>
              </div>
            </div>

            <div className="pt-3 border-t border-white/[0.06] space-y-2.5 text-xs text-zinc-300">
              <div className="flex items-start gap-2">
                <ShieldCheck className="h-4 w-4 text-zinc-200 shrink-0 mt-0.5" />
                <p className="text-[11px] text-zinc-300 leading-relaxed">
                  {t.ticketSecurityWarning}
                </p>
              </div>
              <div className="flex items-start gap-2">
                <Send className="h-4 w-4 text-zinc-300 shrink-0 mt-0.5" />
                <p className="text-[11px] text-zinc-300 leading-relaxed">
                  {locale === 'fr'
                    ? 'Vous pouvez aussi poser vos questions sur notre canal Telegram officiel.'
                    : 'You can also ask questions in our official Telegram community.'}
                </p>
              </div>
            </div>

            <a
              href="https://t.me/STACK_WALLET_BOT"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center justify-between w-full p-2.5 rounded-xl bg-white/[0.04] border border-white/[0.08] hover:bg-white/[0.08] text-xs font-medium text-white transition-colors"
            >
              <span className="flex items-center gap-2">
                <Headphones className="h-3.5 w-3.5 text-zinc-300" />
                <span>{locale === 'fr' ? 'Assistance Telegram Directe' : 'Direct Telegram Support'}</span>
              </span>
              <ExternalLink className="h-3.5 w-3.5 text-zinc-500" />
            </a>
          </div>
        </div>

        {/* Right Column: Ticket List Feed (lg:col-span-7) */}
        <div className="lg:col-span-7">
          <TicketList />
        </div>
      </div>

      {/* Mobile Layout (< lg) */}
      <div className="lg:hidden">
        {mobileTab === 'list' ? (
          <TicketList />
        ) : (
          <TicketForm
            onSuccess={() => {
              setMobileTab('list');
            }}
            onCancel={() => setMobileTab('list')}
          />
        )}
      </div>
    </div>
  );
}
