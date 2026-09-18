import type { Metadata, Viewport } from 'next';
import Script from 'next/script';
import './globals.css';
import { Header } from '@/components/layout/Header';
import { Footer } from '@/components/layout/Footer';
import { LanguageProvider } from '@/lib/i18n/LanguageContext';
import { TelegramProvider } from '@/lib/telegram/TelegramContext';

export const metadata: Metadata = {
  title: 'Stack Wallet Support - Centre d\'Assistance Officiel',
  description: 'Documentation officielle, base de connaissances et assistance technique pour Stack Wallet.',
  icons: {
    icon: '/stack-wallet-icon.svg',
  },
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
  viewportFit: 'cover',
  themeColor: '#0a0e17',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="fr" className="dark" suppressHydrationWarning>
      <body className="flex min-h-screen min-h-[100dvh] flex-col bg-[#0a0e17] text-slate-100 antialiased selection:bg-blue-600/30 selection:text-white overflow-x-hidden relative">
        {/* Telegram WebApp official script for seamless Mini App integration */}
        <Script
          src="https://telegram.org/js/telegram-web-app.js"
          strategy="beforeInteractive"
        />
        <TelegramProvider>
          <LanguageProvider>
            {/* Ambient soft glow at top */}
            <div className="ambient-glow" />
            
            <Header />
            <main className="flex-1 pb-20 sm:pb-12 z-10 relative">
              {children}
            </main>
            <Footer />
          </LanguageProvider>
        </TelegramProvider>
      </body>
    </html>
  );
}
