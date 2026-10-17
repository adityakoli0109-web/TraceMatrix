from datetime import UTC, datetime, timedelta

from app.models import GraphEdge
from app.services.analysis import (
    build_graph,
    graph_metrics,
    score_candidate,
    shortest_path,
    temporal_deltas,
    timing_similarity,
)


def test_temporal_deltas():
    t0 = datetime(2024, 1, 1, tzinfo=UTC)
    t1 = t0 + timedelta(seconds=60)
    t2 = t1 + timedelta(seconds=60)
    result = temporal_deltas([t2, t0, t1])
    assert result["deltas_seconds"] == [60, 60]
    assert result["mean"] == 60


def test_graph_metrics_and_path():
    edges = [
        GraphEdge(
            investigation_id="x",
            from_address="0x1111111111111111111111111111111111111111",
            to_address="0x2222222222222222222222222222222222222222",
            tx_hash="0x" + "aa" * 32,
            value_raw=10**18,
        ),
        GraphEdge(
            investigation_id="x",
            from_address="0x2222222222222222222222222222222222222222",
            to_address="0x3333333333333333333333333333333333333333",
            tx_hash="0x" + "bb" * 32,
            value_raw=5 * 10**17,
        ),
    ]
    graph = build_graph(edges)
    metrics = graph_metrics(graph)
    assert metrics["edge_count"] == 2
    assert len(metrics["components"][0]) == 3
    path = shortest_path(
        graph,
        "0x1111111111111111111111111111111111111111",
        "0x3333333333333333333333333333333333333333",
    )
    assert path[-1] == "0x3333333333333333333333333333333333333333"


def test_scoring_labels_and_contradiction():
    insufficient = score_candidate(
        direct_match=False,
        temporal=0,
        graph_strength=0,
        behavioral=0,
        reliability=0,
        corroboration=0,
        contradiction=0,
    )
    assert insufficient["label"] == "insufficient_evidence"
    contradicted = score_candidate(
        direct_match=True,
        temporal=1,
        graph_strength=1,
        behavioral=1,
        reliability=1,
        corroboration=1,
        contradiction=0.9,
    )
    assert contradicted["label"] == "contradicted_hypothesis"
    match = score_candidate(
        direct_match=True,
        temporal=0.8,
        graph_strength=0.6,
        behavioral=0.4,
        reliability=0.4,
        corroboration=1,
        contradiction=0,
    )
    assert match["label"] == "direct_indicator_match"
    assert 0 <= match["overall"] <= 1


def test_timing_similarity():
    assert timing_similarity([60, 60], [62, 58]) > 0.9
    assert timing_similarity([], [1]) == 0
