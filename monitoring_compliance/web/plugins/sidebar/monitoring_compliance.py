#!/usr/bin/env python3
"""Sidebar snap-in linking to the Monitoring Compliance dashboard, plus the JSON AJAX
endpoint that feeds it.

The dashboard itself (see ``package's web/htdocs/monitoring_compliance/``) is a standalone,
static web page -- deliberately not a Setup/WATO page (there is no stable, documented
third-party API for adding one to Checkmk's Setup section) and not embedded in the sidebar
itself beyond a bookmark-style link. A sidebar snap-in is the one genuinely stable,
documented place to add a discoverable entry point to it in Checkmk's own UI.

It shows two things the check services themselves only summarize in plain-text notices:

* The persistent **Capability Database**
  (``$OMD_ROOT/var/monitoring_compliance/capability_db.json``, written by the
  ``monitoring_compliance`` check -- see ``agent_based/monitoring_compliance.py``'s
  ``_update_capability_db``) -- every capability ever observed on any host, deduplicated,
  with type/name/token, which hosts it was seen on, monitorable/monitored flags and
  first/last-seen timestamps.
* The **Known Catalog** (the ``ALIASES``/``TITLES``/``HINTS``/``_SIGNATURES_RAW`` tables in
  ``agent_based/monitoring_compliance.py``) -- every application type the detection logic
  recognizes at all, annotated with whether a covering check plug-in is currently available
  on this site (via ``cmk -L``, the same call and cache file the special agent itself uses:
  ``$OMD_ROOT/tmp/monitoring_compliance_plugins.cache`` -- so a plug-in that only just
  arrived via a freshly uploaded MKP is picked up the same way, once the cache expires or a
  fresh page load re-runs ``cmk -L``). The dashboard additionally lets an admin add, edit or
  remove catalog entries at runtime (see "Known Catalog editing" below) -- these
  additions/overrides/tombstones are stored separately from the built-in tables, in
  ``$OMD_ROOT/var/monitoring_compliance/custom_catalog.json``.

Both are read directly by this AJAX endpoint (it runs as the site user in the GUI process,
so it can read the database file and shell out to ``cmk -L`` itself) -- no special agent run
or check service needed to view them. The Capability Database is always read-only here; the
Known Catalog additionally accepts writes for its custom-entries layer (CSRF-protected, see
``MonitoringComplianceData`` below).

Known Catalog editing
----------------------
An entry added/edited here is **actively used by the real detection check**, not just
shown on this reference page: ``agent_based/monitoring_compliance.py``'s
``check_monitoring_compliance`` reads this same ``custom_catalog.json`` on every check run
(``_load_dashboard_catalog_entries`` / ``_dashboard_catalog_rules``) and feeds each entry's
"Matches" patterns into ``_resolve_token()`` as case-insensitive regexes, exactly like a
host-specific entry in the "Custom capability mappings" check parameter already does -- a
host-specific mapping there still wins over a dashboard entry for the same token, and both
are checked before the built-in ``ALIASES``/``_SIGNATURES_RAW`` tables. The entry's title
and hint are likewise used in that check's finding messages, not just here. The one caveat
called out again in the dashboard's own UI copy: this changes *detection* (whether a
capability resolves to your token at all), never Setup/WATO configuration -- whether that
token then counts as "monitored" still depends on which plug-ins are actually assigned to
the host. Disable this per host via the "Ignore the Known Catalog dashboard's custom
entries" check parameter if a host should not pick up site-wide dashboard entries at all.

Storage format of ``custom_catalog.json``: ``{"entries": {"<token>": null | {"title":
str, "patterns": [str, ...], "hint": str}}}``. A ``null`` value is a tombstone -- it hides
that token entirely from the merged catalog *view* and is never fed into detection either
way (whether the token was originally built-in or itself only ever existed in this
custom-entries file; built-in detection itself is unaffected by a tombstone, same as
before). A dict value both creates a brand-new entry (if the token isn't one of the
built-in ``TITLES``) and overrides an existing one (built-in or custom) with the same
token -- and its ``patterns`` are validated as compilable regexes when saved (see
``_save_catalog_entry``), since a bad pattern would otherwise just silently never match at
check time.

Packaging / loading
--------------------
This file is a *legacy web plug-in*. Checkmk loads it via ``cmk.gui.sidebar`` ->
``load_web_plugins("sidebar", globals())`` from
``$OMD_ROOT/local/share/check_mk/web/plugins/sidebar/``. That loader injects the sidebar API
(``SidebarSnapin``, ``snapin_registry`` ...) into this module's globals; we additionally
import them from ``cmk.gui.sidebar`` so the module is also importable/analysable on its own.
The snap-in registers itself at import time via ``snapin_registry.register``.

The AJAX endpoint is registered the same way (import-time side effect), but through
``cmk.gui.pages.page_registry`` -- the generic, documented mechanism every JSON AJAX endpoint
in Checkmk's own GUI uses (e.g. ``cmk.gui.views.page_ajax_reschedule``, the "reschedule
check now" button's endpoint, follows the identical ``AjaxPage`` + ``PageEndpoint`` pattern
this file copies).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any, override

from flask import session

# --- Checkmk GUI API (stable public modules) -------------------------------
from cmk.ccc.exceptions import MKGeneralException
from cmk.gui.config import Config
from cmk.gui.htmllib.html import html
from cmk.gui.http import request
from cmk.gui.i18n import _
from cmk.gui.pages import AjaxPage, PageContext, PageEndpoint, PageResult, page_registry
from cmk.gui.utils.csrf_token import check_csrf_token

# --- Sidebar API -----------------------------------------------------------
# These names are injected into this module's globals by load_web_plugins().
# Importing them explicitly is safe (the cmk.gui.sidebar module has already
# bound them by the time the loader runs) and keeps the module self-contained.
from cmk.gui.sidebar import (  # noqa: E402
    SidebarSnapin,
    snapin_registry,
    write_snapin_exception,
)

# Relative to the current site's /check_mk/ base -- resolves to
# /<site>/check_mk/monitoring_compliance/index.html without needing to know the site name
# or host. Matches the .mkp's htdocs layout
# (web/htdocs/monitoring_compliance/index.html).
_URL_DASHBOARD = "monitoring_compliance/index.html"
_ACTION_PAGE_NAME = "monitoring_compliance_data"

# Same cache TTL/file the special agent's own available_plugins() uses
# (agent_based/../libexec/agent_monitoring_compliance) -- sharing the cache file means a
# fresh special-agent run and a dashboard page load never both pay for their own `cmk -L`.
_PLUGIN_CACHE_TTL = 3600


def _omd_root() -> Path:
    omd_root = os.environ.get("OMD_ROOT")
    if not omd_root:
        raise MKGeneralException(_("OMD_ROOT is not set -- not running inside a Checkmk site"))
    return Path(omd_root)


def _current_csrf_token() -> str | None:
    # Mirrors cmk.gui.htmllib.generator's own set_js_csrf_token(), the same mechanism
    # Checkmk's page renderer uses to hand the browser a token for later AJAX calls --
    # necessary here because the dashboard is plain static HTML, never rendered by Checkmk's
    # own HTML generator, so it never gets a csrf token embedded automatically the way a
    # normal Checkmk page would. Broad try/except deliberately: this must never turn into an
    # unhandled error for the read-only "catalog" action just because session/session_info
    # isn't there (e.g. an unauthenticated/automation session, or -- as caught by this
    # extension's own build smoke test -- no Flask request context at all) -- accessing the
    # werkzeug session proxy outside of one raises RuntimeError, which plain hasattr() would
    # not catch.
    try:
        if not hasattr(session, "session_info"):
            return None
        return session.session_info.csrf_token
    except Exception:  # noqa: BLE001
        return None


def _capability_db_path() -> Path:
    # Mirrors agent_based/monitoring_compliance.py's _db_path() default exactly. A custom
    # "Alternative capability database path" configured in the special-agent rule is
    # intentionally not read here (that would mean this GUI page accepting/following an
    # arbitrary file path); if a custom path is in use, the page's "not found" message names
    # the default path it looked for instead.
    return _omd_root() / "var" / "monitoring_compliance" / "capability_db.json"


def _human_size(num: float) -> str:
    for unit in ("B", "KiB", "MiB", "GiB"):
        if abs(num) < 1024.0:
            return f"{num:.0f} {unit}" if unit == "B" else f"{num:.1f} {unit}"
        num /= 1024.0
    return f"{num:.1f} TiB"


def _load_capability_db() -> dict[str, Any]:
    path = _capability_db_path()
    if not path.is_file():
        return {"exists": False, "path": str(path)}

    try:
        size_bytes = path.stat().st_size
        with path.open(encoding="utf-8") as fh:
            db = json.load(fh)
    except Exception as exc:  # noqa: BLE001
        return {"exists": True, "path": str(path), "error": str(exc)}

    caps = db.get("capabilities", {}) if isinstance(db, dict) else {}
    by_type: dict[str, int] = {}
    hosts: set[str] = set()
    tokens: set[str] = set()
    monitorable = monitored = 0
    entries: list[dict[str, Any]] = []

    for rec in caps.values():
        if not isinstance(rec, dict):
            continue
        ctype = str(rec.get("type", "?"))
        by_type[ctype] = by_type.get(ctype, 0) + 1
        is_monitorable = bool(rec.get("monitorable"))
        is_monitored = bool(rec.get("monitored"))
        if is_monitorable:
            monitorable += 1
        if is_monitored:
            monitored += 1
        token = str(rec.get("token") or "")
        if token:
            tokens.add(token)
        rec_hosts = [str(h) for h in (rec.get("hosts") or [])]
        hosts.update(rec_hosts)
        entries.append({
            "type": ctype,
            "name": str(rec.get("name", "")),
            "token": token,
            "hosts": rec_hosts,
            "monitorable": is_monitorable,
            "monitored": is_monitored,
            "first_seen": int(rec.get("first_seen", 0) or 0),
            "last_seen": int(rec.get("last_seen", 0) or 0),
        })

    entries.sort(key=lambda e: (-e["last_seen"], e["type"], e["name"]))

    return {
        "exists": True,
        "path": str(path),
        "size_bytes": size_bytes,
        "size_human": _human_size(size_bytes),
        "updated_ts": int(db.get("updated_ts", 0)) if isinstance(db, dict) else 0,
        "total": len(caps),
        "monitorable": monitorable,
        "monitored": monitored,
        "hosts": len(hosts),
        "tokens": len(tokens),
        "by_type": by_type,
        "entries": entries,
    }


def _plugin_token(name: str) -> str:
    m = re.match(r"[a-z0-9]+", str(name).lower())
    return m.group(0) if m else ""


def _clean_pattern(pat: str) -> str:
    out = pat.replace(r"\b", "").replace(r"\s*", " ").replace("\\", "")
    return out.strip()


# ---------------------------------------------------------------------------
# Custom Known Catalog entries (user additions/overrides/tombstones)
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"^[a-z][a-z0-9_]{1,39}$")


def _custom_catalog_path() -> Path:
    return _omd_root() / "var" / "monitoring_compliance" / "custom_catalog.json"


def _validate_token(raw: str) -> str:
    token = raw.strip().lower()
    if not _TOKEN_RE.match(token):
        raise MKGeneralException(_(
            "Invalid token %r: must be 2-40 characters, lowercase letters/digits/"
            "underscore only, starting with a letter (this is matched against the "
            "leading identifier of a Checkmk plug-in name, e.g. plug-in "
            "'foobar_status' needs token 'foobar').") % raw)
    return token


def _load_custom_catalog_raw() -> dict[str, Any]:
    path = _custom_catalog_path()
    if not path.is_file():
        return {"entries": {}}
    try:
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict) and isinstance(data.get("entries"), dict):
            return data
    except Exception:  # noqa: BLE001
        pass
    return {"entries": {}}


def _write_custom_catalog_raw(data: dict[str, Any]) -> None:
    import fcntl  # noqa: PLC0415
    import tempfile  # noqa: PLC0415

    path = _custom_catalog_path()
    directory = path.parent
    directory.mkdir(parents=True, exist_ok=True)
    lock_path = str(path) + ".lock"
    with open(lock_path, "w", encoding="utf-8") as lock_fh:
        fcntl.flock(lock_fh, fcntl.LOCK_EX)
        try:
            data["updated_ts"] = int(time.time())
            fd, tmp = tempfile.mkstemp(dir=directory)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh)
            os.replace(tmp, path)
        finally:
            fcntl.flock(lock_fh, fcntl.LOCK_UN)


def _save_catalog_entry() -> dict[str, Any]:
    """Handles both "add a new application" and "edit an existing one" -- an upsert keyed
    by token, same as the module docstring's storage format describes.

    Patterns are validated as compilable regexes here (they are fed to
    ``monitoring_compliance``'s ``_resolve_token()`` as ``re.search(pattern, raw,
    re.IGNORECASE)`` on every check run once saved) -- rejecting a bad one immediately is
    much friendlier than it silently never matching anything at check time.
    """
    token = _validate_token(request.get_str_input_mandatory("token"))
    title = request.get_str_input_mandatory("title").strip()
    if not title:
        raise MKGeneralException(_("Title must not be empty"))
    patterns_raw = request.get_str_input("patterns") or ""
    patterns = [p.strip() for p in patterns_raw.splitlines() if p.strip()]
    for pattern in patterns:
        try:
            re.compile(pattern)
        except re.error as exc:
            raise MKGeneralException(
                _("Invalid pattern %r (must be a valid regular expression): %s")
                % (pattern, exc)
            ) from exc
    hint = (request.get_str_input("hint") or "").strip()

    data = _load_custom_catalog_raw()
    data.setdefault("entries", {})[token] = {
        "title": title,
        "patterns": patterns,
        "hint": hint,
    }
    _write_custom_catalog_raw(data)
    return {"token": token}


def _delete_catalog_entry() -> dict[str, Any]:
    """Tombstones a token (dict value -> null) rather than physically removing the key --
    this also correctly hides a *built-in* token that never had a custom override before."""
    token = _validate_token(request.get_str_input_mandatory("token"))
    data = _load_custom_catalog_raw()
    data.setdefault("entries", {})[token] = None
    _write_custom_catalog_raw(data)
    return {"token": token}


def _available_plugins() -> tuple[list[str], list[str]]:
    """Same source and cache file as the special agent's own available_plugins()."""
    errors: list[str] = []
    cache_file = _omd_root() / "tmp" / "monitoring_compliance_plugins.cache"

    try:
        if cache_file.is_file() and (time.time() - cache_file.stat().st_mtime) < _PLUGIN_CACHE_TTL:
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            if isinstance(cached, list):
                return [str(p) for p in cached], errors
    except Exception as exc:  # noqa: BLE001
        errors.append(f"Plug-in cache not readable: {exc}")

    plugins: set[str] = set()
    try:
        proc = subprocess.run(
            ["cmk", "-L"], capture_output=True, text=True, timeout=30, check=False,
        )
        for line in proc.stdout.splitlines():
            if not line or line.startswith(" "):
                continue
            name = line.split()[0]
            if name:
                plugins.add(name)
        if not plugins and proc.stderr:
            errors.append(f"cmk -L returned no result: {proc.stderr.strip()[:200]}")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"cmk -L failed: {exc}")

    result = sorted(plugins)
    try:
        if result:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps(result), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    return result, errors


def _load_known_catalog() -> dict[str, Any]:
    try:
        from cmk_addons.plugins.monitoring_compliance.agent_based.monitoring_compliance import (  # noqa: E501
            ALIASES,
            HINTS,
            TITLES,
            _SIGNATURES_RAW,
        )
    except Exception:  # noqa: BLE001
        ALIASES, HINTS, TITLES = {}, {}, {}
        _SIGNATURES_RAW = ()

    available, errors = _available_plugins()
    avail_tokens = {_plugin_token(p) for p in available}

    # Built-in entries first (from the compliance check's own source tables) ...
    merged: dict[str, dict[str, Any]] = {}
    for tok in TITLES:
        patterns_raw = [p for p, t in _SIGNATURES_RAW if t == tok]
        patterns_raw += sorted({a for a, t in ALIASES.items() if t == tok})
        seen: set[str] = set()
        patterns: list[str] = []
        for p in patterns_raw:
            cleaned = _clean_pattern(p)
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                patterns.append(cleaned)
        merged[tok] = {
            "title": TITLES.get(tok, tok),
            "patterns": patterns,
            "hint": HINTS.get(tok, ""),
            "custom": False,
        }

    # ... then layer the user-maintained additions/overrides/tombstones on top (see the
    # module docstring's "Known Catalog editing" section for the storage format).
    custom = _load_custom_catalog_raw()
    for tok, override in custom.get("entries", {}).items():
        if override is None:
            merged.pop(tok, None)
            continue
        if not isinstance(override, dict):
            continue
        merged[tok] = {
            "title": str(override.get("title") or tok),
            "patterns": [str(p) for p in (override.get("patterns") or []) if str(p).strip()],
            "hint": str(override.get("hint", "")),
            "custom": True,
        }

    entries: list[dict[str, Any]] = []
    for tok, rec in merged.items():
        entries.append({
            "token": tok,
            "title": rec["title"],
            "available": tok in avail_tokens,
            "patterns": rec["patterns"],
            "hint": rec["hint"],
            "custom": rec["custom"],
        })

    entries.sort(key=lambda e: (not e["available"], e["title"]))

    return {
        "total": len(entries),
        "available_count": sum(1 for e in entries if e["available"]),
        "entries": entries,
        "errors": errors,
        "csrf_token": _current_csrf_token(),
    }


class MonitoringComplianceSnapin(SidebarSnapin):
    """A single bookmark link to the standalone Monitoring Compliance dashboard."""

    @classmethod
    def type_name(cls) -> str:
        return "monitoring_compliance"

    @classmethod
    def title(cls) -> str:
        return _("Monitoring Compliance")

    @classmethod
    def description(cls) -> str:
        return _(
            "One-click link to the Monitoring Compliance dashboard: the persistent "
            "Capability Database (every capability ever observed, deduplicated, with the "
            "hosts it was seen on) and the editable Known Catalog (every application type "
            "the detection logic recognizes, annotated with plug-in availability on this "
            "site; add, edit or remove catalog entries directly from the dashboard)."
        )

    @classmethod
    def refresh_regularly(cls) -> bool:
        return False

    def show(self, config: Config) -> None:
        try:
            self._render()
        except Exception as exc:  # noqa: BLE001 - never blank the whole sidebar
            write_snapin_exception(exc)

    def _render(self) -> None:
        html.open_div(style="padding:2px 0;")
        html.open_a(href=_URL_DASHBOARD, target="_blank",
                    title=_("Open the Monitoring Compliance dashboard in a new tab"))
        html.write_text_permissive(_("\U0001f4cb Compliance Dashboard"))
        html.close_a()
        html.open_div(style="color:#888;font-size:90%;margin-top:4px;")
        html.write_text_permissive(
            _("Capability Database & Known Catalog, browsable and searchable."))
        html.close_div()
        html.close_div()


snapin_registry.register(MonitoringComplianceSnapin)


class MonitoringComplianceData(AjaxPage):
    """JSON AJAX endpoint the dashboard's own JS calls to load both databases and to edit
    the Known Catalog's custom-entries layer.

    Reachable at /<site>/check_mk/monitoring_compliance_data.py -- same AjaxPage/
    PageEndpoint pattern as every other JSON AJAX page in Checkmk's own GUI (e.g.
    'reschedule check now', cmk.gui.views.page_ajax_reschedule.PageRescheduleCheck).
    AjaxPage.handle_page() wraps whatever page() returns into
    {"result_code", "result", "severity"} and serializes it -- no manual JSON encoding or
    content-type handling needed here.

    "capdb"/"catalog" are read-only (no CSRF check). "catalog_save"/"catalog_delete" write
    to custom_catalog.json and require the CSRF token the dashboard got from its last
    "catalog" load (see _current_csrf_token()) -- matching every other state-changing
    action in Checkmk's own GUI.
    """

    @override
    def page(self, ctx: PageContext) -> PageResult:
        action = request.get_ascii_input_mandatory("action")
        if action == "capdb":
            return _load_capability_db()
        if action == "catalog":
            return _load_known_catalog()
        if action == "catalog_save":
            check_csrf_token()
            return _save_catalog_entry()
        if action == "catalog_delete":
            check_csrf_token()
            return _delete_catalog_entry()
        raise MKGeneralException(_("Unknown action: %s") % action)


page_registry.register(PageEndpoint(_ACTION_PAGE_NAME, MonitoringComplianceData()))
