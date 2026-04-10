"""
╔════════════════════════════════════════════════════════════════════════════╗
║                    AutoScaleOps - Test Suite                               ║
╚════════════════════════════════════════════════════════════════════════════╝

Run tests with:
    python -m pytest tests/ -v
"""

import sys
from pathlib import Path

# Add root to path
sys.path.insert(0, str(Path(__file__).parent.parent))