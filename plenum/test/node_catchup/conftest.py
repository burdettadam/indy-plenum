import pytest

from plenum.common.messages.node_messages import PrePrepare, Prepare, Commit, Checkpoint
from plenum.test.spy_helpers import getAllReturnVals
from stp_core.common.log import getlogger
from plenum.common.util import randomString
from plenum.test.conftest import getValueFromModule
from plenum.test.helper import vdr_send_random_and_check
from plenum.test.node_catchup.helper import waitNodeDataEquality, \
    check_last_3pc_master
from plenum.test.pool_transactions.helper import \
    vdr_add_new_steward_and_node, vdr_pool_refresh
from plenum.test.test_node import checkNodesConnected, getNonPrimaryReplicas


def whitelist():
    return ['got error while verifying message']


logger = getlogger()


@pytest.fixture(scope="module")
def poolAfterSomeTxns(
        looper,
        txnPoolNodeSet,
        vdr_pool_handle,
        vdr_wallet_client,
        request):
    txnCount = getValueFromModule(request, "txnCount", 5)
    vdr_send_random_and_check(looper, txnPoolNodeSet,
                              vdr_pool_handle,
                              vdr_wallet_client,
                              txnCount)
    yield looper, vdr_pool_handle, vdr_wallet_client


@pytest.fixture
def broken_node_and_others(txnPoolNodeSet):
    node = getNonPrimaryReplicas(txnPoolNodeSet, 0)[-1].node
    other = [n for n in txnPoolNodeSet if n != node]

    def brokenSendToReplica(msg, frm):
        logger.warning(
            "{} is broken. 'sendToReplica' does nothing. {} from {}".format(node.name, msg, frm))

    node.nodeMsgRouter.extend(
        (
            (PrePrepare, brokenSendToReplica),
            (Prepare, brokenSendToReplica),
            (Commit, brokenSendToReplica),
            (Checkpoint, brokenSendToReplica),
        )
    )

    return node, other
