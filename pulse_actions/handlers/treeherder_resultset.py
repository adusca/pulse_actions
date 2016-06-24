import logging

from mozci import query_jobs
from mozci.mozci import trigger_all_talos_jobs
from mozci.ci_manager import BuildAPIManager
from mozci.sources import buildjson
from thclient import TreeherderClient

LOG = logging.getLogger(__name__)


def on_resultset_action_event(data, message, dry_run, treeherder_host, acknowledge):
    # Cleaning mozci caches
    buildjson.BUILDS_CACHE = {}
    query_jobs.JOBS_CACHE = {}
    repo_name = data["project"]
    action = data["action"]
    times = data["times"]
    # Pulse gives us resultset_id, we need to get revision from it.
    resultset_id = data["resultset_id"]

    treeherder_client = TreeherderClient(host=treeherder_host)

    # We do not handle 'cancel_all' action right now, so skip it.
    if action == "cancel_all":
        if acknowledge:
            message.ack()
        return
    LOG.info("%s action requested by %s on repo_name %s with resultset_id: %s" % (
        data['action'],
        data["requester"],
        data["project"],
        data["resultset_id"])
    )
    revision = treeherder_client.get_resultsets(repo_name, id=resultset_id)[0]["revision"]
    status = None

    if action == "trigger_missing_jobs":
        mgr = BuildAPIManager()
        mgr.trigger_missing_jobs_for_revision(repo_name, revision, dry_run=dry_run)
        if acknowledge:
            status = 'trigger_missing_jobs request sent'
        else:
            status = 'Dry-mode, no request sent'

    elif action == "trigger_all_talos_jobs":
        trigger_all_talos_jobs(
            repo_name=repo_name,
            revision=revision,
            times=times,
            priority=-1,
            dry_run=dry_run
        )
        if acknowledge:
            status = 'trigger_all_talos_jobs: {0} times request sent with priority'\
                     'lower then normal'.format(times)
        else:
            status = 'Dry-mode, no request sent'

    LOG.debug(status)

    if acknowledge:
        # We need to ack the message to remove it from our queue
        message.ack()
