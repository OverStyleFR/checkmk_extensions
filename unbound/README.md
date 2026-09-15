# Unbound

## What it monitors

Checkmk plug-in that monitors the [unbound](https://nlnetlabs.nl/projects/unbound/about/)
caching/validating DNS resolver via `unbound-control stats_noreset`: query
rate, answer types (rate or ratio, e.g. NXDOMAIN/SERVFAIL share), cache hit
ratio and miss rate, and unwanted reply rate.

This is a maintenance fork of the original, unmaintained
[PLUTEX/checkmk-unbound](https://github.com/PLUTEX/checkmk-unbound) MKP by
Jan-Philipp Litza. Upstream has seen no releases addressing current Checkmk
versions, so we took over maintenance here.

## Changes in this fork (2.0.0)

Upstream 1.2.0 used the legacy `web/plugins/wato` and
`web/plugins/metrics` GUI plug-in structure (`cmk.gui.valuespec` /
`cmk.gui.plugins.metrics`). Its `unbound_parameters.py` referenced
`FixedValue` from `cmk.gui.valuespec` without importing it:

```
NameError: name 'FixedValue' is not defined
```

which broke loading the `static_checks:unbound_answers` ruleset (visible as
a `cmk-update-config` "Rulesets" pre-action error) on current Checkmk
versions that validate every ruleset's valuespec eagerly.

Rather than just patching the import, this fork migrates the whole
ruleset/graphing layer to the modern `cmk_addons_plugins` API
(`cmk.rulesets.v1` and `cmk.graphing.v1`), which is what the legacy
valuespec-based plug-ins are being replaced by across Checkmk. The
`agent_based` check logic is unchanged apart from adapting to the new
parameter shape for the answer-rate-vs-ratio choice.

## Requirements

- Checkmk 2.3.0b1 or newer.
- `unbound-control` reachable on the monitored host (local control socket,
  default unbound config).
- For the "Unbound Answers" service (breakdown by response code), unbound
  must have **extended statistics** enabled:
  `extended-statistics: yes` in `unbound.conf`
  (in OPNsense: Services > Unbound DNS > Advanced > "Enable extended
  statistics"). Without this, `unbound-control stats_noreset` omits the
  `num.answer.rcode.*` counters, so only "Unbound Cache" gets discovered.
  Restart unbound and re-run service discovery afterwards.

## Installation

```bash
mkp add unbound-2.0.0.mkp
mkp enable unbound 2.0.0
```

### Deploy the agent plug-in

```bash
# on the unbound host
cp agents/plugins/unbound /usr/lib/check_mk_agent/plugins/unbound
chmod +x /usr/lib/check_mk_agent/plugins/unbound
# test:
/usr/lib/check_mk_agent/plugins/unbound
```

Then rediscover the host in Checkmk — the unbound services appear.

## Changelog

- **2.0.0** — Migrated rulesets/graphing from the legacy `web/plugins/wato`
  + `web/plugins/metrics` layout to the modern `cmk_addons_plugins`
  (`cmk.rulesets.v1` / `cmk.graphing.v1`) layout, fixing the
  `FormSpecNotImplementedError` / `NameError: FixedValue` breakage on
  current Checkmk versions. Renamed metrics with an `unbound_` prefix to
  avoid collisions with Checkmk builtin metrics. Added checkman pages.
  Agent plug-in now falls back to `unbound-control -c <conf>` when the
  default invocation fails (OPNsense/*BSD).
- **1.2.0** — Last upstream release (Jan-Philipp Litza / PLUTEX).
