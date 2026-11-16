import pytest
from pharmaflow.config import HopperConfig

def test_valid_config():
    HopperConfig().validate()

def test_invalid_outlet():
    with pytest.raises(ValueError):
        HopperConfig(outlet_width_m=0.2).validate()
