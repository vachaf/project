#!/usr/bin/env python3
"""Additive Stage E After capture and cross-revision comparison CLI."""
from __future__ import annotations
import argparse, json, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from src.prepare_full_output_harness.artifacts import ArtifactError
from src.prepare_full_output_harness.stage_e_after_adapter import AfterAdapterError, compare_cross_revision, run_after
from src.prepare_full_output_harness.stage_e_after_contract import AFTER_REVISION, AFTER_TREE, ExitCode, AfterIdentity, AFTER_SOURCE_FILES, after_source_digest, digest_files

class RunnerError(RuntimeError): pass
def git(root:Path,*args:str)->str:
    result=subprocess.run(["git","-C",str(root),*args],text=True,capture_output=True,check=False)
    if result.returncode: raise RunnerError("git identity check failed")
    return result.stdout.strip()
def validate(root:Path)->tuple[str,str]:
    if git(root,"rev-parse","HEAD")!=AFTER_REVISION or git(root,"rev-parse","HEAD^{tree}")!=AFTER_TREE: raise RunnerError("After identity mismatch")
    if subprocess.run(["git","-C",str(root),"symbolic-ref","-q","HEAD"],capture_output=True).returncode!=1: raise RunnerError("After must be detached")
    if git(root,"status","--porcelain=v1","--untracked-files=all"): raise RunnerError("After must be clean")
    if git(ROOT,"status","--porcelain=v1","--untracked-files=all"): raise RunnerError("verification worktree must be clean")
    return git(ROOT,"rev-parse","HEAD"),git(ROOT,"rev-parse","HEAD^{tree}")
def parser()->argparse.ArgumentParser:
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest="command",required=True)
    c=sub.add_parser("capture-after"); c.add_argument("--subject-root",type=Path,required=True); c.add_argument("--run-role",choices=("after-1","after-2"),required=True); c.add_argument("--output-root",type=Path,required=True)
    x=sub.add_parser("compare-cross-revision"); x.add_argument("--canonical-before-root",type=Path,required=True); x.add_argument("--after-1-root",type=Path,required=True); x.add_argument("--after-2-root",type=Path,required=True); x.add_argument("--output-root",type=Path,required=True)
    return p
def main(argv:list[str]|None=None)->int:
    try:
        args=parser().parse_args(argv)
        if args.command=="capture-after":
            revision,tree=validate(args.subject_root)
            identity=AfterIdentity(AFTER_REVISION,AFTER_TREE,revision,after_source_digest(args.subject_root),digest_files(ROOT,("scripts/verify_prepare_after_compatibility.py",)),digest_files(ROOT,("src/prepare_full_output_harness/artifacts.py","src/prepare_full_output_harness/capture.py","src/prepare_full_output_harness/compare.py","src/prepare_full_output_harness/identity.py","src/prepare_full_output_harness/inventory.py","src/prepare_full_output_harness/isolation.py")),digest_files(ROOT,("src/prepare_full_output_harness/stage_e_after_contract.py","src/prepare_full_output_harness/stage_e_after_adapter.py","scripts/prepare_after_capture_child.py")))
            summary=run_after(run_role=args.run_role,subject_root=args.subject_root,verification_root=ROOT,output_root=args.output_root,identity=identity); status=summary["status"]
        else: summary=compare_cross_revision(canonical_before_root=args.canonical_before_root,after_1_root=args.after_1_root,after_2_root=args.after_2_root,output_root=args.output_root); status=summary["final_verdict"]
        print(json.dumps({"status":status,"summary":summary},separators=(",",":"))); return int(ExitCode[status])
    except (RunnerError,AfterAdapterError,ArtifactError,OSError,ValueError,KeyError,TypeError) as exc:
        print(json.dumps({"status":"BLOCKED","error_code":getattr(exc,"code","runner_error")},separators=(",",":"))); return int(ExitCode.BLOCKED)
if __name__=="__main__": raise SystemExit(main())
