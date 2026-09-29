'use client';

import React, { useRef, useState, useCallback } from 'react';

interface BorderGlowProps {
  children: React.ReactNode;
  className?: string;
  glowColor?: string;
  backgroundColor?: string;
  borderRadius?: number;
  glowIntensity?: number;
}

export const BorderGlow: React.FC<BorderGlowProps> = ({
  children,
  className = '',
  glowColor = 'rgba(255, 255, 255, 0.35)',
  backgroundColor = '#0c0c0f',
  borderRadius = 16,
}) => {
  const cardRef = useRef<HTMLDivElement>(null);
  const [cursorAngle, setCursorAngle] = useState(0);
  const [isHovered, setIsHovered] = useState(false);

  const handlePointerMove = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    const card = cardRef.current;
    if (!card) return;
    const rect = card.getBoundingClientRect();
    const cx = rect.width / 2;
    const cy = rect.height / 2;
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const radians = Math.atan2(y - cy, x - cx);
    let degrees = radians * (180 / Math.PI) + 90;
    if (degrees < 0) degrees += 360;
    setCursorAngle(degrees);
  }, []);

  return (
    <div
      ref={cardRef}
      onPointerMove={handlePointerMove}
      onPointerEnter={() => setIsHovered(true)}
      onPointerLeave={() => setIsHovered(false)}
      className={`relative isolate group transition-all duration-300 ${className}`}
      style={{
        borderRadius: `${borderRadius}px`,
      }}
    >
      {/* Outer border glow following angle */}
      <div
        className="pointer-events-none absolute -inset-[1px] rounded-[inherit] transition-opacity duration-300 ease-out"
        style={{
          opacity: isHovered ? 1 : 0.25,
          background: `conic-gradient(from ${cursorAngle}deg at 50% 50%, ${glowColor} 0deg, rgba(255, 255, 255, 0.05) 60deg, transparent 120deg, transparent 240deg, rgba(255, 255, 255, 0.05) 300deg, ${glowColor} 360deg)`,
        }}
        aria-hidden="true"
      />

      {/* Surface Card Background */}
      <div
        className="relative h-full w-full rounded-[inherit] border border-white/[0.08] transition-colors duration-200"
        style={{
          backgroundColor,
        }}
      >
        {children}
      </div>
    </div>
  );
};

export default BorderGlow;
