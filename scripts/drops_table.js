(function () {
  var table = document.getElementById("drops-table");
  if (!table) return;
  var body = table.tBodies[0];
  if (!body) return;
  var countEl = document.getElementById("drops-visible-count");
  var sortKeySelect = document.getElementById("sort-key");
  var picksList = document.getElementById("my-picks-list");
  var picksEmpty = document.getElementById("my-picks-empty");
  var cardsMount = document.getElementById("drop-cards");
  var summaryEl = document.getElementById("prefs-summary");
  var STORAGE_KEY = "suumo-buyer-prefs-v1";
  var HIGHLIGHT_LIMIT = 7;
  var sortKey = "rate";
  var sortDir = -1;
  var PRESETS = {
    family: {
      wards: [],
      priceMin: 4000,
      priceMax: 9000,
      maxAge: 25,
      minArea: 55,
      maxWalk: 15,
      layouts: ["2LDK", "3LDK", "4LDK+"],
    },
    compact: {
      wards: [],
      priceMin: 2500,
      priceMax: 6000,
      maxAge: 20,
      minArea: 40,
      maxWalk: 10,
      layouts: ["1LDK", "2LDK"],
    },
  };

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

  function checkedValues(name) {
    return Array.prototype.map
      .call(document.querySelectorAll('input[name="' + name + '"]:checked'), function (input) {
        return input.value;
      })
      .filter(Boolean);
  }

  function parseOptionalNumber(id) {
    var el = document.getElementById(id);
    if (!el) return null;
    var raw = (el.value || "").trim();
    if (!raw) return null;
    var n = Number(raw);
    return Number.isFinite(n) ? n : null;
  }

  function emptyPrefs() {
    return {
      wards: [],
      priceMin: null,
      priceMax: null,
      maxAge: null,
      minArea: null,
      maxWalk: null,
      layouts: [],
    };
  }

  function readPrefs() {
    var prefs = emptyPrefs();
    prefs.wards = checkedValues("pref-ward");
    prefs.layouts = checkedValues("pref-layout");
    prefs.priceMin = parseOptionalNumber("prefs-price-min");
    prefs.priceMax = parseOptionalNumber("prefs-price-max");
    prefs.maxAge = parseOptionalNumber("prefs-max-age");
    prefs.minArea = parseOptionalNumber("prefs-min-area");
    prefs.maxWalk = parseOptionalNumber("prefs-max-walk");
    if (prefs.priceMin != null && prefs.priceMax != null && prefs.priceMin > prefs.priceMax) {
      var swap = prefs.priceMin;
      prefs.priceMin = prefs.priceMax;
      prefs.priceMax = swap;
    }
    return prefs;
  }

  function setChecked(name, values) {
    var wanted = {};
    (values || []).forEach(function (value) {
      wanted[value] = true;
    });
    Array.prototype.forEach.call(document.querySelectorAll('input[name="' + name + '"]'), function (input) {
      input.checked = Boolean(wanted[input.value]);
    });
  }

  function setOptional(id, value) {
    var el = document.getElementById(id);
    if (!el) return;
    el.value = value == null || value === "" ? "" : String(value);
  }

  function writePrefs(prefs) {
    setChecked("pref-ward", prefs.wards || []);
    setChecked("pref-layout", prefs.layouts || []);
    setOptional("prefs-price-min", prefs.priceMin);
    setOptional("prefs-price-max", prefs.priceMax);
    setOptional("prefs-max-age", prefs.maxAge);
    setOptional("prefs-min-area", prefs.minArea);
    setOptional("prefs-max-walk", prefs.maxWalk);
  }

  function prefsAreEmpty(prefs) {
    return (
      (!prefs.wards || !prefs.wards.length) &&
      prefs.priceMin == null &&
      prefs.priceMax == null &&
      prefs.maxAge == null &&
      prefs.minArea == null &&
      prefs.maxWalk == null &&
      (!prefs.layouts || !prefs.layouts.length)
    );
  }

  function savePrefs(prefs) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs));
    } catch (err) {
      /* ignore quota / private mode */
    }
  }

  function loadSavedPrefs() {
    try {
      var raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return;
      var parsed = JSON.parse(raw);
      if (!parsed || typeof parsed !== "object") return;
      writePrefs({
        wards: parsed.wards || [],
        layouts: parsed.layouts || [],
        priceMin: parsed.priceMin,
        priceMax: parsed.priceMax,
        maxAge: parsed.maxAge,
        minArea: parsed.minArea,
        maxWalk: parsed.maxWalk,
      });
    } catch (err) {
      /* ignore broken storage */
    }
  }

  function layoutToken(text) {
    var match = String(text || "")
      .toUpperCase()
      .replace(/\s+/g, "")
      .match(/(\d+)(S?L?D?K)/);
    if (!match) return null;
    return { rooms: Number(match[1]), kind: match[2].replace("S", "") };
  }

  function layoutMatches(listing, wanted) {
    if (!wanted || !wanted.length) return true;
    var got = layoutToken(listing);
    if (!got) return false;
    for (var i = 0; i < wanted.length; i += 1) {
      var raw = wanted[i];
      var plus = raw.slice(-1) === "+";
      var need = layoutToken(plus ? raw.slice(0, -1) : raw);
      if (!need) continue;
      if (plus) {
        if (got.rooms >= need.rooms && got.kind.indexOf(need.kind) !== -1) return true;
      } else if (got.rooms === need.rooms && got.kind === need.kind) {
        return true;
      }
    }
    return false;
  }

  function rowMatchesPrefs(row, prefs) {
    if (prefsAreEmpty(prefs)) return true;
    if (prefs.wards.length) {
      var ward = rowDisplay(row, "ward");
      if (prefs.wards.indexOf(ward) === -1) return false;
    }
    var price = rowNumber(row, "new");
    if (prefs.priceMin != null && (price == null || price < prefs.priceMin)) return false;
    if (prefs.priceMax != null && (price == null || price > prefs.priceMax)) return false;
    if (prefs.maxAge != null) {
      var age = rowNumber(row, "built");
      if (age == null || age > prefs.maxAge) return false;
    }
    if (prefs.minArea != null) {
      var area = rowNumber(row, "area");
      if (area == null || area < prefs.minArea) return false;
    }
    if (prefs.maxWalk != null) {
      var walk = rowNumber(row, "walk");
      if (walk == null || walk > prefs.maxWalk) return false;
    }
    if (prefs.layouts.length && !layoutMatches(rowDisplay(row, "layout"), prefs.layouts)) {
      return false;
    }
    return true;
  }

  function rowMatchesFilter(row, input) {
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

  function dropRate(row) {
    var oldPrice = rowNumber(row, "old");
    var newPrice = rowNumber(row, "new");
    if (oldPrice == null || oldPrice <= 0 || newPrice == null || newPrice >= oldPrice) return null;
    return ((oldPrice - newPrice) / oldPrice) * 100;
  }

  function formatMan(value) {
    if (value == null) return "-";
    if (value >= 10000) {
      var oku = Math.floor(value / 10000);
      var man = value % 10000;
      if (man === 0) return oku + "億円";
      return oku + "億" + man + "万円";
    }
    return value + "万円";
  }

  function escapeText(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function listingHref(row) {
    var link = row.querySelector("a[href]");
    return link ? link.getAttribute("href") : "";
  }

  function cardHtml(row, extraClass) {
    var href = listingHref(row);
    var rate = dropRate(row);
    var rateText = rate == null ? "-" : "△" + rate.toFixed(1) + "%";
    var oldPrice = rowNumber(row, "old");
    var newPrice = rowNumber(row, "new");
    var delta = rowNumber(row, "delta");
    var meta = [
      rowDisplay(row, "ward"),
      rowDisplay(row, "layout"),
      rowDisplay(row, "built"),
      rowDisplay(row, "walk"),
      rowDisplay(row, "area"),
    ]
      .filter(function (item) {
        return item && item !== "-";
      })
      .join(" · ");
    var deltaText = delta == null ? "" : (delta < 0 ? "-" : "+") + formatMan(Math.abs(delta));
    var inner =
      '<p class="pick-meta">' +
      escapeText(meta) +
      "</p><h3>" +
      escapeText(rowDisplay(row, "name")) +
      '</h3><p class="pick-rate">' +
      escapeText(rateText) +
      "</p><p>" +
      escapeText(formatMan(oldPrice)) +
      " → " +
      escapeText(formatMan(newPrice)) +
      (deltaText ? "（" + escapeText(deltaText) + "）" : "") +
      "</p>";
    if (href) {
      return (
        '<a class="' +
        extraClass +
        '" href="' +
        escapeText(href) +
        '" target="_blank" rel="noopener">' +
        inner +
        "</a>"
      );
    }
    return '<div class="' + extraClass + '">' + inner + "</div>";
  }

  function summarizePrefs(prefs) {
    if (prefsAreEmpty(prefs)) return "条件なし（全市況）";
    var parts = [];
    if (prefs.wards.length) {
      parts.push(prefs.wards.length <= 3 ? prefs.wards.join("・") : prefs.wards.length + "エリア");
    }
    if (prefs.priceMin != null || prefs.priceMax != null) {
      parts.push((prefs.priceMin || "下限なし") + "〜" + (prefs.priceMax || "上限なし") + "万円");
    }
    if (prefs.maxAge != null) parts.push("築" + prefs.maxAge + "年以内");
    if (prefs.minArea != null) parts.push(prefs.minArea + "m2以上");
    if (prefs.maxWalk != null) parts.push("徒歩" + prefs.maxWalk + "分以内");
    if (prefs.layouts.length) parts.push(prefs.layouts.join("・"));
    return parts.join(" ／ ");
  }

  function dataRows() {
    return Array.prototype.filter.call(body.rows, function (row) {
      return row.querySelector("td") && row.cells.length > 1;
    });
  }

  function visibleDataRows() {
    return dataRows().filter(function (row) {
      return !row.hidden;
    });
  }

  function renderHighlights(prefs) {
    if (!picksList) return;
    var ranked = dataRows()
      .filter(function (row) {
        return rowMatchesPrefs(row, prefs);
      })
      .map(function (row) {
        return {
          row: row,
          rate: dropRate(row),
          amount: rowNumber(row, "delta") || 0,
          name: rowDisplay(row, "name"),
        };
      })
      .filter(function (item) {
        return item.rate != null;
      });
    ranked.sort(function (a, b) {
      if (b.rate !== a.rate) return b.rate - a.rate;
      if (a.amount !== b.amount) return a.amount - b.amount;
      if (a.name < b.name) return -1;
      if (a.name > b.name) return 1;
      return 0;
    });
    ranked = ranked.slice(0, HIGHLIGHT_LIMIT);
    picksList.innerHTML = ranked
      .map(function (item) {
        return cardHtml(item.row, "pick");
      })
      .join("");
    if (picksEmpty) {
      picksEmpty.hidden = ranked.length > 0;
      picksEmpty.textContent = prefsAreEmpty(prefs)
        ? "値下げがありません。"
        : "条件に合う値下げはありません。エリアや築年を緩めてみてください。";
    }
  }

  function renderCards() {
    if (!cardsMount) return;
    cardsMount.innerHTML = visibleDataRows()
      .map(function (row) {
        return cardHtml(row, "listing-card");
      })
      .join("");
  }

  function applyFilters() {
    var prefs = readPrefs();
    savePrefs(prefs);
    if (summaryEl) summaryEl.textContent = summarizePrefs(prefs);
    var inputs = table.querySelectorAll("[data-filter]");
    var shown = 0;
    Array.prototype.forEach.call(body.rows, function (row) {
      if (row.cells.length <= 1) {
        row.hidden = !prefsAreEmpty(prefs);
        return;
      }
      var visible = rowMatchesPrefs(row, prefs);
      Array.prototype.forEach.call(inputs, function (input) {
        if (!rowMatchesFilter(row, input)) visible = false;
      });
      row.hidden = !visible;
      if (visible) shown += 1;
    });
    if (countEl) countEl.textContent = String(shown);
    renderHighlights(prefs);
    renderCards();
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
    renderCards();
    renderHighlights(readPrefs());
  }

  function typeForKey(key) {
    var th = table.querySelector('th[data-key="' + key + '"]');
    return th ? th.getAttribute("data-type") || "text" : "text";
  }

  function setAreaPreset(kind) {
    Array.prototype.forEach.call(document.querySelectorAll('input[name="pref-ward"]'), function (input) {
      if (kind === "none") {
        input.checked = false;
        return;
      }
      input.checked = input.getAttribute("data-area-kind") === kind;
    });
    applyFilters();
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

  var prefsRoot = document.getElementById("prefs");
  if (prefsRoot) {
    prefsRoot.addEventListener("change", applyFilters);
    prefsRoot.addEventListener("input", applyFilters);
  }

  Array.prototype.forEach.call(document.querySelectorAll("[data-area-preset]"), function (btn) {
    btn.addEventListener("click", function () {
      setAreaPreset(btn.getAttribute("data-area-preset"));
    });
  });

  Array.prototype.forEach.call(document.querySelectorAll("[data-pref-preset]"), function (btn) {
    btn.addEventListener("click", function () {
      var preset = PRESETS[btn.getAttribute("data-pref-preset")];
      if (!preset) return;
      var current = readPrefs();
      writePrefs({
        wards: current.wards,
        priceMin: preset.priceMin,
        priceMax: preset.priceMax,
        maxAge: preset.maxAge,
        minArea: preset.minArea,
        maxWalk: preset.maxWalk,
        layouts: preset.layouts,
      });
      applyFilters();
    });
  });

  var clearBtn = document.getElementById("prefs-clear");
  if (clearBtn) {
    clearBtn.addEventListener("click", function () {
      writePrefs(emptyPrefs());
      applyFilters();
    });
  }

  loadSavedPrefs();
  if (sortKeySelect) sortKeySelect.value = "rate";
  sortBy("rate", "number", "desc");
  applyFilters();
})();
