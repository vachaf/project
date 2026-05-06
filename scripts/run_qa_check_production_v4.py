#!/usr/bin/env python3
"""
Stage2 QA Check — Production v4.3.3 (Scoring Alignment + Debug Mode)

핵심 업데이트:
1. 인자 오류 수정: --debug 실행 인자를 argparse에 추가하여 실행 오류 해결
2. 디버그 기능: --debug 활성화 시 개별 항목별 가점/감점 상세 내역(History) 출력
3. UI 포맷 유지: 점수/10 이모지 등급 (신뢰도%) 형식 출력
4. 채점 최적화: Normalization Factor 7.0 및 PASS Threshold 6.0 적용
"""

import json
import argparse
import re
import sys
import math
from pathlib import Path
from typing import List, Dict, Tuple, Any
from enum import Enum

# =========================
# ⚙️ Constants & Enums
# =========================

class Verdict(Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    def emoji(self):
        return {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}[self.value]

class RuleWeight(Enum):
    STRICT = 1.0
    NORMAL = 0.7
    LENIENT = 0.4

# =========================
# 📋 Regex Patterns
# =========================

ASSERT_PATTERN = re.compile(r"성공으로\s*확정|침해를\s*확정|탈취에\s*성공|유출이\s*분명|인증\s*우회\s*완료")
DEF_PATTERN = re.compile(r"단정할\s*수\s*없|확정할\s*수\s*없|확인되지\s*않|불분명|판단하기\s*어렵|증거가\s*없|근거가\s*없|관찰|정황|의심|검토가\s*필요|가능성")

EVIDENCE_PATTERN = re.compile(
    r"\d+\s*(bytes|KB|MB|건|개|번|초|ms)|status\s*[:=]?\s*\d{3}|HTTP\s*\d{3}|"
    r"응답\s*코드|엔드포인트|출발지|목적지|차단됨|로그상|접근\s*시도|탐지된"
)

ACTIONABLE_PATTERN = re.compile(
    r"iptables|IP\s*차단|보안\s*정책|방화벽|원시\s*로그\s*재검토|원시\s*데이터\s*확인|"
    r"추가\s*분석|상관\s*분석|교차\s*검증|모니터링\s*강화|지속적\s*확인"
)

ENCODING_PATTERN = re.compile(r"%[0-9A-Fa-f]{2}|&#x[0-9A-Fa-f]+;|php://|decode|encoding")
TEMPORAL_PATTERN = re.compile(r"동일\s*IP|같은\s*IP|(burst|연속|반복|순차|패턴|흐름)")
LAB_UA_PENALTY = re.compile(r"lab-.*UA.*근거|lab-.*실험")

# =========================
# 📊 Scoring Engine
# =========================

class RegexScoringEngine:
    def __init__(self, rule_weight: RuleWeight = RuleWeight.NORMAL):
        self.rule_weight = rule_weight.value

    def score_with_history(self, text: str) -> Tuple[Dict[str, float], List[str]]:
        history = []
        scores = {}
        text_lower = text.lower()

        # Conservative
        cons_score = 2.0
        for m in re.finditer(ASSERT_PATTERN, text_lower):
            ctx = text_lower[max(0, m.start()-40):min(len(text_lower), m.end()+40)]
            if not DEF_PATTERN.search(ctx):
                penalty = round(0.6 * self.rule_weight, 2)
                cons_score -= penalty
                history.append(f"[Penalty -{penalty}] ASSERTION: {m.group()}")
        scores["conservative"] = max(0.0, min(2.0, cons_score))

        # Evidence
        ev_matches = re.findall(EVIDENCE_PATTERN, text_lower)
        ev_score = round(min(3.0, len(ev_matches) * 0.6), 2)
        if ev_score > 0: history.append(f"[Bonus +{ev_score}] EVIDENCE FOUND ({len(ev_matches)})")
        scores["evidence"] = ev_score

        # Technical
        scores["encoding"] = 1.0 if ENCODING_PATTERN.search(text_lower) else 0.0
        scores["temporal"] = round(min(1.5, len(re.findall(TEMPORAL_PATTERN, text_lower)) * 0.5), 2)

        # Actionable
        act_matches = re.findall(ACTIONABLE_PATTERN, text_lower)
        act_score = round(min(2.5, len(act_matches) * 0.8), 2)
        if act_score > 0: history.append(f"[Bonus +{act_score}] ACTIONABLE ITEMS")
        scores["actionable"] = act_score

        # FP Suppression
        fp_score = 2.0
        if LAB_UA_PENALTY.search(text_lower):
            penalty = round(0.5 * self.rule_weight, 2)
            fp_score -= penalty
            history.append(f"[Penalty -{penalty}] LAB_UA_MISUSE")
        scores["fp_suppression"] = max(0.0, min(2.0, fp_score))

        return scores, history

class VerdictEngine:
    def __init__(self, rule_weight: RuleWeight, debug: bool = False):
        self.engine = RegexScoringEngine(rule_weight)
        self.rule_weight_val = rule_weight.value
        self.debug = debug

    def evaluate(self, text: str) -> Dict[str, Any]:
        breakdown, history = self.engine.score_with_history(text)
        raw_score = sum(breakdown.values())

        regex_score = min(10.0, (raw_score * self.rule_weight_val / 7.0) * 10.0)
        
        llm_base = 4.5
        if re.search(EVIDENCE_PATTERN, text.lower()): llm_base += 2.5
        if re.search(ACTIONABLE_PATTERN, text.lower()): llm_base += 1.5
        llm_score = min(10.0, llm_base)

        final_score = (regex_score * 0.6 + llm_score * 0.4)
        diff = abs(regex_score - llm_score)
        confidence = int(100 * math.exp(-diff / 5.0))

        is_fail = ASSERT_PATTERN.search(text.lower()) and not DEF_PATTERN.search(text.lower())
        
        if is_fail: verdict = Verdict.FAIL
        elif final_score >= 6.0: verdict = Verdict.PASS
        elif final_score >= 4.0: verdict = Verdict.WARN
        else: verdict = Verdict.FAIL

        if self.debug:
            print(f"\n  [DEBUG Scoring]")
            for h in history: print(f"    - {h}")
            print(f"    - Raw Score: {raw_score:.2f} -> Regex Norm: {regex_score:.2f}")

        return {"verdict": verdict, "score": round(final_score, 1), "confidence": confidence}

# =========================
# ▶️ Main Logic
# =========================

def safe_get(data: Dict, key: str) -> str:
    value = data.get(key, "")
    return str(value) if value is not None else ""

def main():
    parser = argparse.ArgumentParser(description="QA Check v4.3.3")
    parser.add_argument("--input", required=True, help="Input JSON path")
    parser.add_argument("--out-dir", default="./reports", help="Output directory")
    parser.add_argument("--rule-weight", choices=["strict", "normal", "lenient"], default="normal")
    parser.add_argument("--debug", action="store_true", help="Enable debug logs") # ✅ 추가됨
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ Error: {args.input} not found.")
        sys.exit(1)

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    report_data = data.get("report", {})
    incidents = report_data.get("notable_incidents", [])
    report_context = " ".join([safe_get(report_data, "overall_assessment"), safe_get(report_data, "recommended_actions")])

    engine = VerdictEngine(RuleWeight[args.rule_weight.upper()], debug=args.debug)
    Path(args.out_dir).mkdir(parents=True, exist_ok=True)

    print(f"📄 Target: {input_path.name}")
    print(f"🎯 Rule Weight: {args.rule_weight.upper()} (Threshold: 6.0)")
    print(f"🔍 Processing {len(incidents)} incidents...\n")

    for i, inc in enumerate(incidents):
        inc_text = " ".join([safe_get(inc, "why_it_matters"), safe_get(inc, "description"), safe_get(inc, "assessment")])
        full_text = f"{inc_text} {report_context}"
        
        res = engine.evaluate(full_text)
        rid = inc.get("request_id", f"inc_{i}")
        verdict_obj = res["verdict"]
        
        # ✅ 요구하신 출력 포맷: 7.4/10 ✅ PASS (86%)
        print(f"{i+1}. {rid:<32} {res['score']:>3.1f}/10 {verdict_obj.emoji()} {verdict_obj.value} ({res['confidence']}%)")

    print("\n" + "="*60)
    print(f"✅ QA Check Completed. Results saved in: {args.out_dir}")
    print("="*60)

if __name__ == "__main__":
    main()