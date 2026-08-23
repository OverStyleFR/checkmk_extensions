# Checkmk Monitoring Compliance

Detects installed and/or running services on a host that are not yet monitored,
even though a suitable Checkmk plug-in is available on the server. The result
is a **"Checkmk Monitoring Compliance"** service with WARN/CRIT logic and a
compliance metric (`compliance_percent`).
<img width="1856" height="616" alt="image" src="https://github.com/user-attachments/assets/bbf15235-7a02-4bea-8a5d-c97b05307249" />


## How it works

Detection is capability-based rather than relying on a static application
list. Every data source contributes typed capabilities (type + name), which
are correlated to the check plug-ins available on the site via a normalized
name token and an alias table. Any program whose name matches an available
plug-in is therefore detected automatically.

Detection sources:

- Existing agent sections that are present on the host.
- Running systemd service units (agent plug-in or built-in section) and, on
  Windows, running services (via the Windows agent plug-in).
- Running processes (`ps` / `ps_lnx`).
- Host labels (read server-side via Livestatus).
- Installed packages from the HW/SW inventory (read server-side by the
  special agent) and from the optional agent plug-ins.

Capabilities are written to a persistent, deduplicated capability database.
The check does not bind the cached `lnx_packages` / `win_reg_uninstall` agent
sections, so the service is driven by live data and recomputes on the normal
check interval (and can be rescheduled). Installed-package data still only
changes as fast as the HW/SW inventory is refreshed.


## Services

| Service | Description |
|---|---|
| `Checkmk Monitoring Compliance` | Per-host compliance service (WARN/CRIT logic, `compliance_percent` metric) |
| `Checkmk Capability Database` | Statistics about the persistent capability database (file size, entry counts, distinct hosts/tokens, last update). Enable "Report capability database statistics" in the special-agent rule on exactly one host (e.g. the Checkmk server). |
| `Checkmk Known Catalog` | Read-only reference listing the application types the detection knows about (alias/signature/title tables), annotated with plug-in availability on this site. Always OK, informational only. Enable "Report known catalog" in the special-agent rule. |

## GUI Dashboard

A **Monitoring Compliance** sidebar snap-in (add it via the sidebar's "Add snap-in"
button) shows two links: the main one opens the dashboard *inside* Checkmk itself
(`target="main"`, the same mechanism every built-in sidebar link uses — the sidebar and
top bar stay put); a small "↗" link next to it opens the same page in a separate browser
tab instead. Either way it's a standalone dashboard page listing both databases in full,
browsable and searchable/sortable/filterable form — well beyond what the two services'
plain-text notices show:

- **Capability Database** tab — every capability ever observed, deduplicated, with type,
  name, token, the hosts it was seen on, monitorable/monitored flags and first/last-seen
  timestamps. Each row has a **"→ Known Catalog"** action (admins only) to adopt it: pick
  an existing Known Catalog entry from a dropdown to add this capability's name to it as
  an extra match, or create a brand-new entry pre-filled from it. Goes through the exact
  same `catalog_save` action as editing the Known Catalog directly — see below.
- **Known Catalog** tab — every application type the detection logic recognizes, with its
  matching name patterns, a deployment hint, and whether a covering plug-in is currently
  available on this site (re-checked against `cmk -L`, so a plug-in from a freshly
  uploaded MKP shows up here too). **Editable**: use "+ Add application" or a row's
  Edit/Delete buttons to add, change or remove catalog entries at runtime.

  These edits are **actively used by the compliance check itself**, not just displayed
  here: on every check run, `agent_based/monitoring_compliance.py` reads the same
  `custom_catalog.json` and feeds each entry's "Matches" (case-insensitive regexes) into
  its token-resolution logic — exactly like a host-specific entry in the "Custom
  capability mappings" check parameter already does, and checked before the built-in
  `ALIASES`/`_SIGNATURES_RAW` tables (a host-specific mapping still wins over a dashboard
  entry for the same token). The entry's title/hint are used in the check's finding
  messages too. Disable this per host via the new "Ignore the Known Catalog dashboard's
  custom entries" check parameter if a host shouldn't pick up site-wide dashboard entries.
  Deleting a *built-in* entry still only hides it from this catalog view — its own
  built-in detection logic is unaffected (there's nothing to "undo" there); deleting a
  *custom* entry removes it, including its detection rule. The **"Checkmk Known
  Catalog"** service (see below) lists the same merged set too, marking dashboard
  additions/overrides with "(custom)".

The dashboard (`web/htdocs/monitoring_compliance/`) reads the Capability Database and the
built-in part of the Known Catalog live via a small JSON AJAX endpoint
(`web/plugins/sidebar/monitoring_compliance.py`, reachable at
`/<site>/check_mk/monitoring_compliance_data.py`) — no special-agent run required to view
it, though the "Report capability database statistics" / "Report known catalog" options
still control the two summary *services* described above. Catalog edits are stored in
`$OMD_ROOT/var/monitoring_compliance/custom_catalog.json` (CSRF-protected writes, same
mechanism as every other state-changing AJAX action in Checkmk's own GUI; patterns are
validated as compilable regexes when saved) and read directly by the dashboard, the main
compliance check and the "Checkmk Known Catalog" service alike.

**Governance**: viewing either tab only needs a logged-in Checkmk session (any role — same
as any other page). Editing the Known Catalog (Add/Edit/Delete) requires Checkmk's own
`wato.edit` permission ("Setup: make changes"), which only the built-in **admin** role has
by default — a `user`/`guest`-role user gets a read-only view (the Add/Edit/Delete controls
are hidden) and the AJAX endpoint enforces the same permission server-side regardless of
what the UI shows, via `cmk.gui.logged_in.user.need_permission("wato.edit")`. This reuses
Checkmk's existing role/permission system as-is rather than inventing a separate,
extension-specific permission — if you've customized which roles have `wato.edit`, that
customization applies here automatically.

The dashboard's colors/fonts are matched to Checkmk's own two built-in themes
("facelift"/light and "modern-dark"/dark, sampled directly from a real site's compiled
theme CSS — page/panel backgrounds, borders, the primary-button green, and the
OK/WARN/CRIT state colors Checkmk itself uses everywhere) and it follows **Checkmk's own
configured theme** (per-user setting, or the site default) rather than only the browser's
OS-level dark/light preference — the dashboard asks the AJAX endpoint for it directly
(`cmk.gui.theme.current_theme.theme.get()`), so it stays correct even when the two
disagree. Every text/background color pairing was verified against the WCAG contrast
ratio it needs (4.5:1 for normal text) in both themes.

## Deployment

- The special agent runs server-side and reads host labels, HW/SW inventory
  data and, when configured, the capability-database/known-catalog data.
- Optional agent plug-ins (`agents/plugins/mk_monitoring_compliance` for
  Linux/shell, `agents/windows/plugins/mk_monitoring_compliance.ps1` for
  Windows PowerShell) provide clean capability data straight from the host
  and can be deployed via the Agent Bakery (commercial editions).
- Configure the special agent via the ruleset "Checkmk Monitoring Compliance"
  (`monitoring_compliance/rulesets/special_agent.py`) and per-service
  thresholds via the corresponding check-parameter rulesets.

## Requirements

- Checkmk >= 2.3.0p1.
- Agent Bakery deployment of the optional plug-ins requires a commercial
  edition (CEE).

## Installing

```
mkp add monitoring_compliance-1.5.9.mkp
mkp enable monitoring_compliance 1.5.9
```

## Changelog

- **1.6.6** — The Capability Database tab now has a "→ Known Catalog" row action
  (admins only): assign an observed capability to an existing Known Catalog entry as an
  extra match, or create a brand-new entry pre-filled from it. Uses the same
  `catalog_save` action as editing the Known Catalog directly — no new server-side
  action, no new permission.
- **1.6.5**:
  - Opening the dashboard while not logged in to the Checkmk site used to show a
    confusing "Unexpected response from the site (not valid JSON)" red error banner
    (the login redirect returns an HTML login page, not JSON). Now detected directly
    and shown as a calm "you need to be logged in" prompt with a direct login link
    instead.
  - Faster initial load: the dashboard now fetches theme + Capability Database + Known
    Catalog in a single combined `bootstrap` request instead of three separate ones —
    each is otherwise a full Checkmk request (session/auth setup included), so this cuts
    real, not just perceived, load time. Reloading just the catalog after an edit is
    unaffected (still its own single request).
- **1.6.4** — Known Catalog editing is now gated on Checkmk's own `wato.edit`
  permission ("Setup: make changes"), which only the built-in admin role has by
  default. A user without it gets a read-only dashboard (Add/Edit/Delete controls
  hidden); the AJAX endpoint enforces the same permission server-side either way, so
  hiding the controls is a convenience, not the actual boundary. Viewing both tabs
  still only needs a logged-in session, any role.
- **1.6.3**:
  - The dashboard now matches Checkmk's own visual design (colors/fonts sampled from a
    real site's facelift/modern-dark theme CSS) and follows Checkmk's own configured
    theme (per-user setting or site default), not just the browser's OS-level dark/light
    preference. Every color pairing was checked against WCAG contrast requirements in
    both themes.
  - The sidebar snap-in's link now opens the dashboard inside Checkmk itself by default
    (`target="main"`), with a small secondary "↗" link to open it in a new browser tab
    instead — previously it only ever opened in a new tab.
  - Fixed: the **"Checkmk Known Catalog"** service only ever listed the built-in
    detection tables, never entries added through the dashboard, even though the
    dashboard's own view and the main compliance check both already picked them up
    correctly. `known_catalog.py` now merges `custom_catalog.json` the same way.
- **1.6.2** — The Known Catalog dashboard's custom entries are now actively used for
  detection, not just displayed. `agent_based/monitoring_compliance.py` reads
  `custom_catalog.json` on every check run and feeds its patterns/titles/hints into the
  same token-resolution logic the "Custom capability mappings" check parameter already
  uses (host-specific mappings there still take precedence for the same token). New
  "Ignore the Known Catalog dashboard's custom entries" check parameter to opt a host out.
  Patterns are now validated as compilable regexes when saved from the dashboard. See the
  updated "GUI Dashboard" section for the exact precedence rules.
- **1.6.1** — Dashboard follow-ups:
  - The dashboard's tables now use the full browser width instead of a fixed max-width
    column.
  - The Known Catalog is now editable: add/edit/delete entries directly from the
    dashboard ("+ Add application" and per-row Edit/Delete), stored in
    `var/monitoring_compliance/custom_catalog.json` and layered on top of the built-in
    catalog tables. Availability is still re-checked against `cmk -L`, so a plug-in
    provided by a newly uploaded MKP is picked up for custom entries the same way it is
    for built-in ones. See the updated "GUI Dashboard" section for the scope of what
    editing here does (and does not) affect.
- **1.6.0** — Added a **Monitoring Compliance** sidebar snap-in linking to a new,
  standalone dashboard page (`web/htdocs/monitoring_compliance/`) that lists the
  Capability Database and Known Catalog in full, browsable/searchable/sortable form —
  fed live by a read-only JSON AJAX endpoint
  (`web/plugins/sidebar/monitoring_compliance.py`), no special-agent run required to view
  it. See the new "GUI Dashboard" section above.
- **1.5.28** — Consolidated fixes for false positives/negatives in the
  capability correlation logic (supersedes the 1.5.27 release; internal
  test-cycle version bumps in between are not listed individually):
  - MSSQL: an installed MSSQL-related package/tool (ODBC/OLE DB drivers,
    SQL Server Compact, SQL Server Management Studio, the SQL Server
    Browser service package, etc.) is no longer sufficient by itself to
    recommend deploying the MSSQL monitoring plug-in. Only a currently
    *running* SQL Server engine service (`MSSQL$<instance>` /
    `MSSQLSERVER`, matched via the Windows "services" section) counts as
    usage evidence.
  - IIS: analogous fix — an installed IIS-related package (e.g. "IIS URL
    Rewrite Module") or the IIS remote management service
    ("IIS-Verwaltungsdienst" / WMSVC) running is no longer sufficient by
    itself. Only the actual web-serving engine service ("W3SVC" / "World
    Wide Web Publishing Service") in a running state counts as usage
    evidence for recommending the IIS application-pool plug-in.
  - Correctly suggest the "DHCP pools (Windows)" plug-in when the Windows
    "Service DHCPServer" is found running.
  - Generalized the usage-evidence exclusion for
    `TOKENS_REQUIRE_USAGE_EVIDENCE` tokens (`lvm`, `zfs`, `corosync`,
    `dmraid`, `mssql`, `iis`): installed packages (`package`/
    `inv_package` capability types) can never by themselves satisfy the
    usage-evidence requirement for these tokens, regardless of package
    name — avoids fragile per-package name-pattern exclude lists.
  - Fixed two `BooleanChoice` fields in the "Checkmk Monitoring
    Compliance" special-agent rule and the check-parameter rule
    (`no_plugin_check`, `no_labels`, `no_inventory`, `report_db_stats`,
    `report_known_catalog` and `informational_only`,
    `disable_capability_db`) showing an unlabeled second checkbox stacked
    under the outer "enable this option" checkbox. Added an explicit
    `label=` to each affected `BooleanChoice`, so the inner checkbox now
    carries its own descriptive text instead of appearing blank.
- **1.5.26** — Fixed a false negative where PowerDNS (Authoritative
  Server + Recursor) was not detected as a capability even though it was
  installed and actively monitored. The package/process/systemd-unit
  names (`pdns`, `pdns-recursor`, `pdns_server`) were never mapped to the
  Checkmk plug-in prefix `powerdns_*` because no alias existed. Added the
  missing alias plus title/hint entries.
- **1.5.25** — Fixed a false positive where the Apache client-tools
  package (`apache2-utils`, and the equivalent `apache2-bin`/
  `httpd-tools` on other distros) was treated as evidence of an actual
  Apache HTTP server. These packages ship `htpasswd`/`ab`/`htdigest`
  only and are frequently pulled in as a dependency of unrelated
  packages. Now excluded via the client-only evidence exclusion.
- **1.5.24** — Fixed a false positive where the NUT (Network UPS Tools)
  client package (`nut-client`) and its `nut-monitor.service` unit
  (`upsmon` running in client mode) were treated as evidence of a local
  NUT server (`upsd`). The evidence-exclusion mechanism (previously
  `PACKAGE_EVIDENCE_EXCLUDE`, package-only) was generalized to
  `EVIDENCE_EXCLUDE` and now also applies to running capability
  evidence (systemd units/processes), not just installed packages.
- **1.5.23** — Fixed a false positive where the `libdbd-mysql-perl`
  Perl DBI driver (a pure client library) was treated as evidence of an
  installed MySQL/MariaDB server. Added to the existing client-evidence
  exclusion for the `mysql` token.
- **1.5.22** — Fixed a false positive where the MySQL/MariaDB client
  libraries/tools (`mysql-common`, `mariadb-common`, `libmysqlclient*`,
  `libmariadb*`) — commonly pulled in as a dependency by unrelated
  packages — were treated as evidence of an installed MySQL/MariaDB
  server. Introduced `PACKAGE_EVIDENCE_EXCLUDE` to exclude such
  client-only package names from installation evidence for the `mysql`
  token; genuine server packages or runtime evidence (systemd
  unit/process `mysqld`/`mariadbd`) are still detected as before.
- **1.5.21** — Fixed a false positive where mere presence of the
  `dmraid` package (openSUSE) was treated as evidence of active
  software RAID usage. Added a new usage-evidence source: the `md`
  section (`/proc/mdstat`) must report at least one array before the
  finding is raised, matching the existing LVM/ZFS/Corosync pattern.
- **1.5.20** — Fixed a false positive where the `site` token — the
  leading token of both the Checkmk-bundled `site_object_counts`
  plug-in and countless unrelated `site-*` packages (e.g. a web
  server's `site-config` vhost package) — caused a spurious "available
  plug-in" finding from pure leading-token coincidence. Added to
  `STOP_TOKENS`, same class as the existing `intel`/`watchdog` entries.
- **1.5.19** — Dropped the `mtr` finding. The package match is genuine,
  but the check_mk `mtr` plug-in requires deliberate manual setup (a
  per-host list of static target hosts, configured via a dedicated
  agent bakery rule), making mere package presence far too weak a
  signal for a missing-default finding.
- **1.5.18** — Dropped the `iptables` finding. iptables/netfilter
  tooling ships as a standard part of virtually every Linux
  distribution regardless of whether it is actually used for
  firewalling, so mere package presence carries no real compliance
  signal. Unlike the token-collision cases above, the plug-in match
  itself is genuine — it is simply not a meaningful finding, and no
  cheap usage evidence is available for it.
- **1.5.17** — Corosync package presence alone is not evidence of
  actual cluster usage (e.g. on Proxmox VE, it's a standard dependency
  installed regardless of clustering). Now requires the
  `corosync.service` systemd unit to be loaded and active before
  raising a finding, matching the existing LVM/ZFS usage-evidence
  pattern.
- **1.5.16** — Fixed a false positive where the systemd hardware-
  watchdog multiplexer unit (`watchdog-mux.service`, part of the base
  `watchdog` package, unrelated to any monitored subsystem) shared its
  leading token with the unrelated environmental-sensor plug-ins
  `watchdog_sensors*` (Watchdog Inc. weather-station hardware), causing
  a false "available plug-in(s)" finding from pure token-prefix
  coincidence. Added `watchdog` to `STOP_TOKENS`, same class as `intel`.
- **1.5.15** — Fixed a false positive where Ceph client-side tooling
  (`ceph-common`, `ceph-fuse`) was tokenized to the same canonical token as
  the actual Ceph server/daemon packages, so hosts with only client-side
  Ceph tooling installed were falsely reported as having available
  `ceph_df`/`ceph_status`/`ceph_status_mgrs` server plug-ins. Client-side
  packages now resolve to a distinct token.
- **1.5.14** — Fixed a false positive where the RabbitMQ client library
  package (`librabbitmq4`) was tokenized to the same canonical token as the
  actual `rabbitmq-server` package, incorrectly reporting an "available"
  RabbitMQ server plug-in on hosts that only have the client library
  installed. The client library now resolves to a distinct token.
- **1.5.13** — Fixed a false positive where the ISC DHCP client/common
  packages (`isc-dhcp-client`, `isc-dhcp-common`) were tokenized to the same
  canonical token as the actual `isc-dhcp-server` package, incorrectly
  reporting an "available" `isc_dhcpd` plug-in on hosts that only have the
  DHCP client installed. Client/common packages now resolve to distinct
  tokens.
- **1.5.11** — Fixed a false positive where the NFS client package
  (`nfs-common`) and its `nfs-blkmap.service` boot-time unit were tokenized
  to the same canonical token as the actual NFS server (`nfs-kernel-server`/
  `nfs-server`), incorrectly reporting an "available" NFS exports plug-in on
  pure NFS-client hosts. NFS server evidence is now derived specifically
  from the `nfs-server`/`nfs-kernel-server` systemd unit or package name.
- **1.5.9** — Kernel/library-only features (LVM, ZFS) are no longer flagged
  as an unmonitored finding merely because the package is installed or an
  always-on boot hook unit exists. We now require corroborating evidence of
  actual use from the already-collected `df` section (no extra agent
  plug-in): a mounted filesystem with `fs_type == "zfs"`, or a mounted
  LVM-managed block device (`/dev/mapper/<vg>-<lv>` or `/dev/dm-<N>`). Without
  that evidence the capability is dropped entirely, eliminating false
  positives on hosts where the package is present but never actually used.
- **1.5.8** — Fixed a false positive where the generic package/process
  tokenizer collided by coincidence: an installed package `intel-microcode`
  was tokenized to `intel`, which is also the leading token of the
  hardware-specific `intel_true_scale_*` plug-in family, so it was
  incorrectly reported as an "available plug-in" for that package. `intel`
  is now excluded via `STOP_TOKENS`, the same mechanism already used to
  filter other generic/base-OS token collisions (`cpu`, `mem`, `kernel`, ...).
- **1.5.7** — Fixed HW/SW inventory package detection: the server-side agent
  was looking for the inventory file at `var/check_mk/inventory/<host>`
  (bare/`.gz`), but modern Checkmk (>=2.2) stores it as
  `<host>.json`/`<host>.json.gz` with the actual tree nested one level
  deeper under a `raw_tree` key alongside `meta`. Both bugs meant
  `inventory_packages` always silently returned an empty list, so
  inventory-only subsystems (e.g. `apt`) were never picked up as a
  capability even though they were clearly visible in the HW/SW Inventory
  itself. Now reads `<host>.json[.gz]` (falling back to the legacy
  extension-less layout) and unwraps `raw_tree` when present.
- **1.5.6** — Fixed a remaining LVM2 false positive: `lvm2-activation-early`
  (and other distro-specific `lvm2-*` boot hooks not covered by the 1.5.5
  fixed name list) are now caught by a generic `lvm2-` prefix match instead
  of an exact-name list, since the whole `lvm2-*` unit family behaves the
  same way (always "loaded active" regardless of actual LVM usage).
- **1.5.5** — Fixed a false positive on `lvm2-monitor.service` (and its
  sibling `lvm2-lvmpolld` units): these are boot-time housekeeping units
  from the base `lvm2` package that show "loaded active" on virtually
  every Debian/Ubuntu host, even with no LVM volume group in use at all
  (unlike ZFS's import units, they have no condition that gates them on
  actual usage). They are now excluded from systemd-unit-based capability
  detection.
- **1.5.4** — Fixed false positives from the built-in `systemd_units` section:
  units are now only counted when actually present and active (loaded +
  active running, or loaded + active exited for legitimate oneshot units),
  instead of matching on unit name alone. This eliminates spurious findings
  from masked units, template unit instances (`name@instance.service`,
  e.g. `heartbeat-failed@frr.service` wrongly matching a "Heartbeat"
  capability), and units reported by systemd but not actually loaded
  (`not-found`/inactive/dead, e.g. leftover OnFailure= hooks).

