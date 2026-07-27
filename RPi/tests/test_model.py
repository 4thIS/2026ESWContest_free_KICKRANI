from pi.infer.model import StubModel


def test_stub_model_returns_fixed_class():
    assert StubModel("gravel").predict(window=[]) == "gravel"


def test_stub_model_default_is_asphalt():
    assert StubModel().predict([]) == "asphalt"
