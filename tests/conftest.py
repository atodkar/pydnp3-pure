"""Shared test configuration and fixtures."""

import sys
from pathlib import Path

# Ensure the src directory is on the path for test discovery
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
