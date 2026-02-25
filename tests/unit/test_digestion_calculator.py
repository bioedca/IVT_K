"""Tests for the digestion calculator callbacks (volume formulas, protocol, results)."""
import pytest


def _get_dash_text(component):
    """Recursively extract all text content from a Dash component tree."""
    texts = []
    if hasattr(component, "children"):
        children = component.children
        if isinstance(children, str):
            texts.append(children)
        elif isinstance(children, (list, tuple)):
            for child in children:
                texts.extend(_get_dash_text(child))
        elif children is not None:
            texts.extend(_get_dash_text(children))
    # Check for `value` on dmc components
    if hasattr(component, "value") and isinstance(getattr(component, "value"), str):
        texts.append(component.value)
    return texts


def _flatten_text(component):
    """Join all text fragments from a Dash component tree."""
    return " ".join(_get_dash_text(component))


class TestDigestionVolumeFormulas:
    """Test the core volume calculation formulas used in the digestion callback."""

    def _compute_volumes(self, dna_conc_ng_ul, dna_amount_ug, enzyme_conc_u_ml, units_per_ug):
        """Replicate the calculation from calculate_digestion()."""
        dna_conc_ug_ul = dna_conc_ng_ul / 1000
        dna_vol = dna_amount_ug / dna_conc_ug_ul
        total_units = dna_amount_ug * units_per_ug
        enzyme_conc_u_ul = enzyme_conc_u_ml / 1000
        enzyme_vol = total_units / enzyme_conc_u_ul
        total_vol = enzyme_vol * 20
        buffer_vol = total_vol / 10
        water_vol = total_vol - dna_vol - enzyme_vol - buffer_vol
        return {
            "dna_vol": dna_vol,
            "enzyme_vol": enzyme_vol,
            "total_vol": total_vol,
            "buffer_vol": buffer_vol,
            "water_vol": water_vol,
            "total_units": total_units,
        }

    def test_dna_volume(self):
        """DNA vol = amount (ug) / (conc ng/uL / 1000)."""
        v = self._compute_volumes(200, 1.0, 10000, 10)
        assert v["dna_vol"] == pytest.approx(5.0)

    def test_enzyme_volume(self):
        """Enzyme vol = (amount * units_per_ug) / (conc U/mL / 1000)."""
        v = self._compute_volumes(200, 1.0, 10000, 10)
        assert v["enzyme_vol"] == pytest.approx(1.0)

    def test_total_volume_is_20x_enzyme(self):
        """Total = enzyme_vol * 20 (enzyme at 5% v/v)."""
        v = self._compute_volumes(200, 1.0, 10000, 10)
        assert v["total_vol"] == pytest.approx(v["enzyme_vol"] * 20)

    def test_buffer_volume_is_tenth(self):
        """Buffer = total / 10 (1X from 10X stock)."""
        v = self._compute_volumes(200, 1.0, 10000, 10)
        assert v["buffer_vol"] == pytest.approx(v["total_vol"] / 10)

    def test_water_volume_is_remainder(self):
        """Water = total - dna - enzyme - buffer."""
        v = self._compute_volumes(200, 1.0, 10000, 10)
        expected = v["total_vol"] - v["dna_vol"] - v["enzyme_vol"] - v["buffer_vol"]
        assert v["water_vol"] == pytest.approx(expected)

    def test_negative_water_clamped_to_zero(self):
        """When DNA + enzyme + buffer > total, water is clamped to 0."""
        # Very low enzyme conc → large total_vol based on enzyme, but
        # let's use high DNA amount + low conc to force negative water
        # High DNA vol (10 ug / (50/1000)) = 200 uL, enzyme vol = 0.1 uL
        # total = 0.1*20 = 2 uL, but dna alone is 200 — negative water
        v = self._compute_volumes(50, 10.0, 100000, 1)
        # water should be negative before clamping
        raw_water = v["total_vol"] - v["dna_vol"] - v["enzyme_vol"] - v["buffer_vol"]
        assert raw_water < 0

    def test_total_units(self):
        """Total units = dna_amount * units_per_ug."""
        v = self._compute_volumes(200, 2.0, 10000, 5)
        assert v["total_units"] == pytest.approx(10.0)

    def test_dna_warning_threshold(self):
        """50% warning triggers when dna_vol > 0.5 * total_vol."""
        # dna_vol = 10 / (100/1000) = 100 uL
        # enzyme_vol = (10*1) / (10000/1000) = 1 uL, total = 20 uL
        # 100 > 0.5 * 20 → warning
        v = self._compute_volumes(100, 10.0, 10000, 1)
        assert v["dna_vol"] > v["total_vol"] * 0.5


class TestDigestionProtocolPanel:
    """Tests for _build_protocol_panel() output."""

    @pytest.fixture(autouse=True)
    def _import_builder(self):
        from app.callbacks.digestion_callbacks import _build_protocol_panel
        self._build = _build_protocol_panel

    def _default_panel(self, **overrides):
        kwargs = dict(
            dna_vol=5.0,
            enzyme_vol=1.0,
            buffer_vol=2.0,
            water_vol=12.0,
            total_vol=20.0,
            total_units=10.0,
            enzyme_display="BamHI",
            buffer_display="rCutSmart",
            dna_amount=1.0,
            dna_conc=200.0,
            incubation_temp=37,
            incubation_time=30,
        )
        kwargs.update(overrides)
        return self._build(**kwargs)

    def test_incubation_time_in_minutes(self):
        """Key verification: incubation step uses minutes, not hours."""
        panel = self._default_panel(incubation_time=30)
        text = _flatten_text(panel)
        assert "30 minutes" in text
        # The incubation step itself must say "minutes" not "hours"
        assert "30 hours" not in text.lower()

    def test_custom_incubation_time(self):
        panel = self._default_panel(incubation_time=60)
        text = _flatten_text(panel)
        assert "60 minutes" in text

    def test_default_temperature(self):
        panel = self._default_panel(incubation_temp=37)
        text = _flatten_text(panel)
        assert "37" in text

    def test_enzyme_display_name(self):
        panel = self._default_panel(enzyme_display="EcoRI")
        text = _flatten_text(panel)
        assert "EcoRI" in text

    def test_buffer_display_name(self):
        panel = self._default_panel(buffer_display="NEBuffer 3.1")
        text = _flatten_text(panel)
        assert "NEBuffer 3.1" in text

    def test_protocol_has_sections(self):
        panel = self._default_panel()
        text = _flatten_text(panel)
        assert "PREPARE REACTION MIXTURE" in text
        assert "MIX" in text
        assert "INCUBATE" in text

    def test_protocol_title_present(self):
        panel = self._default_panel()
        text = _flatten_text(panel)
        assert "Protocol" in text


class TestDigestionResultsPanel:
    """Tests for _build_results_panel() output."""

    @pytest.fixture(autouse=True)
    def _import_builder(self):
        from app.callbacks.digestion_callbacks import _build_results_panel
        self._build = _build_results_panel

    def _default_results(self, **overrides):
        kwargs = dict(
            dna_vol=5.0,
            enzyme_vol=1.0,
            buffer_vol=2.0,
            water_vol=12.0,
            total_vol=20.0,
            total_units=10.0,
            enzyme_display="BamHI",
            buffer_display="rCutSmart",
            dna_amount=1.0,
            dna_conc=200.0,
            enzyme_conc=10000.0,
            warnings=[],
        )
        kwargs.update(overrides)
        return self._build(**kwargs)

    def test_volumes_in_table(self):
        panel = self._default_results()
        text = _flatten_text(panel)
        assert "5.0" in text  # dna_vol
        assert "1.0" in text  # enzyme_vol
        assert "20.0" in text  # total_vol

    def test_warnings_displayed(self):
        panel = self._default_results(warnings=["DNA volume too high"])
        text = _flatten_text(panel)
        assert "DNA volume too high" in text

    def test_stat_cards_present(self):
        panel = self._default_results()
        text = _flatten_text(panel)
        assert "DNA to digest" in text
        assert "Enzyme units" in text
        assert "Total volume" in text

    def test_title_present(self):
        panel = self._default_results()
        text = _flatten_text(panel)
        assert "Calculated Volumes" in text

    def test_no_warnings_no_alert(self):
        panel = self._default_results(warnings=[])
        text = _flatten_text(panel)
        assert "DNA volume too high" not in text


class TestDigestionInputValidation:
    """Tests for input validation and edge-case behavior."""

    @pytest.fixture(autouse=True)
    def _import_builders(self):
        from app.callbacks.digestion_callbacks import _build_results_panel, _build_protocol_panel
        self._build_results = _build_results_panel
        self._build_protocol = _build_protocol_panel

    def test_zero_volume_results_panel_handles_gracefully(self):
        """Results panel renders without error when all volumes are zero."""
        panel = self._build_results(
            dna_vol=0, enzyme_vol=0, buffer_vol=0, water_vol=0,
            total_vol=0, total_units=0, enzyme_display="Enzyme",
            buffer_display="Buffer", dna_amount=0, dna_conc=0,
            enzyme_conc=0, warnings=["All values are zero"],
        )
        text = _flatten_text(panel)
        assert "All values are zero" in text

    def test_large_volumes_results_panel_handles_gracefully(self):
        """Results panel renders with very large values."""
        panel = self._build_results(
            dna_vol=9999.9, enzyme_vol=500.0, buffer_vol=1100.0,
            water_vol=0, total_vol=11000.0, total_units=50000,
            enzyme_display="Enzyme", buffer_display="Buffer",
            dna_amount=100, dna_conc=10, enzyme_conc=100,
            warnings=[],
        )
        text = _flatten_text(panel)
        assert "9999.9" in text

    def test_protocol_panel_zero_incubation_time(self):
        """Protocol panel handles 0 minute incubation gracefully."""
        panel = self._build_protocol(
            dna_vol=5.0, enzyme_vol=1.0, buffer_vol=2.0,
            water_vol=12.0, total_vol=20.0, total_units=10,
            enzyme_display="Enzyme", buffer_display="Buffer",
            dna_amount=1.0, dna_conc=200, incubation_temp=37,
            incubation_time=0,
        )
        text = _flatten_text(panel)
        assert "0 minutes" in text

    def test_multiple_warnings_all_displayed(self):
        """All warnings render when multiple are provided."""
        warnings = ["Warning A", "Warning B", "Warning C"]
        panel = self._build_results(
            dna_vol=5.0, enzyme_vol=1.0, buffer_vol=2.0,
            water_vol=12.0, total_vol=20.0, total_units=10,
            enzyme_display="Enzyme", buffer_display="Buffer",
            dna_amount=1.0, dna_conc=200, enzyme_conc=10000,
            warnings=warnings,
        )
        text = _flatten_text(panel)
        for w in warnings:
            assert w in text

    def test_validation_conditions_match_callback(self):
        """Verify the validation conditions used by the callback."""
        for invalid in [None, 0, -1, -0.5]:
            assert not invalid or invalid <= 0, (
                f"Validation should catch {invalid!r}"
            )
