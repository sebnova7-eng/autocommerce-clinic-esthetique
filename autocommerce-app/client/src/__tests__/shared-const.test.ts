import { describe, it, expect } from 'vitest';
import { COOKIE_NAME, ONE_YEAR_MS } from '@shared/const';

describe('shared/const', () => {
  it('COOKIE_NAME est une chaîne non vide', () => {
    expect(typeof COOKIE_NAME).toBe('string');
    expect(COOKIE_NAME.length).toBeGreaterThan(0);
  });

  it('ONE_YEAR_MS correspond à 365 jours en millisecondes', () => {
    expect(ONE_YEAR_MS).toBe(1000 * 60 * 60 * 24 * 365);
    expect(ONE_YEAR_MS).toBe(31536000000);
  });

  it('ONE_YEAR_MS est un entier positif', () => {
    expect(ONE_YEAR_MS).toBeGreaterThan(0);
    expect(Number.isInteger(ONE_YEAR_MS)).toBe(true);
  });
});
