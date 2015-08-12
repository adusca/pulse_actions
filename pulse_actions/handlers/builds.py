import logging
from mozci.mozci import trigger_missing_jobs_for_revision, trigger_range, trigger_all_talos_jobs

logging.basicConfig(format='%(levelname)s:\t %(message)s')
LOG = logging.getLogger()
MEMORY_SAVING_MODE = True


def on_builds_finish_event(data, message, dry_run):
    # We need to ack the message to remove it from our queue
    message.ack()
    build_status = data['payload']['build']['text']
    requester = data['payload']['build']['blame']
    properties = data['payload']['build']['properties']
    dictionary = {}
    for property_list in properties:
        if property_list[0] == 'branch':
            repo_name = property_list[1]
        if property_list[0] == 'revision':
            revision = property_list[1]
        if property_list[0] == 'buildername':
            build = property_list[1]
        if property_list[0] == 'mozci_request':
            dictionary = property_list[1]

    # if 'mozci_request' is not present, ignore the build and take no action
    # or if the build has not completed successfully ignore.
    if not dictionary or 'successful' not in build_status:
        return

    if dictionary['type'] == 'trigger_missing_jobs_for_revision':
        LOG.info("Triggering missing jobs after build %s requested by %s has completed." % (build, requester))
        trigger_missing_jobs_for_revision(repo_name, revision, dry_run=dry_run)
    elif dictionary['type'] == 'manual_backfill':
        buildername = dictionary['builders'][0]
        LOG.info("Backfilling jobs after build %s requested by %s has completed." % (build, requester))
        LOG.info("Buildername to be backfilled: %s" % buildername)
        # We are calling trigger_range, since we just want to trigger the missing buildername, not backfill it.
        trigger_range(buildername, [revision], dry_run=dry_run)
    elif dictionary['type'] == 'trigger_all_talos_jobs':
        times = dictionary['times']
        LOG.info("Triggering talos jobs after build %s requested by %s has completed." % (build, requester))
        LOG.info("Number of times to trigger: %d" % times)
        trigger_all_talos_jobs(repo_name, revision, times, dry_run=dry_run)
