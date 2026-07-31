"""Dependency injection container and assembly."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from app.clients.http import build_fetcher
from app.config import get_settings, get_thresholds, Settings, Thresholds
from app.contracts import Institution, ForwardMarkers
from app.institution import get_institution
from app.clients.embeddings import SentenceTransformerEmbeddings, HashingEmbeddings, GeminiEmbeddings
from app.clients.vector import ChromaVectorIndex
from app.clients.gemini import GeminiClient
from app.clients.featherless import FeatherlessClient
from app.interfaces import Store, HttpFetcher, VectorIndex, EmbeddingModel, LLMClient, Notifier
from app.investigate.aggregate import Aggregator
from app.intervene.delivery import TelegramNotifier, WebSocketNotifier
from app.investigate.cascade import Cascade
from app.recognise.strain import StrainEngine
from app.investigate.agents import (
    ContactForensics, DomainForensics, FraudHeuristics,
    TemplateProvenance, URLSafety, StrainPrior,
    InstitutionalSource, OfficialChannel, OpenWebResearch
)
from app.storage.sqlite_store import SqliteStore

logger = logging.getLogger(__name__)


@dataclass
class Container:
    settings: Settings
    thresholds: Thresholds
    institution: Institution
    fetcher: HttpFetcher
    store: Store
    aggregator: Aggregator
    index: VectorIndex
    embeddings: EmbeddingModel
    llm: LLMClient
    featherless: FeatherlessClient
    notifiers: list[Notifier]
    strain_engine: StrainEngine

    def build_cascade(self, markers: ForwardMarkers | None = None) -> Cascade:
        """Construct a fresh Cascade for one investigation."""
        official = {d.lower().lstrip(".") for d in (self.institution.domains.official or [])}
        
        agents = [
            # Tier 0
            FraudHeuristics(
                official_domains=official,
                correlated_discount=self.thresholds.f("aggregation.correlated_discount"),
                saturation=self.thresholds.f("aggregation.agent_saturation")
            ),
            TemplateProvenance(markers=markers),
            StrainPrior(
                store=self.store,
                institution_id=self.institution.id,
                same_institution_weight=self.thresholds.f("aggregation.strain_prior.same_institution"),
                cross_institution_weight=self.thresholds.f("aggregation.strain_prior.cross_institution")
            ),
            
            # Tier 1
            DomainForensics(self.institution, self.fetcher),
            URLSafety(self.institution, self.fetcher),
            ContactForensics(self.institution, self.fetcher),
            
            # Tier 2
            InstitutionalSource(self.institution, self.index, self.embeddings),
            OfficialChannel(self.institution, self.index, self.embeddings),
            
            # Tier 3
            OpenWebResearch(self.fetcher, self.featherless)
        ]
        
        return Cascade(
            agents=agents,
            aggregator=self.aggregator,
            exit_bars=self.thresholds.get("cascade.exit"),
            false_exit_multiplier=self.thresholds.f("cascade.false_exit_multiplier"),
            unverified_exit_multiplier=self.thresholds.f("cascade.unverified_exit_multiplier"),
            deadline_ms=self.thresholds.i("cascade.deadline_ms"),
            confirming_agents=set(self.thresholds.get("verdict.confirming_agents"))
        )


def build_container(institution_id: str | None = None) -> Container:
    settings = get_settings()
    thresholds = get_thresholds()
    inst = get_institution(institution_id)
    fetcher = build_fetcher()
    aggregator = Aggregator.from_thresholds(thresholds)
    
    db_path_str = settings.database_url
    if db_path_str.startswith("sqlite+aiosqlite:///"):
        db_path_str = db_path_str.replace("sqlite+aiosqlite:///", "")
    elif db_path_str.startswith("sqlite:///"):
        db_path_str = db_path_str.replace("sqlite:///", "")
    
    store = SqliteStore(Path(db_path_str))
    embeddings = GeminiEmbeddings(api_key=settings.gemini_api_key)
    index = ChromaVectorIndex(persist_dir=str(Path(db_path_str).parent / 'chroma'))
    llm = GeminiClient(fetcher, settings.gemini_api_key, settings.gemini_model)
    featherless = FeatherlessClient(
        fetcher,
        api_key=settings.featherless_api_key,
        model=settings.featherless_model,
        base_url=settings.featherless_base_url,
    )
    strain_engine = StrainEngine(
        store=store,
        embeddings=embeddings,
        index=index,
        same_strain=thresholds.f("strain.same_strain"),
        mutation=thresholds.f("strain.mutation"),
        amount_tolerance=thresholds.f("strain.amount_tolerance"),
        min_content_chars=thresholds.i("strain.min_content_chars"),
    )
    
    return Container(
        settings=settings,
        thresholds=thresholds,
        institution=inst,
        fetcher=fetcher,
        store=store,
        aggregator=aggregator,
        index=index,
        embeddings=embeddings,
        llm=llm,
        featherless=featherless,
        notifiers=[
            TelegramNotifier(getattr(settings, "telegram_token", None), getattr(settings, "telegram_admin_id", None)),
            WebSocketNotifier()
        ],
        strain_engine=strain_engine,
    )
