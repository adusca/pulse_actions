import handlers.treeherder_buildbot as treeherder_buildbot
import handlers.treeherder_resultset as treeherder_resultset
import handlers.treeherder_runnable as treeherder_runnable
import handlers.backfilling as backfilling


HANDLERS_BY_EXCHANGE = {
    "exchange/treeherder/v1/job-actions": {
        "manual_backfill": treeherder_buildbot.on_buildbot_prod_event
    },
    "exchange/treeherder-stage/v1/job-actions": {
        "manual_backfill-stage": treeherder_buildbot.on_buildbot_stage_event
    },
    "exchange/treeherder/v1/resultset-actions": {
        "resultset_actions": treeherder_resultset.on_resultset_action_prod_event
    },
    "exchange/treeherder-stage/v1/resultset-actions": {
        "resultset_actions-stage": treeherder_resultset.on_resultset_action_stage_event
    },
    "exchange/treeherder/v1/resultset-runnable-job-actions": {
        "runnable": treeherder_runnable.on_runnable_job_prod_event
    },
    "exchange/treeherder-stage/v1/resultset-runnable-job-actions": {
        "runnable-stage": treeherder_runnable.on_runnable_job_stage_event
    },
    "exchange/build/normalized": {
        "backfilling": backfilling.on_event
    }
}
