'use client';

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { api } from '@/lib/api';
import { TicketResponse } from '@/types';
import { useTranslation } from '@/lib/i18n/LanguageContext';
import { useTelegram } from '@/lib/telegram/TelegramContext';
import { useToast } from '@/components/ui/Toast';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Alert } from '@/components/ui/Alert';
import {
  Headphones,
  Send,
  CheckCircle2,
  UploadCloud,
  X,
  Maximize2,
  Trash2,
  FileImage,
  ShieldCheck,
  Copy,
  Check,
  Plus,
  KeyRound,
  Server,
  ArrowLeftRight,
  Layers,
  HelpCircle,
} from 'lucide-react';

interface TicketFormProps {
  initialQuestion?: string;
  initialAutomatedAnswer?: string;
  onSuccess?: (ticket: TicketResponse) => void;
  onCancel?: () => void;
}

interface AttachedFile {
  file: File;
  previewUrl: string;
  name: string;
  size: number;
}

export const TicketForm: React.FC<TicketFormProps> = ({
  initialQuestion = '',
  initialAutomatedAnswer = '',
  onSuccess,
  onCancel,
}) => {
  const { t, locale } = useTranslation();
  const { user: tgUser, triggerHaptic } = useTelegram();
  const { toast } = useToast();

  const [category, setCategory] = useState<string>('seed');
  const [userId, setUserId] = useState<string>(() => (tgUser?.id ? String(tgUser.id) : '10001'));
  const [userHandle, setUserHandle] = useState<string>(() =>
    tgUser?.username ? `@${tgUser.username}` : tgUser?.first_name || ''
  );
  const [question, setQuestion] = useState<string>(initialQuestion);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [createdTicket, setCreatedTicket] = useState<TicketResponse | null>(null);
  const [copiedRef, setCopiedRef] = useState(false);

  // Attachment state
  const [attachment, setAttachment] = useState<AttachedFile | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [zoomModalOpen, setZoomModalOpen] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const categories = [
    { id: 'seed', label: t.categorySeed, icon: KeyRound },
    { id: 'node', label: t.categoryNode, icon: Server },
    { id: 'swap', label: t.categorySwap, icon: ArrowLeftRight },
    { id: 'tx', label: t.categoryTx, icon: Layers },
    { id: 'other', label: t.categoryOther, icon: HelpCircle },
  ];

  // Clean up object URLs to avoid memory leaks
  useEffect(() => {
    return () => {
      if (attachment?.previewUrl.startsWith('blob:')) {
        URL.revokeObjectURL(attachment.previewUrl);
      }
    };
  }, [attachment]);

  const handleProcessFile = useCallback(
    (file: File) => {
      if (!file.type.startsWith('image/')) {
        setError(locale === 'fr' ? 'Le fichier doit être une image (PNG, JPG, WebP ou GIF).' : 'Selected file must be an image (PNG, JPG, WebP or GIF).');
        return;
      }

      if (file.size > 5 * 1024 * 1024) {
        setError(locale === 'fr' ? 'La taille de l’image ne doit pas dépasser 5 Mo.' : 'Image file size must not exceed 5 MB.');
        return;
      }

      setError(null);
      if (attachment?.previewUrl.startsWith('blob:')) {
        URL.revokeObjectURL(attachment.previewUrl);
      }

      const previewUrl = URL.createObjectURL(file);
      setAttachment({
        file,
        previewUrl,
        name: file.name,
        size: file.size,
      });
      triggerHaptic('light');
    },
    [attachment, triggerHaptic, locale]
  );

  // Support paste from clipboard (Ctrl+V / Cmd+V)
  const handlePaste = useCallback(
    (e: React.ClipboardEvent | ClipboardEvent) => {
      const items = e.clipboardData?.items;
      if (!items) return;

      for (let i = 0; i < items.length; i++) {
        const item = items[i];
        if (item.type.indexOf('image') !== -1) {
          const file = item.getAsFile();
          if (file) {
            handleProcessFile(file);
            break;
          }
        }
      }
    },
    [handleProcessFile]
  );

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleProcessFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      handleProcessFile(e.target.files[0]);
    }
  };

  const handleRemoveAttachment = () => {
    if (attachment?.previewUrl.startsWith('blob:')) {
      URL.revokeObjectURL(attachment.previewUrl);
    }
    setAttachment(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
    triggerHaptic('light');
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} o`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} Ko`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} Mo`;
  };

  const handleCopyTicketRef = (ticketId: number) => {
    navigator.clipboard?.writeText(String(ticketId));
    setCopiedRef(true);
    toast({
      title: t.ticketCopied,
      description: `Ticket #${ticketId}`,
      variant: 'success',
    });
    setTimeout(() => setCopiedRef(false), 2000);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const parsedUserId = parseInt(userId, 10);
    if (isNaN(parsedUserId) || parsedUserId <= 0) {
      setError(t.errInvalidUserId);
      return;
    }

    if (!question.trim()) {
      setError(t.errEmptyRequest);
      return;
    }

    setIsLoading(true);
    triggerHaptic('medium');

    try {
      const selectedCatObj = categories.find((c) => c.id === category);
      const catLabel = selectedCatObj ? selectedCatObj.label : 'Général';
      let finalQuestion = `[Catégorie: ${catLabel}]\n${question.trim()}`;

      // If an image is attached, upload it first
      if (attachment) {
        const formData = new FormData();
        formData.append('file', attachment.file);

        const uploadRes = await fetch('/api/attachments', {
          method: 'POST',
          body: formData,
        });

        if (!uploadRes.ok) {
          throw new Error(t.ticketAttachmentError);
        }

        const uploadData = await uploadRes.json();
        if (uploadData.url) {
          finalQuestion += `\n\n[Pièce jointe: ${uploadData.url}]`;
        }
      }

      const ticket = await api.createTicket({
        user_id: parsedUserId,
        user_handle: userHandle.trim() || undefined,
        question: finalQuestion,
        automated_answer: initialAutomatedAnswer || undefined,
      });

      triggerHaptic('heavy');
      setCreatedTicket(ticket);
      toast({
        title: t.ticketCreatedSuccess,
        description: `${t.ticketCreatedMsg} #${ticket.id}`,
        variant: 'success',
      });
      if (onSuccess) {
        onSuccess(ticket);
      }
    } catch (err: unknown) {
      const msg = (err as { message?: string })?.message || t.errTicketSave;
      setError(msg);
      toast({
        title: 'Erreur',
        description: msg,
        variant: 'error',
      });
    } finally {
      setIsLoading(false);
    }
  };

  if (createdTicket) {
    return (
      <Card elevated className="p-6 border-emerald-500/30 bg-emerald-950/20 backdrop-blur-2xl">
        <div className="flex items-start gap-4">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 shadow-lg shadow-emerald-500/10">
            <CheckCircle2 className="h-6 w-6" />
          </div>
          <div className="space-y-3 flex-1 min-w-0">
            <div className="flex items-center justify-between gap-2 flex-wrap">
              <h3 className="text-base font-semibold text-white">
                {t.ticketCreatedSuccess}
              </h3>
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono font-bold text-emerald-300 bg-emerald-500/15 px-2.5 py-1 rounded-lg border border-emerald-500/30">
                  #{createdTicket.id}
                </span>
                <button
                  type="button"
                  onClick={() => handleCopyTicketRef(createdTicket.id)}
                  className="p-1 rounded-lg bg-white/[0.06] hover:bg-white/[0.12] text-zinc-300 hover:text-white transition-colors cursor-pointer"
                  title="Copier le numéro de ticket"
                >
                  {copiedRef ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
                </button>
              </div>
            </div>

            <p className="text-xs sm:text-sm text-zinc-300 leading-relaxed font-normal">
              {t.ticketCreatedTrack}
            </p>

            {attachment && (
              <div className="mt-3 p-3 rounded-xl bg-black/40 border border-emerald-500/20 flex items-center gap-3">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={attachment.previewUrl}
                  alt={attachment.name}
                  className="h-12 w-12 rounded-lg object-cover border border-white/10"
                />
                <div className="text-xs min-w-0">
                  <div className="font-medium text-white truncate max-w-[200px]">{attachment.name}</div>
                  <div className="text-zinc-400 text-[11px]">{formatFileSize(attachment.size)}</div>
                </div>
              </div>
            )}

            <div className="pt-3 flex items-center gap-3">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => {
                  setCreatedTicket(null);
                  setQuestion('');
                  handleRemoveAttachment();
                }}
              >
                <Plus className="h-3.5 w-3.5 mr-1 text-white" />
                {t.btnNewTicket}
              </Button>
            </div>
          </div>
        </div>
      </Card>
    );
  }

  return (
    <Card elevated className="p-5 sm:p-7 shadow-2xl border-white/[0.09] bg-[#121216]" onPaste={handlePaste}>
      {/* Form Header */}
      <div className="flex items-center gap-3 mb-6 pb-4 border-b border-white/[0.08]">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white/[0.08] text-white border border-white/[0.15] shadow-sm">
          <Headphones className="h-5 w-5" />
        </div>
        <div>
          <h3 className="text-base font-semibold text-white">{t.ticketFormTitle}</h3>
          <p className="text-xs text-zinc-400 mt-0.5">{t.ticketFormSub}</p>
        </div>
      </div>

      {error && (
        <Alert type="error" className="mb-5">
          {error}
        </Alert>
      )}

      <form onSubmit={handleSubmit} className="space-y-5">
        {/* Category Picker Pills */}
        <div>
          <label className="block text-xs font-medium text-zinc-400 mb-2 uppercase tracking-wider">
            {t.ticketCategoryLabel}
          </label>
          <div className="flex flex-wrap gap-1.5">
            {categories.map((cat) => {
              const Icon = cat.icon;
              const isSelected = category === cat.id;
              return (
                <button
                  key={cat.id}
                  type="button"
                  onClick={() => {
                    triggerHaptic('light');
                    setCategory(cat.id);
                  }}
                  className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium transition-all cursor-pointer ${
                    isSelected
                      ? 'bg-white text-black font-semibold shadow-md shadow-white/10'
                      : 'bg-white/[0.03] border border-white/[0.08] text-zinc-400 hover:text-white hover:bg-white/[0.06]'
                  }`}
                >
                  <Icon className="h-3.5 w-3.5" />
                  <span>{cat.label}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Telegram ID & Contact Handle */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Input
            label={t.userIdLabel}
            type="number"
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            required
            helperText={t.ticketUserIdHelper}
          />
          <Input
            label={t.userHandleLabel}
            placeholder={t.ticketContactPlaceholder}
            value={userHandle}
            onChange={(e) => setUserHandle(e.target.value)}
            helperText={locale === 'fr' ? 'Optionnel' : 'Optional'}
          />
        </div>

        {/* Issue Description Textarea with Character Counter */}
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <label className="text-xs font-medium text-zinc-400 uppercase tracking-wider">
              {t.issueDescLabel}
            </label>
            <span className="text-[11px] font-mono text-zinc-500">
              {question.length} / 2000
            </span>
          </div>
          <textarea
            rows={4}
            maxLength={2000}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            required
            placeholder={t.ticketQuestionPlaceholder}
            className="w-full rounded-xl bg-white/[0.04] backdrop-blur-md border border-white/[0.1] px-3.5 py-2.5 text-xs sm:text-sm text-white placeholder-zinc-500 transition-colors focus:border-white/40 focus:outline-none focus:ring-1 focus:ring-white/20"
          />
        </div>

        {/* Attachment Dropzone */}
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <label className="text-xs font-medium text-zinc-400 uppercase tracking-wider">
              {t.ticketAttachmentLabel}
            </label>
            <span className="text-[11px] text-zinc-500 font-normal lowercase">png, jpg, webp (&le; 5 Mo)</span>
          </div>

          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileInputChange}
            accept="image/png,image/jpeg,image/webp,image/gif"
            className="hidden"
          />

          {!attachment ? (
            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`border-2 border-dashed rounded-xl p-4 sm:p-5 text-center cursor-pointer transition-all ${
                isDragging
                  ? 'border-white/60 bg-white/[0.08]'
                  : 'border-white/[0.12] hover:border-white/30 bg-white/[0.02] hover:bg-white/[0.04]'
              }`}
            >
              <div className="flex flex-col items-center justify-center gap-2">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white/[0.06] text-zinc-300 border border-white/[0.1]">
                  <UploadCloud className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-xs text-zinc-300 font-medium">{t.ticketAttachmentDrop}</p>
                  <p className="text-[11px] text-zinc-500 mt-0.5">{t.ticketAttachmentHint}</p>
                </div>
              </div>
            </div>
          ) : (
            <div className="rounded-xl border border-white/[0.12] bg-white/[0.03] p-3 flex items-center justify-between gap-3">
              <div className="flex items-center gap-3 min-w-0">
                <div className="relative group cursor-pointer shrink-0" onClick={() => setZoomModalOpen(true)}>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={attachment.previewUrl}
                    alt={attachment.name}
                    className="h-14 w-14 rounded-lg object-cover border border-white/[0.15] group-hover:opacity-80 transition-opacity"
                  />
                  <div className="absolute inset-0 flex items-center justify-center bg-black/40 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity">
                    <Maximize2 className="h-4 w-4 text-white" />
                  </div>
                </div>

                <div className="min-w-0">
                  <div className="flex items-center gap-1.5">
                    <FileImage className="h-3.5 w-3.5 text-zinc-400 shrink-0" />
                    <p className="text-xs font-medium text-white truncate max-w-[200px] sm:max-w-xs">
                      {attachment.name}
                    </p>
                  </div>
                  <p className="text-[11px] text-zinc-400 mt-0.5">
                    {formatFileSize(attachment.size)} • {t.ticketAttachedImage}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                <button
                  type="button"
                  onClick={() => setZoomModalOpen(true)}
                  className="p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-white/[0.08] transition-colors cursor-pointer"
                  title={t.ticketAttachmentView}
                >
                  <Maximize2 className="h-4 w-4" />
                </button>
                <button
                  type="button"
                  onClick={handleRemoveAttachment}
                  className="p-1.5 rounded-lg text-zinc-400 hover:text-rose-400 hover:bg-rose-500/10 transition-colors cursor-pointer"
                  title={t.ticketAttachmentRemove}
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Security Notice */}
        <div className="rounded-xl bg-white/[0.02] border border-white/[0.06] p-3.5 flex items-start gap-2.5 text-xs text-zinc-400">
          <ShieldCheck className="h-4 w-4 text-zinc-300 shrink-0 mt-0.5" />
          <p className="text-[11px] leading-relaxed">
            {t.ticketSecurityWarning}
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center justify-end gap-3 pt-3 border-t border-white/[0.08]">
          {onCancel && (
            <Button type="button" variant="ghost" size="sm" onClick={onCancel} disabled={isLoading}>
              {t.btnCancel}
            </Button>
          )}
          <Button type="submit" variant="primary" size="sm" isLoading={isLoading} className="shadow-lg shadow-white/10">
            <Send className="h-3.5 w-3.5 mr-1.5" />
            {t.btnSubmitTicket}
          </Button>
        </div>
      </form>

      {/* Lightbox Zoom Modal */}
      {zoomModalOpen && attachment && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/90 backdrop-blur-md"
          onClick={() => setZoomModalOpen(false)}
        >
          <div className="relative max-w-4xl max-h-[90vh] flex flex-col items-center" onClick={(e) => e.stopPropagation()}>
            <button
              onClick={() => setZoomModalOpen(false)}
              className="absolute -top-10 right-0 p-1.5 rounded-lg text-zinc-400 hover:text-white transition-colors cursor-pointer"
            >
              <X className="h-6 w-6" />
            </button>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={attachment.previewUrl}
              alt={attachment.name}
              className="max-h-[80vh] max-w-full rounded-xl object-contain border border-white/[0.15] shadow-2xl"
            />
            <p className="text-xs text-zinc-300 mt-2">{attachment.name} ({formatFileSize(attachment.size)})</p>
          </div>
        </div>
      )}
    </Card>
  );
};
