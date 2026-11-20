"""Rutas para ejecución desde código y desde un paquete PyInstaller."""
import os
import sys
from pathlib import Path

RESOURCES = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ['AGROTRACK_DATA_DIR']).expanduser().resolve() if os.environ.get('AGROTRACK_DATA_DIR') else (
    Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else RESOURCES
)
