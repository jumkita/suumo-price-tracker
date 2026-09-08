(function () {
  var table = document.getElementById("drops-table");
  if (!table) return;
  var body = table.tBodies[0];
  if (!body) return;
  var countEl = document.getElementById("drops-visible-count");
  var sortKeySelect = document.getElementById("sort-key");
  var sortKey = "";
  var sortDir = 1;

  function rowDisplay(row, key) {
    return row.getAttribute("data-" + key) || "";
  }

  function rowFilterValue(row, key) {
    return row.getAttribute("data-" + key + "-filter") || rowDisplay(row, key);
  }

  function rowNumber(row, key) {
    var raw = row.getAttribute("data-" + key + "-sort");
    if (raw == null || raw === "") return null;
    var n = Number(raw);
    return Number.isNaN(n) ? null : n;
  }

  function rowValue(row, key, type) {
    if (type === "number") {
      var n = rowNumber(row, key);
      if (n == null) return Number.POSITIVE_INFINITY * sortDir;
      return n;
    }
    return rowDisplay(row, key);
  }

  function walkMatches(minutes, token) {
    if (minutes == null) return false;
    if (token === "lte5") return minutes <= 5;
    if (token === "lte10") return minutes <= 10;
    if (token === "lte15") return minutes <= 15;
    if (token === "lte20") return minutes <= 20;
    if (token === "gte20") return minutes >= 20;
    return false;
  }

  function rowMatches(row, input) {
    var needle = (input.value || "").trim();
    if (!needle) return true;
    var key = input.getAttribute("data-filter");
    var mode = input.getAttribute("data-filter-mode") || "exact";
    if (mode === "text") {
      return rowDisplay(row, key).toLowerCase().indexOf(needle.toLowerCase()) !== -1;
    }
    if (mode === "walk") {
      return walkMatches(rowNumber(row, key), needle);
    }
    return rowFilterValue(row, key) === needle;
  }

  function applyFilters() {
    var inputs = table.querySelectorAll("[data-filter]");
    var shown = 0;
    Array.prototype.forEach.call(body.rows, function (row) {
      var visible = true;
      Array.prototype.forEach.call(inputs, function (input) {
        if (!rowMatches(row, input)) visible = false;
      });
      row.hidden = !visible;
      if (visible) shown += 1;
    });
    if (countEl) countEl.textContent = String(shown);
  }

  function setSortState(key, dir) {
    sortKey = key;
    sortDir = dir;
    if (sortKeySelect && key) sortKeySelect.value = key;
    Array.prototype.forEach.call(table.querySelectorAll("th[data-key]"), function (th) {
      th.setAttribute(
        "aria-sort",
        th.getAttribute("data-key") === key ? (dir === 1 ? "ascending" : "descending") : "none"
      );
    });
  }

  function sortBy(key, type, dirMode) {
    if (dirMode === "asc") {
      setSortState(key, 1);
    } else if (dirMode === "desc") {
      setSortState(key, -1);
    } else if (sortKey === key) {
      setSortState(key, -sortDir);
    } else {
      setSortState(key, 1);
    }
    var rows = Array.prototype.slice.call(body.rows);
    rows.sort(function (a, b) {
      var av = rowValue(a, key, type);
      var bv = rowValue(b, key, type);
      if (av < bv) return -1 * sortDir;
      if (av > bv) return 1 * sortDir;
      return 0;
    });
    rows.forEach(function (row) {
      body.appendChild(row);
    });
  }

  function typeForKey(key) {
    var th = table.querySelector('th[data-key="' + key + '"]');
    return th ? th.getAttribute("data-type") || "text" : "text";
  }

  Array.prototype.forEach.call(table.querySelectorAll("[data-sort-key]"), function (btn) {
    btn.addEventListener("click", function (event) {
      event.stopPropagation();
      var key = btn.getAttribute("data-sort-key");
      sortBy(key, typeForKey(key), btn.getAttribute("data-sort-dir") || "toggle");
    });
  });

  var sortAsc = document.getElementById("sort-asc");
  var sortDesc = document.getElementById("sort-desc");
  if (sortAsc) {
    sortAsc.addEventListener("click", function () {
      var key = sortKeySelect ? sortKeySelect.value : "";
      if (key) sortBy(key, typeForKey(key), "asc");
    });
  }
  if (sortDesc) {
    sortDesc.addEventListener("click", function () {
      var key = sortKeySelect ? sortKeySelect.value : "";
      if (key) sortBy(key, typeForKey(key), "desc");
    });
  }

  Array.prototype.forEach.call(table.querySelectorAll("[data-filter]"), function (input) {
    input.addEventListener("change", applyFilters);
    input.addEventListener("input", applyFilters);
  });
  applyFilters();
})();
