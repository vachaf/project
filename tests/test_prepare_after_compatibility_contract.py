from __future__ import annotations
import pytest
from src.prepare_full_output_harness.stage_e_after_contract import AFTER_REVISION, AFTER_TREE, PHASE_A_BEFORE_REVISION, PHASE_A_BEFORE_TREE, AfterCaptureRequest, AfterContractError, AfterIdentity, PhaseABeforeIdentity

def identity()->AfterIdentity: return AfterIdentity(AFTER_REVISION,AFTER_TREE,"7d9a4929939eba037e4a6029862114664b01ca71","a"*64,"b"*64,"c"*64,"d"*64)
def test_after_identity_is_honest_and_serialized()->None:
    assert AFTER_REVISION == "0f99059b4831f3b39a7106cfb43702c714ec5fce"
    assert AFTER_TREE == "3cc97f2bba269cbab735f15354316180e8a88e22"
    value=AfterCaptureRequest("after-1","/subject","/fixture","case",identity()).as_dict()
    assert value["identity"]["subject_revision"]==AFTER_REVISION
    assert value["identity"]["subject_tree"]==AFTER_TREE
def test_unapproved_revision_is_rejected()->None:
    with pytest.raises(AfterContractError): AfterIdentity("0"*40,AFTER_TREE,"7"*40,"a"*64,"b"*64,"c"*64,"d"*64)
def test_phase_a_before_identity_and_role_are_bound()->None:
    phase=PhaseABeforeIdentity(PHASE_A_BEFORE_REVISION,PHASE_A_BEFORE_TREE,"7"*40,"a"*64,"b"*64,"c"*64,"d"*64)
    request=AfterCaptureRequest("phase-a-before-1","/s","/i","c",phase)
    assert request.as_dict()["identity"]["subject_revision"]==PHASE_A_BEFORE_REVISION
    with pytest.raises(AfterContractError): AfterCaptureRequest("after-1","/s","/i","c",phase)
@pytest.mark.parametrize("role",["before-1","after","after-3","phase-a-before"])
def test_only_two_after_roles_are_allowed(role:str)->None:
    with pytest.raises(AfterContractError): AfterCaptureRequest(role,"/s","/i","c",identity())
