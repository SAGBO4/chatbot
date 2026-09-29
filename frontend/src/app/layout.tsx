import type { Metadata, Viewport } from 'next';
import Script from 'next/script';
import './globals.css';
import { Header } from '@/components/layout/Header';
import { Footer } from '@/components/layout/Footer';
import { LanguageProvider } from '@/lib/i18n/LanguageContext';
import { TelegramProvider } from '@/lib/telegram/TelegramContext';
import { ToastProvider } from '@/components/ui/Toast';

export const metadata: Metadata = {
  title: 'Stack Wallet Support — Centre Technique & Base de Connaissances',
  description: 'Centre d’assistance officiel, fiches techniques vérifiées et gestion des tickets pour Stack Wallet.',
  icons: {
    icon: '/stack-icon-white.png',
  },
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
  viewportFit: 'cover',
  themeColor: '#050507',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="fr" className="dark" suppressHydrationWarning>
      <body className="flex min-h-screen min-h-[100dvh] flex-col bg-[#050507] text-zinc-100 antialiased selection:bg-white/20 selection:text-white overflow-x-hidden relative">
        {/* Telegram WebApp script for seamless Mini App integration */}
        <Script
          src="https://telegram.org/js/telegram-web-app.js"
          strategy="beforeInteractive"
        />
        <TelegramProvider>
          <LanguageProvider>
            <ToastProvider>
              {/* Stack Wallet monochrome ambient light */}
              <div
                className="pointer-events-none fixed -top-36 left-1/2 -translate-x-1/2 w-[800px] h-[400px] bg-gradient-to-b from-white/[0.05] via-white/[0.01] to-transparent blur-3xl rounded-full z-0"
                aria-hidden="true"
              />

              {/* Subtle architectural background texture */}
              <div
                className="pointer-events-none fixed inset-0 z-0 bg-grid-dots opacity-50 [mask-image:radial-gradient(ellipse_60%_50%_at_50%_0%,#000_70%,transparent_100%)]"
                aria-hidden="true"
              />

              <Header />
              <main className="flex-1 pb-8 md:pb-12 z-10 relative">
                {children}
              </main>
              <Footer />
            </ToastProvider>
          </LanguageProvider>
        </TelegramProvider>
      </body>
    </html>
  );
}
