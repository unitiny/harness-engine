"""Tests for acceptance.core.layers module."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from acceptance.core.layers import (
    L1EnvironmentChecker,
    L2NetworkChecker,
    L3ConsoleChecker,
    L4DOMChecker,
    L5PersistenceChecker,
    Layer,
    get_checker,
)
from acceptance.core.result import LayerResult


class TestLayerOrder:
    """Tests for the Layer enum ordering."""

    def test_layer_order(self):
        assert Layer.L1_ENVIRONMENT.order == 1
        assert Layer.L2_NETWORK.order == 2
        assert Layer.L3_CONSOLE.order == 3
        assert Layer.L4_DOM.order == 4
        assert Layer.L5_PERSISTENCE.order == 5


class TestLayerResult:
    """Tests for the LayerResult dataclass."""

    def test_layer_result_creation(self):
        result = LayerResult(layer_name="L1", passed=True, message="OK")
        assert result.layer_name == "L1"
        assert result.passed is True
        assert result.message == "OK"

    def test_layer_result_str_passed(self):
        result = LayerResult(layer_name="L1", passed=True, message="All good")
        text = str(result)
        assert "PASS" in text
        assert "L1" in text

    def test_layer_result_str_failed(self):
        result = LayerResult(layer_name="L2", passed=False, message="Error found")
        text = str(result)
        assert "FAIL" in text
        assert "L2" in text


class TestGetChecker:
    """Tests for the get_checker factory function."""

    def test_get_checker_l1(self):
        checker = get_checker(Layer.L1_ENVIRONMENT)
        assert isinstance(checker, L1EnvironmentChecker)

    def test_get_checker_l2(self):
        checker = get_checker(Layer.L2_NETWORK)
        assert isinstance(checker, L2NetworkChecker)

    def test_get_checker_l3(self):
        checker = get_checker(Layer.L3_CONSOLE)
        assert isinstance(checker, L3ConsoleChecker)

    def test_get_checker_l4(self):
        checker = get_checker(Layer.L4_DOM)
        assert isinstance(checker, L4DOMChecker)

    def test_get_checker_l5(self):
        checker = get_checker(Layer.L5_PERSISTENCE)
        assert isinstance(checker, L5PersistenceChecker)

    def test_get_checker_invalid(self):
        """get_checker with a non-registered layer raises ValueError."""
        from acceptance.core.layers import LAYER_CHECKERS

        from unittest.mock import patch

        # Patch LAYER_CHECKERS to return None for a given layer key,
        # simulating an unregistered layer.
        with patch.dict(LAYER_CHECKERS, {}, clear=True):
            with pytest.raises(ValueError, match="No checker registered"):
                get_checker(Layer.L1_ENVIRONMENT)
