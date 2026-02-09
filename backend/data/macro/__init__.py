"""
Macro / Cross-Asset Data Sources

Fetches data that is structurally uncorrelated to equity momentum, value,
and sentiment signals.  Used by the MacroRiskOverlay to coordinate risk
across all agents.
"""

from data.macro.fred import FredClient
from data.macro.volatility_regime import VolatilityRegimeClient

__all__ = [
    "FredClient",
    "VolatilityRegimeClient",
]
