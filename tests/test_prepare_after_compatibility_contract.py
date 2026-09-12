from __future__ import annotations
import pytest
from src.prepare_full_output_harness.stage_e_after_contract import AFTER_REVISION, AFTER_TREE, AfterCaptureRequest, AfterContractError, AfterIdentity

def identity()->AfterIdentity: return AfterIdentity(AFTER_REVISION,AFTER_TREE,"7d9a4929939eba037e4a6029862114664b01ca71","a"*64,"b"*64,"c"*64,"d"*64)
def test_after_identity_is_honest_and_serialized()->None:
    value=AfterCaptureRequest("after-1","/subject","/fixture","case",identity()).as_dict()
    assert value["identity"]["subject_revision"]==AFTER_REVISION
    assert value["identity"]["subject_tree"]==AFTER_TREE
def test_unapproved_revision_is_rejected()->None:
    with pytest.raises(AfterContractError): AfterIdentity("0"*40,AFTER_TREE,"7"*40,"a"*64,"b"*64,"c"*64,"d"*64)
@pytest.mark.parametrize("role",["before-1","after","after-3"])
def test_only_two_after_roles_are_allowed(role:str)->None:
    with pytest.raises(AfterContractError): AfterCaptureRequest(role,"/s","/i","c",identity())
