"""Rebuild the app graph from the current editable workflow."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
subprocess.run([sys.executable, str(ROOT / 'tools' / 'compile_workflow.py'),
                str(ROOT / 'workflows' / 'BobHead_Comfyui_v06.json')], check=True)
