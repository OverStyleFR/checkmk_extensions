/* Monitoring Compliance Dashboard
 *
 * Static page served by the monitoring_compliance .mkp
 * (web/htdocs/monitoring_compliance/). Talks to the AJAX endpoint registered by
 * web/plugins/sidebar/monitoring_compliance.py at
 * /<site>/check_mk/monitoring_compliance_data.py -- one directory up from this page,
 * same relative-URL pattern used by every sibling GameQuest/Checkmk static app.
 */
(function () {
  "use strict";

  var DATA_URL = "../monitoring_compliance_data.py";

  // Set from the last successful "catalog" load (see renderCatalog) -- needed for the
  // mutating catalog_save/catalog_delete actions. Checkmk's check_csrf_token() reads it
  // from a "_csrf_token" request var (note the leading underscore), matching what
  // cmk.gui.htmllib.generator's set_js_csrf_token() would normally embed for a page
  // Checkmk itself rendered; this dashboard is plain static HTML, so it has to be fetched
  // explicitly instead.
  var csrfToken = null;

  function authRequiredError() {
    var err = new Error(
      "You are not logged in to this Checkmk site. Please log in, then reload this page."
    );
    err.authRequired = true;
    return err;
  }

  function handleAjaxResponse(promise) {
    return promise
      .catch(function () {
        throw new Error(
          "Could not reach the monitoring_compliance_data.py endpoint. This page only " +
          "works when opened through an installed monitoring_compliance .mkp on a " +
          "Checkmk site, not as a local/standalone file."
        );
      })
      .then(function (resp) {
        // An unauthenticated request gets redirected to Checkmk's login page -- fetch()
        // follows that transparently, so what lands here is a 200 OK whose body is the
        // login page's HTML, not our JSON. Detected two ways: the final URL now names
        // login.py (fetch's `resp.url` reflects the post-redirect URL), or -- as a
        // fallback covering any other non-JSON response -- the content-type isn't JSON.
        // Either way this is a distinct, expected condition, not a real error: it gets a
        // dedicated friendly prompt (see showAuthRequired()) instead of the generic red
        // error banner.
        if (/\/login\.py(?:[?#]|$)/.test(resp.url)) {
          throw authRequiredError();
        }
        var contentType = resp.headers.get("content-type") || "";
        if (contentType.indexOf("json") === -1) {
          throw authRequiredError();
        }
        return resp.json().catch(function () {
          throw new Error("Unexpected response from the site (not valid JSON).");
        });
      })
      .then(function (data) {
        if (data.result_code !== 0) {
          throw new Error(typeof data.result === "string" ? data.result : "Request failed.");
        }
        return data.result;
      });
  }

  function apiGet(action) {
    var qs = new URLSearchParams({ action: action }).toString();
    return handleAjaxResponse(
      fetch(DATA_URL + "?" + qs, { method: "GET", credentials: "same-origin" })
    );
  }

  function apiPost(action, params) {
    var body = new URLSearchParams(
      Object.assign({ action: action, _csrf_token: csrfToken || "" }, params || {})
    );
    return handleAjaxResponse(
      fetch(DATA_URL, { method: "POST", credentials: "same-origin", body: body })
    );
  }

  function escapeHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function fmtDate(ts) {
    if (!ts) return "–";
    var d = new Date(ts * 1000);
    return d.toLocaleString();
  }

  function fmtAge(ts) {
    if (!ts) return null;
    var seconds = Math.max(0, Math.floor(Date.now() / 1000) - ts);
    if (seconds < 90) return seconds + " s ago";
    if (seconds < 5400) return Math.round(seconds / 60) + " min ago";
    if (seconds < 172800) return (seconds / 3600).toFixed(1) + " h ago";
    return (seconds / 86400).toFixed(1) + " d ago";
  }

  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    attrs = attrs || {};
    Object.keys(attrs).forEach(function (k) {
      if (k === "text") node.textContent = attrs[k];
      else if (k === "html") node.innerHTML = attrs[k];
      else node.setAttribute(k, attrs[k]);
    });
    (children || []).forEach(function (c) { node.appendChild(c); });
    return node;
  }

  // -- generic sortable/filterable table state --------------------------------

  function makeTableController(opts) {
    // opts: { rows, columns: [{key, label, get(row), sortValue(row), render(row)}],
    //         searchFields(row) -> string[], defaultSort: {key, dir} }
    var state = {
      search: "",
      sortKey: opts.defaultSort.key,
      sortDir: opts.defaultSort.dir,
      extraFilter: null, // function(row) -> bool
    };

    function filtered() {
      var q = state.search.trim().toLowerCase();
      var rows = opts.rows;
      if (state.extraFilter) rows = rows.filter(state.extraFilter);
      if (q) {
        rows = rows.filter(function (row) {
          return opts.searchFields(row).some(function (f) {
            return String(f || "").toLowerCase().indexOf(q) !== -1;
          });
        });
      }
      var col = opts.columns.find(function (c) { return c.key === state.sortKey; });
      if (col) {
        var dir = state.sortDir === "desc" ? -1 : 1;
        rows = rows.slice().sort(function (a, b) {
          var av = col.sortValue(a);
          var bv = col.sortValue(b);
          if (av < bv) return -1 * dir;
          if (av > bv) return 1 * dir;
          return 0;
        });
      }
      return rows;
    }

    return { state: state, filtered: filtered };
  }

  function renderTable(container, ctrl, columns) {
    var table = el("table");
    var thead = el("thead");
    var headRow = el("tr");
    columns.forEach(function (col) {
      var th = el("th", { text: col.label });
      if (col.sortable === false) {
        th.style.cursor = "default";
      } else {
        if (col.key === ctrl.state.sortKey) {
          th.classList.add("sorted");
          if (ctrl.state.sortDir === "desc") th.classList.add("desc");
        }
        th.addEventListener("click", function () {
          if (ctrl.state.sortKey === col.key) {
            ctrl.state.sortDir = ctrl.state.sortDir === "asc" ? "desc" : "asc";
          } else {
            ctrl.state.sortKey = col.key;
            ctrl.state.sortDir = "asc";
          }
          rerender();
        });
      }
      headRow.appendChild(th);
    });
    thead.appendChild(headRow);
    table.appendChild(thead);

    var tbody = el("tbody");
    var rows = ctrl.filtered();
    if (rows.length === 0) {
      var td = el("td", { colspan: String(columns.length), class: "muted" });
      td.textContent = "No matching entries.";
      var tr = el("tr");
      tr.appendChild(td);
      tbody.appendChild(tr);
    } else {
      rows.forEach(function (row) {
        var tr = el("tr");
        columns.forEach(function (col) {
          var td = document.createElement("td");
          if (col.cls) td.className = col.cls;
          td.innerHTML = col.render(row);
          tr.appendChild(td);
        });
        tbody.appendChild(tr);
      });
    }
    table.appendChild(tbody);

    var scroller = el("div", { class: "table-scroll" });
    scroller.appendChild(table);
    container.innerHTML = "";
    container.appendChild(scroller);

    function rerender() {
      renderTable(container, ctrl, columns);
    }
  }

  function statusBadge(ok, yes, no) {
    return ok
      ? '<span class="badge ok">' + escapeHtml(yes) + "</span>"
      : '<span class="badge neutral">' + escapeHtml(no) + "</span>";
  }

  // -- Capability Database ------------------------------------------------

  function renderCapdb(data) {
    var content = document.getElementById("capdb-content");
    content.innerHTML = "";

    if (data.error) {
      content.appendChild(el("div", {
        class: "error-banner",
        text: "Capability database at " + data.path + " could not be read: " + data.error,
      }));
      return;
    }

    if (!data.exists) {
      content.appendChild(el("div", { class: "empty-state", html:
        "No capability database found yet.<br>Expected at:<br><code>" +
        escapeHtml(data.path) + "</code><br><br>" +
        "Enable &ldquo;Report capability database statistics&rdquo; in the " +
        "&ldquo;Checkmk Monitoring Compliance&rdquo; special-agent rule on exactly one " +
        "host (e.g. the Checkmk server), and make sure the " +
        "&ldquo;Checkmk Monitoring Compliance&rdquo; check has run at least once anywhere " +
        "to start populating it."
      }));
      return;
    }

    var tiles = el("div", { class: "tiles" });
    var age = fmtAge(data.updated_ts);
    [
      [data.total, "Entries"],
      [data.monitorable, "Monitorable"],
      [data.monitored, "Monitored"],
      [data.hosts, "Distinct hosts"],
      [data.tokens, "Distinct tokens"],
      [data.size_human, "Database size"],
      [age || "–", "Last update"],
    ].forEach(function (pair) {
      tiles.appendChild(el("div", { class: "tile" }, [
        el("div", { class: "value", text: String(pair[0]) }),
        el("div", { class: "label", text: pair[1] }),
      ]));
    });
    content.appendChild(tiles);

    var byType = el("div", { class: "by-type" });
    Object.keys(data.by_type).sort().forEach(function (t) {
      byType.appendChild(el("span", { class: "chip", html:
        escapeHtml(t) + ": <b>" + data.by_type[t] + "</b>" }));
    });
    content.appendChild(byType);

    var controls = el("div", { class: "controls" });
    var search = el("input", { type: "search", placeholder: "Search name, token, type, host…" });
    var typeSelect = el("select");
    typeSelect.appendChild(el("option", { value: "", text: "All types" }));
    Object.keys(data.by_type).sort().forEach(function (t) {
      typeSelect.appendChild(el("option", { value: t, text: t }));
    });
    var statusSelect = el("select");
    [
      ["", "All"],
      ["monitorable", "Monitorable"],
      ["not-monitorable", "Not monitorable"],
      ["monitored", "Monitored"],
      ["not-monitored", "Not monitored"],
    ].forEach(function (pair) {
      statusSelect.appendChild(el("option", { value: pair[0], text: pair[1] }));
    });
    var count = el("span", { class: "count" });
    controls.appendChild(search);
    controls.appendChild(typeSelect);
    controls.appendChild(statusSelect);
    controls.appendChild(count);
    content.appendChild(controls);

    var tableHost = el("div");
    content.appendChild(tableHost);

    var columns = [
      { key: "type", label: "Type", sortValue: function (r) { return r.type; },
        render: function (r) { return escapeHtml(r.type); } },
      { key: "name", label: "Name", sortValue: function (r) { return r.name.toLowerCase(); },
        render: function (r) { return escapeHtml(r.name); } },
      { key: "token", label: "Token", cls: "mono", sortValue: function (r) { return r.token; },
        render: function (r) { return r.token ? '<code>' + escapeHtml(r.token) + '</code>' : '<span class="muted">–</span>'; } },
      { key: "monitorable", label: "Monitorable", sortValue: function (r) { return r.monitorable ? 1 : 0; },
        render: function (r) { return statusBadge(r.monitorable, "yes", "no"); } },
      { key: "monitored", label: "Monitored", sortValue: function (r) { return r.monitored ? 1 : 0; },
        render: function (r) { return statusBadge(r.monitored, "yes", "no"); } },
      { key: "hosts", label: "Hosts", cls: "hosts", sortValue: function (r) { return r.hosts.length; },
        render: function (r) {
          if (!r.hosts.length) return '<span class="muted">–</span>';
          var shown = r.hosts.slice(0, 3).map(escapeHtml).join(", ");
          var extra = r.hosts.length > 3 ? " +" + (r.hosts.length - 3) + " more" : "";
          return '<span title="' + escapeHtml(r.hosts.join(", ")) + '">' + shown + extra + "</span>";
        } },
      { key: "first_seen", label: "First seen", sortValue: function (r) { return r.first_seen; },
        render: function (r) { return fmtDate(r.first_seen); } },
      { key: "last_seen", label: "Last seen", sortValue: function (r) { return r.last_seen; },
        render: function (r) { return fmtDate(r.last_seen); } },
    ];
    if (data.can_edit) {
      // Row identity for the delegated click handler below is an index into data.entries
      // (assigned once, up front) rather than encoding type/name/token into the DOM --
      // a capability's raw "name" is arbitrary text (a process/package name), unsafe to
      // pack into a delimited attribute value.
      data.entries.forEach(function (r, i) { r._idx = i; });
      columns.push({
        key: "_adopt", label: "Actions", sortable: false, sortValue: function () { return 0; },
        render: function (r) {
          return '<button type="button" class="btn small" data-adopt-idx="' + r._idx +
            '">&rarr; Known Catalog</button>';
        },
      });
    }

    var ctrl = makeTableController({
      rows: data.entries,
      columns: columns,
      searchFields: function (r) { return [r.type, r.name, r.token].concat(r.hosts); },
      defaultSort: { key: "last_seen", dir: "desc" },
    });

    function applyFilters() {
      var type = typeSelect.value;
      var status = statusSelect.value;
      ctrl.state.extraFilter = function (r) {
        if (type && r.type !== type) return false;
        if (status === "monitorable" && !r.monitorable) return false;
        if (status === "not-monitorable" && r.monitorable) return false;
        if (status === "monitored" && !r.monitored) return false;
        if (status === "not-monitored" && r.monitored) return false;
        return true;
      };
      ctrl.state.search = search.value;
      renderTable(tableHost, ctrl, columns);
      count.textContent = ctrl.filtered().length + " / " + data.entries.length + " entries";
    }

    // Delegated on the (stable) tableHost container, same reasoning as the Known
    // Catalog table's row actions: a header-click re-sort replaces the row buttons via
    // renderTable's own internal rerender, not through applyFilters.
    tableHost.addEventListener("click", function (ev) {
      var btn = ev.target.closest("[data-adopt-idx]");
      if (!btn) return;
      var row = data.entries[Number(btn.getAttribute("data-adopt-idx"))];
      if (row) openAdoptModal(row);
    });

    search.addEventListener("input", applyFilters);
    typeSelect.addEventListener("change", applyFilters);
    statusSelect.addEventListener("change", applyFilters);
    applyFilters();
  }

  // -- Known Catalog --------------------------------------------------------

  // Last-loaded catalog response, kept around so the Capability Database tab's "Adopt
  // into Known Catalog" action can offer existing entries to assign to without a
  // separate fetch (both tabs load together via the "bootstrap" action anyway).
  var lastCatalogData = null;

  function loadCatalog() {
    return apiGet("catalog").then(function (data) {
      csrfToken = data.csrf_token || csrfToken;
      lastCatalogData = data;
      renderCatalog(data);
      return data;
    });
  }

  function renderCatalog(data) {
    var content = document.getElementById("catalog-content");
    content.innerHTML = "";

    var tiles = el("div", { class: "tiles" });
    [
      [data.total, "Known application types"],
      [data.available_count, "Monitorable on this site"],
      [data.total - data.available_count, "No covering plug-in"],
    ].forEach(function (pair) {
      tiles.appendChild(el("div", { class: "tile" }, [
        el("div", { class: "value", text: String(pair[0]) }),
        el("div", { class: "label", text: pair[1] }),
      ]));
    });
    content.appendChild(tiles);

    if (data.errors && data.errors.length) {
      content.appendChild(el("div", { class: "error-banner",
        text: "Notes: " + data.errors.join("; ") }));
    }

    var controls = el("div", { class: "controls" });
    var search = el("input", { type: "search", placeholder: "Search title, token, pattern…" });
    var statusSelect = el("select");
    [["", "All"], ["available", "Monitorable"], ["unavailable", "Not available"]].forEach(function (pair) {
      statusSelect.appendChild(el("option", { value: pair[0], text: pair[1] }));
    });
    // Add/Edit/Delete require the "wato.edit" permission server-side regardless of what
    // this UI shows -- can_edit only decides whether to show controls that would
    // otherwise just fail with a permission error on click. See _EDIT_PERMISSION in
    // web/plugins/sidebar/monitoring_compliance.py for the actual enforcement.
    var count = el("span", { class: "count" });
    controls.appendChild(search);
    controls.appendChild(statusSelect);
    if (data.can_edit) {
      var addBtn = el("button", { type: "button", class: "btn primary", text: "+ Add application" });
      addBtn.addEventListener("click", function () { openCatalogModal(null); });
      controls.appendChild(addBtn);
    }
    controls.appendChild(count);
    content.appendChild(controls);

    if (!data.total) {
      content.appendChild(el("div", { class: "empty-state", html:
        "Known catalog is empty (catalog tables unavailable, or the " +
        "&ldquo;Report known catalog&rdquo; option is not enabled in the " +
        "&ldquo;Checkmk Monitoring Compliance&rdquo; special-agent rule)." +
        (data.can_edit ? " You can still add your own entries above." : "")
      }));
      return;
    }

    var tableHost = el("div");
    content.appendChild(tableHost);

    var columns = [
      { key: "title", label: "Application", sortValue: function (r) { return r.title.toLowerCase(); },
        render: function (r) {
          return escapeHtml(r.title) + (r.custom ? '<span class="badge custom-tag">custom</span>' : "");
        } },
      { key: "token", label: "Token", cls: "mono", sortValue: function (r) { return r.token; },
        render: function (r) { return '<code>' + escapeHtml(r.token) + '</code>'; } },
      { key: "available", label: "Status", sortValue: function (r) { return r.available ? 1 : 0; },
        render: function (r) {
          return r.available
            ? '<span class="badge ok">monitorable</span>'
            : '<span class="badge warn">no plug-in here</span>';
        } },
      { key: "patterns", label: "Matches", sortValue: function (r) { return r.patterns.length; },
        render: function (r) {
          if (!r.patterns.length) return '<span class="muted">–</span>';
          return '<span class="patterns">' + r.patterns.map(function (p) {
            return '<span class="chip">' + escapeHtml(p) + '</span>';
          }).join("") + '</span>';
        } },
      { key: "hint", label: "Deployment hint", sortValue: function (r) { return r.hint; },
        render: function (r) { return r.hint ? escapeHtml(r.hint) : '<span class="muted">–</span>'; } },
    ];
    if (data.can_edit) {
      columns.push({
        key: "_actions", label: "Actions", sortable: false, sortValue: function () { return 0; },
        render: function (r) {
          return (
            '<span class="row-actions">' +
            '<button type="button" class="btn small" data-edit="' + escapeHtml(r.token) + '">Edit</button>' +
            '<button type="button" class="btn small danger" data-delete="' + escapeHtml(r.token) + '">Delete</button>' +
            "</span>"
          );
        },
      });
    }

    var ctrl = makeTableController({
      rows: data.entries,
      columns: columns,
      searchFields: function (r) { return [r.title, r.token].concat(r.patterns); },
      defaultSort: { key: "title", dir: "asc" },
    });

    function applyFilters() {
      var status = statusSelect.value;
      ctrl.state.extraFilter = function (r) {
        if (status === "available" && !r.available) return false;
        if (status === "unavailable" && r.available) return false;
        return true;
      };
      ctrl.state.search = search.value;
      renderTable(tableHost, ctrl, columns);
      count.textContent = ctrl.filtered().length + " / " + data.entries.length + " types";
    }

    // Delegated on the (stable) tableHost container rather than rebound per render --
    // clicking a column header to re-sort replaces the buttons underneath via renderTable's
    // own internal rerender (not through applyFilters), which would otherwise leave fresh
    // Edit/Delete buttons with no listeners at all.
    tableHost.addEventListener("click", function (ev) {
      var editBtn = ev.target.closest("[data-edit]");
      if (editBtn) {
        var tok = editBtn.getAttribute("data-edit");
        var entry = data.entries.find(function (e) { return e.token === tok; });
        if (entry) openCatalogModal(entry);
        return;
      }
      var delBtn = ev.target.closest("[data-delete]");
      if (delBtn) {
        var delTok = delBtn.getAttribute("data-delete");
        if (!window.confirm("Remove \"" + delTok + "\" from the Known Catalog? " +
            "This also stops any of its matches from being used for live detection. " +
            "(A built-in entry is hidden from this catalog view, not deleted from the " +
            "extension itself – its own built-in detection is unaffected; a custom " +
            "one is removed entirely.)")) {
          return;
        }
        apiPost("catalog_delete", { token: delTok })
          .then(loadCatalog)
          .catch(function (err) { window.alert(err.message || String(err)); });
      }
    });

    search.addEventListener("input", applyFilters);
    statusSelect.addEventListener("change", applyFilters);
    applyFilters();
  }

  // -- Known Catalog add/edit modal -----------------------------------------

  var catalogModal = null;
  var catalogForm = null;
  var catalogModalError = null;
  var catalogFields = null;
  var catalogEditingToken = null; // null while adding a brand-new entry

  function initCatalogModal() {
    catalogModal = document.getElementById("catalog-modal");
    catalogForm = document.getElementById("catalog-form");
    catalogModalError = document.getElementById("catalog-modal-error");
    catalogFields = {
      token: document.getElementById("catalog-field-token"),
      title: document.getElementById("catalog-field-title"),
      patterns: document.getElementById("catalog-field-patterns"),
      hint: document.getElementById("catalog-field-hint"),
    };
    document.getElementById("catalog-modal-cancel").addEventListener("click", closeCatalogModal);
    catalogModal.addEventListener("click", function (ev) {
      if (ev.target === catalogModal) closeCatalogModal();
    });
    document.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape" && !catalogModal.hidden) closeCatalogModal();
    });
    catalogForm.addEventListener("submit", function (ev) {
      ev.preventDefault();
      submitCatalogModal();
    });
  }

  function openCatalogModal(entry, opts) {
    // opts.forceAdd: prefill fields from `entry` (e.g. from the Capability Database's
    // "Adopt into Known Catalog" action, see openAdoptModal below) but still treat it as
    // adding a brand-new entry -- token stays editable, unlike editing a real existing one.
    var isEdit = !!entry && !(opts && opts.forceAdd);
    catalogEditingToken = isEdit ? entry.token : null;
    document.getElementById("catalog-modal-title").textContent =
      isEdit ? "Edit application" : "Add application";
    catalogModalError.hidden = true;
    catalogModalError.textContent = "";
    catalogFields.token.value = entry ? entry.token : "";
    catalogFields.token.disabled = isEdit;
    catalogFields.title.value = entry ? entry.title : "";
    catalogFields.patterns.value = entry ? entry.patterns.join("\n") : "";
    catalogFields.hint.value = entry ? entry.hint : "";
    catalogModal.hidden = false;
    (isEdit ? catalogFields.title : catalogFields.token).focus();
  }

  function closeCatalogModal() {
    catalogModal.hidden = true;
    catalogEditingToken = null;
  }

  function submitCatalogModal() {
    var token = catalogEditingToken || catalogFields.token.value.trim();
    var saveBtn = document.getElementById("catalog-modal-save");
    saveBtn.disabled = true;
    apiPost("catalog_save", {
      token: token,
      title: catalogFields.title.value,
      patterns: catalogFields.patterns.value,
      hint: catalogFields.hint.value,
    })
      .then(function () {
        closeCatalogModal();
        return loadCatalog();
      })
      .catch(function (err) {
        catalogModalError.textContent = err.message || String(err);
        catalogModalError.hidden = false;
      })
      .then(function () { saveBtn.disabled = false; }, function () { saveBtn.disabled = false; });
  }

  // -- Capability Database -> Known Catalog "adopt" flow ----------------------
  // Only reachable via the capdb table's "-> Known Catalog" button, itself only shown
  // when data.can_edit is true (see renderCapdb) -- but the actual write still goes
  // through catalog_save, which enforces the wato.edit permission server-side regardless.

  var adoptModal = null;
  var adoptTargetSelect = null;
  var adoptModalError = null;
  var adoptContext = null; // the capdb row {type, name, token} being adopted

  function initAdoptModal() {
    adoptModal = document.getElementById("adopt-modal");
    adoptTargetSelect = document.getElementById("adopt-target-select");
    adoptModalError = document.getElementById("adopt-modal-error");
    document.getElementById("adopt-modal-cancel").addEventListener("click", closeAdoptModal);
    document.getElementById("adopt-modal-continue").addEventListener("click", submitAdoptModal);
    adoptModal.addEventListener("click", function (ev) {
      if (ev.target === adoptModal) closeAdoptModal();
    });
    document.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape" && !adoptModal.hidden) closeAdoptModal();
    });
    adoptTargetSelect.addEventListener("change", function () {
      document.getElementById("adopt-target-hint").textContent = adoptTargetSelect.value
        ? "Adds this capability's name as an additional match on the selected entry " +
          "(its title/hint are left unchanged)."
        : "Creates a brand-new Known Catalog entry, pre-filled from this capability.";
    });
  }

  function openAdoptModal(row) {
    adoptContext = row;
    document.getElementById("adopt-modal-info").textContent =
      row.type + " · " + row.name + (row.token ? " · token: " + row.token : "");
    adoptTargetSelect.innerHTML = "";
    adoptTargetSelect.appendChild(el("option", { value: "", text: "+ Create new Known Catalog entry" }));
    var entries = (lastCatalogData && lastCatalogData.entries) || [];
    entries.slice().sort(function (a, b) { return a.title.localeCompare(b.title); })
      .forEach(function (e) {
        adoptTargetSelect.appendChild(el("option", { value: e.token, text: e.title + " [" + e.token + "]" }));
      });
    document.getElementById("adopt-target-hint").textContent =
      "Creates a brand-new Known Catalog entry, pre-filled from this capability.";
    adoptModalError.hidden = true;
    adoptModalError.textContent = "";
    adoptModal.hidden = false;
  }

  function closeAdoptModal() {
    adoptModal.hidden = true;
    adoptContext = null;
  }

  function submitAdoptModal() {
    var targetToken = adoptTargetSelect.value;

    if (!targetToken) {
      // Create new: hand off to the normal Add/Edit modal, prefilled. The capability's
      // own token is only usable as a starting guess if it already looks like a valid
      // catalog token (lowercase/digits/underscore) -- otherwise leave it blank for the
      // admin to fill in themselves rather than pre-filling something save would reject.
      var guessedToken = /^[a-z][a-z0-9_]{1,39}$/.test(adoptContext.token || "")
        ? adoptContext.token
        : "";
      closeAdoptModal();
      switchToTab("catalog");
      openCatalogModal({ token: guessedToken, title: "", patterns: [adoptContext.name], hint: "" },
        { forceAdd: true });
      return;
    }

    // Assign to an existing entry: append this capability's name as an additional match,
    // keeping that entry's title/hint untouched. catalog_save is an upsert keyed by
    // token, so re-sending the existing title/hint alongside the merged patterns is a
    // safe no-op update to those fields.
    var entries = (lastCatalogData && lastCatalogData.entries) || [];
    var existing = entries.filter(function (e) { return e.token === targetToken; })[0];
    if (!existing) return;
    var patterns = existing.patterns.slice();
    if (patterns.indexOf(adoptContext.name) === -1) patterns.push(adoptContext.name);

    var continueBtn = document.getElementById("adopt-modal-continue");
    continueBtn.disabled = true;
    apiPost("catalog_save", {
      token: existing.token,
      title: existing.title,
      patterns: patterns.join("\n"),
      hint: existing.hint,
    })
      .then(function () {
        closeAdoptModal();
        switchToTab("catalog");
        return loadCatalog();
      })
      .catch(function (err) {
        adoptModalError.textContent = err.message || String(err);
        adoptModalError.hidden = false;
      })
      .then(function () { continueBtn.disabled = false; }, function () { continueBtn.disabled = false; });
  }

  // -- tabs + bootstrap -------------------------------------------------------

  function showError(containerId, err) {
    document.getElementById(containerId).innerHTML =
      '<div class="error-banner">' + escapeHtml(err.message || String(err)) + "</div>";
  }

  var authPromptShown = false;

  function showAuthRequired() {
    // Deliberately NOT the red error-banner treatment: being logged out is an expected,
    // unremarkable situation (a link shared around, a session that timed out), not
    // something broken -- it gets the same calm empty-state look as e.g. "no capability
    // database yet", plus a direct login link that returns here afterwards.
    if (authPromptShown) return;
    authPromptShown = true;
    var loginUrl =
      "../login.py?_origtarget=" + encodeURIComponent(location.pathname + location.search);
    var html =
      '<div class="empty-state">' +
      "You need to be logged in to this Checkmk site to view this dashboard." +
      "<br><br>" +
      '<a class="btn primary" href="' + escapeHtml(loginUrl) + '">Log in</a>' +
      "</div>";
    document.getElementById("capdb-content").innerHTML = html;
    document.getElementById("catalog-content").innerHTML = html;
  }

  function switchToTab(tabName) {
    document.querySelectorAll("nav.tabs button").forEach(function (b) {
      b.classList.toggle("active", b.dataset.tab === tabName);
    });
    document.querySelectorAll(".panel").forEach(function (p) {
      p.classList.toggle("active", p.id === "panel-" + tabName);
    });
  }

  function initTabs() {
    document.querySelectorAll("nav.tabs button").forEach(function (btn) {
      btn.addEventListener("click", function () { switchToTab(btn.dataset.tab); });
    });
  }

  function applyTheme(themeName) {
    // Mirrors Checkmk's own <body data-theme="facelift|modern-dark"> attribute (see
    // cmk.gui.htmllib.html.HTMLGenerator), just with the dashboard's own simpler
    // light/dark vocabulary -- the CSS keys its whole palette off this attribute (see
    // index.html's <style>), with prefers-color-scheme only as a fallback for the brief
    // window before this fetch resolves.
    document.documentElement.setAttribute("data-theme", themeName === "dark" ? "dark" : "light");
  }

  function init() {
    initTabs();
    initCatalogModal();
    initAdoptModal();
    // One combined "bootstrap" round trip for the initial load instead of three separate
    // theme/capdb/catalog fetches -- each fetch is a full Checkmk WSGI request (session/
    // auth setup, JSON serialization, ...), and cutting that down to one is a bigger win
    // than the three individually-fast requests running concurrently already were.
    // Post-edit reloads still use plain apiGet("catalog") (see loadCatalog()) -- no need
    // to re-fetch the theme or the capability DB just because a catalog entry changed.
    apiGet("bootstrap")
      .then(function (data) {
        applyTheme(data.theme);
        renderCapdb(data.capdb);
        csrfToken = data.catalog.csrf_token || csrfToken;
        lastCatalogData = data.catalog;
        renderCatalog(data.catalog);
      })
      .catch(function (err) {
        if (err.authRequired) {
          showAuthRequired();
          return;
        }
        showError("capdb-content", err);
        showError("catalog-content", err);
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
