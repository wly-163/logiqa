import { createI18n } from 'vue-i18n'
import zhCN from './locales/zh-CN'
import zhTW from './locales/zh-TW'
import enUS from './locales/en-US'
import jaJP from './locales/ja-JP'

export const LOCALE_KEY = 'logiqa-locale'
export const LOCALES = [
  { value: 'zh-CN', native: '简体中文' },
  { value: 'zh-TW', native: '繁體中文' },
  { value: 'en-US', native: 'English' },
  { value: 'ja-JP', native: '日本語' },
]

const ALLOWED = LOCALES.map((x) => x.value)

export function detectLocale() {
  try {
    const saved = localStorage.getItem(LOCALE_KEY)
    if (saved && ALLOWED.includes(saved)) return saved
  } catch (e) {}
  const nav = String(navigator.language || 'zh-CN').toLowerCase()
  if (nav.startsWith('zh-tw') || nav.startsWith('zh-hk') || nav.startsWith('zh-mo')) return 'zh-TW'
  if (nav.startsWith('zh')) return 'zh-CN'
  if (nav.startsWith('ja')) return 'ja-JP'
  if (nav.startsWith('en')) return 'en-US'
  return 'zh-CN'
}

export const i18n = createI18n({
  legacy: false,
  locale: detectLocale(),
  fallbackLocale: 'zh-CN',
  messages: {
    'zh-CN': zhCN,
    'zh-TW': zhTW,
    'en-US': enUS,
    'ja-JP': jaJP,
  },
})

export function applyHtmlLang(code) {
  document.documentElement.lang = code
}

export function setLocale(code) {
  if (!ALLOWED.includes(code)) return
  i18n.global.locale.value = code
  try { localStorage.setItem(LOCALE_KEY, code) } catch (e) {}
  applyHtmlLang(code)
}

applyHtmlLang(i18n.global.locale.value)
