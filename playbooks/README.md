# Playbooks

This directory contains collection-provided entrypoints that compose the
`stackhpc.cephadm` roles into common workflows.

Available playbooks:

* `cephadm.yml`: end-to-end deployment and post-bootstrap configuration.
* `cephadm-deploy.yml`: bootstrap and configure a Ceph cluster with cephadm.
* `cephadm-commands-pre.yml`: run custom commands before post-deployment
  configuration.
* `cephadm-ec-profiles.yml`: manage erasure coding profiles.
* `cephadm-crush-rules.yml`: manage CRUSH rules.
* `cephadm-pools.yml`: manage pools.
* `cephadm-keys.yml`: manage cephx keys.
* `cephadm-placement-policies.yml`: manage RGW placement policies.
* `cephadm-service-spec.yml`: apply arbitrary cephadm service specs.
* `cephadm-config-template.yml`: manage cephadm config-key templates.
* `cephadm-commands-post.yml`: run custom commands after post-deployment
  configuration.
* `ceph-enter-maintenance.yml`: place Ceph hosts into maintenance serially.
* `ceph-exit-maintenance.yml`: remove Ceph hosts from maintenance serially.

These playbooks assume the inventory groups documented by the underlying roles,
especially `ceph` and `mons`.
