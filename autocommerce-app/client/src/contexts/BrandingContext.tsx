import React, { createContext, useContext, useState, useEffect } from 'react';
import { settingsApi, BrandingResponse } from '@/lib/api';

interface BrandingContextType {
  branding: BrandingResponse | null;
  isLoading: boolean;
  applyTheme: (branding: BrandingResponse) => void;
}

const BrandingContext = createContext<BrandingContextType | undefined>(undefined);

const DEFAULT_BRANDING: BrandingResponse = {
  nom_clinique: 'Clinique',
  couleur_primaire: '#0EA5A4',
  couleur_secondaire: '#0F172A',
  logo_url: undefined,
  contenu_landing: {
    titre: 'Bienvenue',
    sous_titre: 'Votre clinique esthétique de confiance',
    services_mis_en_avant: [],
    adresse: '',
    telephone: '',
    horaires: '',
  },
};

export const BrandingProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [branding, setBranding] = useState<BrandingResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const loadBranding = async () => {
      try {
        const response = await settingsApi.getBranding();
        const data = response.data;
        setBranding(data);
        applyTheme(data);
      } catch (err) {
        console.error('Failed to load branding:', err);
        // Use default branding on error
        setBranding(DEFAULT_BRANDING);
        applyTheme(DEFAULT_BRANDING);
      } finally {
        setIsLoading(false);
      }
    };

    loadBranding();
  }, []);

  const applyTheme = (brandingData: BrandingResponse) => {
    const root = document.documentElement;

    // Apply primary color
    if (brandingData.couleur_primaire) {
      root.style.setProperty('--primary', brandingData.couleur_primaire);
      // Also update related colors
      root.style.setProperty('--sidebar-primary', brandingData.couleur_primaire);
      root.style.setProperty('--chart-1', brandingData.couleur_primaire);
    }

    // Apply secondary color
    if (brandingData.couleur_secondaire) {
      root.style.setProperty('--secondary', brandingData.couleur_secondaire);
      root.style.setProperty('--muted', brandingData.couleur_secondaire);
    }

    // Store branding for later use
    sessionStorage.setItem('branding', JSON.stringify(brandingData));
  };

  const value: BrandingContextType = {
    branding: branding || DEFAULT_BRANDING,
    isLoading,
    applyTheme,
  };

  return <BrandingContext.Provider value={value}>{children}</BrandingContext.Provider>;
};

export const useBranding = () => {
  const context = useContext(BrandingContext);
  if (!context) {
    throw new Error('useBranding must be used within BrandingProvider');
  }
  return context;
};
