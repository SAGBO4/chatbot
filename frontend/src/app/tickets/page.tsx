'use client';

import React, { useState } from 'react';
import { TicketList } from '@/components/tickets/TicketList';
import { TicketForm } from '@/components/tickets/TicketForm';
import { Button } from '@/components/ui/Button';
import { useTranslation } from '@/lib/i18n/LanguageContext';
import { Ticket, Plus, ArrowLeft } from 'lucide-react';
import Link from 'next/link';

export default function TicketsPage() {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<'list' | 'create'>('list');

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:py-12">
      {/* Top Header & Navigation */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
        <div>
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 text-xs text-neutral-400 hover:text-white mb-2 transition-colors"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            <span>{t.navSupport}</span>
          </Link>
          <div className="flex items-center gap-2">
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-white">
              {t.ticketsTitle}
            </h1>
            <span className="rounded-full bg-white/10 border border-white/20 px-2.5 py-0.5 text-[10px] font-medium text-white">
              Assistance
            </span>
          </div>
          <p className="text-xs sm:text-sm text-neutral-400 mt-1">{t.ticketsSub}</p>
        </div>

        <div className="grid grid-cols-2 sm:flex sm:items-center gap-2 w-full sm:w-auto">
          <Button
            variant={activeTab === 'list' ? 'primary' : 'secondary'}
            size="sm"
            onClick={() => setActiveTab('list')}
            className="w-full justify-center"
          >
            <Ticket className="h-3.5 w-3.5 mr-1.5" />
            {t.navTickets}
          </Button>
          <Button
            variant={activeTab === 'create' ? 'primary' : 'outline'}
            size="sm"
            onClick={() => setActiveTab('create')}
            className="w-full justify-center"
          >
            <Plus className="h-3.5 w-3.5 mr-1.5" />
            {t.btnNewTicket}
          </Button>
        </div>
      </div>

      {/* Main View Area */}
      {activeTab === 'list' ? (
        <TicketList />
      ) : (
        <div className="max-w-2xl mx-auto">
          <TicketForm
            onSuccess={() => {
              setActiveTab('list');
            }}
            onCancel={() => setActiveTab('list')}
          />
        </div>
      )}
    </div>
  );
}
