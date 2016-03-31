"""
This module deals with Treeherder's job-actions exchanges.

- exchange/treeherder/v1/job-actions on buildbot.#.#.
- exchange/treeherder-stage/v1/job-actions on buildbot.#.#.
Exchange documentation:
 https://wiki.mozilla.org/Auto-tools/Projects/Pulse/Exchanges#Treeherder:_Job_Actions
"""
import logging

from pulse_actions.publisher import MessageHandler
from pulse_actions.utils.misc import (
    filter_invalid_builders,
    get_maxRevisions
    TREEHERDER
)

from mozci import query_jobs
from mozci.mozci import manual_backfill
from mozci.sources import buildjson
from thclient import TreeherderClient

LOG = logging.getLogger(__name__)


def on_buildbot_prod_event(data, message, dry_run):
    """Act upon events on the production exchange"""
    return on_buildbot_event(data, message, dry_run, stage=False)


def on_buildbot_stage_event(data, message, dry_run):
    """Act upon events on the stage exchange"""
    return on_buildbot_event(data, message, dry_run, stage=True)


def on_buildbot_event(data, message, dry_run, stage=False):
    """Act upon buildbot events."""
    # Cleaning mozci caches
    buildjson.BUILDS_CACHE = {}
    query_jobs.JOBS_CACHE = {}

    if stage:
        treeherder_client = TreeherderClient(host='treeherder.allizom.org')
    else:
        treeherder_client = TreeherderClient()

    action = data['action']
    job_id = data['job_id']
    repo_name = data['project']
    requester = data['requester']

    result = treeherder_client.get_jobs(repo_name, id=job_id)
    # If result not found, ignore
    if not result:
        LOG.info("We could not find any result for repo_name: %s and "
                 "job_id: %s" % (repo_name, job_id))
        message.ack()
        return

    result = result[0]
    resultset_id = result["result_set_id"]
    result_sets = treeherder_client.get_resultsets(repo_name, id=resultset_id)
    revision = result_sets[0]["revision"]

    treeherder_link = TREEHERDER % {'repo': repo_name, 'revision': resultset['revision']}

    LOG.info("%s action requested by %s on repo_name %s for %s" % (
        action,
        data["requester"],
        data["project"],
        data["job_id"]
    )
    )

    buildername = result["ref_data_name"]
    status = None

    buildername = filter_invalid_builders(buildername)

    # Treeherder can send us invalid builder names
    # https://bugzilla.mozilla.org/show_bug.cgi?id=1242038
    if buildername is None:
        status = 'Builder %s was invalid.' % buildername[0]

    # Backfill action
    elif action == "backfill":
        manual_backfill(
            revision,
            buildername,
            max_revisions=get_maxRevisions(buildername),
            dry_run=dry_run
        )
        if not dry_run:
            status = 'Backfill request sent'
        else:
            status = 'Dry-run mode, nothing was backfilled'

    # Send a pulse message showing what we did
    message_sender = MessageHandler()
    pulse_message = {
        'job_id': job_id,
        'action': action,
        'requester': data['requester'],
        'status': status}
    routing_key = '{}.{}'.format(repo_name, action)
    try:
        message_sender.publish_message(pulse_message, routing_key)
    except:
        LOG.warning("Failed to publish message over pulse stream.")

    if not dry_run:
        # We need to ack the message to remove it from our queue
        message.ack()
