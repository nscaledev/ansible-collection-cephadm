from unittest.mock import patch

import pytest

from ansible_collections.stackhpc.cephadm.plugins.modules import cephadm_pool
from . import cephadm_test_common


COMPRESSION = {'compression_algorithm': 'lz4',
               'compression_mode': 'aggressive'}


def run_pool(params, responses, fails=False):
    cephadm_test_common.set_module_args(dict(name='test-pool', **params))
    exception = (cephadm_test_common.AnsibleFailJson if fails
                 else cephadm_test_common.AnsibleExitJson)
    with patch('ansible.module_utils.basic.AnsibleModule.run_command',
               side_effect=responses) as command, \
            patch('ansible.module_utils.basic.AnsibleModule.exit_json',
                  side_effect=cephadm_test_common.exit_json), \
            patch('ansible.module_utils.basic.AnsibleModule.fail_json',
                  side_effect=cephadm_test_common.fail_json):
        with pytest.raises(exception) as result:
            cephadm_pool.main()
    commands = [call.args[0][8:] for call in command.call_args_list]
    return result.value.args[0], commands


@pytest.mark.parametrize('pool_type', ['replicated', 'erasure'])
@pytest.mark.parametrize('compression', [
    {}, COMPRESSION, {'compression_algorithm': 'lz4'},
    {'compression_mode': 'aggressive'}, {'compression_mode': 'none'},
])
def test_compression_applied_when_creating_pool(pool_type, compression):
    params = dict(pool_type=pool_type, application='rbd', **compression)
    result, commands = run_pool(
        params, [(2, '', 'pool does not exist')]
        + [(0, '', '')] * (2 + len(compression)))

    assert result['changed']
    assert result['rc'] == 0
    assert commands[1][0] == 'create'
    assert commands[2] == ['application', 'enable', 'test-pool', 'rbd']
    assert commands[3:] == [
        ['set', 'test-pool', key, value]
        for key, value in compression.items()
    ]


def test_failed_creation_does_not_apply_compression():
    result, commands = run_pool(
        dict(application='rbd', **COMPRESSION),
        [(2, '', 'pool does not exist'), (1, '', 'creation failed')],
        fails=True)

    assert not result['changed']
    assert result['rc'] == 1
    assert result['stderr'] == 'creation failed'
    assert len(commands) == 2


@pytest.mark.parametrize('successful_sets', [0, 1])
def test_compression_failure_is_reported(successful_sets):
    result, commands = run_pool(
        COMPRESSION,
        [(2, '', 'pool does not exist'), (0, '', '')]
        + [(0, '', '')] * successful_sets
        + [(1, '', 'compression failed')], fails=True)

    assert result['changed']
    assert result['rc'] == 1
    assert result['stderr'] == 'compression failed'
    assert len(commands) == 3 + successful_sets


def test_existing_pool_with_matching_compression_is_unchanged():
    details = dict(pg_num=32, pg_placement_num=32, size=3,
                   pg_autoscale_mode='on', target_size_ratio=None,
                   application='rbd', **COMPRESSION)
    with patch.object(cephadm_pool, 'get_pool_details',
                      return_value=(0, [], details, '')):
        result, commands = run_pool(
            dict(size='3', application='rbd', **COMPRESSION), [(0, '', '')])

    assert not result['changed']
    assert result['rc'] == 0
    assert len(commands) == 1
