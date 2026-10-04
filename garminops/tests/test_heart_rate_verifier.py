import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('hr_verifier',
    Path(__file__).resolve().parents[2] / 'scripts/verify_garmin_heart_rate.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.mark.skip(reason='KI-001: user stopped null-clearing/restoration tests; reopen only on explicit request.')
@pytest.mark.parametrize('value', [None, 0, False, -1])
def test_never_test_values_without_verified_restore_contract(value):
    with pytest.raises(ValueError, match='can be restored'):
        module.reversible_change({'sport':'DEFAULT', 'restingHeartRateUsed':value},
                                 'restingHeartRateUsed', 1)


def test_invalid_boundary_change_is_rejected_before_live_test():
    profile = {'sport':'DEFAULT', **{f'zone{i}Floor':100+i*10 for i in range(1,6)}}
    with pytest.raises(ValueError, match='increase strictly'):
        module.reversible_change(profile, 'zone1Floor', 10)
    assert module.reversible_change(profile, 'zone1Floor', 1) == {'zone1Floor':111}
    assert profile['zone1Floor'] == 110
