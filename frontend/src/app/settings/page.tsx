'use client';

import React, { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import { WarningListResponse } from '@/types';
import { useTranslation } from '@/lib/i18n/LanguageContext';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Alert } from '@/components/ui/Alert';
import { Badge } from '@/components/ui/Badge';
import {
  Settings,
  ShieldCheck,
  AlertTriangle,
  RefreshCw,
  Search,
  CheckCircle2,
  XCircle,
  Plus,
  Trash2,
  Save,
  ArrowLeft,
} from 'lucide-react';
import Link from 'next/link';

export default function SettingsPage() {
  const { t } = useTranslation();

  // Settings state
  const [communityGroupId, setCommunityGroupId] = useState('');
  const [botLanguage, setBotLanguage] = useState('');
  const [isSavingSettings, setIsSavingSettings] = useState(false);
  const [settingsSuccess, setSettingsSuccess] = useState(false);
  const [settingsError, setSettingsError] = useState<string | null>(null);

  // Whitelist state
  const [whitelist, setWhitelist] = useState<{ user_id: number; added_by: string; created_at: string }[]>([]);
  const [newWhitelistId, setNewWhitelistId] = useState('');
  const [isAddingWhitelist, setIsAddingWhitelist] = useState(false);
  const [checkUserId, setCheckUserId] = useState('');
  const [checkResult, setCheckResult] = useState<{ is_whitelisted: boolean; user_id: number } | null>(null);
  const [whitelistError, setWhitelistError] = useState<string | null>(null);

  // Moderation state
  const [warnUserId, setWarnUserId] = useState('');
  const [warnGroupId, setWarnGroupId] = useState('-1001234567890');
  const [isQueryingWarns, setIsQueryingWarns] = useState(false);
  const [warningData, setWarningData] = useState<WarningListResponse | null>(null);
  const [warnError, setWarnError] = useState<string | null>(null);

  const refreshData = async () => {
    try {
      const [grpRes, langRes, wlRes] = await Promise.allSettled([
        api.getAdminSetting('community_group_id'),
        api.getAdminSetting('language'),
        api.listWhitelist(),
      ]);

      if (grpRes.status === 'fulfilled') {
        setCommunityGroupId(grpRes.value.value || '');
      }
      if (langRes.status === 'fulfilled') {
        setBotLanguage(langRes.value.value || 'fr');
      }
      if (wlRes.status === 'fulfilled') {
        setWhitelist(wlRes.value.entries || []);
      }
    } catch {
      // ignore
    }
  };

  useEffect(() => {
    let ignore = false;
    const init = async () => {
      try {
        const [grpRes, langRes, wlRes] = await Promise.allSettled([
          api.getAdminSetting('community_group_id'),
          api.getAdminSetting('language'),
          api.listWhitelist(),
        ]);

        if (!ignore) {
          if (grpRes.status === 'fulfilled') {
            setCommunityGroupId(grpRes.value.value || '');
          }
          if (langRes.status === 'fulfilled') {
            setBotLanguage(langRes.value.value || 'fr');
          }
          if (wlRes.status === 'fulfilled') {
            setWhitelist(wlRes.value.entries || []);
          }
        }
      } catch {
        // ignore
      }
    };
    init();
    return () => {
      ignore = true;
    };
  }, []);

  const handleSaveSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSavingSettings(true);
    setSettingsError(null);
    setSettingsSuccess(false);

    try {
      await Promise.all([
        api.setAdminSetting('community_group_id', communityGroupId.trim()),
        api.setAdminSetting('language', botLanguage.trim() || 'fr'),
      ]);
      setSettingsSuccess(true);
      setTimeout(() => setSettingsSuccess(false), 3000);
    } catch (err: unknown) {
      const msg = (err as { message?: string })?.message || 'Erreur lors de l’enregistrement des paramètres.';
      setSettingsError(msg);
    } finally {
      setIsSavingSettings(false);
    }
  };

  const handleAddWhitelist = async (e: React.FormEvent) => {
    e.preventDefault();
    const parsedId = parseInt(newWhitelistId.trim(), 10);
    if (isNaN(parsedId) || parsedId <= 0) return;

    setIsAddingWhitelist(true);
    setWhitelistError(null);
    try {
      await api.addWhitelist(parsedId);
      setNewWhitelistId('');
      refreshData();
    } catch (err: unknown) {
      const msg = (err as { message?: string })?.message || 'Erreur lors de l’ajout dans la whitelist.';
      setWhitelistError(msg);
    } finally {
      setIsAddingWhitelist(false);
    }
  };

  const handleRemoveWhitelist = async (userId: number) => {
    try {
      await api.removeWhitelist(userId);
      setWhitelist((prev) => prev.filter((item) => item.user_id !== userId));
    } catch (err: unknown) {
      const msg = (err as { message?: string })?.message || 'Erreur lors de la suppression.';
      setWhitelistError(msg);
    }
  };

  const handleCheckWhitelist = async (e: React.FormEvent) => {
    e.preventDefault();
    const parsedId = parseInt(checkUserId.trim(), 10);
    if (isNaN(parsedId) || parsedId <= 0) return;

    setCheckResult(null);
    try {
      const res = await api.checkWhitelist(parsedId);
      setCheckResult(res);
    } catch (err: unknown) {
      const msg = (err as { message?: string })?.message || 'Erreur lors de la vérification.';
      setWhitelistError(msg);
    }
  };

  const handleQueryWarnings = async (e: React.FormEvent) => {
    e.preventDefault();
    const parsedUserId = parseInt(warnUserId.trim(), 10);
    const parsedGroupId = parseInt(warnGroupId.trim(), 10);
    if (isNaN(parsedUserId)) return;

    setIsQueryingWarns(true);
    setWarnError(null);
    setWarningData(null);
    try {
      const res = await api.getWarnings(parsedUserId, isNaN(parsedGroupId) ? -1001234567890 : parsedGroupId);
      setWarningData(res);
    } catch (err: unknown) {
      const msg = (err as { message?: string })?.message || 'Erreur lors de la recherche des avertissements.';
      setWarnError(msg);
    } finally {
      setIsQueryingWarns(false);
    }
  };

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:py-12">
      {/* Header */}
      <div className="mb-8">
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 text-xs text-neutral-400 hover:text-white mb-2 transition-colors"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          <span>{t.navSupport}</span>
        </Link>
        <div className="flex items-center gap-2">
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-white">
            {t.settingsTitle}
          </h1>
          <span className="rounded-full bg-white/10 border border-white/20 px-2.5 py-0.5 text-[10px] font-medium text-white">
            Administration
          </span>
        </div>
        <p className="text-xs sm:text-sm text-neutral-400 mt-1">{t.settingsSub}</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left: Settings & Whitelist */}
        <div className="space-y-6">
          {/* Settings Card */}
          <Card elevated className="p-5 border-white/[0.08]">
            <div className="flex items-center justify-between pb-3 border-b border-white/[0.08] mb-4">
              <div className="flex items-center gap-2.5">
                <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-white/[0.08] text-white border border-white/[0.15]">
                  <Settings className="h-4 w-4" />
                </div>
                <h3 className="text-sm font-semibold text-white">{t.groupConfigCard}</h3>
              </div>
              <Button variant="outline" size="sm" onClick={refreshData}>
                <RefreshCw className="h-3.5 w-3.5 text-white" />
              </Button>
            </div>

            {settingsError && <Alert type="error" className="mb-4">{settingsError}</Alert>}
            {settingsSuccess && <Alert type="success" className="mb-4">Paramètres enregistrés avec succès.</Alert>}

            <form onSubmit={handleSaveSettings} className="space-y-3.5">
              <Input
                label={t.currentGroupId}
                value={communityGroupId}
                onChange={(e) => setCommunityGroupId(e.target.value)}
                placeholder="ex: -1001234567890"
                helperText="ID Telegram du groupe communautaire surveillé"
              />

              <Input
                label={t.activeLang}
                value={botLanguage}
                onChange={(e) => setBotLanguage(e.target.value)}
                placeholder="fr ou en"
                helperText="Code de langue par défaut du bot (fr / en)"
              />

              <div className="flex justify-end pt-1">
                <Button type="submit" variant="primary" size="sm" isLoading={isSavingSettings}>
                  <Save className="h-3.5 w-3.5 mr-1.5" />
                  Sauvegarder
                </Button>
              </div>
            </form>
          </Card>

          {/* Whitelist Card */}
          <Card elevated className="p-5 border-white/[0.08]">
            <div className="flex items-center gap-2.5 pb-3 border-b border-white/[0.08] mb-4">
              <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-white/[0.08] text-white border border-white/[0.15]">
                <ShieldCheck className="h-4 w-4" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-white">Whitelist Administrateurs</h3>
                <p className="text-[11px] text-neutral-400">Gestion des privilèges de configuration du bot</p>
              </div>
            </div>

            {whitelistError && <Alert type="error" className="mb-4">{whitelistError}</Alert>}

            {/* Check user */}
            <form onSubmit={handleCheckWhitelist} className="flex items-center gap-2 mb-4">
              <div className="flex-1 min-w-0">
                <Input
                  type="number"
                  value={checkUserId}
                  onChange={(e) => setCheckUserId(e.target.value)}
                  placeholder="Vérifier un ID Telegram..."
                  required
                />
              </div>
              <Button type="submit" variant="secondary" size="sm" className="shrink-0">
                <Search className="h-3.5 w-3.5 mr-1 text-white" />
                {t.btnCheckWhitelist}
              </Button>
            </form>

            {checkResult && (
              <div
                className={`p-2.5 rounded-xl border flex items-center gap-2 text-xs font-medium mb-4 ${
                  checkResult.is_whitelisted
                    ? 'bg-emerald-950/20 border-emerald-500/30 text-emerald-300'
                    : 'bg-rose-950/20 border-rose-500/30 text-rose-300'
                }`}
              >
                {checkResult.is_whitelisted ? <CheckCircle2 className="h-4 w-4" /> : <XCircle className="h-4 w-4" />}
                <span>
                  {checkResult.is_whitelisted ? t.whitelistedSuccess : t.whitelistedDenied}
                </span>
              </div>
            )}

            {/* Add user form */}
            <form onSubmit={handleAddWhitelist} className="flex items-center gap-2 mb-4">
              <div className="flex-1 min-w-0">
                <Input
                  type="number"
                  value={newWhitelistId}
                  onChange={(e) => setNewWhitelistId(e.target.value)}
                  placeholder="Nouvel ID Telegram..."
                  required
                />
              </div>
              <Button type="submit" variant="primary" size="sm" isLoading={isAddingWhitelist} className="shrink-0">
                <Plus className="h-3.5 w-3.5 mr-1" />
                Ajouter
              </Button>
            </form>

            {/* Whitelist table */}
            <div className="space-y-1.5 mt-3 max-h-48 overflow-y-auto">
              {whitelist.length === 0 ? (
                <p className="text-xs text-neutral-500 italic text-center py-2">Aucun admin dans la whitelist.</p>
              ) : (
                whitelist.map((item) => (
                  <div
                    key={item.user_id}
                    className="flex items-center justify-between p-2.5 rounded-xl bg-white/[0.04] border border-white/[0.08] text-xs"
                  >
                    <div>
                      <span className="font-mono font-semibold text-white">ID: {item.user_id}</span>
                      <span className="text-[10px] text-neutral-400 ml-2">ajouté par {item.added_by}</span>
                    </div>
                    <button
                      onClick={() => handleRemoveWhitelist(item.user_id)}
                      className="text-neutral-400 hover:text-rose-400 p-1 cursor-pointer transition-colors"
                      title="Supprimer"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ))
              )}
            </div>
          </Card>
        </div>

        {/* Right: Moderation Warnings Audit */}
        <div>
          <Card elevated className="p-5 border-white/[0.08]">
            <div className="flex items-center gap-2.5 pb-3 border-b border-white/[0.08] mb-4">
              <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-white/[0.08] text-white border border-white/[0.15]">
                <AlertTriangle className="h-4 w-4 text-amber-400" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-white">{t.moderationCardTitle}</h3>
                <p className="text-[11px] text-neutral-400">{t.moderationCardDesc}</p>
              </div>
            </div>

            <form onSubmit={handleQueryWarnings} className="space-y-3 mb-4">
              <Input
                type="number"
                value={warnUserId}
                onChange={(e) => setWarnUserId(e.target.value)}
                label="User ID Telegram *"
                placeholder="ex: 10001"
                required
              />
              <Input
                value={warnGroupId}
                onChange={(e) => setWarnGroupId(e.target.value)}
                label="Group ID *"
                placeholder="ex: -1001234567890"
                required
              />
              <div className="flex justify-end">
                <Button type="submit" variant="secondary" size="sm" isLoading={isQueryingWarns}>
                  <Search className="h-3.5 w-3.5 mr-1 text-white" />
                  {t.btnQueryWarnings}
                </Button>
              </div>
            </form>

            {warnError && <Alert type="error">{warnError}</Alert>}

            {warningData && (
              <div className="space-y-3 pt-2">
                <div className="p-3.5 rounded-xl bg-white/[0.04] border border-white/[0.08] flex items-center justify-between">
                  <span className="text-xs text-neutral-400 font-medium">{t.warningsTotal}</span>
                  <Badge variant={warningData.count > 0 ? 'warning' : 'success'} size="sm">
                    {warningData.count} avertissement(s)
                  </Badge>
                </div>

                {warningData.warnings.length === 0 ? (
                  <p className="text-xs text-neutral-500 italic text-center py-3">
                    Aucun avertissement enregistré pour cet utilisateur dans ce groupe.
                  </p>
                ) : (
                  <div className="space-y-2">
                    {warningData.warnings.map((w) => (
                      <div
                        key={w.id}
                        className="p-3 rounded-xl bg-white/[0.04] border border-white/[0.08] text-xs space-y-1"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-semibold text-white">Avertissement #{w.id}</span>
                          <span className="text-[10px] text-neutral-400">
                            {new Date(w.created_at).toLocaleDateString()}
                          </span>
                        </div>
                        <p className="text-neutral-200">{w.reason || 'Aucune raison spécifiée'}</p>
                        <div className="text-[10px] text-neutral-400">Émis par : {w.warned_by}</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
