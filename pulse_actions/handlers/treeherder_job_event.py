"""
This module deals with Treeherder's job actions.

Exchange documentation:
 https://wiki.mozilla.org/Auto-tools/Projects/Pulse/Exchanges#Treeherder:_Job_Actions

- exchange/treeherder/v1/job-actions on buildbot.#.#.
- exchange/treeherder-stage/v1/job-actions on buildbot.#.#.
"""
import logging

from pulse_actions.utils.misc import filter_invalid_builders

from mozci import query_jobs
from mozci.mozci import manual_backfill
from mozci.sources import buildjson
from thclient import TreeherderClient

LOG = logging.getLogger(__name__)


def on_event(data, message, dry_run, treeherder_host='treeherder.mozilla.org'):
    """Act upon Treeherder job events.

    Return if the outcome was successful or not
    """
    # Pulse gives us a job_id and a job_guid, we need request_id.
    LOG.info("%s action requested by %s on repo_name %s with job_id: %s" % (
        data['action'],
        data['requester'],
        data['project'],
        data['job_id'])
    )
    # Cleaning mozci caches
    buildjson.BUILDS_CACHE = {}
    query_jobs.JOBS_CACHE = {}

    treeherder_client = TreeherderClient(host=treeherder_host)

    job_id = data['job_id']
    repo_name = data['project']

    # We want to know the status of the job we're processing
    job = treeherder_client.get_jobs(repo_name, id=job_id)

    # If result not found, ignore
    if not job:
        LOG.info("We could not find any result for repo_name: %s and "
                 "job_id: %s" % (repo_name, job_id))
        return False

    # XXX: Determine the structure of the job
    result = job[0]
    buildername = result["ref_data_name"]
    resultset_id = result["result_set_id"]
    result_sets = treeherder_client.get_resultsets(repo_name, id=resultset_id)
    revision = result_sets[0]["revision"]
    action = data['action']
    status = None

    buildername = filter_invalid_builders(buildername)

    # Treeherder can send us invalid builder names
    # https://bugzilla.mozilla.org/show_bug.cgi?id=1242038
    if buildername is None:
        status = 'Builder %s was invalid.' % buildername[0]

    # Backfill action
    elif action == "backfill":
        manual_backfill(
            revision=revision,
            buildername=buildername,
            dry_run=dry_run,
        )
        if not dry_run:
            status = 'Backfill request sent'
        else:
            status = 'Dry-run mode, nothing was backfilled'
        LOG.debug(status)

    if not dry_run:
        # We need to ack the message to remove it from our queue
        message.ack()
