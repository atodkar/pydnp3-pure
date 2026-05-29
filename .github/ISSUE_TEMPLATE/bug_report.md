---
name: Bug Report
about: Report a bug or unexpected behavior
title: "[BUG] "
labels: bug
assignees: ''
---

**Describe the bug**
A clear description of what the bug is.

**To Reproduce**
```python
# Minimal code to reproduce the issue
from pydnp3_pure.mock import create_loopback_pair

pair = create_loopback_pair()
# ... steps that trigger the bug
```

**Expected behavior**
What you expected to happen.

**Actual behavior**
What actually happened (include tracebacks if applicable).

**Environment**
- OS: [e.g., Ubuntu 22.04, Windows 11]
- Python version: [e.g., 3.11.5]
- pydnp3-pure version: [e.g., 0.1.0]

**Additional context**
Hex dumps, Wireshark captures, or protocol logs (use `pydnp3_pure.debug.hex_dump()`).
