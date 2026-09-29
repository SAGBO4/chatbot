'use client';

import React, { useEffect, useRef, useState, useCallback } from 'react';

interface PixelCardProps {
  children: React.ReactNode;
  className?: string;
  gap?: number;
  speed?: number;
  colors?: string[];
  backgroundColor?: string;
}

export const PixelCard: React.FC<PixelCardProps> = ({
  children,
  className = '',
  gap = 6,
  speed = 25,
  colors = ['#ffffff', '#e4e4e7', '#a1a1aa', '#71717a'],
  backgroundColor = '#0c0c0f',
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [isHovered, setIsHovered] = useState(false);
  const animFrameRef = useRef<number | null>(null);

  const drawPixels = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (!isHovered) return;

    const cols = Math.floor(canvas.width / gap);
    const rows = Math.floor(canvas.height / gap);

    // Draw random shimmering pixels near edges or center
    const numPixels = Math.floor((cols * rows) * 0.08);
    for (let i = 0; i < numPixels; i++) {
      const col = Math.floor(Math.random() * cols);
      const row = Math.floor(Math.random() * rows);
      const x = col * gap;
      const y = row * gap;
      const color = colors[Math.floor(Math.random() * colors.length)];
      const alpha = (Math.random() * 0.4 + 0.1).toFixed(2);

      ctx.fillStyle = color;
      ctx.globalAlpha = parseFloat(alpha);
      ctx.fillRect(x, y, 2, 2);
    }
  }, [gap, colors, isHovered]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    const resize = () => {
      const rect = container.getBoundingClientRect();
      canvas.width = rect.width;
      canvas.height = rect.height;
    };

    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(container);

    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!isHovered) {
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
      const canvas = canvasRef.current;
      if (canvas) {
        const ctx = canvas.getContext('2d');
        if (ctx) ctx.clearRect(0, 0, canvas.width, canvas.height);
      }
      return;
    }

    let lastTime = 0;
    const interval = 1000 / speed;

    const loop = (time: number) => {
      if (time - lastTime >= interval) {
        lastTime = time;
        drawPixels();
      }
      animFrameRef.current = requestAnimationFrame(loop);
    };

    animFrameRef.current = requestAnimationFrame(loop);

    return () => {
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
    };
  }, [isHovered, speed, drawPixels]);

  return (
    <div
      ref={containerRef}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      className={`relative overflow-hidden rounded-2xl border border-white/[0.08] transition-colors duration-200 ${className}`}
      style={{ backgroundColor }}
    >
      <canvas
        ref={canvasRef}
        className="pointer-events-none absolute inset-0 z-0 h-full w-full"
        aria-hidden="true"
      />
      <div className="relative z-10">{children}</div>
    </div>
  );
};

export default PixelCard;
