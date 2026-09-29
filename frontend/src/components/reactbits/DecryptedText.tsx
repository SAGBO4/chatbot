'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';

interface DecryptedTextProps {
  text: string;
  speed?: number;
  maxIterations?: number;
  sequential?: boolean;
  revealDirection?: 'start' | 'end' | 'center';
  useOriginalCharsOnly?: boolean;
  characters?: string;
  className?: string;
  encryptedClassName?: string;
  parentClassName?: string;
  animateOn?: 'view' | 'hover';
}

export const DecryptedText: React.FC<DecryptedTextProps> = ({
  text,
  speed = 40,
  maxIterations = 10,
  sequential = true,
  revealDirection = 'start',
  useOriginalCharsOnly = false,
  characters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*()_+~|}{[]:;?><',
  className = 'text-white',
  encryptedClassName = 'text-zinc-500 font-mono',
  parentClassName = '',
  animateOn = 'view',
}) => {
  const [displayText, setDisplayText] = useState<string>(text);
  const [isDecrypted, setIsDecrypted] = useState<boolean>(false);
  const [revealedIndices, setRevealedIndices] = useState<Set<number>>(new Set());
  const containerRef = useRef<HTMLSpanElement>(null);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const hasAnimatedRef = useRef<boolean>(false);

  const getAvailableChars = useCallback(() => {
    return useOriginalCharsOnly
      ? Array.from(new Set(text.split(''))).filter((char) => char !== ' ')
      : characters.split('');
  }, [useOriginalCharsOnly, text, characters]);

  const shuffleText = useCallback(
    (originalText: string, currentRevealed: Set<number>) => {
      const charPool = getAvailableChars();
      return originalText
        .split('')
        .map((char, i) => {
          if (char === ' ') return ' ';
          if (currentRevealed.has(i)) return originalText[i];
          const randomIndex = Math.floor(Math.random() * charPool.length);
          return charPool[randomIndex] ?? char;
        })
        .join('');
    },
    [getAvailableChars]
  );

  const triggerDecrypt = useCallback(() => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    setIsDecrypted(false);

    const currentRevealed = new Set<number>();
    let iteration = 0;
    const textLength = text.length;

    intervalRef.current = setInterval(() => {
      if (sequential) {
        let nextIndex = currentRevealed.size;
        if (revealDirection === 'end') {
          nextIndex = textLength - 1 - currentRevealed.size;
        } else if (revealDirection === 'center') {
          const mid = Math.floor(textLength / 2);
          const offset = Math.floor(currentRevealed.size / 2);
          nextIndex = currentRevealed.size % 2 === 0 ? mid + offset : mid - offset - 1;
        }

        if (nextIndex >= 0 && nextIndex < textLength) {
          currentRevealed.add(nextIndex);
        }

        setRevealedIndices(new Set(currentRevealed));
        setDisplayText(shuffleText(text, currentRevealed));

        if (currentRevealed.size >= textLength) {
          if (intervalRef.current) clearInterval(intervalRef.current);
          setDisplayText(text);
          setIsDecrypted(true);
        }
      } else {
        iteration++;
        setDisplayText(shuffleText(text, currentRevealed));
        if (iteration >= maxIterations) {
          if (intervalRef.current) clearInterval(intervalRef.current);
          setDisplayText(text);
          setIsDecrypted(true);
          const allIndices = new Set(Array.from({ length: textLength }, (_, i) => i));
          setRevealedIndices(allIndices);
        }
      }
    }, speed);
  }, [text, sequential, revealDirection, speed, maxIterations, shuffleText]);

  useEffect(() => {
    if (animateOn === 'view') {
      const observer = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting && !hasAnimatedRef.current) {
              hasAnimatedRef.current = true;
              triggerDecrypt();
            }
          });
        },
        { threshold: 0.1 }
      );

      const el = containerRef.current;
      if (el) observer.observe(el);
      return () => {
        if (el) observer.unobserve(el);
        if (intervalRef.current) clearInterval(intervalRef.current);
      };
    }
  }, [animateOn, triggerDecrypt]);

  const handleMouseEnter = () => {
    if (animateOn === 'hover') {
      triggerDecrypt();
    }
  };

  return (
    <span
      ref={containerRef}
      onMouseEnter={handleMouseEnter}
      className={`inline-block select-none ${parentClassName}`}
    >
      <span className="sr-only">{text}</span>
      <span aria-hidden="true">
        {displayText.split('').map((char, index) => {
          const isRevealed = revealedIndices.has(index) || isDecrypted;
          return (
            <span key={index} className={isRevealed ? className : encryptedClassName}>
              {char}
            </span>
          );
        })}
      </span>
    </span>
  );
};

export default DecryptedText;
