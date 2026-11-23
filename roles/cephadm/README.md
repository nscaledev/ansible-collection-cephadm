# cephadm

This role bootstraps and configures Ceph using cephadm.

[![asciicast](https://asciinema.org/a/752639.svg)](https://asciinema.org/a/752639)

## Existing clusters and new hosts

The role sets `cephadm_bootstrap` from each host's service facts.
The configured bootstrap MON remains the source of the cluster SSH public key.
Key preparation on that MON reads existing files even when the MON already has Ceph services.
Private-key generation runs only for a bootstrap MON that needs bootstrap and has no local private key.

If an existing cluster has no local public-key file, the role reads the current public key from the monitor store and saves it.
Public-key authorization runs on new hosts without Ceph services.
Existing hosts skip that authorization task.
Package preparation, logrotate, image pulls, and OSD configuration remain active.

Keep `cephadm_bootstrap_host` on an existing MON during cluster expansion.
Set `cephadm_ssh_user` to the existing cluster SSH user.
A new cluster with a supplied private key also needs its matching public-key file.
Check mode skips public-key discovery and authorization when the required public key is unavailable.

## Prerequisites

### Host prerequisites

* The role assumes target hosts connection over SSH with user that has passwordless sudo configured.
* Either direct Internet access or private registry with desired Ceph image accessible to all hosts is required.

### Inventory

This role assumes the existence of the following groups:

* `ceph`
* `mons`
* `mgrs`
* `osds`

Optional groups (those services will be deployed when group exists)::

* `rgws`

All Ceph hosts must be in the `ceph` group.

## Role variables

* General
  * `cephadm_ceph_release`: Ceph release to deploy (default: squid)
  * `cephadm_container_engine`: Whether to use docker_login or podman_login (default: docker)
  * `cephadm_fsid`: FSID to use for cluster (default: empty - cephadm will generate FSID)
  * `cephadm_recreate`: If existing cluster should be destroyed and recreated (default: false)
  * `cephadm_custom_repos`: Boolean: disables configuring offical Ceph YUM/APT repositories - `cephadm_ceph_release` is ignored. Can serve as a workaround for a lack of supported OS distro + Ceph release combination upstream. (default: false)
  * `cephadm_package_update`: If enabled - cephadm package will be updated to latest version (default: false)
  * `cephadm_host_labels`: If set (list format) - those additional labels will be applied to host definitions (default: [] - empty list)
  * Bootstrap settings
    * `cephadm_bootstrap_host`: The host on which to bootstrap Ceph (default: `groups['mons'][0]`)
    * `cephadm_enable_dashboard`: If enabled - dashboard service on MGR will be enabled (default: false)
    * `cephadm_enable_firewalld`: If enabled - firewalld will be installed and rules will be applied (default: false)
    * `cephadm_enable_monitoring`: If enabled - cephadm monitoring stack will be deployed i.e. prometheus/node-exporters/grafana (default: false)
    * `cephadm_image`: If set - cephadm will use this image
    * `cephadm_haproxy_image`: If set - cephadm will use this image for HAProxy in the ingress service
    * `cephadm_keepalived_image`: If set - cephadm will use this image for Keepalived in the ingress service
    * `cephadm_install_ceph_cli`: If enabled - ceph cli will be installed on the hosts (default: false)
    * `cephadm_ssh_public_key`: Location where ssh public key used by cephadm will be saved (default: /etc/ceph/cephadm.pub)
    * `cephadm_ssh_private_key`: Location where ssh private key used by cephadm will be saved (default: /etc/ceph/cephadm.id)
    * `cephadm_ssh_user`: Pre-existing user name that should be used for bootstrapping the cluster. User must have passwordless sudo enabled. Since 1.4.0 (default: `ansible_user`)
    * `cephadm_bootstrap_additional_parameters`: additional arguments to pass to `cephadm bootstrap`
    * `cephadm_apt_repo_dist`: overide (default) `ansible_distribution_release` for debian package repository
  * MONs and MGRs
    * `cephadm_mon_count`: Number of MONs to deploy (default: equals to number of hosts in `mons` Ansible group)
    * `cephadm_mgr_count`: Number of MGRs to deploy (default: equals to number of hosts in `mgrs` Ansible group)
  * OSDs
    * `cephadm_osd_devices`: List of /dev/device paths to use (e.g. for multipath devices that can't be used using an OSD spec)
      Example:
      ```
          cephadm_osd_devices:
            - /dev/sdb
            - /dev/sdc
      ```
    * `cephadm_osd_spec`: OSD spec to apply in YAML (recommended) or dict format
      Example:
      ```
          cephadm_osd_spec: |
            service_type: osd
            service_id: osd_spec_default
            placement:
              host_pattern: '*'
            data_devices:
              model: MZ7KH960HAJR0D3
            db_devices:
              model: Dell Express Flash PM1725b 1.6TB SFF
      ```
  * RGWs
    * `cephadm_radosgw_services`: List of Rados Gateways services to deploy. `id` is an arbitrary name for the service,
      `count_per_host` is desired number of RGW services per host. `networks` is optional list of networks to bind to.
      `spec` is optional additional service specification. Previously undocumented `port` variable is no longer supported.
      Example:
      ```
          cephadm_radosgw_services:
            - id: myrgw
              count_per_host: 2
              networks:
                - 10.66.0.0/24
              spec:
                rgw_realm: myrealm
                rgw_zone: myzone
                rgw_frontend_port: 1234
      ```
  * Ingress
    * `cephadm_ingress_services`: List of ingress services to deploy. `id` should match name (not id) of the RGW service to
      which ingress will point to. `spec` is a service specification required by Cephadm to deploy the ingress (haproxy +
      keepalived pair).
      Example:
      ```
          cephadm_ingress_services:
            - id: rgw.myrgw
              spec:
                frontend_port: 443
                monitor_port: 1967
                virtual_ip: 10.66.0.1/24
                ssl_cert: {example_certificate_chain}
      ```
      Note that adding RGW or other services to an existing deployment requires setting `cephadm_bootstrap` variable to *true*.

* Registry
    * `cephadm_registry_url`: (default: not used)
    * `cephadm_registry_username`: (default: not used)
    * `cephadm_registry_password`: (default: not used)

* Networking
  * Mandatory
    * `cephadm_public_interface`: Public interface (mandatory)
    * `cephadm_public_network`: Public network including CIDR (mandatory)
  * Optional
    * `cephadm_admin_interface`: Admin interface (default: use ``cephadm_public_interface``)
    * `cephadm_cluster_interface`: Cluster interface (optional - if not defined ceph will not use dedicated cluster network)
    * `cephadm_cluster_network`: Cluster network including CIDR (optional - if not defined ceph will not use dedicated cluster network)
