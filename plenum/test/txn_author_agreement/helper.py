import json
import base64
from typing import Optional, Dict, Any, Union, NamedTuple, Tuple, List
from datetime import datetime
import base58
from hashlib import sha256

from indy_vdr.ledger import build_txn_author_agreement_request, build_get_txn_author_agreement_request, \
    build_get_acceptance_mechanisms_request, build_disable_all_txn_author_agreements_request

from plenum.common.constants import CONFIG_LEDGER_ID, STATE_PROOF, ROOT_HASH, PROOF_NODES, MULTI_SIGNATURE, \
    MULTI_SIGNATURE_PARTICIPANTS, MULTI_SIGNATURE_SIGNATURE, MULTI_SIGNATURE_VALUE, MULTI_SIGNATURE_VALUE_LEDGER_ID, \
    MULTI_SIGNATURE_VALUE_STATE_ROOT, MULTI_SIGNATURE_VALUE_TXN_ROOT, MULTI_SIGNATURE_VALUE_POOL_STATE_ROOT, \
    MULTI_SIGNATURE_VALUE_TIMESTAMP, TXN_AUTHOR_AGREEMENT_TEXT, TXN_AUTHOR_AGREEMENT_VERSION, \
    AML_VERSION, AML, AML_CONTEXT, GET_TXN_AUTHOR_AGREEMENT_DIGEST, GET_TXN_AUTHOR_AGREEMENT_VERSION, \
    OP_FIELD_NAME, DATA, TXN_TIME, REPLY, \
    TXN_METADATA, TXN_METADATA_SEQ_NO, TXN_METADATA_TIME, GET_TXN_AUTHOR_AGREEMENT_AML_VERSION, \
    GET_TXN_AUTHOR_AGREEMENT_AML_TIMESTAMP, TXN_AUTHOR_AGREEMENT_AML, TXN_AUTHOR_AGREEMENT_RETIREMENT_TS, TXN_TYPE, \
    TXN_AUTHOR_AGREEMENT, TXN_AUTHOR_AGREEMENT_DIGEST, TXN_AUTHOR_AGREEMENT_RATIFICATION_TS, TXN_AUTHOR_AGREEMENT_DISABLE
from plenum.common.types import f
from plenum.common.util import randomString
from plenum.server.request_handlers.static_taa_helper import StaticTAAHelper
from plenum.server.request_handlers.txn_author_agreement_aml_handler import TxnAuthorAgreementAmlHandler
from plenum.server.request_managers.write_request_manager import WriteRequestManager
from plenum.test.helper import vdr_sign_and_submit_req, vdr_get_and_check_replies, vdr_sign_and_submit_op
from state.pruning_state import PruningState
from plenum.common.request import Request
from plenum.common.txn_util import reqToTxn

TaaData = NamedTuple("TaaData", [
    ("text", str),
    ("version", str),
    ("seq_no", int),
    ("txn_time", int),
    ("digest", str)
])

TaaAmlData = NamedTuple("TaaAmlData", [
    ("version", str),
    ("aml", dict),
    ("amlContext", str),
    ("seq_no", int),
    ("txn_time", int)
])


def sdk_send_txn_author_agreement(looper, pool_handle, sdk_wallet, version: str,
                                  text: Optional[str] = None,
                                  ratified: Optional[int] = None,
                                  retired: Optional[int] = None):
    """Send a transaction author agreement"""
    # Convert None values to appropriate defaults
    text = text or ""
    ratified = ratified or 0
    retired = retired or 0
    
    req = looper.loop.run_until_complete(build_txn_author_agreement_request(
        sdk_wallet[1], text, version, ratified, retired))
    rep = vdr_sign_and_submit_req(looper, pool_handle, sdk_wallet, req)
    return vdr_get_and_check_replies(looper, [rep])[0]


def sdk_send_txn_author_agreement_disable(looper, pool_handle, sdk_wallet):
    req = looper.loop.run_until_complete(build_disable_all_txn_author_agreements_request(sdk_wallet[1]))
    rep = vdr_sign_and_submit_req(looper, pool_handle, sdk_wallet, req)
    return vdr_get_and_check_replies(looper, [rep])[0]


def set_txn_author_agreement(
        looper, pool_handle, sdk_wallet, text: str, version: str, ratified: int, retired: Optional[int]
) -> TaaData:
    reply = sdk_send_txn_author_agreement(looper, pool_handle, sdk_wallet, version, text,
                                          ratified=ratified, retired=retired)[1]

    assert reply[OP_FIELD_NAME] == REPLY
    result = reply[f.RESULT.nm]

    return TaaData(
        text, version,
        seq_no=result[TXN_METADATA][TXN_METADATA_SEQ_NO],
        txn_time=result[TXN_METADATA][TXN_METADATA_TIME],
        # TODO: Add ratified?
        digest=StaticTAAHelper.taa_digest(text, version)
    )


def sdk_get_txn_author_agreement(looper, pool_handle, wallet,
                                 digest: Optional[str] = None,
                                 version: Optional[str] = None,
                                 timestamp: Optional[int] = None):
    params = {}
    if digest is not None:
        params[GET_TXN_AUTHOR_AGREEMENT_DIGEST] = digest
    if version is not None:
        params[GET_TXN_AUTHOR_AGREEMENT_VERSION] = version
    if timestamp is not None:
        params['timestamp'] = timestamp
    req = looper.loop.run_until_complete(build_get_txn_author_agreement_request(wallet[1], json.dumps(params)))
    rep = vdr_sign_and_submit_req(looper, pool_handle, wallet, req)
    return vdr_get_and_check_replies(looper, [rep])[0]


def sdk_get_taa_aml(looper, pool_handle, sdk_wallet,
                    version: Optional[str] = None,
                    timestamp: Optional[int] = None):
    """Get transaction author agreement acceptance mechanisms"""
    # Convert None values to appropriate defaults
    version = version or ""
    timestamp = timestamp or 0
    
    req = looper.loop.run_until_complete(build_get_acceptance_mechanisms_request(
        sdk_wallet[1], timestamp, version))
    rep = vdr_sign_and_submit_req(looper, pool_handle, sdk_wallet, req)
    return vdr_get_and_check_replies(looper, [rep])[0]


def get_txn_author_agreement(looper, pool_handle, wallet,
                            digest: Optional[str] = None,
                            version: Optional[str] = None,
                            timestamp: Optional[int] = None) -> Tuple[Dict[str, Any], Any]:
    """Get transaction author agreement"""
    params = {}
    if digest is not None:
        params[GET_TXN_AUTHOR_AGREEMENT_DIGEST] = digest
    if version is not None:
        params[GET_TXN_AUTHOR_AGREEMENT_VERSION] = version
    if timestamp is not None:
        params['timestamp'] = timestamp
        
    req = looper.loop.run_until_complete(build_get_txn_author_agreement_request(wallet[1], json.dumps(params)))
    rep = vdr_sign_and_submit_req(looper, pool_handle, wallet, req)
    return vdr_get_and_check_replies(looper, [rep])[0]


def get_aml_req_handler(node):
    aml_req_handler = node.write_manager.request_handlers[TXN_AUTHOR_AGREEMENT_AML][0]
    assert isinstance(aml_req_handler, TxnAuthorAgreementAmlHandler)
    return aml_req_handler


def taa_digest(text: str, version: str) -> str:
    return sha256('{}{}'.format(version, text).encode()).hexdigest()


def check_state_proof(result: Dict[str, Any], expected_key: Optional[str] = None, expected_value: Optional[Any] = None) -> None:
    """Check if the state proof in the result is valid"""
    # TODO: This was copy-pasted from indy node (and extended), probably there should be better place for it
    assert STATE_PROOF in result
    state_proof = result[STATE_PROOF]
    assert ROOT_HASH in state_proof
    assert state_proof[ROOT_HASH]
    assert PROOF_NODES in state_proof
    assert state_proof[PROOF_NODES]
    assert MULTI_SIGNATURE in state_proof

    multi_sig = state_proof[MULTI_SIGNATURE]
    assert multi_sig
    assert multi_sig[MULTI_SIGNATURE_PARTICIPANTS]
    assert multi_sig[MULTI_SIGNATURE_SIGNATURE]
    assert MULTI_SIGNATURE_VALUE in multi_sig

    multi_sig_value = multi_sig[MULTI_SIGNATURE_VALUE]
    assert MULTI_SIGNATURE_VALUE_LEDGER_ID in multi_sig_value
    assert multi_sig_value[MULTI_SIGNATURE_VALUE_LEDGER_ID]
    assert MULTI_SIGNATURE_VALUE_STATE_ROOT in multi_sig_value
    assert multi_sig_value[MULTI_SIGNATURE_VALUE_STATE_ROOT]
    assert MULTI_SIGNATURE_VALUE_TXN_ROOT in multi_sig_value
    assert multi_sig_value[MULTI_SIGNATURE_VALUE_TXN_ROOT]
    assert MULTI_SIGNATURE_VALUE_POOL_STATE_ROOT in multi_sig_value
    assert multi_sig_value[MULTI_SIGNATURE_VALUE_POOL_STATE_ROOT]
    assert MULTI_SIGNATURE_VALUE_TIMESTAMP in multi_sig_value
    assert multi_sig_value[MULTI_SIGNATURE_VALUE_TIMESTAMP]

    if expected_key is not None and expected_value is not None:
        proof_nodes = base64.b64decode(state_proof[PROOF_NODES])
        root_hash = base58.b58decode(state_proof[ROOT_HASH])
        assert PruningState.verify_state_proof(root_hash,
                                             expected_key,
                                             expected_value,
                                             proof_nodes, serialized=True)

    # TODO: Validate signatures as well?


def expected_state_data(data: TaaData) -> Dict:
    return {
        'lsn': data.seq_no,
        'lut': data.txn_time,
        'val': {
            TXN_AUTHOR_AGREEMENT_TEXT: data.text,
            TXN_AUTHOR_AGREEMENT_VERSION: data.version,
            TXN_AUTHOR_AGREEMENT_DIGEST: StaticTAAHelper.taa_digest(data.text, data.version),
            TXN_AUTHOR_AGREEMENT_RATIFICATION_TS: data.txn_time
        }
    }


def expected_data(data: TaaData):
    return {
        TXN_AUTHOR_AGREEMENT_TEXT: data.text,
        TXN_AUTHOR_AGREEMENT_VERSION: data.version,
        TXN_AUTHOR_AGREEMENT_DIGEST: StaticTAAHelper.taa_digest(data.text, data.version),
        TXN_AUTHOR_AGREEMENT_RATIFICATION_TS: data.txn_time
    }, data.seq_no, data.txn_time


def expected_aml_data(data: TaaAmlData):
    return {
               AML_VERSION: data.version,
               AML: data.aml,
               AML_CONTEXT: data.amlContext
           }, data.seq_no, data.txn_time


def gen_random_txn_author_agreement(text_size=1024, version_size=16):
    return randomString(text_size), randomString(version_size)


def calc_taa_digest(text: str, version: str) -> str:
    return WriteRequestManager._taa_digest(text, version)


def vdr_send_txn_author_agreement(looper, pool_handle, vdr_wallet, version: str,
                                 text: str, ratified: int, retired: Optional[int] = None) -> Tuple[Dict[str, Any], Any]:
    """Send a transaction author agreement using VDR"""
    # Convert None to 0 for retirement timestamp if not provided
    retirement_ts = retired if retired is not None else 0
    req = looper.loop.run_until_complete(build_txn_author_agreement_request(
        vdr_wallet[1], text, version, ratified, retirement_ts))
    return vdr_sign_and_submit_req(looper, pool_handle, vdr_wallet, req)


def vdr_send_txn_author_agreement_disable(looper, pool_handle, vdr_wallet) -> Tuple[Dict[str, Any], Any]:
    """Disable all transaction author agreements using VDR"""
    req = looper.loop.run_until_complete(build_disable_all_txn_author_agreements_request(vdr_wallet[1]))
    return vdr_sign_and_submit_req(looper, pool_handle, vdr_wallet, req)


def vdr_send_txn_author_agreement_with_retirement(
        looper, pool_handle, vdr_wallet, text: str, version: str, ratified: int, retired: Optional[int]
) -> Tuple[Dict[str, Any], Any]:
    """Send a transaction author agreement with retirement using VDR"""
    reply = vdr_send_txn_author_agreement(looper, pool_handle, vdr_wallet, version, text,
                                         ratified, retired)
    return reply


def vdr_get_txn_author_agreement_aml(
        looper, pool_handle, vdr_wallet,
        version: Optional[str] = None,
        timestamp: Optional[int] = None,
        write_reply: bool = False
) -> Tuple[Dict[str, Any], Any]:
    """Get transaction author agreement AML using VDR"""
    return get_txn_author_agreement(
        looper, pool_handle, vdr_wallet,
        version=version,
        timestamp=timestamp
    )