'use client';

import React, { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import { CryptoPriceResponse } from '@/types';
import { useTranslation } from '@/lib/i18n/LanguageContext';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Alert } from '@/components/ui/Alert';
import {
  TrendingUp,
  TrendingDown,
  RefreshCw,
  Coins,
  Search,
  DollarSign,
  BarChart3,
  ArrowLeft,
} from 'lucide-react';
import Link from 'next/link';

export default function CryptoPage() {
  const { t } = useTranslation();
  const [prices, setPrices] = useState<CryptoPriceResponse[]>([]);
  const [search, setSearch] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadPrices = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.getCryptoPrices();
      setPrices(data);
    } catch (err: unknown) {
      const msg = (err as { message?: string })?.message || 'Erreur lors de la récupération des cours crypto.';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    let ignore = false;
    const initPrices = async () => {
      try {
        const data = await api.getCryptoPrices();
        if (!ignore) {
          setPrices(data);
          setIsLoading(false);
        }
      } catch (err: unknown) {
        if (!ignore) {
          const msg = (err as { message?: string })?.message || 'Erreur lors de la récupération des cours crypto.';
          setError(msg);
          setIsLoading(false);
        }
      }
    };

    initPrices();
    const interval = setInterval(initPrices, 60000);
    return () => {
      ignore = true;
      clearInterval(interval);
    };
  }, []);

  const filteredPrices = prices.filter((coin) =>
    coin.symbol.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:py-12">
      {/* Top Header */}
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
              {t.cryptoTitle}
            </h1>
            <span className="rounded-full bg-white/10 border border-white/20 px-2.5 py-0.5 text-[10px] font-medium text-white">
              Stack Multicoin
            </span>
          </div>
          <p className="text-xs sm:text-sm text-neutral-400 mt-1">{t.cryptoSub}</p>
        </div>

        <Button
          variant="secondary"
          size="sm"
          onClick={loadPrices}
          disabled={isLoading}
        >
          <RefreshCw className={`h-3.5 w-3.5 mr-1.5 ${isLoading ? 'animate-spin text-white' : ''}`} />
          <span>{t.btnRefresh}</span>
        </Button>
      </div>

      {/* Search and Filters */}
      <div className="bg-white/[0.03] backdrop-blur-2xl border border-white/[0.08] p-4 rounded-2xl mb-6">
        <div className="relative max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-neutral-400 pointer-events-none" />
          <input
            type="text"
            placeholder="Rechercher un actif (ex: BTC, ETH, FIRO, SOL)..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-xl bg-white/[0.04] backdrop-blur-md border border-white/[0.1] pl-9 pr-3 py-2 text-xs text-white placeholder-neutral-500 focus:border-white/40 focus:outline-none focus:ring-1 focus:ring-white/20"
          />
        </div>
      </div>

      {error && (
        <Alert type="error" className="mb-6">
          {error}
        </Alert>
      )}

      {/* Crypto Cards Grid */}
      {isLoading && prices.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-neutral-400">
          <RefreshCw className="h-6 w-6 animate-spin text-white mb-3" />
          <p className="text-xs">Chargement des cours crypto en direct...</p>
        </div>
      ) : filteredPrices.length === 0 ? (
        <Card elevated className="p-12 text-center border-white/[0.08]">
          <Coins className="h-8 w-8 mx-auto text-neutral-500 mb-3" />
          <h3 className="text-sm font-semibold text-white">Aucun actif trouvé</h3>
          <p className="text-xs text-neutral-400 mt-1">
            Vérifiez l&apos;orthographe du symbole recherché.
          </p>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredPrices.map((coin) => {
            const isPositive = coin.change_24h_pct >= 0;
            return (
              <Card
                key={coin.symbol}
                elevated
                hoverable
                className="p-5 border-white/[0.08]"
              >
                <div className="flex items-center justify-between pb-3 border-b border-white/[0.08]">
                  <div className="flex items-center gap-2.5">
                    <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-white/[0.08] border border-white/[0.15] text-white font-mono font-bold text-xs">
                      {coin.symbol.slice(0, 3)}
                    </div>
                    <div>
                      <h3 className="text-sm font-bold text-white tracking-wide">
                        {coin.symbol}
                      </h3>
                      <span className="text-[11px] text-neutral-400">Actif Supporté</span>
                    </div>
                  </div>

                  <Badge variant={isPositive ? 'success' : 'error'} size="sm">
                    {isPositive ? (
                      <TrendingUp className="h-3 w-3" />
                    ) : (
                      <TrendingDown className="h-3 w-3" />
                    )}
                    <span>
                      {isPositive ? '+' : ''}
                      {coin.change_24h_pct.toFixed(2)}%
                    </span>
                  </Badge>
                </div>

                <div className="pt-3.5">
                  <div className="text-xs text-neutral-400 font-medium">{t.cryptoPrice}</div>
                  <div className="text-xl sm:text-2xl font-bold text-white mt-0.5">
                    ${coin.price_usd.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 })}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3 mt-4 pt-3 border-t border-white/[0.08] text-xs">
                  <div>
                    <div className="text-neutral-500 flex items-center gap-1">
                      <BarChart3 className="h-3 w-3 text-neutral-400" />
                      <span>{t.cryptoMarketCap}</span>
                    </div>
                    <div className="font-medium text-neutral-200 mt-0.5">
                      ${(coin.market_cap_usd / 1e6).toFixed(1)}M
                    </div>
                  </div>

                  <div>
                    <div className="text-neutral-500 flex items-center gap-1">
                      <DollarSign className="h-3 w-3 text-neutral-400" />
                      <span>{t.cryptoVolume}</span>
                    </div>
                    <div className="font-medium text-neutral-200 mt-0.5">
                      ${(coin.volume_24h_usd / 1e6).toFixed(1)}M
                    </div>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
