"""Exercise the real key-preparation tasks with local, disposable fixtures."""

import copy
import grp
import pwd
import os
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[4]


@pytest.mark.parametrize(
    "scenario",
    [
        "fresh",
        "existing",
        "new_osd",
        "new_mon",
        "missing_private",
        "missing_public",
        "missing_pair",
    ],
)
@pytest.mark.parametrize("check_mode", [False, True])
def test_key_preparation_and_new_host_authorization(
    tmp_path, scenario, check_mode
):
    local_keys = tmp_path / "keys"
    local_keys.mkdir()
    private = local_keys / "cephadm.id"
    public = local_keys / "cephadm.pub"
    expansion = scenario in {
        "new_osd",
        "new_mon",
        "missing_private",
        "missing_public",
        "missing_pair",
    }
    if scenario != "fresh" and scenario not in {
        "missing_private",
        "missing_pair",
    }:
        private.write_text("existing-private-fixture\n")
    if scenario not in {"fresh", "missing_public", "missing_pair"}:
        public.write_text("existing-public-fixture\n")
    original_private = private.read_bytes() if private.exists() else None
    library = tmp_path / "library"
    library.mkdir()
    # The generator is the only substituted preparation module. It never
    # handles a real key, and its check mode writes no fixture files.
    (library / "openssh_keypair.py").write_text("""from pathlib import Path
from ansible.module_utils.basic import AnsibleModule
m = AnsibleModule(
    argument_spec=dict(path=dict(required=True), size=dict(type='int'),
                       comment=dict()),
    supports_check_mode=True)
p = Path(m.params['path'])
if not m.check_mode:
    p.write_text('generated-private-fixture\\n')
    Path(str(p) + '.pub').write_text('generated-public-fixture\\n')
m.exit_json(changed=True, public_key='generated-public-fixture')
""")
    executable = tmp_path / "bin"
    executable.mkdir()
    (executable / "cephadm").write_text(
        "#!/bin/sh\n"
        'printf "read\\n" >> "$KEY_READ_LOG"\n'
        'printf "existing-public-fixture\\n"\n'
    )
    (executable / "cephadm").chmod(0o755)
    prep_source = (
        ROOT / "roles/cephadm/tasks/prereqs_bootstrap.yml"
    ).read_text()
    prep_path = tmp_path / "prepare.yml"
    prep_source = prep_source.replace("/etc/ceph", str(local_keys))
    prep_source = prep_source.replace(
        "owner: root", "owner: " + pwd.getpwuid(os.getuid()).pw_name
    )
    prep_source = prep_source.replace(
        "group: root", "group: " + grp.getgrgid(os.getgid()).gr_name
    )
    prep_path.write_text(prep_source)
    main = yaml.safe_load((ROOT / "roles/cephadm/tasks/main.yml").read_text())
    preparation = copy.deepcopy(
        next(t for t in main if t.get("name") == "Bootstrap prereqs")
    )
    preparation["include_tasks"] = str(prep_path)
    auth = yaml.safe_load(
        (ROOT / "roles/cephadm/tasks/prereqs.yml").read_text()
    )[0]
    authorization = {
        "name": auth["name"],
        "when": auth.get("when"),
        "ansible.builtin.copy": {
            "dest": str(tmp_path / "authorized.{{ inventory_hostname }}"),
            "content": auth["ansible.posix.authorized_key"]["key"],
            "mode": "0600",
        },
    }
    new_host = "mon1" if scenario == "new_mon" else "osd1"
    names = ["mon0", "old-osd", new_host]
    hosts = {
        name: {
            "ansible_connection": "local",
            "ansible_python_interpreter": sys.executable,
            "cephadm_bootstrap": scenario == "fresh"
            or (expansion and name == new_host),
        }
        for name in names
    }
    inventory = tmp_path / "inventory.yml"
    inventory.write_text(yaml.safe_dump({"all": {"hosts": hosts}}))
    play = [
        {
            "hosts": "all",
            "gather_facts": False,
            "any_errors_fatal": True,
            "vars": {
                "cephadm_bootstrap_host": "mon0",
                "cephadm_ssh_user": "root",
                "ansible_become": False,
                "cephadm_fsid": "fixture",
                "cephadm_ssh_private_key": str(private),
                "cephadm_ssh_public_key": str(public),
            },
            "tasks": [preparation, authorization],
        }
    ]
    path = tmp_path / "play.yml"
    path.write_text(yaml.safe_dump(play, sort_keys=False))
    env = os.environ.copy()
    env.update(
        {
            "ANSIBLE_LOCAL_TEMP": str(tmp_path / "local"),
            "ANSIBLE_REMOTE_TEMP": str(tmp_path / "remote"),
            "ANSIBLE_LIBRARY": str(library),
            "KEY_READ_LOG": str(tmp_path / "read.log"),
            "PATH": str(executable) + os.pathsep + env.get("PATH", ""),
        }
    )
    command = ["ansible-playbook", "-i", str(inventory), str(path)]
    if check_mode:
        command += ["--check", "--diff"]
    result = subprocess.run(
        command,
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    if original_private is not None:
        assert private.read_bytes() == original_private
    elif scenario != "fresh" or check_mode:
        assert not private.exists()
    else:
        assert private.read_text() == "generated-private-fixture\n"
    authorized = {
        p.name.removeprefix("authorized.")
        for p in tmp_path.glob("authorized.*")
    }
    expected = (
        set()
        if check_mode
        else (
            set(names)
            if scenario == "fresh"
            else ({new_host} if expansion else set())
        )
    )
    assert authorized == expected
    for name in authorized:
        assert (tmp_path / ("authorized." + name)).read_text().strip() == (
            "generated-public-fixture"
            if scenario == "fresh"
            else "existing-public-fixture"
        )
    assert (tmp_path / "read.log").exists() == (
        scenario in {"missing_pair", "missing_public"} and not check_mode
    )
    if not check_mode:
        before = {
            p.name: p.stat().st_mtime_ns for p in tmp_path.glob("authorized.*")
        }
        key_times = {
            p.name: p.stat().st_mtime_ns
            for p in (private, public)
            if p.exists()
        }
        for name in names:
            hosts[name]["cephadm_bootstrap"] = False
        inventory.write_text(yaml.safe_dump({"all": {"hosts": hosts}}))
        again = subprocess.run(
            command,
            cwd=tmp_path,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        assert again.returncode == 0, again.stdout + again.stderr
        assert {
            p.name: p.stat().st_mtime_ns for p in tmp_path.glob("authorized.*")
        } == before
        assert {
            p.name: p.stat().st_mtime_ns
            for p in (private, public)
            if p.exists()
        } == key_times
