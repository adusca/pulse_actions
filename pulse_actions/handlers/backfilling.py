"""
This module is for the following use case:

 - Automatic backfilling:

    * If we use pulse_actions to listen to mozilla-inbound finished
      *test* jobs, we should be able to re-trigger a job a couple of
      times (similar to what trigger bot does on try) and backfill
      back to the last known good

    * Notice that trigger bot has conditions on when to stop
      re-triggering more than needed
"""
import logging

from mozci.mozci import trigger_range, trigger_job, find_backfill_revlist, \
    query_repo_url_from_buildername
from mozci.query_jobs import FAILURE, WARNING


LOG = logging.getLogger()

MAX_REVISIONS = 5


def on_event(data, message, dry_run):
    """Automatically backfill failed jobs."""
    payload = data["payload"]
    status = payload["status"]
    buildername = payload["buildername"]

    # Backfill a failed job
    if status in [FAILURE, WARNING]:
        revision = payload["revision"]
        LOG.info("**")  # visual separator
        LOG.info("Failed job found at revision %s. Buildername: %s",
                 revision, buildername)

        # We want to have 2 jobs for the current revision
        trigger_job(
            buildername=buildername,
            revision=revision,
            times=2,
            dry_run=dry_run)

        # We want to assure 1 apperance of each job on the past revisions
        repo_url = query_repo_url_from_buildername(buildername)
        revlist = find_backfill_revlist(
            repo_url=repo_url,
            revision=revision,
            max_revisions=MAX_REVISIONS,
            buildername=buildername)

        trigger_range(
            buildername=buildername,
            revisions=revlist[1:],
            times=1,
            dry_run=dry_run,
        )
    else:
        # TODO: change this to debug after a testing period
        LOG.info("'%s' with status %i. Nothing to be done.",
                 buildername, status)

    # We need to ack the message to remove it from our queue
    message.ack()
