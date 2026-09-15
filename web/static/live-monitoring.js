(() => {
  "use strict";

  const AUTO_REFRESH_MS = 5000;
  const MAX_SELECTED_LOGS = 50;
  const $ = (selector) => document.querySelector(selector);
  const el = {
    connection: $("#liveConnectionText"), rows: $("#liveLogRows"), detail: $("#liveDetail"), error: $("#liveError"),
    count: $("#liveRowCount"), latest: $("#liveLatestLog"), fetched: $("#liveFetchedAt"), form: $("#liveFilterForm"),
    period: $("#livePeriod"), status: $("#liveStatus"), method: $("#liveMethod"), ip: $("#liveSourceIp"), keyword: $("#liveKeyword"),
    auto: $("#liveAutoButton"), refresh: $("#liveRefreshButton"), latestButton: $("#liveLatestButton"),
    older: $("#liveOlderButton"), newer: $("#liveNewerButton"), direction: $("#livePageDirection"),
    selectedCount: $("#liveSelectedCount"), clearSelection: $("#liveClearSelectionButton"),
    submitSelection: $("#liveSubmitSelectionButton"), jobFeedback: $("#liveJobFeedback"),
    selectionBar: $("#liveSelectionBar"), pager: $("#livePager"), detailCard: $("#liveDetailCard"),
  };
  const state = {
    loading: false, submitting: false, auto: true, cursor: null, older: null, newer: null,
    items: [], selected: null, selectedOrder: [], rawRequest: 0,
  };
  const processingLabels = { complete: "처리 완료", partial: "부분 관찰", unavailable: "관찰 불가", error: "탐지기 오류" };
  const assessmentLabels = { review_required: "검토 필요", no_signal: "관찰 신호 없음", undetermined: "확인 미정" };

  function value(input) { return input === null || input === undefined || input === "" ? "값 없음" : String(input); }
  function node(tag, className, content) {
    const result = document.createElement(tag);
    if (className) result.className = className;
    if (content !== undefined) result.textContent = value(content);
    return result;
  }
  function date(input) {
    if (!input) return "저장된 로그 없음";
    const parsed = new Date(input);
    return Number.isNaN(parsed.getTime()) ? String(input) : new Intl.DateTimeFormat("ko-KR", {
      timeZone: "Asia/Seoul", dateStyle: "medium", timeStyle: "medium",
    }).format(parsed);
  }
  function statusClass(input) {
    const parsed = Number(input);
    if (!Number.isInteger(parsed)) return "live-status-none";
    if (parsed >= 200 && parsed < 300) return "live-status-2xx";
    if (parsed >= 300 && parsed < 400) return "live-status-3xx";
    if (parsed >= 400 && parsed < 500) return "live-status-4xx";
    if (parsed >= 500 && parsed < 600) return "live-status-5xx";
    return "live-status-none";
  }
  function showError(message) { el.error.hidden = !message; el.error.textContent = message || ""; }
  function observationLabel(observation) {
    if (!observation) return "관찰 정보 미제공";
    const key = `${observation.processing_status}:${observation.assessment}`;
    return ({
      "complete:review_required": "검토 필요", "complete:no_signal": "관찰 신호 없음",
      "partial:review_required": "검토 필요 · 부분 관찰", "partial:undetermined": "부분 관찰 · 신호 유무 확인 미완료",
      "unavailable:undetermined": "관찰 불가", "error:undetermined": "탐지기 오류",
    })[key] || "관찰 정보 미제공";
  }
  function appendLabel(target, primary, secondary = "") {
    target.append(node("span", "", primary));
    if (secondary) target.append(document.createTextNode(" "), node("span", "live-secondary", secondary));
  }
  function sectionHeading(primary, secondary = "") {
    const heading = node("h3", "live-section-heading");
    appendLabel(heading, primary, secondary);
    return heading;
  }
  function stateClass(prefix, input) {
    return `${prefix}-${String(input || "").replace(/[^a-z0-9_-]/gi, "-")}`;
  }
  function observationFact(primary, secondary, content, className = "") {
    const row = node("div", className);
    const term = node("dt"); appendLabel(term, primary, secondary);
    const description = node("dd"); description.append(node("code", "live-tech-code", content));
    row.append(term, description); return row;
  }
  function observationState(primary, secondary, rawValue, labels, classPrefix) {
    const row = node("div", `live-observation-state-card ${stateClass(classPrefix, rawValue)}`);
    const term = node("dt"); appendLabel(term, primary, secondary);
    const description = node("dd");
    description.append(node("span", "", labels[rawValue] || rawValue), node("code", "live-state-code", rawValue));
    row.append(term, description); return row;
  }
  function fields(item) {
    return [
      ["로그 시각 (KST)", date(item.log_time)], ["DB 행 ID (DB ID)", item.row_id], ["요청 식별자 (Request ID)", item.request_id],
      ["출발지 IP 원문", item.src_ip], ["출발지 IP 기준", item.client_ip_source], ["요청 방식 (HTTP Method)", item.method], ["요청 경로 (URI)", item.uri],
      ["요청 대상 원문 (Request Target)", item.request_target], ["서버 응답 상태 (HTTP status)", item.status_code], ["응답 크기 (Bytes)", item.response_body_bytes],
      ["User-Agent 원문", item.user_agent], ["로그 스키마", item.log_schema],
    ];
  }
  function renderObservation(item) {
    const section = node("section", "live-observation");
    section.append(sectionHeading("보안 관찰", "Security observation"));
    const observation = item.observation;
    if (!observation) { section.append(node("p", "live-observation-note", "관찰 정보 미제공")); return section; }

    const states = node("dl", "live-observation-state-grid");
    states.append(
      observationState("처리 상태", "processing_status", observation.processing_status, processingLabels, "live-processing"),
      observationState("관찰 평가", "Assessment", observation.assessment, assessmentLabels, "live-assessment"),
    );
    section.append(states);
    section.append(node("p", "live-observation-note", "처리 상태는 관찰 처리의 완료·가용 범위를 나타내며 공격 심각도나 공격 성공 여부를 뜻하지 않습니다."));

    section.append(node("div", "live-observation-meta-heading", "관찰 메타데이터"));
    const facts = node("dl", "live-observation-facts");
    facts.append(
      observationFact("관찰 스키마", "Schema", observation.schema_version),
      observationFact("탐지기 버전", "Detector", observation.detector_version),
      observationFact("신호 채택 정책", "Adoption policy", observation.adoption_policy_version),
    );
    section.append(facts);

    const note = observation.assessment === "no_signal"
      ? "현재 detector·allowlist·관찰 범위에서 채택 신호가 없다는 뜻이며 정상 상태를 뜻하지 않습니다. 안전 상태를 뜻하지도 않습니다."
      : observation.assessment === "review_required"
        ? "추가 검토가 필요한 관찰 구조이며 보안 판정이 아닙니다."
        : "처리 범위가 불완전하여 신호 유무를 정하지 않습니다.";
    section.append(node("p", "live-observation-note", note));

    const signals = Array.isArray(observation.signals) ? observation.signals : [];
    section.append(node("div", "live-adopted-heading", "채택 신호 (Adopted signals)"));
    if (!signals.length) { section.append(node("p", "", "표시할 채택 신호가 없습니다.")); return section; }
    const list = node("div", "live-signal-list");
    signals.forEach((signal) => {
      const article = node("article", "live-signal"); article.append(node("h4", "", signal.signal_id));
      const meta = node("dl", "live-observation-facts");
      meta.append(
        observationFact("신호 채택 규칙", "Adoption rule", signal.adoption_rule_id),
        observationFact("탐지 규칙", "Detector rules", Array.isArray(signal.rule_ids) ? signal.rule_ids.join(", ") : "값 없음"),
      );
      article.append(meta);
      const evidenceList = node("ul", "live-evidence-list");
      (Array.isArray(signal.evidence) ? signal.evidence : []).forEach((evidence) => {
        const source = `${value(evidence.source_field)} · ${value(evidence.surface)} · ${value(evidence.decode_type)} depth ${value(evidence.decode_depth)}`;
        const entry = node("li"); entry.append(node("span", "live-evidence-source", source), node("code", "", evidence.matched_text)); evidenceList.append(entry);
      });
      article.append(evidenceList); list.append(article);
    });
    section.append(list); return section;
  }
  async function renderDetail() {
    el.detail.replaceChildren();
    const item = state.items.find((row) => row.row_id === state.selected);
    if (!item) { el.detail.append(node("p", "", "로그를 선택해주세요.")); return; }
    const list = node("dl", "live-detail-list");
    fields(item).forEach(([label, content]) => { const row = node("div"); row.append(node("dt", "", label), node("dd", "", content)); list.append(row); });
    el.detail.append(sectionHeading("선택 로그 메타데이터", "Selected log metadata"), list, renderObservation(item));
    const raw = node("pre", "live-raw-log", "원문 조회 중");
    el.detail.append(sectionHeading("원천 로그 원문", "raw_log 원문"), raw);
    const request = ++state.rawRequest;
    try {
      const response = await fetch(`/api/live/logs/${item.row_id}/raw`, { headers: { Accept: "application/json" } });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "원문을 조회하지 못했습니다.");
      if (request === state.rawRequest && state.selected === item.row_id) raw.textContent = value(payload.raw_log);
    } catch (error) {
      if (request === state.rawRequest) raw.textContent = error instanceof Error ? error.message : "원문을 조회하지 못했습니다.";
    }
  }

  function hasSelected(rowId) { return state.selectedOrder.includes(rowId); }
  function syncPresentationVisibility() {
    const hasRows = state.items.length > 0;
    const hasSelectedInput = state.selectedOrder.length > 0;
    const hasPageNavigation = hasRows || state.cursor !== null || Boolean(state.older) || Boolean(state.newer);
    el.selectionBar.hidden = !hasRows && !hasSelectedInput;
    el.detailCard.hidden = !hasRows;
    el.pager.hidden = !hasPageNavigation;
  }
  function updateSelectionControls() {
    const selectedCount = state.selectedOrder.length;
    el.selectedCount.textContent = `선택 ${selectedCount} / ${MAX_SELECTED_LOGS}건`;
    el.clearSelection.disabled = state.submitting || selectedCount === 0;
    el.submitSelection.disabled = state.submitting || selectedCount === 0;
    document.querySelectorAll(".live-row-checkbox").forEach((checkbox) => {
      const rowId = Number(checkbox.dataset.rowId); const checked = hasSelected(rowId);
      checkbox.checked = checked;
      checkbox.disabled = state.submitting || (selectedCount >= MAX_SELECTED_LOGS && !checked);
    });
    syncPresentationVisibility();
  }
  function selectForAnalysis(rowId) {
    if (state.submitting || hasSelected(rowId)) return;
    if (state.selectedOrder.length >= MAX_SELECTED_LOGS) {
      showError(`분석 입력은 최대 ${MAX_SELECTED_LOGS}건까지 선택할 수 있습니다.`); updateSelectionControls(); return;
    }
    state.selectedOrder.push(rowId); showError(""); updateSelectionControls();
  }
  function deselectForAnalysis(rowId) {
    if (state.submitting) return;
    state.selectedOrder = state.selectedOrder.filter((selectedId) => selectedId !== rowId);
    updateSelectionControls();
  }
  function createSelectionCell(item) {
    const cell = node("td", "live-row-select"); const label = node("label"); const checkbox = node("input", "live-row-checkbox");
    checkbox.type = "checkbox"; checkbox.dataset.rowId = String(item.row_id);
    checkbox.setAttribute("aria-label", `DB ID ${item.row_id} 분석 입력 선택`); checkbox.checked = hasSelected(item.row_id);
    checkbox.addEventListener("click", (event) => event.stopPropagation());
    checkbox.addEventListener("keydown", (event) => event.stopPropagation());
    checkbox.addEventListener("change", () => { if (checkbox.checked) selectForAnalysis(item.row_id); else deselectForAnalysis(item.row_id); });
    label.append(checkbox, node("span", "", "선택")); cell.append(label); return cell;
  }
  function renderRows() {
    el.rows.replaceChildren();
    if (!state.items.length) {
      const row = node("tr"); const cell = node("td", "", "조건에 맞는 로그가 없습니다."); cell.colSpan = 10; row.append(cell); el.rows.append(row);
      state.selected = null; renderDetail(); updateSelectionControls(); return;
    }
    if (!state.items.some((row) => row.row_id === state.selected)) state.selected = state.items[0].row_id;
    state.items.forEach((item) => {
      const row = node("tr"); if (item.row_id === state.selected) row.className = "is-selected"; row.tabIndex = 0;
      row.append(createSelectionCell(item), node("td", "", date(item.log_time)), node("td", "", item.row_id),
        node("td", "", item.request_id), node("td", "", item.src_ip), node("td", "", item.method), node("td", "", item.uri));
      const status = node("td"); status.append(node("span", `live-status-code ${statusClass(item.status_code)}`, item.status_code));
      row.append(status, node("td", "live-observation-label", observationLabel(item.observation)), node("td", "", item.response_body_bytes));
      const selectDetail = () => { state.selected = item.row_id; renderRows(); renderDetail(); };
      row.addEventListener("click", (event) => { if (!event.target.closest(".live-row-select")) selectDetail(); });
      row.addEventListener("keydown", (event) => {
        if (event.target !== row) return;
        if (event.key === "Enter" || event.key === " ") { event.preventDefault(); selectDetail(); }
      });
      el.rows.append(row);
    });
    updateSelectionControls();
  }

  function query(cursor) {
    const params = new URLSearchParams({ period: el.period.value, limit: "50" });
    if (el.status.value) params.set("status_class", el.status.value); if (el.method.value) params.set("method", el.method.value);
    if (el.ip.value.trim()) params.set("src_ip", el.ip.value.trim()); if (el.keyword.value.trim()) params.set("q", el.keyword.value.trim());
    if (cursor) params.set("cursor", cursor); return params;
  }
  function syncInteractionLock() {
    const locked = state.submitting;
    Array.from(el.form.elements).forEach((control) => { control.disabled = locked; });
    el.auto.disabled = locked; el.refresh.disabled = locked;
    el.latestButton.disabled = locked || state.cursor === null; el.older.disabled = locked || !state.older; el.newer.disabled = locked || !state.newer;
    updateSelectionControls();
  }
  async function snapshot(cursor = state.cursor) {
    if (state.loading || state.submitting) return;
    state.loading = true; showError(""); el.connection.textContent = "DB 조회 중";
    try {
      const response = await fetch(`/api/live/snapshot?${query(cursor)}`, { headers: { Accept: "application/json" } });
      const payload = await response.json(); if (!response.ok) throw new Error(payload.error || "조회 실패");
      state.cursor = cursor || null; state.items = Array.isArray(payload.items) ? payload.items : [];
      state.older = payload.older_cursor || null; state.newer = payload.newer_cursor || null;
      renderRows(); renderDetail(); el.count.textContent = `${state.items.length}건`;
      el.latest.textContent = date(payload.latest_log_time); el.fetched.textContent = date(payload.fetched_at);
      el.connection.textContent = "DB 조회 성공"; el.direction.textContent = state.cursor ? "과거 범위 · 최신순" : "현재 범위 · 최신순";
    } catch (error) {
      el.connection.textContent = "DB 조회 실패"; showError(`${error instanceof Error ? error.message : "조회 실패"} 이전 목록은 유지합니다.`);
    } finally { state.loading = false; syncInteractionLock(); }
  }

  function renderJobFeedback({ kind, title, message, jobId = null, missingCount = 0 }) {
    el.jobFeedback.replaceChildren(); el.jobFeedback.className = `live-job-feedback is-${kind}`;
    el.jobFeedback.append(node("h2", "", title), node("p", "", message));
    if (missingCount > 0) el.jobFeedback.append(node("p", "", `선택한 로그 중 제출 시점에 확인되지 않은 항목이 ${missingCount}건 있습니다.`));
    if (jobId !== null && jobId !== undefined) {
      const link = node("a", "", `작업 #${jobId} 상세 보기`); link.href = `/job/${encodeURIComponent(String(jobId))}`; el.jobFeedback.append(link);
    }
    el.jobFeedback.hidden = false;
  }
  function neutralFailure(status, payload) {
    if (status === 400) return { title: "선택 내용을 확인해주세요", message: "요청 형식이나 선택 개수가 허용 범위와 맞지 않습니다. 선택은 유지됩니다." };
    if (status === 503) return { title: "작업 저장소를 사용할 수 없습니다", message: "선택은 유지됩니다. 잠시 후 다시 시도해주세요." };
    if (status === 500) return { title: "분석 작업을 만들지 못했습니다", message: "아직 분석 결과가 생성된 것은 아닙니다. 선택은 유지됩니다." };
    return { title: "분석 작업을 만들지 못했습니다", message: payload && payload.code
      ? "서버 응답을 처리하지 못했습니다. 선택은 유지됩니다." : "응답을 확인하지 못했습니다. 선택은 유지됩니다." };
  }
  async function submitSelectedLogs() {
    if (state.submitting || state.selectedOrder.length === 0) return;
    const selectedLogIds = state.selectedOrder.slice(); state.submitting = true; showError(""); syncInteractionLock();
    try {
      const response = await fetch("/api/live/jobs/create", {
        method: "POST", headers: { Accept: "application/json", "Content-Type": "application/json" },
        body: JSON.stringify({ selected_log_ids: selectedLogIds }),
      });
      const payload = await response.json().catch(() => ({}));
      const missingCount = Array.isArray(payload.missing_log_ids) ? payload.missing_log_ids.length : 0;
      if (response.ok && payload.ok === true && payload.status === "PENDING" && payload.job_id != null) {
        state.selectedOrder = [];
        renderJobFeedback({ kind: "success", title: "분석 작업을 만들었습니다",
          message: "선택한 exact source log IDs가 PENDING 작업 입력으로 등록되었습니다.", jobId: payload.job_id, missingCount });
        return;
      }
      if (response.ok && payload.code === "NO_DATA") {
        renderJobFeedback({ kind: "notice", title: "분석 작업을 만들지 않았습니다",
          message: "선택한 로그를 제출 시점에 확인할 수 없습니다. 선택은 유지됩니다.", missingCount });
        return;
      }
      if (response.status === 409 && payload.code === "duplicate_active_job") {
        renderJobFeedback({ kind: "notice", title: "같은 선택의 진행 중 작업이 있습니다",
          message: "새 작업을 중복 생성하지 않았습니다. 선택은 유지됩니다.", jobId: payload.existing_job_id, missingCount });
        return;
      }
      renderJobFeedback({ kind: "error", ...neutralFailure(response.status, payload) });
    } catch (_error) {
      renderJobFeedback({ kind: "error", title: "서버에 연결하지 못했습니다",
        message: "분석 작업이 생성되었는지 확인할 수 없습니다. 선택은 유지됩니다." });
    } finally { state.submitting = false; syncInteractionLock(); }
  }

  el.form.addEventListener("submit", (event) => { event.preventDefault(); if (state.submitting) return; state.cursor = null; state.selected = null; snapshot(null); });
  el.refresh.addEventListener("click", () => { if (!state.submitting) snapshot(); });
  el.latestButton.addEventListener("click", () => { if (state.submitting) return; state.cursor = null; state.selected = null; snapshot(null); });
  el.older.addEventListener("click", () => { if (!state.submitting && state.older) snapshot(state.older); });
  el.newer.addEventListener("click", () => { if (!state.submitting && state.newer) snapshot(state.newer); });
  el.auto.addEventListener("click", () => {
    if (state.submitting) return; state.auto = !state.auto; el.auto.setAttribute("aria-pressed", String(state.auto));
    el.auto.textContent = state.auto ? "자동 확인: 켜짐 (5초)" : "자동 확인: 꺼짐";
  });
  el.clearSelection.addEventListener("click", () => { if (state.submitting) return; state.selectedOrder = []; updateSelectionControls(); });
  el.submitSelection.addEventListener("click", submitSelectedLogs);
  window.setInterval(() => { if (state.auto && state.cursor === null && !state.submitting) snapshot(null); }, AUTO_REFRESH_MS);
  updateSelectionControls(); snapshot(null);
})();
