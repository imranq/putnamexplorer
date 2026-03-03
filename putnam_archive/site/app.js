(() => {
  const data = window.PUTNAM_DATA || { problems: [] };
  const RECENT_KEY = "putnam_recent_ids_v1";
  const RECENT_MAX = 16;
  let filtered = data.problems.slice().sort((a, b) => b.year - a.year || a.session.localeCompare(b.session) || a.number - b.number);
  let activeId = null;
  let recentIds = loadRecentIds();

  const el = {
    search: document.getElementById("search"),
    year: document.getElementById("yearFilter"),
    session: document.getElementById("sessionFilter"),
    topic: document.getElementById("topicFilter"),
    hasSolution: document.getElementById("hasSolution"),
    list: document.getElementById("list"),
    detail: document.getElementById("detail"),
    stats: document.getElementById("stats"),
    recentWrap: document.getElementById("recentWrap"),
    recentRow: document.getElementById("recentRow"),
  };

  function unique(values) {
    return [...new Set(values.filter(Boolean))].sort((a, b) => ("" + a).localeCompare("" + b));
  }

  function fillFilters() {
    unique(data.problems.map(p => p.year)).sort((a, b) => b - a).forEach(y => {
      const opt = document.createElement("option");
      opt.value = String(y);
      opt.textContent = y;
      el.year.appendChild(opt);
    });

    unique(data.problems.map(p => p.topic)).forEach(t => {
      const opt = document.createElement("option");
      opt.value = t;
      opt.textContent = t;
      el.topic.appendChild(opt);
    });
  }

  function matches(p, q) {
    const needle = q.toLowerCase();
    if (!needle) return true;
    const blob = `${p.id} ${p.problem_text} ${p.problem_tex} ${p.solution_text || ""}`.toLowerCase();
    return blob.includes(needle);
  }

  function applyFilters() {
    const q = el.search.value.trim();
    const y = el.year.value;
    const s = el.session.value;
    const t = el.topic.value;
    const requireSolution = el.hasSolution.checked;

    filtered = data.problems.filter(p => {
      if (y && String(p.year) !== y) return false;
      if (s && p.session !== s) return false;
      if (t && p.topic !== t) return false;
      if (requireSolution && !p.solution_tex) return false;
      if (!matches(p, q)) return false;
      return true;
    }).sort((a, b) => b.year - a.year || a.session.localeCompare(b.session) || a.number - b.number);

    const prevActive = activeId;
    if (!filtered.find(p => p.id === activeId)) {
      activeId = filtered[0]?.id || null;
    }
    if (activeId && activeId !== prevActive) {
      touchRecent(activeId);
      renderRecent();
    }

    renderList();
    renderDetail();
  }

  function makeItem(p) {
    const div = document.createElement("button");
    div.className = "item" + (p.id === activeId ? " active" : "");
    div.dataset.id = p.id;
    div.innerHTML = `
      <div class="title">${p.id}</div>
      <div class="meta">${p.topic || "Unlabeled"} ${p.solution_tex ? " • solution" : ""}</div>
    `;
    div.onclick = () => {
      activeId = p.id;
      touchRecent(p.id);
      renderList();
      renderRecent();
      renderDetail();
    };
    return div;
  }

  function renderList() {
    el.stats.textContent = `${filtered.length} / ${data.problems.length} problems`;
    el.list.innerHTML = "";
    filtered.forEach(p => el.list.appendChild(makeItem(p)));
  }

  function renderRecent() {
    if (!el.recentRow || !el.recentWrap) return;
    el.recentRow.innerHTML = "";
    const validIds = recentIds.filter(id => data.problems.some(p => p.id === id));
    if (!validIds.length) {
      el.recentWrap.style.display = "none";
      return;
    }
    el.recentWrap.style.display = "block";
    validIds.forEach(id => {
      const chip = document.createElement("button");
      chip.className = "recent-chip";
      chip.textContent = id;
      chip.onclick = () => {
        activeId = id;
        touchRecent(id);
        renderRecent();
        renderList();
        renderDetail();
      };
      el.recentRow.appendChild(chip);
    });
  }

  function renderDetail() {
    const p = filtered.find(x => x.id === activeId);
    if (!p) {
      el.detail.innerHTML = "<h2>No match</h2>";
      return;
    }

    const hintItems = (p.hints || [p.hint_1, p.hint_2, p.hint_3].filter(Boolean))
      .filter(Boolean)
      .map(h => `<li>${escapeHtml(h)}</li>`)
      .join("");

    const problemBody = formatTexForReading(p.problem_tex);
    const solutionBody = formatTexForReading(
      p.solution_tex || "No TeX solution available in archive for this year/problem."
    );
    const problemRendered = p.problem_html
      ? normalizePandocHtml(p.problem_html)
      : `<pre class="tex-raw">${escapeHtml(problemBody)}</pre>`;
    const solutionRendered = p.solution_html
      ? normalizePandocHtml(p.solution_html)
      : `<pre class="tex-raw">${escapeHtml(solutionBody)}</pre>`;

    el.detail.innerHTML = `
      <h2>${p.id}</h2>
      <p>
        <span class="chip">${p.topic || "Unlabeled"}</span>
        ${p.secondary_topics?.map(t => `<span class="chip">${t}</span>`).join("") || ""}
        ${p.difficulty ? `<span class="chip">${p.difficulty}</span>` : ""}
      </p>
      <h3>Problem</h3>
      <div class="block-head">
        <div class="copy-actions">
          <button class="copy-btn" data-copy="problem" title="Copy problem">⧉</button>
          <button class="copy-btn" data-copy="both" title="Copy problem and solution">⧉+</button>
        </div>
      </div>
      <div class="tex-block">${problemRendered}</div>
      ${hintItems ? `
      <h3>Hints</h3>
      <ol class="hint-list">${hintItems}</ol>
      ` : ""}
      <details class="solution-wrap">
        <summary>${p.solution_tex ? "Show solution" : "Solution unavailable"}</summary>
        <div class="copy-actions solution-actions">
          <button class="copy-btn" data-copy="solution" ${p.solution_tex ? "" : "disabled"} title="Copy solution">⧉</button>
          <button class="copy-btn" data-copy="both" title="Copy problem and solution">⧉+</button>
        </div>
        <div class="tex-block">${solutionRendered}</div>
      </details>
    `;

    bindCopyActions(p, problemBody, solutionBody);

    if (window.MathJax && window.MathJax.typesetPromise) {
      window.MathJax.typesetPromise([el.detail]).catch(() => {});
    }
  }

  function getActiveIndex() {
    return filtered.findIndex(p => p.id === activeId);
  }

  function setActiveByIndex(idx) {
    if (!filtered.length) return;
    const clamped = Math.max(0, Math.min(filtered.length - 1, idx));
    activeId = filtered[clamped].id;
    touchRecent(activeId);
    renderRecent();
    renderList();
    renderDetail();
    const activeEl = el.list.querySelector(`.item[data-id="${activeId}"]`);
    if (activeEl) activeEl.scrollIntoView({ block: "nearest" });
  }

  function toggleSolution() {
    const details = el.detail.querySelector(".solution-wrap");
    if (!details) return;
    details.open = !details.open;
  }

  function installKeyboardShortcuts() {
    document.addEventListener("keydown", (e) => {
      const target = e.target;
      const inEditor =
        target instanceof HTMLInputElement ||
        target instanceof HTMLTextAreaElement ||
        target instanceof HTMLSelectElement ||
        target?.isContentEditable;

      if (e.key === "/") {
        e.preventDefault();
        el.search.focus();
        el.search.select();
        return;
      }

      if (inEditor) return;

      if (e.key === "j") {
        e.preventDefault();
        setActiveByIndex(getActiveIndex() + 1);
      } else if (e.key === "k") {
        e.preventDefault();
        setActiveByIndex(getActiveIndex() - 1);
      } else if (e.key === "s") {
        e.preventDefault();
        toggleSolution();
      }
    });
  }

  function bindCopyActions(problem, problemBody, solutionBody) {
    el.detail.querySelectorAll(".copy-btn").forEach(btn => {
      btn.addEventListener("click", async () => {
        const mode = btn.dataset.copy;
        let text = "";
        if (mode === "problem") {
          text = `${problem.id} Problem\n\n${problemBody}`;
        } else if (mode === "solution") {
          text = `${problem.id} Solution\n\n${solutionBody}`;
        } else {
          text = `${problem.id} Problem\n\n${problemBody}\n\n---\n\n${problem.id} Solution\n\n${solutionBody}`;
        }
        const ok = await copyToClipboard(text);
        flashCopyButton(btn, ok);
      });
    });
  }

  async function copyToClipboard(text) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (_) {
      try {
        const ta = document.createElement("textarea");
        ta.value = text;
        ta.setAttribute("readonly", "");
        ta.style.position = "absolute";
        ta.style.left = "-9999px";
        document.body.appendChild(ta);
        ta.select();
        const ok = document.execCommand("copy");
        document.body.removeChild(ta);
        return ok;
      } catch (__){
        return false;
      }
    }
  }

  function flashCopyButton(btn, ok) {
    const prev = btn.textContent;
    btn.textContent = ok ? "✓" : "!";
    btn.classList.add(ok ? "copy-ok" : "copy-fail");
    setTimeout(() => {
      btn.textContent = prev;
      btn.classList.remove("copy-ok", "copy-fail");
    }, 900);
  }

  function escapeHtml(s) {
    return (s || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;");
  }

  function formatTexForReading(s) {
    if (!s) return "";
    return s
      .replace(/\\noindent\b/g, "")
      .replace(/\\begin\{(?:itemize|enumerate|center)\}/g, "")
      .replace(/\\end\{(?:itemize|enumerate|center)\}/g, "")
      .replace(/\\item(?:\[[^\]]*\])?/g, "\n• ")
      .replace(/\\textbf\{([^{}]*)\}/g, "$1")
      .replace(/\n{3,}/g, "\n\n")
      .trim();
  }

  function normalizePandocHtml(s) {
    return (s || "")
      .replace(/<p>\s*<\/p>/g, "")
      .trim();
  }

  function loadRecentIds() {
    try {
      const raw = localStorage.getItem(RECENT_KEY);
      const parsed = JSON.parse(raw || "[]");
      return Array.isArray(parsed) ? parsed.filter(x => typeof x === "string") : [];
    } catch (_) {
      return [];
    }
  }

  function saveRecentIds() {
    try {
      localStorage.setItem(RECENT_KEY, JSON.stringify(recentIds.slice(0, RECENT_MAX)));
    } catch (_) {}
  }

  function touchRecent(id) {
    if (!id) return;
    recentIds = [id, ...recentIds.filter(x => x !== id)].slice(0, RECENT_MAX);
    saveRecentIds();
  }

  ["input", "change"].forEach(evt => {
    el.search.addEventListener(evt, applyFilters);
    el.year.addEventListener(evt, applyFilters);
    el.session.addEventListener(evt, applyFilters);
    el.topic.addEventListener(evt, applyFilters);
    el.hasSolution.addEventListener(evt, applyFilters);
  });

  fillFilters();
  applyFilters();
  if (activeId) touchRecent(activeId);
  renderRecent();
  installKeyboardShortcuts();
})();
