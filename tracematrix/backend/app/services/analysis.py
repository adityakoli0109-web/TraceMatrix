from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from statistics import mean, pstdev
from typing import Any

import networkx as nx
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.ethutil import raw_to_decimal_string
from app.models import AnalysisResult, AnalysisRun, CandidateLink, GraphEdge, OsintEvidence

ALGO_VERSION = "qce-1.0.0"
DEFAULT_WINDOW_SECONDS = 3600


def temporal_deltas(timestamps: list[datetime]) -> dict[str, Any]:
    ordered = sorted([ts.astimezone(UTC) for ts in timestamps if ts is not None])
    deltas = []
    for first, second in zip(ordered, ordered[1:], strict=False):
        deltas.append((second - first).total_seconds())
    if not deltas:
        return {"count": 0, "deltas_seconds": [], "mean": None, "stdev": None}
    return {
        "count": len(deltas),
        "deltas_seconds": deltas,
        "mean": mean(deltas),
        "stdev": pstdev(deltas) if len(deltas) > 1 else 0.0,
    }


def timing_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    ma, mb = mean(a), mean(b)
    denom = max(ma, mb, 1.0)
    return max(0.0, 1.0 - abs(ma - mb) / denom)


def build_graph(edges: list[GraphEdge]) -> nx.DiGraph:
    graph = nx.DiGraph()
    for edge in edges:
        if not edge.to_address:
            continue
        weight = float(edge.value_raw or 0)
        if graph.has_edge(edge.from_address, edge.to_address):
            graph[edge.from_address][edge.to_address]["weight"] += weight
            graph[edge.from_address][edge.to_address]["count"] += 1
            graph[edge.from_address][edge.to_address]["tx_hashes"].append(edge.tx_hash)
        else:
            graph.add_edge(
                edge.from_address,
                edge.to_address,
                weight=weight,
                count=1,
                tx_hashes=[edge.tx_hash],
            )
    return graph


def graph_metrics(graph: nx.DiGraph) -> dict[str, Any]:
    undirected = graph.to_undirected()
    communities = []
    if undirected.number_of_nodes() > 0:
        comms = nx.algorithms.community.greedy_modularity_communities(undirected)
        communities = [sorted(list(c)) for c in comms]
    nodes = []
    for node in sorted(graph.nodes):
        inflow = sum(data.get("weight", 0) for _, _, data in graph.in_edges(node, data=True))
        outflow = sum(data.get("weight", 0) for _, _, data in graph.out_edges(node, data=True))
        nodes.append(
            {
                "address": node,
                "in_degree": graph.in_degree(node),
                "out_degree": graph.out_degree(node),
                "tx_count": graph.in_degree(node) + graph.out_degree(node),
                "inflow_wei": str(int(inflow)),
                "outflow_wei": str(int(outflow)),
                "inflow_eth": raw_to_decimal_string(int(inflow), 18),
                "outflow_eth": raw_to_decimal_string(int(outflow), 18),
            }
        )
    components = [sorted(list(c)) for c in nx.weakly_connected_components(graph)]
    return {
        "nodes": nodes,
        "communities": communities,
        "components": components,
        "edge_count": graph.number_of_edges(),
        "notice": "Graph connectivity does not prove common ownership.",
    }


def shortest_path(graph: nx.DiGraph, source: str, target: str) -> list[str]:
    try:
        return nx.shortest_path(graph, source.lower(), target.lower())
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return []


def shared_counterparties(graph: nx.DiGraph, a: str, b: str) -> list[str]:
    na = set(graph.predecessors(a)) | set(graph.successors(a))
    nb = set(graph.predecessors(b)) | set(graph.successors(b))
    return sorted(na & nb)


def score_candidate(
    *,
    direct_match: bool,
    temporal: float,
    graph_strength: float,
    behavioral: float,
    reliability: float,
    corroboration: float,
    contradiction: float,
) -> dict[str, Any]:
    weights = {
        "direct_indicator": 0.28,
        "temporal": 0.12,
        "graph": 0.18,
        "behavioral": 0.12,
        "reliability": 0.12,
        "corroboration": 0.10,
        "contradiction": 0.08,
    }
    components = {
        "direct_indicator": 1.0 if direct_match else 0.0,
        "temporal": max(0.0, min(temporal, 1.0)),
        "graph": max(0.0, min(graph_strength, 1.0)),
        "behavioral": max(0.0, min(behavioral, 1.0)),
        "reliability": max(0.0, min(reliability, 1.0)),
        "corroboration": max(0.0, min(corroboration, 1.0)),
        "contradiction": max(0.0, min(contradiction, 1.0)),
    }
    overall = (
        components["direct_indicator"] * weights["direct_indicator"]
        + components["temporal"] * weights["temporal"]
        + components["graph"] * weights["graph"]
        + components["behavioral"] * weights["behavioral"]
        + components["reliability"] * weights["reliability"]
        + components["corroboration"] * weights["corroboration"]
        - components["contradiction"] * weights["contradiction"]
    )
    overall = round(max(0.0, min(overall, 1.0)), 4)
    if not direct_match and overall < 0.15:
        label = "insufficient_evidence"
        narrative = "Insufficient evidence."
    elif components["contradiction"] >= 0.7:
        label = "contradicted_hypothesis"
        narrative = "Contradicted hypothesis — independent observations conflict with the proposed link."
    elif direct_match:
        label = "direct_indicator_match"
        narrative = "Observed fact: a public source mentions this address. That is not identity verification."
    elif overall >= 0.45:
        label = "investigative_lead"
        narrative = "Investigative lead / statistical association. Heuristic only — not a probability of identity."
    else:
        label = "unverified_attribution"
        narrative = "Unverified attribution. Treat as a lead for review, not a confirmed relationship."
    explanation = (
        f"Heuristic score {overall} using qce-1.0.0. Components: "
        + ", ".join(f"{k}={v:.2f}" for k, v in components.items())
        + ". This is a prioritization heuristic, not a calibrated identity probability."
    )
    return {
        "overall": overall,
        "components": components,
        "label": label,
        "explanation": explanation,
        "narrative": narrative,
    }


def analyze_investigation(db: Session, investigation_id: str, user_id: str | None = None) -> dict[str, Any]:
    edges = db.scalars(select(GraphEdge).where(GraphEdge.investigation_id == investigation_id)).all()
    evidence = db.scalars(select(OsintEvidence).where(OsintEvidence.investigation_id == investigation_id)).all()
    graph = build_graph(edges)
    metrics = graph_metrics(graph)
    timestamps = [e.timestamp for e in edges if e.timestamp]
    temporal = temporal_deltas(timestamps)

    tx_times: dict[str, list[datetime]] = defaultdict(list)
    amounts: dict[str, list[int]] = defaultdict(list)
    for edge in edges:
        if edge.timestamp:
            tx_times[edge.from_address].append(edge.timestamp)
            tx_times[edge.to_address].append(edge.timestamp)
        amounts[edge.from_address].append(int(edge.value_raw or 0))
        amounts[edge.to_address].append(int(edge.value_raw or 0))

    run = AnalysisRun(
        investigation_id=investigation_id,
        algorithm_version=ALGO_VERSION,
        configuration={"temporal_window_seconds": DEFAULT_WINDOW_SECONDS, "weights": "qce-1.0.0"},
        input_refs={"edge_count": len(edges), "evidence_count": len(evidence)},
        created_by=user_id,
    )
    db.add(run)
    db.flush()

    db.execute(delete(CandidateLink).where(CandidateLink.investigation_id == investigation_id))
    candidates = []
    observed_addresses = {n["address"] for n in metrics["nodes"]}
    for item in evidence:
        address = (item.indicator or "").lower()
        if not address:
            continue
        in_graph = address in observed_addresses
        temporal_score = 0.0
        matched_events = []
        if item.original_timestamp and timestamps:
            for ts in timestamps:
                delta = abs((ts - item.original_timestamp).total_seconds())
                if delta <= DEFAULT_WINDOW_SECONDS:
                    temporal_score = max(temporal_score, 1.0 - delta / DEFAULT_WINDOW_SECONDS)
                    matched_events.append({"tx_timestamp": ts.isoformat(), "delta_seconds": delta})
        graph_strength = 0.6 if in_graph else 0.0
        if in_graph:
            node = next(n for n in metrics["nodes"] if n["address"] == address)
            graph_strength = min(1.0, 0.3 + 0.05 * node["tx_count"])
        reliability = 0.4 if item.source_type == "github" else 0.35
        contradiction = 0.0
        if item.original_timestamp and timestamps:
            min_ts, max_ts = min(timestamps), max(timestamps)
            if item.original_timestamp < min_ts - timedelta(days=365 * 5):
                contradiction = 0.4
        scored = score_candidate(
            direct_match=in_graph and bool(address),
            temporal=temporal_score,
            graph_strength=graph_strength,
            behavioral=timing_similarity(
                [ (tx_times[address][i+1]-tx_times[address][i]).total_seconds() for i in range(len(tx_times[address])-1) ] if len(tx_times[address]) > 1 else [],
                [ (a - b).total_seconds() for a, b in zip(sorted(timestamps)[1:], sorted(timestamps), strict=False) ] if len(timestamps) > 1 else [],
            ),
            reliability=reliability,
            corroboration=1.0 if in_graph else 0.0,
            contradiction=contradiction,
        )
        supporting = []
        contradictory = []
        if in_graph:
            supporting.append(
                {
                    "type": "observed_fact",
                    "text": "Address appears both in public OSINT text and in the ingested transaction graph.",
                }
            )
        supporting.append(
            {
                "type": "direct_indicator_match" if address else "unverified_attribution",
                "text": f"Public source {item.source_url} provided indicator {address or '(none)'}.",
            }
        )
        if matched_events:
            supporting.append({"type": "statistical_association", "text": f"{len(matched_events)} events within the temporal window."})
        if contradiction:
            contradictory.append({"type": "contradicted_hypothesis", "text": "OSINT timestamp is far outside the observed chain window."})
        if not in_graph:
            contradictory.append(
                {
                    "type": "insufficient_evidence",
                    "text": "Indicator was not observed in the ingested graph neighborhood.",
                }
            )
        row = CandidateLink(
            investigation_id=investigation_id,
            wallet_address=address,
            relationship_type="osint_indicator_overlap",
            supporting=supporting,
            contradictory=contradictory,
            temporal_score=scored["components"]["temporal"],
            graph_score=scored["components"]["graph"],
            reliability_score=scored["components"]["reliability"],
            overall_score=scored["overall"],
            label=scored["label"],
            explanation=scored["explanation"],
            evidence_ids=[item.id],
            component_scores=scored["components"],
            verification_status="unreviewed",
        )
        db.add(row)
        candidates.append(row)

    payload = {
        "algorithm_version": ALGO_VERSION,
        "temporal": temporal,
        "graph": metrics,
        "candidate_count": len(candidates),
        "generated_at": datetime.now(UTC).isoformat(),
        "disclaimer": "Scores are explainable heuristics for triage, not identity probabilities.",
    }
    db.add(AnalysisResult(run_id=run.id, investigation_id=investigation_id, result_type="full", payload=payload))
    db.flush()
    return {"run_id": run.id, "payload": payload}
