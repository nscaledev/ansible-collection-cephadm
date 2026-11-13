"""Run SSH guards through Ansible without real host keys."""

import copy
import os
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[4]


@pytest.mark.parametrize("bootstrap_required", [False, True])
@pytest.mark.parametrize("check_mode", [False, True])
def test_ssh_preparation_uses_bootstrap_host_state(
        tmp_path, bootstrap_required, check_mode):
    main = yaml.safe_load((ROOT / "roles/cephadm/tasks/main.yml").read_text())
    preparation = copy.deepcopy(next(
        task for task in main if task.get("name") == "Bootstrap prereqs"))
    auth_path = ROOT / "roles/cephadm/tasks/prereqs.yml"
    authorization = yaml.safe_load(auth_path.read_text())[0]
    # Substitute key generation and authorized_keys writes with harmless files.
    # Keep the production include condition and the public-key lookup/guard.
    preparation["include_tasks"] = str(tmp_path / "prepare.yml")
    (tmp_path / "prepare.yml").write_text(yaml.safe_dump([
        {"name": "Record key preparation", "ansible.builtin.copy": {
            "dest": str(tmp_path / "prepared"),
            "content": "prepared\n", "mode": "0600"}},
        {"ansible.builtin.set_fact": {
            "cephadm_ssh_public_key_content": "fixture-public-key"}},
    ]))
    authorization = {
        "name": authorization["name"], "when": authorization.get("when"),
        "ansible.builtin.copy": {
            "dest": str(tmp_path / "authorized.{{ inventory_hostname }}"),
            "content": authorization["ansible.posix.authorized_key"]["key"],
            "mode": "0600",
        },
    }
    hosts = {
        name: {
            "ansible_connection": "local",
            "ansible_python_interpreter": sys.executable,
            "cephadm_bootstrap": (bootstrap_required if name == "mon0"
                                  else not bootstrap_required),
        } for name in ["mon0", "mon1", "osd0"]
    }
    inventory_path = tmp_path / "inventory.yml"
    inventory_path.write_text(yaml.safe_dump({"all": {"hosts": hosts}}))
    (tmp_path / "play.yml").write_text(yaml.safe_dump([{
        "hosts": "all", "gather_facts": False,
        "vars": {"cephadm_bootstrap_host": "mon0",
                 "cephadm_ssh_user": "root", "ansible_become": False},
        "tasks": [preparation, authorization],
    }], sort_keys=False))
    env = os.environ.copy()
    env["ANSIBLE_LOCAL_TEMP"] = str(tmp_path / "local")
    env["ANSIBLE_REMOTE_TEMP"] = str(tmp_path / "remote")
    command = ["ansible-playbook", "-i", str(inventory_path),
               str(tmp_path / "play.yml")]
    if check_mode:
        command += ["--check", "--diff"]
    result = subprocess.run(command, cwd=tmp_path, env=env,
                            text=True, capture_output=True, check=False)
    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    if bootstrap_required and not check_mode:
        assert (tmp_path / "prepared").exists()
        assert len(list(tmp_path.glob("authorized.*"))) == 3
        hosts["mon0"]["cephadm_bootstrap"] = False
        inventory_path.write_text(yaml.safe_dump({"all": {"hosts": hosts}}))
        again = subprocess.run(command, cwd=tmp_path, env=env,
                               text=True, capture_output=True, check=False)
        assert again.returncode == 0, again.stdout + again.stderr
        assert "changed=0" in again.stdout
    else:
        assert not (tmp_path / "prepared").exists()
        assert not list(tmp_path.glob("authorized.*"))
