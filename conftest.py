"""conftest.py — pytest root configuration.
This file makes exchange_core, graders, and harness importable from tests/.
"""
import sys
from pathlib import Path

# Add the project root to the Python path.
sys.path.insert(0, str(Path(__file__).parent))
