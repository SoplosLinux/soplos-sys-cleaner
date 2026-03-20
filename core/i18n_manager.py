"""
Internationalization manager for Soplos Sys Cleaner.
GNU Gettext based, 8 languages.
"""

import os
import locale
import gettext
from pathlib import Path

SUPPORTED_LANGUAGES = {
    'es': 'Español',
    'en': 'English',
    'fr': 'Français',
    'de': 'Deutsch',
    'pt': 'Português',
    'it': 'Italiano',
    'ro': 'Română',
    'ru': 'Русский',
}

DOMAIN = 'soplos-sys-cleaner'

_i18n_manager = None


class I18nManager:
    FALLBACK_CHAIN = ['en', 'es']

    def __init__(self, locale_dir: str, domain: str = DOMAIN):
        self.locale_dir = Path(locale_dir)
        self.domain = domain
        self.current_language = None
        self.translations = {}
        self.fallback_translation = gettext.NullTranslations()
        self._load_translations()
        self.set_language(self.detect_system_language())

    def _load_translations(self):
        for lang_code in SUPPORTED_LANGUAGES:
            mo_file = self.locale_dir / lang_code / 'LC_MESSAGES' / f'{self.domain}.mo'
            if mo_file.exists():
                try:
                    with open(mo_file, 'rb') as f:
                        self.translations[lang_code] = gettext.GNUTranslations(f)
                except Exception as e:
                    print(f"[i18n] Error loading {lang_code}: {e}")
        if 'en' in self.translations:
            self.fallback_translation = self.translations['en']

    def detect_system_language(self) -> str:
        for env_var in ['LANGUAGE', 'LC_ALL', 'LC_MESSAGES', 'LANG']:
            val = os.environ.get(env_var)
            if val:
                code = val.split('_')[0].split('.')[0].lower()
                if code in SUPPORTED_LANGUAGES:
                    return code
        try:
            sys_locale = locale.getdefaultlocale()[0]
            if sys_locale:
                code = sys_locale.split('_')[0].lower()
                if code in SUPPORTED_LANGUAGES:
                    return code
        except Exception:
            pass
        return 'en'

    def set_language(self, lang_code: str) -> bool:
        if lang_code in self.translations:
            self.current_language = lang_code
            self.translations[lang_code].install()
            return True
        for fallback in self.FALLBACK_CHAIN:
            if fallback in self.translations:
                self.current_language = fallback
                self.translations[fallback].install()
                return False
        self.current_language = 'en'
        self.fallback_translation.install()
        return False

    def get_translation(self, message: str, **kwargs) -> str:
        lang = self.current_language
        if lang and lang in self.translations:
            try:
                translated = self.translations[lang].gettext(message)
            except Exception:
                translated = message
        else:
            translated = message
        if translated == message and self.fallback_translation:
            try:
                translated = self.fallback_translation.gettext(message)
            except Exception:
                pass
        if kwargs:
            try:
                translated = translated.format(**kwargs)
            except Exception:
                pass
        return translated

    def get_current_language(self) -> str:
        return self.current_language or 'en'

    def get_available_languages(self):
        return {k: v for k, v in SUPPORTED_LANGUAGES.items() if k in self.translations}

    def _(self, message: str, **kwargs) -> str:
        return self.get_translation(message, **kwargs)


def _get_manager() -> I18nManager:
    global _i18n_manager
    if _i18n_manager is None:
        locale_dir = Path(__file__).parent.parent / 'locale'
        _i18n_manager = I18nManager(str(locale_dir))
    return _i18n_manager


def _(message: str, **kwargs) -> str:
    return _get_manager().get_translation(message, **kwargs)


def set_language(lang_code: str) -> bool:
    return _get_manager().set_language(lang_code)


def get_current_language() -> str:
    return _get_manager().get_current_language()


def get_available_languages():
    return _get_manager().get_available_languages()


def initialize_i18n(locale_dir: str = None) -> str:
    global _i18n_manager
    if locale_dir is None:
        locale_dir = str(Path(__file__).parent.parent / 'locale')
    _i18n_manager = I18nManager(locale_dir)
    return _i18n_manager.get_current_language()
