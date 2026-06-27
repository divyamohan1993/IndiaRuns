"""No train/serve skew: features.extract is a pure deterministic function of the record,
so the offline (Plane A) matrix and the rank-time (Plane B) re-derivation are byte-equal.
Also pins the feature vector width, names, and monotone-sign coverage."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import features  # noqa: E402
from tests import fixtures  # noqa: E402


def test_feature_meta_consistent():
    meta = features.feature_meta()
    assert meta["feature_names"] == features.FEATURE_NAMES
    assert meta["n_features"] == len(features.FEATURE_NAMES)
    # every feature has a monotone sign in {-1, 0, +1}
    for n in features.FEATURE_NAMES:
        assert features.MONOTONE[n] in (-1, 0, 1)
    # salary inversion is never a feature
    assert not any("salary" in n for n in features.FEATURE_NAMES)


def test_extract_is_deterministic():
    c = fixtures.base_candidate()
    v1 = features.extract(fixtures.clone(c))
    v2 = features.extract(fixtures.clone(c))
    assert v1 == v2
    assert len(v1) == features.N_FEATURES


def test_no_skew_offline_vs_online():
    # "Offline" builds with the same module; "online" re-derives. Must be identical.
    c = fixtures.base_candidate()
    offline = features.extract_det(fixtures.clone(c))
    online = features.extract_det(fixtures.clone(c))
    assert offline == online


def test_semantic_features_default_zero_without_embeddings():
    c = fixtures.base_candidate()
    v = features.extract(c)  # no semantic dict
    idx = {n: i for i, n in enumerate(features.FEATURE_NAMES)}
    for name in ("emb_cos_retrieval", "emb_cos_jd_overall", "lexical_cos_jd", "svd_1"):
        assert v[idx[name]] == 0.0


def test_semantic_features_injected():
    c = fixtures.base_candidate()
    v = features.extract(c, semantic={"emb_cos_jd_overall": 0.7, "lexical_cos_jd": 0.4})
    idx = {n: i for i, n in enumerate(features.FEATURE_NAMES)}
    assert v[idx["emb_cos_jd_overall"]] == 0.7
    assert v[idx["lexical_cos_jd"]] == 0.4


def test_keyword_stuffer_signature():
    # Non-eng title + AI skills => ai_skill_x_non_eng > 0 (the detector fires).
    stuffer = features.extract_det(fixtures.keyword_stuffer_candidate())
    fit = features.extract_det(fixtures.base_candidate())
    assert stuffer["non_eng_title_flag"] == 1.0
    assert stuffer["ai_skill_x_non_eng"] > 0.0
    assert fit["ai_skill_x_non_eng"] == 0.0  # eng title => detector silent


def test_evidence_beats_keywords():
    # The genuine fit has career evidence; the stuffer has none in descriptions.
    fit = features.extract_det(fixtures.base_candidate())
    stuffer = features.extract_det(fixtures.keyword_stuffer_candidate())
    fit_evid = fit["evid_ranking_search_reco"] + fit["evid_built_endto_end"] + fit["evid_production_deploy"]
    stuffer_evid = (stuffer["evid_ranking_search_reco"] + stuffer["evid_built_endto_end"]
                    + stuffer["evid_production_deploy"])
    assert fit_evid > stuffer_evid
