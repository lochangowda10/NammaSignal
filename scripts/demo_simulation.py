"""
NammaSignal Deterministic Simulation Demo
Executes the full Silk Board Cloudburst scenario directly from terminal.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from apps.api.dependencies import get_simulation_manager


def main():
    print("=" * 80)
    print("NAMMASIGNAL - PHYSICAL HAZARD EVIDENCE FUSION SIMULATION")
    print("Scenario: Silk Board Junction Heavy Rainfall & Cloudburst")
    print("=" * 80)

    sim = get_simulation_manager()
    sim.reset_simulation()

    for i in range(1, 6):
        step = sim.execute_next_scenario_step()
        print(f"\n[STEP {step['step']}] {step['title']}")
        print(f"Description: {step['description']}")
        print(f"Cedar Authorization: {step.get('cedar_decision', 'N/A')}")
        print(f"Risk Level:         {step.get('risk_level')}")
        print(f"Confidence Level:   {step.get('confidence_level')}")
        print(f"Confidence Score:   {step.get('confidence_score')}")
        if "advisory" in step:
            print(f"Commuter Advisory:  {step['advisory']}")
        print("-" * 80)

    print("\nSimulation successfully demonstrated the complete intelligence loop!")


if __name__ == "__main__":
    main()
