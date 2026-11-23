# Bootstrap SSH integration tests

These tests run local Ansible playbooks with the production SSH guards.
They use temporary files instead of host keys and authorized-key files.
They cover fresh clusters, existing clusters, new OSD/MON hosts, missing local key files, repeat runs, and `--check --diff`.

Run this command from the collection root under `ansible_collections/stackhpc/cephadm`:

```bash
ansible-test integration --verbose --docker --requirements bootstrap_ssh_guards
```

The Docker unit-test payload omits built-in modules.
The integration runner supplies the modules that these playbooks require.
The target declares its production task files in `aliases` so the runner copies them into its temporary test directory.
