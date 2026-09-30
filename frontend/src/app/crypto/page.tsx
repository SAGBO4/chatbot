'use client';

import React, { useState, useEffect, useRef, useMemo } from 'react';
import { api } from '@/lib/api';
import { CryptoPriceResponse } from '@/types';
import { useTranslation } from '@/lib/i18n/LanguageContext';
import { useTelegram } from '@/lib/telegram/TelegramContext';
import { useToast } from '@/components/ui/Toast';
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
  Activity,
  ArrowUpDown,
} from 'lucide-react';
import Link from 'next/link';

// Asset metadata for rich display
const ASSET_NAMES: Record<string, { name: string; network: string }> = {
  btc: { name: 'Bitcoin', network: 'Bitcoin Mainnet' },
  eth: { name: 'Ethereum', network: 'Ethereum' },
  firo: { name: 'Firo', network: 'Lelantus Spark' },
  sol: { name: 'Solana', network: 'Solana SPL' },
  ltc: { name: 'Litecoin', network: 'Litecoin MWEB' },
  doge: { name: 'Dogecoin', network: 'Dogecoin' },
  xrp: { name: 'XRP Ledger', network: 'Ripple' },
};

/**
 * Generate a smooth sparkline SVG path based on seed and 24h change
 */
function generateSparkline(symbol: string, changePct: number, isPositive: boolean) {
  const pointsCount = 12;
  const width = 120;
  const height = 36;
  const seed = symbol.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0);

  const points: [number, number][] = [];
  const startY = isPositive ? height * 0.75 : height * 0.25;
  const endY = isPositive ? height * 0.2 : height * 0.8;

  for (let i = 0; i < pointsCount; i++) {
    const x = (i / (pointsCount - 1)) * width;
    // Linear progression + pseudo random wave
    const baseProgress = i / (pointsCount - 1);
    const trendY = startY + (endY - startY) * baseProgress;
    const wave = Math.sin((i + seed) * 1.5) * 6;
    const y = Math.max(4, Math.min(height - 4, trendY + wave));
    points.push([x, y]);
  }

  // Smooth bezier path
  let pathD = `M ${points[0][0]} ${points[0][1]}`;
  for (let i = 0; i < points.length - 1; i++) {
    const xMid = (points[i][0] + points[i + 1][0]) / 2;
    const yMid = (points[i][1] + points[i + 1][1]) / 2;
    pathD += ` Q ${points[i][0]} ${points[i][1]}, ${xMid} ${yMid}`;
  }
  const last = points[points.length - 1];
  pathD += ` T ${last[0]} ${last[1]}`;

  const areaD = `${pathD} L ${width} ${height} L 0 ${height} Z`;

  return { pathD, areaD };
}

export default function CryptoPage() {
  const { t, locale } = useTranslation();
  const { triggerHaptic } = useTelegram();
  const { toast } = useToast();

  const [prices, setPrices] = useState<CryptoPriceResponse[]>([]);
  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState<'market_cap' | 'price' | 'change' | 'name'>('market_cap');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadPrices = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.getCryptoPrices();
      setPrices(data);
    } catch (err: unknown) {
      const msg = (err as { message?: string })?.message || t.errCryptoLoad;
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  };

  const loadErrorMessage = useRef(t.errCryptoLoad);
  useEffect(() => {
    loadErrorMessage.current = t.errCryptoLoad;
  }, [t.errCryptoLoad]);

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
          const msg = (err as { message?: string })?.message || loadErrorMessage.current;
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

  // Filter and sort prices
  const sortedAndFiltered = useMemo(() => {
    const filtered = prices.filter((coin) => {
      const q = search.toLowerCase();
      const meta = ASSET_NAMES[coin.symbol.toLowerCase()];
      return (
        coin.symbol.toLowerCase().includes(q) ||
        (meta && meta.name.toLowerCase().includes(q))
      );
    });

    return filtered.sort((a, b) => {
      if (sortBy === 'market_cap') return b.market_cap_usd - a.market_cap_usd;
      if (sortBy === 'price') return b.price_usd - a.price_usd;
      if (sortBy === 'change') return b.change_24h_pct - a.change_24h_pct;
      if (sortBy === 'name') return a.symbol.localeCompare(b.symbol);
      return 0;
    });
  }, [prices, search, sortBy]);

  const handleRefresh = async () => {
    triggerHaptic('light');
    await loadPrices();
    toast({
      title: locale === 'fr' ? 'Cours actualisés' : 'Rates updated',
      description: locale === 'fr' ? 'Flux en direct mis à jour' : 'Live rates updated successfully',
      variant: 'success',
    });
  };

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8 lg:py-12">
      {/* Top Header */}
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
              {t.cryptoTitle}
            </h1>
            <span className="rounded-full bg-white/10 border border-white/20 px-2.5 py-0.5 text-[11px] font-medium text-white shadow-sm">
              Live Feed 24/7
            </span>
          </div>
          <p className="text-xs sm:text-sm text-zinc-400 mt-1 max-w-xl font-normal leading-relaxed">{t.cryptoSub}</p>
        </div>

        <Button variant="secondary" size="sm" onClick={handleRefresh} disabled={isLoading}>
          <RefreshCw className={`h-3.5 w-3.5 mr-1.5 ${isLoading ? 'animate-spin text-white' : ''}`} />
          <span>{t.btnRefresh}</span>
        </Button>
      </div>

      {/* Search and Filters Bar */}
      <div className="bg-[#0c0c0f] backdrop-blur-2xl border border-white/[0.08] p-4 rounded-2xl mb-8 flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4 shadow-xl">
        <div className="relative w-full md:max-w-md">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-400 pointer-events-none" />
          <input
            type="text"
            placeholder={t.cryptoSearchPlaceholder}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-xl bg-white/[0.04] backdrop-blur-md border border-white/[0.1] pl-10 pr-3 py-2 text-xs sm:text-sm text-white placeholder-zinc-500 focus:border-white/40 focus:outline-none focus:ring-1 focus:ring-white/20"
          />
        </div>

        {/* Sort Controls & Auto-refresh status */}
        <div className="flex items-center justify-between md:justify-end gap-3 flex-wrap">
          <div className="flex items-center gap-1.5 text-xs text-zinc-400">
            <ArrowUpDown className="h-3.5 w-3.5 text-zinc-400" />
            <span className="hidden sm:inline">{t.cryptoSortBy} :</span>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
              className="rounded-lg bg-white border border-white px-2.5 py-1 text-xs font-semibold text-zinc-950 focus:outline-none focus:ring-2 focus:ring-white/20 cursor-pointer shadow-sm"
            >
              <option value="market_cap" className="bg-white text-zinc-950">{t.cryptoSortMarketCap}</option>
              <option value="price" className="bg-white text-zinc-950">{t.cryptoSortPrice}</option>
              <option value="change" className="bg-white text-zinc-950">{t.cryptoSortChange}</option>
              <option value="name" className="bg-white text-zinc-950">{t.cryptoSortName}</option>
            </select>
          </div>

          <div className="flex items-center gap-1.5 text-[11px] text-zinc-400">
            <Activity className="h-3.5 w-3.5 text-zinc-400" />
            <span>{locale === 'fr' ? '60s auto' : '60s sync'}</span>
          </div>
        </div>
      </div>

      {error && <Alert type="error" className="mb-8">{error}</Alert>}

      {/* Crypto Cards Wide Grid */}
      {isLoading && prices.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-zinc-400">
          <RefreshCw className="h-6 w-6 animate-spin text-white mb-3" />
          <p className="text-xs">{t.cryptoLoading}</p>
        </div>
      ) : sortedAndFiltered.length === 0 ? (
        <Card elevated className="p-12 text-center border-white/[0.08] bg-[#0c0c0f]">
          <Coins className="h-8 w-8 mx-auto text-zinc-500 mb-3" />
          <h3 className="text-sm font-semibold text-white">{t.cryptoNoAsset}</h3>
          <p className="text-xs text-zinc-400 mt-1">{t.cryptoNoAssetHint}</p>
        </Card>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
          {sortedAndFiltered.map((coin) => {
            const isPositive = coin.change_24h_pct >= 0;
            const meta = ASSET_NAMES[coin.symbol.toLowerCase()] || {
              name: coin.symbol.toUpperCase(),
              network: 'Stack Multi-Asset',
            };
            const { pathD, areaD } = generateSparkline(coin.symbol, coin.change_24h_pct, isPositive);

            return (
              <Card
                key={coin.symbol}
                elevated
                hoverable
                className="p-5 border-white/[0.08] flex flex-col justify-between bg-[#0c0c0f] transition-all"
              >
                <div>
                  {/* Card Header: Symbol & 24h Pill */}
                  <div className="flex items-center justify-between pb-3.5 border-b border-white/[0.08]">
                    <div className="flex items-center gap-3">
                      <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-white/[0.08] border border-white/[0.15] text-white font-mono font-bold text-xs shadow-md">
                        {coin.symbol.toUpperCase().slice(0, 4)}
                      </div>
                      <div>
                        <h3 className="text-sm font-bold text-white tracking-wide">
                          {meta.name}
                        </h3>
                        <span className="text-[11px] text-zinc-400 font-normal">{coin.symbol.toUpperCase()}</span>
                      </div>
                    </div>

                    <Badge variant={isPositive ? 'success' : 'error'} size="sm">
                      {isPositive ? (
                        <TrendingUp className="h-3 w-3" />
                      ) : (
                        <TrendingDown className="h-3 w-3" />
                      )}
                      <span className="font-mono">
                        {isPositive ? '+' : ''}
                        {coin.change_24h_pct.toFixed(2)}%
                      </span>
                    </Badge>
                  </div>

                  {/* Price & Sparkline Area */}
                  <div className="pt-4 flex items-end justify-between gap-3">
                    <div>
                      <div className="text-xs text-zinc-400 font-medium">{t.cryptoPrice}</div>
                      <div className="text-2xl font-bold text-white mt-0.5 tracking-tight font-mono">
                        ${coin.price_usd.toLocaleString(undefined, {
                          minimumFractionDigits: 2,
                          maximumFractionDigits: coin.price_usd < 1 ? 6 : 2,
                        })}
                      </div>
                    </div>

                    {/* Sparkline Curve */}
                    <div className="w-[110px] h-[36px] shrink-0 overflow-hidden relative">
                      <svg viewBox="0 0 120 36" className="w-full h-full overflow-visible">
                        <defs>
                          <linearGradient id={`grad-${coin.symbol}`} x1="0" y1="0" x2="0" y2="1">
                            <stop
                              offset="0%"
                              stopColor={isPositive ? '#22c55e' : '#ef4444'}
                              stopOpacity="0.25"
                            />
                            <stop
                              offset="100%"
                              stopColor={isPositive ? '#22c55e' : '#ef4444'}
                              stopOpacity="0.0"
                            />
                          </linearGradient>
                        </defs>
                        <path d={areaD} fill={`url(#grad-${coin.symbol})`} />
                        <path
                          d={pathD}
                          fill="none"
                          stroke={isPositive ? '#22c55e' : '#ef4444'}
                          strokeWidth="2"
                          strokeLinecap="round"
                        />
                      </svg>
                    </div>
                  </div>
                </div>

                {/* Card Footer: Market Cap & Volume */}
                <div className="grid grid-cols-2 gap-3 mt-5 pt-3.5 border-t border-white/[0.08] text-xs">
                  <div>
                    <div className="text-zinc-500 flex items-center gap-1 text-[11px]">
                      <BarChart3 className="h-3 w-3 text-zinc-400" />
                      <span>{t.cryptoMarketCap}</span>
                    </div>
                    <div className="font-semibold text-zinc-200 mt-0.5 text-xs font-mono">
                      ${(coin.market_cap_usd / 1e6).toFixed(1)}M
                    </div>
                  </div>

                  <div>
                    <div className="text-zinc-500 flex items-center gap-1 text-[11px]">
                      <DollarSign className="h-3 w-3 text-zinc-400" />
                      <span>{t.cryptoVolume}</span>
                    </div>
                    <div className="font-semibold text-zinc-200 mt-0.5 text-xs font-mono">
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
