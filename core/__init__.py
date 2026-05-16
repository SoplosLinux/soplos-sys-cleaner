"""Core module for Soplos Sys Cleaner."""
__version__ = '1.0.2-1'

from .application import run_application, create_application
from .i18n_manager import _, initialize_i18n
from .environment import get_environment_detector
from .theme_manager import initialize_theming, get_theme_manager

__all__ = [
    'run_application', 'create_application',
    '_', 'initialize_i18n',
    'get_environment_detector',
    'initialize_theming', 'get_theme_manager',
]
