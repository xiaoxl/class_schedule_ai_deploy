const $ = (selector) => document.querySelector(selector);
const $all = (selector) => Array.from(document.querySelectorAll(selector));

const KIND_LABELS = {
  NormalClass: "Single Class",
  FourCreditClass: "Four-Credit Class",
  HybridClass: "Hybrid Class",
  CrossListingClass: "Cross-Listing Class",
  CoreqClass: "Coreq Class",
};

let lastData = null;
let currentView = "instructor";
let busy = false;
// The file actually submitted to /api/solve. Starts as whatever the user
// picked; after each successful solve it's replaced with that solve's
// own output (built from the response's "excel.raw"), so clicking
// "Solve Schedule" again refines the just-solved result instead of
// restarting from the original upload every time.
let currentFile = null;

// Every solve's full response, in order -- browsable/downloadable via
// tabs without re-fetching (see renderAttemptTabs). Reset whenever a
// fresh file is parsed, since that starts a new lineage. solvedOnce
// gates the "regenerate" flag: the first solve on a given file is a
// normal solve; every solve after that is a re-roll that must return a
// different result (see the /api/solve `regenerate` field).
let attempts = [];
let solvedOnce = false;
let activeAttemptIndex = -1;
// Set when /api/solve comes back 422 (no conflict-free assignment exists
// for this input -- see solver.solve()'s docstring): retrying the same
// input can't succeed, so "Solve Schedule" stays disabled until a fresh
// file is chosen instead of inviting a pointless re-click.
let solveBlocked = false;

const file = $("#scheduleFile");
const zone = $("#dropZone");
const submitButton = $("#submitButton");
const IDLE_BUTTON_TEXT = "Solve Schedule";
const EXCEL_XLSX_MIME =
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";

function updateFileLabel() {
  $("#fileLabel").textContent = file.files[0]?.name || "Drop a schedule file here, or click to choose one";
}

function setBusy(value, buttonText) {
  busy = value;
  file.disabled = value;
  submitButton.disabled = value || !lastData || solveBlocked;
  if (buttonText) submitButton.textContent = buttonText;
}

file.addEventListener("change", () => {
  updateFileLabel();
  if (file.files[0]) parseSelectedFile();
});

["dragenter", "dragover"].forEach((eventName) =>
  zone.addEventListener(eventName, (event) => {
    event.preventDefault();
    zone.classList.add("drag");
  })
);
["dragleave", "drop"].forEach((eventName) =>
  zone.addEventListener(eventName, (event) => {
    event.preventDefault();
    zone.classList.remove("drag");
  })
);
zone.addEventListener("drop", (event) => {
  if (busy) return;
  file.files = event.dataTransfer.files;
  updateFileLabel();
  if (file.files[0]) parseSelectedFile();
});

$all(".view-tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    if (tab.dataset.view === currentView) return;
    currentView = tab.dataset.view;
    $all(".view-tab").forEach((t) => t.classList.toggle("active", t === tab));
    if (lastData) renderView();
  });
});

// Selecting/dropping a file parses it immediately; the button is only
// for the (slow) solve step, which needs an already-parsed schedule.
// A fresh selection always resets currentFile to that literal file,
// discarding any earlier solve's output.
async function parseSelectedFile() {
  if (busy) return;
  lastData = null;
  currentFile = file.files[0];
  attempts = [];
  solvedOnce = false;
  activeAttemptIndex = -1;
  solveBlocked = false;
  renderAttemptTabs();
  setBusy(true, "Parsing…");
  const data = await submitFile("/api/schedule", currentFile);
  if (data) render(data);
  setBusy(false, IDLE_BUTTON_TEXT);
}

$("#uploadForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (busy || !lastData || !currentFile) return;
  setBusy(true, "Solving, this may take up to a minute…");
  // Submits currentFile, not necessarily the original upload -- see its
  // declaration above. regenerate=true from the second solve onward asks
  // the solver to guarantee a different result from this same input
  // (which, by then, is itself the previous solve's own output) instead
  // of possibly reconverging on the same answer.
  const data = await submitFile("/api/solve", currentFile, {
    regenerate: String(solvedOnce),
  });
  if (data && data.excel) {
    currentFile = base64ToFile(data.excel.raw, "solved_schedule.xlsx", EXCEL_XLSX_MIME);
    // data.changes is only this step's diff (its input was the previous
    // attempt's output, not the original file) -- merge it onto the
    // running total so the displayed solve plan always reads as "changed
    // from the original upload", not "changed since last click".
    const previousCumulative = attempts.length
      ? attempts[attempts.length - 1].cumulativeChanges
      : [];
    const cumulativeChanges = mergeChanges(previousCumulative, data.changes);
    attempts.push({ data, cumulativeChanges, label: `Attempt ${attempts.length + 1}` });
    activeAttemptIndex = attempts.length - 1;
    solvedOnce = true;
    render(data, cumulativeChanges);
    renderAttemptTabs();
  } else if (lastResponseStatus === 422) {
    solveBlocked = true;
  }
  setBusy(false, IDLE_BUTTON_TEXT);
});

// ---- cumulative solve plan ----
//
// Each attempt's own `data.changes` is a step diff (previous attempt's
// output -> this attempt's output), not a diff from the original file --
// the backend is stateless and only ever sees one input at a time (see
// webapp.py's /api/solve). Merging every step's diff into a running
// per-(course, field) total, keeping the first "before" and the latest
// "after" seen for each, reconstructs the true original -> current diff
// without the backend needing to track history at all. A field nudged
// back to its original value nets out to no real change, so it's dropped
// rather than shown as a no-op.
function mergeChanges(previous, step) {
  const merged = new Map();
  for (const change of previous) {
    merged.set(`${change.course_id}::${change.field}`, { ...change });
  }
  for (const change of step) {
    const key = `${change.course_id}::${change.field}`;
    const existing = merged.get(key);
    if (existing) {
      existing.after = change.after;
    } else {
      merged.set(key, { ...change });
    }
  }
  return [...merged.values()].filter((change) => change.before !== change.after);
}

function base64ToFile(base64, filename, mimeType) {
  const bytes = Uint8Array.from(atob(base64), (c) => c.charCodeAt(0));
  return new File([bytes], filename, { type: mimeType });
}

// Set by submitFile on every call so callers that care about *why* a
// request failed (see the /api/solve handler's 422 check) can look past
// the generic null-on-failure return without changing that contract for
// every other caller.
let lastResponseStatus = null;

async function submitFile(endpoint, fileToSend, extraFields = {}) {
  if (!fileToSend) return null;
  hideError();
  lastResponseStatus = null;
  try {
    const formData = new FormData();
    formData.append("schedule_file", fileToSend);
    for (const [key, value] of Object.entries(extraFields)) {
      formData.append(key, value);
    }
    const response = await fetch(endpoint, { method: "POST", body: formData });
    lastResponseStatus = response.status;
    const data = await response.json();
    if (!response.ok) {
      const detail = data.detail;
      if (detail && typeof detail === "object") {
        showError(detail.message, detail.records);
      } else {
        showError(detail || "Request failed");
      }
      return null;
    }
    return data;
  } catch (error) {
    showError(error.message);
    return null;
  }
}

// `changesOverride` lets a caller display something other than this
// response's own raw `data.changes` -- specifically the merged
// cumulative-from-original changes for a solve attempt (see
// mergeChanges). Defaults to `data.changes` for a plain parse response,
// which has no such concept.
function render(data, changesOverride = data.changes) {
  lastData = data;
  $("#results").classList.remove("hidden");
  $("#countLabel").textContent = `Parsed ${data.count} classes`;
  renderChanges(changesOverride);
  renderExcelDownloads(data.excel);
  renderViolations(data.violations);
  renderView();
}

// ---- attempt history: every solve's full response, browsable via tabs ----
//
// Purely a client-side view over data already in memory -- selecting an
// older attempt just re-renders it (render() is a pure function of a
// response object), never re-fetches. The next solve always continues
// from currentFile (the latest attempt), regardless of which tab is
// currently being viewed.

function renderAttemptTabs() {
  const box = $("#attemptTabs");
  if (attempts.length < 2) {
    // A single attempt has nothing to switch between -- the normal
    // results view already shows it.
    box.classList.add("hidden");
    box.innerHTML = "";
    return;
  }
  box.innerHTML = attempts
    .map((attempt, index) => {
      const score = attempt.data.violations?.soft_total;
      const scoreLabel = score === undefined ? "" : ` (${score} pts)`;
      const active = index === activeAttemptIndex ? " active" : "";
      return `<button type="button" class="view-tab${active}" data-index="${index}">${esc(attempt.label)}${esc(scoreLabel)}</button>`;
    })
    .join("");
  box.classList.remove("hidden");
}

$("#attemptTabs").addEventListener("click", (event) => {
  const tab = event.target.closest("[data-index]");
  if (!tab) return;
  const index = Number(tab.dataset.index);
  if (index === activeAttemptIndex) return;
  activeAttemptIndex = index;
  render(attempts[index].data, attempts[index].cumulativeChanges);
  renderAttemptTabs();
});

// ---- excel downloads: present after both a plain parse and a solve ----

function renderExcelDownloads(excel) {
  const box = $("#excelDownloads");
  const links = {
    raw: $("#downloadRaw"),
    instructor: $("#downloadInstructor"),
    room: $("#downloadRoom"),
  };
  for (const url of Object.values(links)) {
    if (url.dataset.objectUrl) URL.revokeObjectURL(url.dataset.objectUrl);
  }
  if (!excel) {
    box.classList.add("hidden");
    return;
  }
  for (const [key, anchor] of Object.entries(links)) {
    const bytes = Uint8Array.from(atob(excel[key]), (c) => c.charCodeAt(0));
    const blobUrl = URL.createObjectURL(new Blob([bytes], { type: EXCEL_XLSX_MIME }));
    anchor.href = blobUrl;
    anchor.dataset.objectUrl = blobUrl;
  }
  box.classList.remove("hidden");
}

// ---- changes summary: what the solver actually adjusted ----

const CHANGE_FIELD_LABELS = { instructor: "Instructor", time: "Time", room: "Room" };

function renderChanges(changes) {
  const box = $("#changesSummary");
  if (!changes || !changes.length) {
    box.classList.add("hidden");
    box.innerHTML = "";
    return;
  }
  const groups = groupBy(changes, (c) => c.course_id, "(Unknown course)");
  const items = groups
    .map(([courseId, courseChanges]) => {
      const parts = courseChanges
        .map((c) => {
          const label = CHANGE_FIELD_LABELS[c.field] || c.field;
          const before = c.before || "(empty)";
          const after = c.after || "(empty)";
          return `${esc(label)} ${esc(before)} → ${esc(after)}`;
        })
        .join("; ");
      return `<li><strong>${esc(courseId)}</strong>: ${parts}</li>`;
    })
    .join("");
  box.innerHTML = `<h3>Solve Plan (${groups.length} class(es) adjusted)</h3><ul>${items}</ul>`;
  box.classList.remove("hidden");
}

// ---- violations summary (hard = red, soft = orange/yellow by penalty) ----

function renderViolations(violations) {
  const box = $("#violationsSummary");
  const hard = violations?.hard || [];
  const soft = violations?.soft || [];
  if (!hard.length && !soft.length) {
    box.classList.add("hidden");
    box.innerHTML = "";
    return;
  }
  const orange = soft.filter((f) => f.severity === "orange");
  const yellow = soft.filter((f) => f.severity === "yellow");
  const groups = [];
  if (hard.length) {
    groups.push(renderViolationGroup(
      "red", `Hard Conflicts (${hard.length})`,
      hard.map((v) => ({ subject: v.subject, message: v.message }))
    ));
  }
  if (orange.length) {
    groups.push(renderViolationGroup(
      "orange", `Please Follow If Possible (${orange.length})`,
      orange.map((f) => ({ subject: f.subject, message: f.message, penalty: f.penalty }))
    ));
  }
  if (yellow.length) {
    groups.push(renderViolationGroup(
      "yellow",
      `Soft Preferences Not Met (${yellow.length}, ${violations.soft_total} pts total)`,
      yellow.map((f) => ({ subject: f.subject, message: f.message, penalty: f.penalty }))
    ));
  }
  box.innerHTML = groups.join("");
  box.classList.remove("hidden");
}

function renderViolationGroup(level, title, items) {
  const rows = items
    .map((item) => `<li><strong>${esc(item.subject)}</strong>：${esc(item.message)}${
      item.penalty !== undefined ? ` <span class="penalty">(-${item.penalty})</span>` : ""
    }</li>`)
    .join("");
  return `<div class="violation-group violation-${level}">
    <h3>${esc(title)}</h3>
    <ul>${rows}</ul>
  </div>`;
}

function renderView() {
  const renderers = {
    atomic: renderAtomicView,
    course: () => renderGroupedView(groupByCourse(lastData), "course"),
    instructor: () => renderGroupedView(groupByInstructor(lastData), "instructor"),
    room: () => renderGroupedView(groupByRoom(lastData), "room"),
  };
  $("#classList").innerHTML = (renderers[currentView] || renderAtomicView)();
}

function renderAtomicView() {
  return lastData.classes.map(renderClass).join("");
}

function renderClass(item) {
  const label = KIND_LABELS[item.kind] || item.kind;
  const rows = item.sections.map(renderSection).join("");
  return `<article class="class-card">
    <header><span class="kind-badge">${esc(label)}</span><strong>${esc(item.course_ids.join(" / "))}</strong></header>
    <table>
      <thead><tr><th>Time Slot</th><th>Room</th><th>Instructor</th><th>Type</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  </article>`;
}

function renderSection(section) {
  return `<tr>
    <td>${esc(section["Time Slot"])}</td>
    <td>${esc(section["Room"])}</td>
    <td>${esc(section["Instructor"])}</td>
    <td>${esc(section["Type"])}</td>
  </tr>`;
}

// ---- grouped views (by course / instructor / room) ----
//
// The API already returns every section's Subject/Number/Section/Room/
// Instructor, so these views are pure client-side re-groupings of the
// same upload response -- no extra request needed when switching tabs.

function flattenSections(data) {
  return data.classes.flatMap((item, classIndex) =>
    item.sections.map((section) => ({
      ...section,
      course_id: `${section["Subject"]} ${section["Number"]}-${section["Section"]}`,
      kind: item.kind,
      class_index: classIndex,
      credit_hours: item.credit_hours,
    }))
  );
}

function groupBy(rows, keyFn, fallback) {
  const groups = new Map();
  for (const row of rows) {
    const key = keyFn(row) || fallback;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(row);
  }
  return [...groups.entries()].sort(([a], [b]) => a.localeCompare(b));
}

// Within a room's or instructor's group, MW/MWF meetings are listed
// before TR meetings (any other pattern sorts last), then chronologically
// by start time -- easier to scan than upload order.
const DAY_PATTERN_PRIORITY = { MW: 0, MWF: 0, TR: 1 };
function dayPatternPriority(days) {
  return DAY_PATTERN_PRIORITY[days] ?? 2;
}
function sortByDayThenTime(rows) {
  return [...rows].sort((a, b) => {
    const order = dayPatternPriority(a["Days"]) - dayPatternPriority(b["Days"]);
    return order !== 0 ? order : (a["Start"] || "").localeCompare(b["Start"] || "");
  });
}

function groupByCourse(data) {
  return groupBy(
    flattenSections(data),
    (row) => `${row["Subject"]} ${row["Number"]}`,
    "(Unknown course)"
  );
}

function groupByInstructor(data) {
  return groupBy(flattenSections(data), (row) => row["Instructor"], "(No instructor)").map(
    ([title, rows]) => [title, sortByDayThenTime(rows)]
  );
}

function groupByRoom(data) {
  return groupBy(
    flattenSections(data),
    (row) => [row["Building"], row["Room"]].filter(Boolean).join(" "),
    "(Unassigned room / online)"
  ).map(([title, rows]) => [title, sortByDayThenTime(rows)]);
}

// Total credit hours for an instructor's group. credit_hours is a
// per-class (not per-section) value from the API, so a class with two
// rows in the same group (FourCreditClass, HybridClass, ...) must only
// be counted once -- dedupe by class_index before summing.
function totalCreditHours(rows) {
  const seen = new Set();
  let total = 0;
  for (const row of rows) {
    if (seen.has(row.class_index)) continue;
    seen.add(row.class_index);
    total += row.credit_hours || 0;
  }
  return total;
}

const GROUP_COLUMNS = {
  course: [
    ["Section", (r) => r["Section"]],
    ["Time Slot", (r) => r["Time Slot"]],
    ["Room", (r) => r["Room"]],
    ["Instructor", (r) => r["Instructor"]],
    ["Type", (r) => r["Type"]],
  ],
  instructor: [
    ["Course", (r) => r.course_id],
    ["Time Slot", (r) => r["Time Slot"]],
    ["Room", (r) => r["Room"]],
    ["Type", (r) => r["Type"]],
  ],
  room: [
    ["Course", (r) => r.course_id],
    ["Time Slot", (r) => r["Time Slot"]],
    ["Instructor", (r) => r["Instructor"]],
    ["Type", (r) => r["Type"]],
  ],
};

function renderGroupedView(groups, mode) {
  const columns = GROUP_COLUMNS[mode];
  return groups
    .map(([title, rows]) => {
      const summary = mode === "instructor"
        ? `Total credit hours: ${totalCreditHours(rows)}`
        : null;
      return renderGroupCard(title, rows, columns, summary);
    })
    .join("");
}

function renderGroupCard(title, rows, columns, summary) {
  const head = columns.map(([label]) => `<th>${esc(label)}</th>`).join("");
  const body = rows
    .map(
      (row) =>
        `<tr>${columns.map(([, get]) => `<td>${esc(get(row))}</td>`).join("")}</tr>`
    )
    .join("");
  const badges = `<span class="kind-badge">${rows.length} row(s)</span>`
    + (summary ? `<span class="kind-badge">${esc(summary)}</span>` : "");
  return `<article class="class-card">
    <header><strong>${esc(title)}</strong>${badges}</header>
    <table>
      <thead><tr>${head}</tr></thead>
      <tbody>${body}</tbody>
    </table>
  </article>`;
}

// Error rows can come straight from an unparsed upload row, so they show
// the course identity columns too -- there is no class-card header to
// carry that information the way a successful result has.
function renderErrorRow(record) {
  return `<tr>
    <td>${esc(record["Subject"])}</td>
    <td>${esc(record["Number"])}</td>
    <td>${esc(record["Section"])}</td>
    <td>${esc(record["Time Slot"])}</td>
    <td>${esc(record["Room"])}</td>
    <td>${esc(record["Instructor"])}</td>
  </tr>`;
}

function showError(message, records) {
  const box = $("#errorBox");
  let html = `<p class="error-message">${esc(message)}</p>`;
  if (records && records.length) {
    html += `<table>
      <thead><tr><th>Subject</th><th>Number</th><th>Section</th><th>Time Slot</th><th>Room</th><th>Instructor</th></tr></thead>
      <tbody>${records.map(renderErrorRow).join("")}</tbody>
    </table>`;
  }
  box.innerHTML = html;
  box.classList.remove("hidden");
}

function hideError() {
  $("#errorBox").classList.add("hidden");
}

function esc(value) {
  return String(value ?? "—").replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}
