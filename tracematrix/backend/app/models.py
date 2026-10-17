from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

JSONType = JSON().with_variant(JSONB(), "postgresql")


def uuid_str() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255), default="Analyst")
    role: Mapped[str] = mapped_column(String(32), default="analyst", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    memberships: Mapped[list[InvestigationMember]] = relationship(back_populates="user")


class Investigation(Base):
    __tablename__ = "investigations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    title: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    seed_value: Mapped[str] = mapped_column(String(128), index=True)
    seed_type: Mapped[str] = mapped_column(String(32))
    objective: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    date_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    date_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    max_depth: Mapped[int] = mapped_column(Integer, default=2)
    max_transactions: Mapped[int] = mapped_column(Integer, default=100)
    selected_sources: Mapped[dict] = mapped_column(JSONType, default=dict)
    is_fixture: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    members: Mapped[list[InvestigationMember]] = relationship(back_populates="investigation")
    wallets: Mapped[list[InvestigationWallet]] = relationship(back_populates="investigation")


class InvestigationMember(Base):
    __tablename__ = "investigation_members"
    __table_args__ = (UniqueConstraint("investigation_id", "user_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    member_role: Mapped[str] = mapped_column(String(32), default="analyst")

    investigation: Mapped[Investigation] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="memberships")


class Wallet(Base):
    __tablename__ = "wallets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    address: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    checksum_address: Mapped[str] = mapped_column(String(64))
    first_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    extra: Mapped[dict] = mapped_column(JSONType, default=dict)


class ChainTransaction(Base):
    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    tx_hash: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    block_number: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    from_address: Mapped[str] = mapped_column(String(64), index=True)
    to_address: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    value_wei: Mapped[Decimal] = mapped_column(Numeric(78, 0), default=0)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    gas_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gas_price_wei: Mapped[Decimal | None] = mapped_column(Numeric(78, 0), nullable=True)
    input_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_fixture: Mapped[bool] = mapped_column(Boolean, default=False)
    extra: Mapped[dict] = mapped_column(JSONType, default=dict)


class TokenTransfer(Base):
    __tablename__ = "token_transfers"
    __table_args__ = (UniqueConstraint("tx_hash", "log_index"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    tx_hash: Mapped[str] = mapped_column(String(80), index=True)
    log_index: Mapped[int] = mapped_column(Integer, default=0)
    token_address: Mapped[str] = mapped_column(String(64), index=True)
    from_address: Mapped[str] = mapped_column(String(64), index=True)
    to_address: Mapped[str] = mapped_column(String(64), index=True)
    value_raw: Mapped[Decimal] = mapped_column(Numeric(78, 0), default=0)
    decimals: Mapped[int] = mapped_column(Integer, default=18)
    symbol: Mapped[str | None] = mapped_column(String(32), nullable=True)
    timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    is_fixture: Mapped[bool] = mapped_column(Boolean, default=False)


class InvestigationWallet(Base):
    __tablename__ = "investigation_wallets"
    __table_args__ = (UniqueConstraint("investigation_id", "wallet_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.id"), index=True)
    wallet_id: Mapped[str] = mapped_column(ForeignKey("wallets.id"), index=True)
    hop_distance: Mapped[int] = mapped_column(Integer, default=0)

    investigation: Mapped[Investigation] = relationship(back_populates="wallets")
    wallet: Mapped[Wallet] = relationship()


class GraphEdge(Base):
    __tablename__ = "graph_edges"
    __table_args__ = (UniqueConstraint("investigation_id", "tx_hash", "from_address", "to_address", "token_address"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.id"), index=True)
    from_address: Mapped[str] = mapped_column(String(64), index=True)
    to_address: Mapped[str] = mapped_column(String(64), index=True)
    tx_hash: Mapped[str] = mapped_column(String(80), index=True)
    token_address: Mapped[str] = mapped_column(String(64), default="native")
    value_raw: Mapped[Decimal] = mapped_column(Numeric(78, 0), default=0)
    timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OsintSource(Base):
    __tablename__ = "osint_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    name: Mapped[str] = mapped_column(String(255))
    source_type: Mapped[str] = mapped_column(String(64), index=True)
    endpoint: Mapped[str] = mapped_column(String(1024))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(64), default="not_configured")
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    config: Mapped[dict] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    investigation_id: Mapped[str | None] = mapped_column(ForeignKey("investigations.id"), nullable=True, index=True)
    job_type: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    extra: Mapped[dict] = mapped_column(JSONType, default=dict)


class OsintEvidence(Base):
    __tablename__ = "osint_evidence"
    __table_args__ = (UniqueConstraint("content_hash", "investigation_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.id"), index=True)
    source_type: Mapped[str] = mapped_column(String(64), index=True)
    source_url: Mapped[str] = mapped_column(String(2048))
    source_record_id: Mapped[str] = mapped_column(String(255), default="")
    indicator: Mapped[str] = mapped_column(String(255), index=True)
    original_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    extracted_context: Mapped[str] = mapped_column(Text, default="")
    extraction_method: Mapped[str] = mapped_column(String(128), default="regex_eth_address")
    verification_status: Mapped[str] = mapped_column(String(64), default="unverified")
    reliability: Mapped[str] = mapped_column(String(64), default="unknown")
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    extra: Mapped[dict] = mapped_column(JSONType, default=dict)


class CandidateLink(Base):
    __tablename__ = "candidate_links"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.id"), index=True)
    wallet_address: Mapped[str] = mapped_column(String(64), index=True)
    relationship_type: Mapped[str] = mapped_column(String(64))
    supporting: Mapped[dict] = mapped_column(JSONType, default=list)
    contradictory: Mapped[dict] = mapped_column(JSONType, default=list)
    temporal_score: Mapped[float] = mapped_column(Numeric(8, 4), default=0)
    graph_score: Mapped[float] = mapped_column(Numeric(8, 4), default=0)
    reliability_score: Mapped[float] = mapped_column(Numeric(8, 4), default=0)
    overall_score: Mapped[float] = mapped_column(Numeric(8, 4), default=0)
    label: Mapped[str] = mapped_column(String(64), default="investigative_lead")
    explanation: Mapped[str] = mapped_column(Text, default="")
    evidence_ids: Mapped[dict] = mapped_column(JSONType, default=list)
    component_scores: Mapped[dict] = mapped_column(JSONType, default=dict)
    verification_status: Mapped[str] = mapped_column(String(64), default="unreviewed")
    analysis_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.id"), index=True)
    algorithm_version: Mapped[str] = mapped_column(String(64), default="qce-1.0.0")
    configuration: Mapped[dict] = mapped_column(JSONType, default=dict)
    input_refs: Mapped[dict] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.id"), index=True)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.id"), index=True)
    result_type: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict] = mapped_column(JSONType, default=dict)


class AnalystNote(Base):
    __tablename__ = "analyst_notes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.id"), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    investigation_id: Mapped[str | None] = mapped_column(ForeignKey("investigations.id"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(128), index=True)
    details: Mapped[dict] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReportExport(Base):
    __tablename__ = "report_exports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.id"), index=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    format: Mapped[str] = mapped_column(String(16))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CandidateReview(Base):
    __tablename__ = "candidate_reviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidate_links.id"), index=True)
    reviewer_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[str] = mapped_column(String(32))
    rationale: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
