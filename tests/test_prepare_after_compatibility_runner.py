from __future__ import annotations
import json
from pathlib import Path
import pytest
from src.prepare_full_output_harness.capture import encode_typed
from src.prepare_full_output_harness.stage_e_after_adapter import AfterAdapterError, _strict

def capture(revision:str,value:object)->dict:
    return {"status":"returned","corpus_id":"prepare_regression","case_id":"case","parameter_id":"p","parameters":{"x":1},"clock":{"x":1},"identity":{"subject_revision":revision},"input_identity":{"corpus_id":"prepare_regression","case_id":"case","source_revision":revision,"source_file_sha256":"a","parameter_id":"p","raw_source_hash":"b","projected_payload_hash":"c"},"input_before":encode_typed({"rows":[]}),"input_after":encode_typed({"rows":[]}),"input_mutated":False,"return_value":encode_typed((value,[],[],{},[]))}
def test_strict_cross_revision_allows_only_subject_transition()->None:
    before=capture("4eab95703e00373428e7ea3ec8ca58e0f09ae7c2",{"x":[1,1]}); after=capture("8ae1cf125c77b58f0f848847f889d92fe9006f52",{"x":[1,1]})
    summary,diffs=_strict({"case":before},{"case":after},cross=True)
    assert summary["mismatch_case_count"]==0 and diffs==[]
def test_strict_comparison_does_not_normalize_order_or_duplicates()->None:
    before=capture("4eab95703e00373428e7ea3ec8ca58e0f09ae7c2",{"x":[1,1,2]}); after=capture("8ae1cf125c77b58f0f848847f889d92fe9006f52",{"x":[2,1]})
    summary,diffs=_strict({"case":before},{"case":after},cross=True)
    assert summary["five_output_difference_counts"]["llm_input"]>0 and diffs
def test_unapproved_cross_revision_is_blocked()->None:
    before=capture("0"*40,{}); after=capture("8ae1cf125c77b58f0f848847f889d92fe9006f52",{})
    with pytest.raises(AfterAdapterError): _strict({"case":before},{"case":after},cross=True)
