"""
NammaSignal FastAPI Dependency Injection Container
Provides thread-safe singleton access to core domain services and adapters.
"""

from functools import lru_cache
from persistence.database import DatabaseManager
from persistence.repository import EventRepository
from authorization.evaluator import CedarPolicyEngine
from search.opensearch_client import OpenSearchManager
from domain.correlation import EventCorrelationEngine
from agents.observation_interpreter import ObservationInterpreterAgent
from agents.evidence_analyst import EvidenceAnalystAgent
from agents.advisory_generator import AdvisoryGeneratorAgent
from simulation.scenario_runner import SimulationScenarioManager


@lru_cache
def get_db_manager() -> DatabaseManager:
    return DatabaseManager()


@lru_cache
def get_event_repository() -> EventRepository:
    return EventRepository(get_db_manager())


@lru_cache
def get_cedar_engine() -> CedarPolicyEngine:
    return CedarPolicyEngine()


@lru_cache
def get_search_manager() -> OpenSearchManager:
    return OpenSearchManager()


@lru_cache
def get_correlation_engine() -> EventCorrelationEngine:
    return EventCorrelationEngine()


@lru_cache
def get_interpreter_agent() -> ObservationInterpreterAgent:
    return ObservationInterpreterAgent()


@lru_cache
def get_evidence_analyst() -> EvidenceAnalystAgent:
    return EvidenceAnalystAgent()


@lru_cache
def get_advisory_generator() -> AdvisoryGeneratorAgent:
    return AdvisoryGeneratorAgent()


@lru_cache
def get_simulation_manager() -> SimulationScenarioManager:
    return SimulationScenarioManager(
        repository=get_event_repository(),
        search_manager=get_search_manager(),
        cedar_engine=get_cedar_engine(),
    )
