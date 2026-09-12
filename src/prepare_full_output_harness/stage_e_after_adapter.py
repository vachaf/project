"""Additive Stage E After capture and honest cross-revision comparison."""
from __future__ import annotations
import hashlib, json, subprocess, sys, tempfile
from pathlib import Path
from typing import Any, Callable
from .artifacts import ArtifactWriter, require_completed_read_only_baseline
from .compare import compare_typed
from .isolation import build_isolated_environment
from .stage_e_after_contract import AFTER_REVISION, BEFORE_REVISION, BEFORE_SOURCE_DIGEST, BEFORE_TREE, BEFORE_VERIFICATION_REVISION, CANONICAL_FIXTURES, CORPUS_ID, OUTPUT_SLOT_NAMES, PHASE_A_BEFORE_REVISION, PROTOCOL_VERSION, AfterCaptureRequest, AfterIdentity, PhaseABeforeIdentity

class AfterAdapterError(RuntimeError):
    def __init__(self, code: str, message: str) -> None: super().__init__(message); self.code = code
def _sha(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()

def capture_after(request: AfterCaptureRequest, *, verification_root: str | Path, run_process: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run) -> dict[str, Any]:
    root = Path(verification_root).resolve(strict=True); child = root / "scripts/prepare_after_capture_child.py"
    if not child.is_file(): raise AfterAdapterError("child_missing", "After child is missing")
    with tempfile.TemporaryDirectory(prefix="prepare-stage-e-after-") as cache:
        result = run_process([sys.executable, "-I", str(child)], input=request.to_json(), text=True, capture_output=True,
            env=build_isolated_environment(Path(cache).resolve()), cwd=str(root), check=False)
    if result.returncode: raise AfterAdapterError("child_failed", "After child failed")
    try: response = json.loads(result.stdout)
    except json.JSONDecodeError as exc: raise AfterAdapterError("invalid_child_response", "invalid child JSON") from exc
    if response.get("protocol_version") != PROTOCOL_VERSION or response.get("run_role") != request.run_role: raise AfterAdapterError("protocol_mismatch", "child contract mismatch")
    if response.get("status") not in {"returned", "raised"}: raise AfterAdapterError("invalid_child_status", "invalid child status")
    return response

def run_after(*, run_role: str, subject_root: str | Path, verification_root: str | Path, output_root: str | Path, identity: AfterIdentity | PhaseABeforeIdentity, capture: Callable[..., dict[str, Any]] = capture_after) -> dict[str, Any]:
    subject = Path(subject_root).resolve(strict=True); output = Path(output_root); cases = output.with_name(output.name + ".cases")
    fixtures = subject / "tests/fixtures/prepare_regression"; names = tuple(sorted(p.name for p in fixtures.glob("*.json") if p.is_file()))
    if names != CANONICAL_FIXTURES: raise AfterAdapterError("inventory_mismatch", "fixture inventory differs")
    if output.exists() or cases.exists(): raise AfterAdapterError("output_exists", "output exists")
    cases.mkdir(mode=0o700, parents=False); records=[]; mutations=[]; exceptions=[]
    for filename in CANONICAL_FIXTURES:
        case_id=Path(filename).stem; request=AfterCaptureRequest(run_role, str(subject), str(fixtures/filename), case_id, identity)
        response=capture(request, verification_root=verification_root); writer=ArtifactWriter.create(cases/case_id)
        writer.write_json("capture.json", response); writer.finalize(); validated=require_completed_read_only_baseline(cases/case_id)
        if response.get("input_mutated"): mutations.append(case_id)
        if response["status"] == "raised": exceptions.append(case_id)
        records.append({"case_id":case_id,"fixture":filename,"artifact_path":str(validated),"capture_sha256":_sha(validated/"capture.json"),"status":response["status"],"input_identity":response["input_identity"]})
    status="FAIL" if mutations or exceptions else "PASS"; summary={"status":status,"run_role":run_role,"case_count":len(records),"identity":identity.as_dict(),"corpus_id":CORPUS_ID,"fixtures":list(CANONICAL_FIXTURES),"mutation_case_count":len(mutations),"mutation_cases":mutations,"exception_case_count":len(exceptions),"exception_cases":exceptions,"case_artifacts":records}
    writer=ArtifactWriter.create(output); writer.write_json("summary.json",summary); writer.finalize(); require_completed_read_only_baseline(output); return summary

def _load(root: str | Path) -> tuple[dict[str,Any],dict[str,dict[str,Any]]]:
    base=require_completed_read_only_baseline(root); summary=json.loads((base/"summary.json").read_text()); records=summary.get("case_artifacts")
    if not isinstance(records,list) or len(records)!=25: raise AfterAdapterError("inventory_incomplete","run inventory incomplete")
    captures={}
    for record in records:
        case=require_completed_read_only_baseline(record["artifact_path"])
        if _sha(case/"capture.json") != record["capture_sha256"]: raise AfterAdapterError("case_checksum_mismatch","case checksum differs")
        captures[record["case_id"]]=json.loads((case/"capture.json").read_text())
    if tuple(captures)!=tuple(Path(n).stem for n in CANONICAL_FIXTURES): raise AfterAdapterError("inventory_mismatch","case inventory differs")
    return summary,captures

def _strict(left: dict[str,dict[str,Any]], right: dict[str,dict[str,Any]], *, cross: bool, from_revision: str = BEFORE_REVISION, to_revision: str = AFTER_REVISION) -> tuple[dict[str,Any],list[dict[str,str]]]:
    counts={n:0 for n in OUTPUT_SLOT_NAMES}; mismatches=set(); differences=[]; mutations=[]; state=[]; exceptions=[]
    for case_id in left:
        a,b=left[case_id],right[case_id]
        invariant=("corpus_id","case_id","parameter_id","parameters","clock","input_before")
        if any(a.get(k)!=b.get(k) for k in invariant): raise AfterAdapterError("identity_mismatch",f"case contract differs: {case_id}")
        ai,bi=a["input_identity"],b["input_identity"]
        for key in ("corpus_id","case_id","source_file_sha256","parameter_id","raw_source_hash","projected_payload_hash"):
            if ai.get(key)!=bi.get(key): raise AfterAdapterError("identity_mismatch",f"input identity differs: {case_id}")
        if cross:
            if ai.get("source_revision")!=from_revision or bi.get("source_revision")!=to_revision: raise AfterAdapterError("identity_mismatch","unapproved source transition")
        elif a.get("identity")!=b.get("identity"): raise AfterAdapterError("identity_mismatch","After identities differ")
        if a["status"]!=b["status"]: state.append(case_id); mismatches.add(case_id); continue
        if a.get("input_mutated") or b.get("input_mutated") or a.get("input_after")!=b.get("input_after"): mutations.append(case_id); mismatches.add(case_id)
        if a["status"]=="raised": exceptions.append(case_id); mismatches.add(case_id); continue
        for i,name in enumerate(OUTPUT_SLOT_NAMES):
            diffs=compare_typed(a["return_value"]["items"][i],b["return_value"]["items"][i]); counts[name]+=len(diffs)
            if diffs: mismatches.add(case_id); differences.extend({"case_id":case_id,"slot":name,"kind":d.kind.value,"path":d.path} for d in diffs)
    return {"five_output_difference_counts":counts,"mismatch_case_count":len(mismatches),"mismatch_cases":sorted(mismatches),"mutation_case_count":len(mutations),"mutation_cases":mutations,"success_exception_mismatch_count":len(state),"unexpected_exception_case_count":len(exceptions),"unexpected_exception_cases":exceptions},differences

def compare_cross_revision(*, canonical_before_root: str|Path, after_1_root: str|Path, after_2_root: str|Path, output_root: str|Path) -> dict[str,Any]:
    canonical=Path(canonical_before_root).resolve(strict=True); comparison=require_completed_read_only_baseline(canonical/"comparison")
    old=json.loads((comparison/"summary.json").read_text()); identity=json.loads((comparison/"identity.json").read_text())
    if old.get("final_verdict")!="PASS" or any(old.get("five_output_difference_counts",{}).values()): raise AfterAdapterError("canonical_before_invalid","canonical comparison is not PASS")
    expected={"subject_revision":BEFORE_REVISION,"verification_revision":BEFORE_VERIFICATION_REVISION,"source_tree_digest":BEFORE_SOURCE_DIGEST}
    if any(identity["before_1"].get(k)!=v or identity["before_2"].get(k)!=v for k,v in expected.items()): raise AfterAdapterError("canonical_before_identity_mismatch","canonical identity differs")
    b1s,b1=_load(canonical/"before-1"); b2s,b2=_load(canonical/"before-2"); a1s,a1=_load(after_1_root); a2s,a2=_load(after_2_root)
    after_check,after_diffs=_strict(a1,a2,cross=False); cross1,diffs1=_strict(b1,a1,cross=True); cross2,diffs2=_strict(b2,a2,cross=True)
    if a1s["identity"]!=a2s["identity"]: raise AfterAdapterError("identity_mismatch","After run identities differ")
    fail=bool(after_check["mismatch_case_count"] or cross1["mismatch_case_count"] or cross2["mismatch_case_count"])
    summary={"final_verdict":"FAIL" if fail else "PASS","identity_relation":"expected_cross_revision","inventory_equal":tuple(b1)==tuple(b2)==tuple(a1)==tuple(a2),**cross1,"after_nondeterminism":"DETECTED" if after_check["mismatch_case_count"] else "NOT DETECTED","replica_cross_check_mismatch_count":cross2["mismatch_case_count"]}
    before_identity={**b1s["identity"],"subject_tree":BEFORE_TREE}
    transition={"identity_relation":"expected_cross_revision","before":before_identity,"after":a1s["identity"],"approved_transition":{"from":BEFORE_REVISION,"to":AFTER_REVISION}}
    writer=ArtifactWriter.create(output_root); writer.write_json("summary.json",summary); writer.write_json("identity_transition.json",transition); writer.write_json("inventory.json",{"before":list(b1),"after":list(a1)}); writer.write_json("differences.json",diffs1); writer.write_json("replica_differences.json",after_diffs+diffs2); writer.finalize(); require_completed_read_only_baseline(output_root); return summary

def compare_phase_a(*, before_1_root: str|Path, before_2_root: str|Path, after_1_root: str|Path, after_2_root: str|Path, output_root: str|Path) -> dict[str,Any]:
    b1s,b1=_load(before_1_root); b2s,b2=_load(before_2_root); a1s,a1=_load(after_1_root); a2s,a2=_load(after_2_root)
    if b1s["identity"] != b2s["identity"] or a1s["identity"] != a2s["identity"]:
        raise AfterAdapterError("identity_mismatch", "repeated run identities differ")
    if b1s["identity"].get("subject_revision") != PHASE_A_BEFORE_REVISION or a1s["identity"].get("subject_revision") != AFTER_REVISION:
        raise AfterAdapterError("identity_mismatch", "Phase A transition is not approved")
    before_check,before_diffs=_strict(b1,b2,cross=False); after_check,after_diffs=_strict(a1,a2,cross=False)
    cross1,diffs1=_strict(b1,a1,cross=True,from_revision=PHASE_A_BEFORE_REVISION); cross2,diffs2=_strict(b2,a2,cross=True,from_revision=PHASE_A_BEFORE_REVISION)
    fail=any(item["mismatch_case_count"] for item in (before_check,after_check,cross1,cross2))
    summary={"final_verdict":"FAIL" if fail else "PASS","identity_relation":"expected_phase_a_transition","inventory_equal":tuple(b1)==tuple(b2)==tuple(a1)==tuple(a2),**cross1,"before_nondeterminism":"DETECTED" if before_check["mismatch_case_count"] else "NOT DETECTED","after_nondeterminism":"DETECTED" if after_check["mismatch_case_count"] else "NOT DETECTED","replica_cross_check_mismatch_count":cross2["mismatch_case_count"]}
    transition={"identity_relation":"expected_phase_a_transition","before":b1s["identity"],"after":a1s["identity"],"approved_transition":{"from":PHASE_A_BEFORE_REVISION,"to":AFTER_REVISION}}
    writer=ArtifactWriter.create(output_root); writer.write_json("summary.json",summary); writer.write_json("identity_transition.json",transition); writer.write_json("inventory.json",{"before":list(b1),"after":list(a1)}); writer.write_json("differences.json",diffs1); writer.write_json("replica_differences.json",before_diffs+after_diffs+diffs2); writer.finalize(); require_completed_read_only_baseline(output_root); return summary
