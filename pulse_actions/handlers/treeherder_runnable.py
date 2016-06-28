import logging
import os

from pulse_actions.utils.misc import whitelisted_users, filter_invalid_builders

from mozci import TaskClusterBuildbotManager, query_jobs
from mozci.mozci import trigger_job
from mozci.sources import buildjson, buildbot_bridge
from mozci.taskcluster import schedule_action_task
from thclient import TreeherderClient

LOG = logging.getLogger(__name__)
MEMORY_SAVING_MODE = True
TREEHERDER = 'https://%(host)s/#/jobs?repo=%(repo)s&revision=%(revision)s'


def on_runnable_job_event(data, message, dry_run, treeherder_host, acknowledge):
    # Cleaning mozci caches
    buildjson.BUILDS_CACHE = {}
    query_jobs.JOBS_CACHE = {}

    treeherder_client = TreeherderClient(host=treeherder_host)

    # Grabbing data received over pulse
    repo_name = data["project"]
    requester = data["requester"]
    resultset_id = data["resultset_id"]
    buildernames = data["buildernames"]
    decision_task_id = data["decisionTaskId"]

    resultset = treeherder_client.get_resultsets(repo_name, id=resultset_id)[0]
    revision = resultset["revision"]
    author = resultset["author"]

    treeherder_link = TREEHERDER % {
        'host': treeherder_host,
        'repo': repo_name,
        'revision': resultset['revision']
    }

    if not (requester.endswith('@mozilla.com') or author == requester or
            whitelisted_users(requester)):
        # We want to see this in the alerts
        LOG.error("Notice that we're letting %s schedule jobs for %s." % (requester,
                                                                          treeherder_link))
    '''
    # Everyone can press the button, but only authorized users can trigger jobs
    # TODO: remove this when proper LDAP identication is set up on TH
    if not (requester.endswith('@mozilla.com') or author == requester or
            whitelisted_users(requester)):

        if acknowledge:
            # Remove message from pulse queue
            message.ack()

        # We publish a message saying we will not trigger the job
        pulse_message = {
            'resultset_id': resultset_id,
            'requester': requester,
            'status': "Could not determine if the user is authorized, nothing was triggered."}
        routing_key = '{}.{}'.format(repo_name, 'runnable')
        try:
            message_sender.publish_message(pulse_message, routing_key)
        except:
            LOG.warning("Failed to publish message over pulse stream.")

        LOG.error("Requester %s is not allowed to trigger jobs on %s." %
                  (requester, treeherder_link))
        return  # Raising an exception adds too much noise
    '''

    LOG.info("New jobs requested by %s for %s" % (requester, treeherder_link))
    LOG.info("List of builders:")
    for b in buildernames:
        LOG.info("- %s" % b)

    # Handle TC tasks separately
    task_labels = [x for x in buildernames if x.startswith('TaskLabel==')]
    buildernames = list(set(buildernames) - set(task_labels))

    buildernames = filter_invalid_builders(buildernames)

    # Scheduling TaskCluster jobs
    try:
        credentials = {
            "clientId": os.environ("TC_CLIENT_ID"),
            "accessToken": os.environ("TC_ACCESS_TOKEN")
        }
        schedule_action_task(decision_task_id, task_labels, credentials)
    except Exception, e:
        LOG.warning(str(e))
        raise

    # Treeherder can send us invalid builder names
    # https://bugzilla.mozilla.org/show_bug.cgi?id=1242038
    if buildernames is None:
        if acknowledge:
            # We need to ack the message to remove it from our queue
            message.ack()
        return

    builders_graph, other_builders_to_schedule = buildbot_bridge.buildbot_graph_builder(
        builders=buildernames,
        revision=revision,
        complete=False  # XXX: This can be removed when BBB is in use
    )

    if builders_graph != {}:
        mgr = TaskClusterBuildbotManager(dry_run=dry_run)
        mgr.schedule_graph(
            repo_name=repo_name,
            revision=revision,
            metadata={
                'name': 'pulse_actions_graph',
                'description':
                    'Adding new jobs to push via pulse_actions/treeherder for %s.' % requester,
                'owner': requester,
                'source': treeherder_link,
            },
            builders_graph=builders_graph,
            dry_run=dry_run)
    else:
        LOG.info("We don't have anything to schedule through TaskCluster")

    if other_builders_to_schedule:
        # XXX: We should be able to replace this once all Buildbot jobs run through BBB
        # XXX: There might be a work around with
        #      https://github.com/mozilla/mozilla_ci_tools/issues/424
        LOG.info("We're going to schedule these builders via Buildapi.")
        # This is used for test jobs which need an existing Buildbot job to be scheduled
        for buildername in other_builders_to_schedule:
            trigger_job(revision, buildername, dry_run=dry_run)
    else:
        LOG.info("We don't have anything to schedule through Buildapi")

    if acknowledge:
        # We need to ack the message to remove it from our queue
        message.ack()
