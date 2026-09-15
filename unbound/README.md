# Unbound

## What it monitors

Checkmk plug-in that monitors the [unbound](https://nlnetlabs.nl/projects/unbound/about/)
caching/validating DNS resolver via `unbound-control stats_noreset`: query
rate, answer types (rate or ratio, e.g. NXDOMAIN/SERVFAIL share), cache hit
ratio and miss rate, and unwanted reply rate.

Replacement for the old and unmaintained
[PLUTEX/checkmk-unbound](https://github.com/PLUTEX/checkmk-unbound) MKP by
Jan-Philipp Litza.

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

### Manual deployment of the agent plug-in. E.g. without bakery (RAW edition) or on *BSD

Copy ~/local/share/check_mk/agents/plugins/unbound to your unbound host to 
/usr/lib/check_mk_agent/plugins/unbound

chmod +x /usr/lib/check_mk_agent/plugins/unbound

To test, run:
/usr/lib/check_mk_agent/plugins/unbound

Then rediscover the host in Checkmk — the unbound services appear.

## Changelog

- **2.0.0** — Initial release after forking the unmaintained MKP by Jan-Philipp Litza / PLUTEX.
  - Compatibility with Checkmk 2.5.0 and upcoming 3.0.0.
  - Migrated rulesets/graphing from the legacy API to API v1.
  - Add bakery rule for automatic plugin deployment.
  - Make parameters of all services configurable.
  - Prefix metrics to avoid collisions with built-in metric definitions.
  - Implement a fallback for the non-standard installation directory of `unbound-control` and it's config on OPNsense.
- **1.2.0** — Last upstream release (Jan-Philipp Litza / PLUTEX).
