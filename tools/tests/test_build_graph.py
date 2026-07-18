import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))  # tools/
import build_graph as bg


def _profile():
    return {
        "identity": {"first_name": "Robin", "last_name": "Denis"},
        "domains": [{"id": "quant", "label": {"fr": "Quant", "en": "Quant FR"}},
                    {"id": "risk", "label": {"fr": "Risque", "en": "Risk"}}],
        "experiences": [{"id": "alten", "title": {"fr": "Ingé", "en": "Eng"}, "domains": ["quant"],
                         "relevance": {"quant": 0.8, "general": 0.5}}],
        "education": [{"id": "ece", "title": {"fr": "ECE", "en": "ECE"}}],
        "projects": [{"id": "p1", "name": "P1", "context": "alten", "domains": ["quant", "risk"]}],
        "articles": [{"id": "a1", "title": {"fr": "Art", "en": "Article"}, "domains": ["risk"], "url": "articles/a1.html"}],
        "demos": [{"id": "d1", "title": "D1", "project": "p1"}],
        "skills": {"programming": [{"name": "Python", "used_in": ["alten"], "contexts": ["quant"]}],
                   "radar_scores": {"quant": 0.9}},
        "journey": [{"ref": "experience:alten", "label": {"fr": "Début", "en": "Start"}}],
    }


def test_bi_label_types():
    p = _profile()
    assert bg._bi_label("identity:self", p) == {"fr": "Robin Denis", "en": "Robin Denis"}
    assert bg._bi_label("domain:quant", p) == {"fr": "Quant", "en": "Quant FR"}
    assert bg._bi_label("experience:alten", p) == {"fr": "Ingé", "en": "Eng"}
    assert bg._bi_label("skill:Python", p) == {"fr": "Python", "en": "Python"}
    assert bg._bi_label("demo:d1", p) == {"fr": "D1", "en": "D1"}       # str -> dupliqué
    assert bg._bi_label("journey:0", p) == {"fr": "Début", "en": "Start"}


def test_graph_nodes_bilingual_and_typed():
    p = _profile()
    nodes = bg.graph_nodes(p)
    by_id = {n["id"]: n for n in nodes}
    assert by_id["domain:quant"]["type"] == "domain"
    assert by_id["domain:quant"]["fr"] == "Quant" and by_id["domain:quant"]["en"] == "Quant FR"
    assert "identity:self" in by_id
    # tous les nœuds ont fr+en non vides
    assert all(n["fr"] and n["en"] for n in nodes)


def test_graph_edges_reused():
    p = _profile()
    edges = bg.graph_edges(p)
    rels = {(e["source"], e["target"], e["rel"]) for e in edges}
    assert ("experience:alten", "domain:quant", "has_domain") in rels
    assert ("skill:Python", "experience:alten", "used_in") in rels


def test_layout_deterministic_and_bounded():
    p = _profile()
    nodes, edges = bg.graph_nodes(p), bg.graph_edges(p)
    a = bg.compute_layout(nodes, edges, iterations=50)
    b = bg.compute_layout(nodes, edges, iterations=50)
    assert a == b                                   # déterminisme strict
    assert a["identity:self"] == (500.0, 350.0)     # centre figé
    for (x, y) in a.values():
        assert 10 <= x <= 990 and 10 <= y <= 690    # bornes
        assert x == x and y == y                     # pas de NaN
    assert set(a.keys()) == {n["id"] for n in nodes}
