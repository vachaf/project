(() => {
  "use strict";
  const AUTO_REFRESH_MS = 5000;
  const $ = (selector) => document.querySelector(selector);
  const el = { connection:$("#liveConnectionText"), rows:$("#liveLogRows"), detail:$("#liveDetail"), error:$("#liveError"),
    count:$("#liveRowCount"), latest:$("#liveLatestLog"), fetched:$("#liveFetchedAt"), form:$("#liveFilterForm"),
    period:$("#livePeriod"), status:$("#liveStatus"), method:$("#liveMethod"), ip:$("#liveSourceIp"), keyword:$("#liveKeyword"),
    auto:$("#liveAutoButton"), refresh:$("#liveRefreshButton"), latestButton:$("#liveLatestButton"), older:$("#liveOlderButton"), newer:$("#liveNewerButton"), direction:$("#livePageDirection") };
  const state = { loading:false, auto:true, cursor:null, older:null, newer:null, items:[], selected:null, rawRequest:0 };
  const value = (v) => v === null || v === undefined || v === "" ? "값 없음" : String(v);
  const processingLabels = { complete:"처리 완료", partial:"부분 관찰", unavailable:"관찰 불가", error:"detector 오류" };
  const assessmentLabels = { review_required:"검토 필요", no_signal:"관찰 신호 없음", undetermined:"확인 미정" };
  function node(tag, className, content) { const n=document.createElement(tag); if(className)n.className=className; if(content!==undefined)n.textContent=value(content); return n; }
  function date(value) { if(!value)return "저장된 로그 없음"; const d=new Date(value); return Number.isNaN(d.getTime())?String(value):new Intl.DateTimeFormat("ko-KR",{timeZone:"Asia/Seoul",dateStyle:"medium",timeStyle:"medium"}).format(d); }
  function statusClass(v) { const n=Number(v); if(!Number.isInteger(n))return "live-status-none"; if(n>=200&&n<300)return "live-status-2xx"; if(n>=300&&n<400)return "live-status-3xx"; if(n>=400&&n<500)return "live-status-4xx"; if(n>=500&&n<600)return "live-status-5xx"; return "live-status-none"; }
  function showError(message){el.error.hidden=!message;el.error.textContent=message||"";}
  function observationLabel(observation) {
    if(!observation)return "관찰 정보 미제공";
    const key=`${observation.processing_status}:${observation.assessment}`;
    return ({"complete:review_required":"검토 필요","complete:no_signal":"관찰 신호 없음","partial:review_required":"검토 필요 · 부분 관찰","partial:undetermined":"부분 관찰 · 신호 유무 확인 미완료","unavailable:undetermined":"관찰 불가","error:undetermined":"detector 오류"})[key]||"관찰 정보 미제공";
  }
  function fields(item) { return [["로그 시각 (KST)",date(item.log_time)],["DB ID",item.row_id],["Request ID",item.request_id],["IP 원문",item.src_ip],["IP 기준",item.client_ip_source],["Method",item.method],["URI",item.uri],["Request Target 원문",item.request_target],["HTTP status",item.status_code],["응답 bytes",item.response_body_bytes],["User-Agent 원문",item.user_agent],["로그 형식",item.log_schema]]; }
  function renderObservation(item) {
    const section=node("section","live-observation");section.append(node("h3","","보안 관찰"));
    const observation=item.observation;
    if(!observation){section.append(node("p","live-observation-note","관찰 정보 미제공"));return section;}
    const facts=node("dl","live-observation-facts");
    [["처리 상태",processingLabels[observation.processing_status]||observation.processing_status],["Assessment",assessmentLabels[observation.assessment]||observation.assessment],["Schema",observation.schema_version],["Detector",observation.detector_version],["Adoption policy",observation.adoption_policy_version]].forEach(([label,content])=>{const row=node("div");row.append(node("dt","",label),node("dd","",content));facts.append(row);});
    section.append(facts);
    const note=observation.assessment==="no_signal"?"현재 detector·allowlist·관찰 범위에서 채택 신호가 없다는 뜻이며 정상 상태를 뜻하지 않습니다.":observation.assessment==="review_required"?"추가 검토가 필요한 관찰 구조이며 보안 판정이 아닙니다.":"처리 범위가 불완전하여 신호 유무를 정하지 않습니다.";
    section.append(node("p","live-observation-note",note));
    const signals=Array.isArray(observation.signals)?observation.signals:[];
    if(!signals.length){section.append(node("p","","표시할 채택 신호가 없습니다."));return section;}
    const list=node("div","live-signal-list");
    signals.forEach((signal)=>{const article=node("article","live-signal");article.append(node("h4","",signal.signal_id));const meta=node("dl","live-observation-facts");[["Adoption rule",signal.adoption_rule_id],["Detector rules",Array.isArray(signal.rule_ids)?signal.rule_ids.join(", "):"값 없음"]].forEach(([label,content])=>{const row=node("div");row.append(node("dt","",label),node("dd","",content));meta.append(row);});article.append(meta);const evidenceList=node("ul","live-evidence-list");(Array.isArray(signal.evidence)?signal.evidence:[]).forEach((evidence)=>{const source=`${value(evidence.source_field)} · ${value(evidence.surface)} · ${value(evidence.decode_type)} depth ${value(evidence.decode_depth)}`;const entry=node("li");entry.append(node("span","live-evidence-source",source),node("code","",evidence.matched_text));evidenceList.append(entry);});article.append(evidenceList);list.append(article);});section.append(list);return section;
  }
  async function renderDetail() {
    el.detail.replaceChildren(); const item=state.items.find((r)=>r.row_id===state.selected); if(!item){el.detail.append(node("p","","로그를 선택해주세요."));return;}
    const list=node("dl","live-detail-list"); fields(item).forEach(([label,content])=>{const row=node("div");row.append(node("dt","",label),node("dd","",content));list.append(row);}); el.detail.append(list,renderObservation(item));
    const heading=node("h3","","raw_log 원문"); const raw=node("pre","live-raw-log","원문 조회 중"); el.detail.append(heading,raw);
    const request=++state.rawRequest;
    try { const response=await fetch(`/api/live/logs/${item.row_id}/raw`,{headers:{Accept:"application/json"}}); const payload=await response.json(); if(!response.ok)throw new Error(payload.error||"원문을 조회하지 못했습니다."); if(request===state.rawRequest&&state.selected===item.row_id)raw.textContent=value(payload.raw_log); }
    catch(error){if(request===state.rawRequest)raw.textContent=error instanceof Error?error.message:"원문을 조회하지 못했습니다.";}
  }
  function renderRows(){el.rows.replaceChildren();if(!state.items.length){const tr=node("tr");const td=node("td","","조건에 맞는 로그가 없습니다.");td.colSpan=9;tr.append(td);el.rows.append(tr);state.selected=null;renderDetail();return;}if(!state.items.some((r)=>r.row_id===state.selected))state.selected=state.items[0].row_id;state.items.forEach((item)=>{const tr=node("tr");if(item.row_id===state.selected)tr.className="is-selected";tr.tabIndex=0;tr.append(node("td","",date(item.log_time)),node("td","",item.row_id),node("td","",item.request_id),node("td","",item.src_ip),node("td","",item.method),node("td","",item.uri));const status=node("td");status.append(node("span",`live-status-code ${statusClass(item.status_code)}`,item.status_code));tr.append(status,node("td","live-observation-label",observationLabel(item.observation)),node("td","",item.response_body_bytes));const select=()=>{state.selected=item.row_id;renderRows();renderDetail();};tr.addEventListener("click",select);tr.addEventListener("keydown",(e)=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();select();}});el.rows.append(tr);});}
  function query(cursor){const p=new URLSearchParams({period:el.period.value,limit:"50"});if(el.status.value)p.set("status_class",el.status.value);if(el.method.value)p.set("method",el.method.value);if(el.ip.value.trim())p.set("src_ip",el.ip.value.trim());if(el.keyword.value.trim())p.set("q",el.keyword.value.trim());if(cursor)p.set("cursor",cursor);return p;}
  async function snapshot(cursor=state.cursor){if(state.loading)return;state.loading=true;showError("");el.connection.textContent="DB 조회 중";try{const response=await fetch(`/api/live/snapshot?${query(cursor)}`,{headers:{Accept:"application/json"}});const payload=await response.json();if(!response.ok)throw new Error(payload.error||"조회 실패");state.cursor=cursor||null;state.items=Array.isArray(payload.items)?payload.items:[];state.older=payload.older_cursor||null;state.newer=payload.newer_cursor||null;renderRows();renderDetail();el.count.textContent=`${state.items.length}건`;el.latest.textContent=date(payload.latest_log_time);el.fetched.textContent=date(payload.fetched_at);el.connection.textContent="DB 조회 성공";el.direction.textContent=state.cursor?"과거 범위 · 최신순":"현재 범위 · 최신순";}catch(error){el.connection.textContent="DB 조회 실패";showError(`${error instanceof Error?error.message:"조회 실패"} 이전 목록은 유지합니다.`);}finally{state.loading=false;el.older.disabled=!state.older;el.newer.disabled=!state.newer;el.latestButton.disabled=state.cursor===null;}}
  el.form.addEventListener("submit",(e)=>{e.preventDefault();state.cursor=null;state.selected=null;snapshot(null);});el.refresh.addEventListener("click",()=>snapshot());el.latestButton.addEventListener("click",()=>{state.cursor=null;state.selected=null;snapshot(null);});el.older.addEventListener("click",()=>state.older&&snapshot(state.older));el.newer.addEventListener("click",()=>state.newer&&snapshot(state.newer));el.auto.addEventListener("click",()=>{state.auto=!state.auto;el.auto.setAttribute("aria-pressed",String(state.auto));el.auto.textContent=state.auto?"자동 확인: 켜짐 (5초)":"자동 확인: 꺼짐";});
  window.setInterval(()=>{if(state.auto&&state.cursor===null)snapshot(null);},AUTO_REFRESH_MS);snapshot(null);
})();
