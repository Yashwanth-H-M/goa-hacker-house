"""Official benchmark configuration for the Contextline retrieval adapter."""

from __future__ import annotations

import os


# The supplied competition benchmark imports this constant directly.
# It is configurable for local diagnostics but defaults to the official target.
LATENCY_BUDGET_MS = float(os.getenv("RAG_LATENCY_BUDGET_MS", "50"))
