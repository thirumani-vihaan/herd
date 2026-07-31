import sys
import asyncio
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.wiring import build_container

async def test_wiring():
    print("Building container...")
    container = build_container()
    print(f"Container built for {container.institution.id}")
    
    print("Building cascade...")
    cascade = container.build_cascade(markers=None)
    
    expected_agents = {
        "FraudHeuristics", "TemplateProvenance", "StrainPrior",
        "DomainForensics", "URLSafety", "ContactForensics",
        "InstitutionalSource", "OfficialChannel", "OpenWebResearch"
    }
    
    found_agents = set()
    for tier, agents in cascade.tiers.items():
        for agent in agents:
            found_agents.add(agent.name)
            
    missing = expected_agents - found_agents
    if missing:
        print(f"FAILED: Missing agents in cascade: {missing}")
        sys.exit(1)
        
    print("SUCCESS: All Tier 0 and Tier 1 agents are wired correctly.")
    sys.exit(0)

if __name__ == "__main__":
    asyncio.run(test_wiring())
