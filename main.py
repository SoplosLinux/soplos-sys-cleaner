#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Soplos Sys Cleaner 1.0.0
System cleaning tool for Soplos Linux distributions.
"""

import sys
import os
import warnings
from pathlib import Path

# Add project root to Python path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# Suppress accessibility warnings
warnings.filterwarnings('ignore', '.*Couldn\'t connect to accessibility bus.*', Warning)
warnings.filterwarnings('ignore', '.*Failed to connect to socket.*', Warning)

if not os.environ.get('ENABLE_ACCESSIBILITY'):
    os.environ['NO_AT_BRIDGE'] = '1'
    os.environ['AT_SPI_BUS'] = '0'


def _clean_pycache():
    """Removes __pycache__ directories in the project root."""
    try:
        import shutil
        for root, dirs, files in os.walk(PROJECT_ROOT):
            if '__pycache__' in dirs:
                shutil.rmtree(os.path.join(root, '__pycache__'), ignore_errors=True)
                # Optimize: remove from dirs so os.walk doesn't try to enter it
                if '__pycache__' in dirs:
                    dirs.remove('__pycache__')
    except Exception:
        pass


def main():
    """Main entry point for Soplos Sys Cleaner."""
    try:
        from core import run_application
        res = run_application()
        _clean_pycache()
        return res
    except ImportError as e:
        print(f"Import error: {e}")
        print("Make sure you have installed the dependencies:")
        print("  sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0")
        return 1
    except Exception as e:
        print(f"Application error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
