import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

import enLayout from './locales/en/layout.json'
import enPages from './locales/en/pages.json'
import enComponents from './locales/en/components.json'
import frLayout from './locales/fr/layout.json'
import frPages from './locales/fr/pages.json'
import frComponents from './locales/fr/components.json'

export const LANGUAGE_STORAGE_KEY = 'brainopx_language'
export const SUPPORTED_LANGUAGES = ['en', 'fr']

const storedLanguage = localStorage.getItem(LANGUAGE_STORAGE_KEY)
const initialLanguage = SUPPORTED_LANGUAGES.includes(storedLanguage) ? storedLanguage : 'en'

i18n.use(initReactI18next).init({
  resources: {
    en: { layout: enLayout, pages: enPages, components: enComponents },
    fr: { layout: frLayout, pages: frPages, components: frComponents },
  },
  lng: initialLanguage,
  fallbackLng: 'en',
  ns: ['layout', 'pages', 'components'],
  defaultNS: 'pages',
  interpolation: { escapeValue: false },
  returnEmptyString: false,
})

document.documentElement.lang = initialLanguage
i18n.on('languageChanged', (lng) => {
  document.documentElement.lang = lng
})

export default i18n
