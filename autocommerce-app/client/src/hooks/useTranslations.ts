import { useTranslation } from 'react-i18next';

export const useTranslations = () => {
  const { t, i18n } = useTranslation();

  return {
    t,
    language: i18n.language,
    changeLanguage: i18n.changeLanguage,
    languages: ['fr', 'en', 'it', 'de'],
  };
};

export default useTranslations;
