'use client';

import React, { useEffect, useRef, useState, useCallback } from 'react';

interface CountUpProps {
  to: number;
  from?: number;
  duration?: number;
  delay?: number;
  className?: string;
  decimals?: number;
  prefix?: string;
  suffix?: string;
  separator?: string;
}

export const CountUp: React.FC<CountUpProps> = ({
  to,
  from = 0,
  duration = 1.8,
  delay = 0,
  className = '',
  decimals = 0,
  prefix = '',
  suffix = '',
  separator = '',
}) => {
  const [value, setValue] = useState<number>(to);
  const ref = useRef<HTMLSpanElement>(null);
  const startedRef = useRef<boolean>(false);

  const formatNumber = useCallback(
    (num: number) => {
      const fixed = num.toFixed(decimals);
      if (!separator) return `${prefix}${fixed}${suffix}`;
      const [intPart, decPart] = fixed.split('.');
      const formattedInt = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, separator);
      return `${prefix}${formattedInt}${decPart ? `.${decPart}` : ''}${suffix}`;
    },
    [decimals, prefix, suffix, separator]
  );

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting && !startedRef.current) {
            startedRef.current = true;

            const timer = setTimeout(() => {
              const startTime = performance.now();
              const durationMs = duration * 1000;

              const animate = (currentTime: number) => {
                const elapsed = currentTime - startTime;
                const progress = Math.min(elapsed / durationMs, 1);
                // Ease out quint: 1 - Math.pow(1 - progress, 5)
                const eased = 1 - Math.pow(1 - progress, 4);
                const currentVal = from + (to - from) * eased;
                setValue(currentVal);

                if (progress < 1) {
                  requestAnimationFrame(animate);
                } else {
                  setValue(to);
                }
              };

              requestAnimationFrame(animate);
            }, delay * 1000);

            return () => clearTimeout(timer);
          }
        });
      },
      { threshold: 0.1 }
    );

    const el = ref.current;
    if (el) observer.observe(el);
    return () => {
      if (el) observer.unobserve(el);
    };
  }, [from, to, duration, delay]);

  return (
    <span ref={ref} className={className}>
      {formatNumber(value)}
    </span>
  );
};

export default CountUp;
