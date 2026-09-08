(function () {
  var table = document.getElementById("drops-table");
  if (!table) return;
  var body = table.tBodies[0];
  if (!body) return;
  var countEl = document.getElementById("drops-visible-count");
  var sortKey = "";
  var sortDir = 1;

  function rowValue(row, key, type) {
    if (type === "number") {
      var raw = row.getAttribute("data-" + key + "-sort");
      if (raw == null || raw === "") return Number.POSITIVE_INFINITY * sortDir;
      return Number(raw);
    }
    return row.getAttribute("data-" + key) || "";
  }

  function applyFilters() {
    var inputs = table.querySelectorAll("input[data-filter]");
    var shown = 0;
    Array.prototype.forEach.call(body.rows, function (row) {
      var visible = true;
      Array.prototype.forEach.call(inputs, function (input) {
        var needle = (input.value || "").trim().toLowerCase();
        if (!needle) return;
        var hay = (row.getAttribute("data-" + input.getAttribute("data-filter")) || "").toLowerCase();
        if (hay.indexOf(needle) === -1) visible = false;
      });
      row.hidden = !visible;
      if (visible) shown += 1;
    });
    if (countEl) countEl.textContent = String(shown);
  }

  function sortBy(key, type) {
    if (sortKey === key) {
      sortDir = -sortDir;
    } else {
      sortKey = key;
      sortDir = type === "number" ? 1 : 1;
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
    Array.prototype.forEach.call(table.querySelectorAll("th[data-key]"), function (th) {
      th.setAttribute("aria-sort", th.getAttribute("data-key") === key ? (sortDir === 1 ? "ascending" : "descending") : "none");
    });
  }

  Array.prototype.forEach.call(table.querySelectorAll("th[data-key]"), function (th) {
    th.addEventListener("click", function () {
      sortBy(th.getAttribute("data-key"), th.getAttribute("data-type") || "text");
    });
  });
  Array.prototype.forEach.call(table.querySelectorAll("input[data-filter]"), function (input) {
    input.addEventListener("input", applyFilters);
  });
  applyFilters();
})();
