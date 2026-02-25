"""Tests for app.analysis.data_structure model tier selection and detection."""
import pytest
import pandas as pd

from app.analysis.data_structure import (
    DataStructure,
    DataStructureAnalyzer,
    ModelMetadata,
    ModelTier,
)


class TestDataStructureDetection:
    """Tests for DataStructureAnalyzer.detect()."""

    def test_single_session_single_plate(self):
        df = pd.DataFrame({"session_id": [1, 1, 1], "plate_id": [10, 10, 10]})
        ds = DataStructureAnalyzer.detect(df)
        assert ds.n_sessions == 1
        assert ds.n_plates == 1
        assert ds.max_plates_per_session == 1

    def test_multiple_sessions_single_plate_each(self):
        df = pd.DataFrame({"session_id": [1, 1, 2, 2], "plate_id": [10, 10, 20, 20]})
        ds = DataStructureAnalyzer.detect(df)
        assert ds.n_sessions == 2
        assert ds.n_plates == 2
        assert ds.max_plates_per_session == 1

    def test_single_session_multiple_plates(self):
        df = pd.DataFrame({"session_id": [1, 1, 1], "plate_id": [10, 20, 30]})
        ds = DataStructureAnalyzer.detect(df)
        assert ds.n_sessions == 1
        assert ds.n_plates == 3
        assert ds.max_plates_per_session == 3

    def test_multiple_sessions_multiple_plates(self):
        df = pd.DataFrame({
            "session_id": [1, 1, 2, 2],
            "plate_id": [10, 20, 30, 40],
        })
        ds = DataStructureAnalyzer.detect(df)
        assert ds.n_sessions == 2
        assert ds.n_plates == 4
        assert ds.max_plates_per_session == 2

    def test_uneven_plate_counts(self):
        """Sessions can have different numbers of plates."""
        df = pd.DataFrame({
            "session_id": [1, 1, 1, 2],
            "plate_id": [10, 20, 30, 40],
        })
        ds = DataStructureAnalyzer.detect(df)
        assert ds.n_sessions == 2
        assert ds.max_plates_per_session == 3
        assert ds.plates_per_session[1] == 3
        assert ds.plates_per_session[2] == 1

    def test_plates_per_session_dict(self):
        df = pd.DataFrame({
            "session_id": [1, 1, 2, 2, 3],
            "plate_id": [10, 20, 30, 40, 50],
        })
        ds = DataStructureAnalyzer.detect(df)
        assert ds.plates_per_session == {1: 2, 2: 2, 3: 1}

    def test_detect_empty_dataframe(self):
        """Empty DataFrame returns zero-count DataStructure."""
        df = pd.DataFrame({"session_id": pd.Series(dtype=int), "plate_id": pd.Series(dtype=int)})
        ds = DataStructureAnalyzer.detect(df)
        assert ds.n_sessions == 0
        assert ds.n_plates == 0
        assert ds.max_plates_per_session == 0


class TestModelTierSelection:
    """Tests for DataStructureAnalyzer.select_model_tier()."""

    def test_tier_1_single_session_single_plate(self):
        ds = DataStructure(n_sessions=1, n_plates=1, max_plates_per_session=1)
        meta = DataStructureAnalyzer.select_model_tier(ds)
        assert meta.tier == ModelTier.TIER_1_RESIDUAL_ONLY
        assert not meta.estimates_session_variance
        assert not meta.estimates_plate_variance
        assert meta.estimates_residual_variance

    def test_tier_2a_multiple_sessions_one_plate_each(self):
        ds = DataStructure(n_sessions=3, n_plates=3, max_plates_per_session=1)
        meta = DataStructureAnalyzer.select_model_tier(ds)
        assert meta.tier == ModelTier.TIER_2A_SESSION
        assert meta.estimates_session_variance
        assert not meta.estimates_plate_variance

    def test_tier_2b_one_session_multiple_plates(self):
        ds = DataStructure(n_sessions=1, n_plates=3, max_plates_per_session=3)
        meta = DataStructureAnalyzer.select_model_tier(ds)
        assert meta.tier == ModelTier.TIER_2B_PLATE
        assert not meta.estimates_session_variance
        assert meta.estimates_plate_variance

    def test_tier_3_full_hierarchy(self):
        ds = DataStructure(n_sessions=3, n_plates=6, max_plates_per_session=2)
        meta = DataStructureAnalyzer.select_model_tier(ds)
        assert meta.tier == ModelTier.TIER_3_FULL
        assert meta.estimates_session_variance
        assert meta.estimates_plate_variance
        assert meta.pending_components == []

    def test_tier_1_pending_components(self):
        ds = DataStructure(n_sessions=1, n_plates=1, max_plates_per_session=1)
        meta = DataStructureAnalyzer.select_model_tier(ds)
        assert meta.pending_components == ["session variance", "plate variance"]

    def test_tier_2a_pending_components(self):
        ds = DataStructure(n_sessions=2, n_plates=2, max_plates_per_session=1)
        meta = DataStructureAnalyzer.select_model_tier(ds)
        assert meta.pending_components == ["plate variance"]

    def test_tier_2b_pending_components(self):
        ds = DataStructure(n_sessions=1, n_plates=2, max_plates_per_session=2)
        meta = DataStructureAnalyzer.select_model_tier(ds)
        assert meta.pending_components == ["session variance"]

    def test_empty_data_raises_value_error(self):
        ds = DataStructure(n_sessions=0, n_plates=0, max_plates_per_session=0)
        with pytest.raises(ValueError, match="Cannot select model tier for empty data"):
            DataStructureAnalyzer.select_model_tier(ds)

    def test_frequentist_message_differs(self):
        ds = DataStructure(n_sessions=1, n_plates=1, max_plates_per_session=1)
        bayesian = DataStructureAnalyzer.select_model_tier(ds, method="bayesian")
        freq = DataStructureAnalyzer.select_model_tier(ds, method="frequentist")
        assert "OLS" in freq.user_message
        assert "OLS" not in bayesian.user_message
        # Bayesian message should contain hierarchical-specific language
        assert "hierarchical" in bayesian.user_message.lower()

    def test_tier_3_message_same_for_both_methods(self):
        ds = DataStructure(n_sessions=2, n_plates=4, max_plates_per_session=2)
        bayesian = DataStructureAnalyzer.select_model_tier(ds, method="bayesian")
        freq = DataStructureAnalyzer.select_model_tier(ds, method="frequentist")
        assert bayesian.user_message == freq.user_message


class TestModelMetadata:
    """Tests for ModelMetadata dataclass."""

    def test_to_dict_fields(self):
        meta = ModelMetadata(
            tier=ModelTier.TIER_3_FULL,
            n_sessions=3,
            n_plates=6,
            max_plates_per_session=2,
            estimates_session_variance=True,
            estimates_plate_variance=True,
            user_message="All components estimated.",
            pending_components=[],
        )
        d = meta.to_dict()
        assert d["tier"] == "tier_3"
        assert d["n_sessions"] == 3
        assert d["n_plates"] == 6
        assert d["estimates_session_variance"] is True
        assert d["estimates_plate_variance"] is True
        assert d["estimates_residual_variance"] is True
        assert d["pending_components"] == []
        assert "tier_name" in d

    def test_tier_display_names(self):
        for tier, expected_fragment in [
            (ModelTier.TIER_1_RESIDUAL_ONLY, "Tier 1"),
            (ModelTier.TIER_2A_SESSION, "Tier 2a"),
            (ModelTier.TIER_2B_PLATE, "Tier 2b"),
            (ModelTier.TIER_3_FULL, "Tier 3"),
        ]:
            meta = ModelMetadata(
                tier=tier, n_sessions=1, n_plates=1,
                max_plates_per_session=1,
                estimates_session_variance=False,
                estimates_plate_variance=False,
            )
            assert expected_fragment in meta.to_dict()["tier_name"]
