import json
from typing import List

from indy_vdr import ledger
from plenum.test.helper import vdr_get_and_check_replies, \
    vdr_send_signed_requests, vdr_sign_and_submit_req_obj, vdr_multi_sign_request_objects, vdr_json_to_request_object


def sdk_send_freeze_ledgers(looper, pool_handle, wallets, ledgers_ids: List[int]):
    req = looper.loop.run_until_complete(ledger.build_ledgers_freeze_request(wallets[0][1], ledgers_ids))
    signed_reqs = vdr_multi_sign_request_objects(looper, wallets,
                                                 [vdr_json_to_request_object(json.loads(req))])
    reps = vdr_send_signed_requests(pool_handle, signed_reqs, looper)
    return vdr_get_and_check_replies(looper, reps)[0]


# sdk_wallet needs to be DID with new function since wallet no longer tuple
def sdk_get_frozen_ledgers(looper, pool_handle, wallet):
    req = looper.loop.run_until_complete(ledger.build_get_frozen_ledgers_request(wallet[1]))
    rep = vdr_sign_and_submit_req_obj(looper, pool_handle, wallet, vdr_json_to_request_object(json.loads(req)))
    return vdr_get_and_check_replies(looper, [rep])[0]
