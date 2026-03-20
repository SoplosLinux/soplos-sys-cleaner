"""Logger for Soplos Sys Cleaner."""

import logging
import os

def _setup_logger():
    level = logging.DEBUG if os.environ.get('SOPLOS_DEBUG') else logging.INFO
    logging.basicConfig(
        level=level,
        format='[%(levelname)s] %(name)s: %(message)s'
    )
    return logging.getLogger('soplos-sys-cleaner')

logger = _setup_logger()
