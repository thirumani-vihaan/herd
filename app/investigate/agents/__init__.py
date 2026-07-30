"""Investigation agents, grouped by tier.

Tier 0 is free and offline. Tier 1 costs a network call. Tier 2 costs money.
The cascade stops at the cheapest tier that can settle the question, which is
why the median claim never reaches Tier 2 at all.
"""
from app.investigate.agents.memory import StrainPrior
from app.investigate.agents.tier0 import FraudHeuristics, TemplateProvenance, load_rules
from app.investigate.agents.tier1 import ContactForensics, DomainForensics, URLSafety
from app.investigate.agents.tier2 import InstitutionalSource, OfficialChannel

__all__ = ["ContactForensics", "DomainForensics", "FraudHeuristics", "StrainPrior",
           "TemplateProvenance", "URLSafety", "load_rules",
           "InstitutionalSource", "OfficialChannel"]
