'use client';

import React from 'react';
import Image from 'next/image';

interface StackLogoProps {
  className?: string;
  height?: number;
  size?: number;
  showSupportBadge?: boolean;
  showText?: boolean;
}

export const StackLogo: React.FC<StackLogoProps> = ({
  className = '',
  height,
  size = 30,
  showSupportBadge = true,
  showText = true,
}) => {
  const actualHeight = height || size;
  // Original aspect ratio: 818 x 171 (~4.78)
  const width = showText ? Math.round(actualHeight * (818 / 171)) : actualHeight;
  const shouldShowBadge = showSupportBadge && showText;

  return (
    <div className={`inline-flex items-center gap-2.5 select-none ${className}`}>
      <Image
        src={showText ? '/stack-logo-white.png' : '/stack-icon-white.png'}
        alt="Stack Wallet"
        width={width}
        height={actualHeight}
        className="h-auto object-contain transition-opacity duration-200 hover:opacity-90 drop-shadow-sm"
        priority
      />
      {shouldShowBadge && (
        <span className="hidden sm:inline-flex items-center rounded-md bg-blue-500/10 border border-blue-500/20 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-blue-400">
          Support
        </span>
      )}
    </div>
  );
};
