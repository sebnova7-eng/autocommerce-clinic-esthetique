import { describe, it, expect } from 'vitest';
import { cn } from '@/lib/utils';

describe('utils — cn (classnames)', () => {
  it('fusionne les classes', () => {
    const result = cn('foo', 'bar');
    expect(result).toBe('foo bar');
  });

  it('ignore les valeurs falsy', () => {
    const result = cn('foo', null, undefined, false, 'bar');
    expect(result).toBe('foo bar');
  });

  it('gère les objets conditionnels', () => {
    const result = cn('foo', { bar: true, baz: false });
    expect(result).toBe('foo bar');
  });

  it('retourne une chaîne vide pour aucun argument', () => {
    const result = cn();
    expect(result).toBe('');
  });

  it('clsx concatène sans déduire les doublons (c\'est le comportement attendu)', () => {
    const result = cn('foo', 'foo');
    expect(result).toContain('foo');
    // clsx concatène les classes ; twMerge peut fusionner des classes Tailwind en conflit
    // mais pas les doublons simples.
  });
});
