from confluence.api.provider import select_provider
from confluence.data.providers.mock_provider import MockDataProvider
from confluence.data.providers.real_provider import RealDataProvider


def test_select_provider_defaults_and_mock_value_give_mock():
    provider, label = select_provider("mock")
    assert isinstance(provider, MockDataProvider)
    assert label == "mock"


def test_select_provider_real_value_gives_real():
    provider, label = select_provider("real")
    assert isinstance(provider, RealDataProvider)
    assert label == "real"


def test_select_provider_is_case_and_whitespace_insensitive():
    provider, label = select_provider("  REAL  ")
    assert isinstance(provider, RealDataProvider)
    assert label == "real"


def test_select_provider_unknown_value_falls_back_to_mock():
    provider, label = select_provider("something-typo'd")
    assert isinstance(provider, MockDataProvider)
    assert label == "mock"
