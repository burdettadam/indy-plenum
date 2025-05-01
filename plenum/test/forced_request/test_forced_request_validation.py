import json

import pytest
from plenum.common.exceptions import RequestNackedException

from plenum.test.helper import vdr_get_and_check_replies

from plenum.common.util import randomString
from plenum.common.constants import FORCE

from plenum.test.pool_transactions.helper import vdr_sign_and_send_prepared_request, vdr_prepare_nym_request, \
    vdr_add_new_nym


def test_forced_request_validation(looper, txnPoolNodeSet, wallet_client,
                                   pool_handle, wallet_steward):
    nym_request, new_did = looper.loop.run_until_complete(
        vdr_prepare_nym_request(wallet_client, randomString(32),
                            None, None))

    request_json = json.loads(nym_request)
    request_json['operation'][FORCE] = True
    node_request = json.dumps(request_json)

    request_couple = vdr_sign_and_send_prepared_request(looper,
                                                        wallet_client,
                                                        pool_handle,
                                                        node_request)

    with pytest.raises(RequestNackedException):
        vdr_get_and_check_replies(looper, [request_couple])

    vdr_add_new_nym(looper, pool_handle, wallet_steward)
