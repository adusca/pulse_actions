import logging
import os
import sys
import traceback

from argparse import ArgumentParser
from timeit import default_timer

import pulse_actions.handlers.treeherder_buildbot as treeherder_buildbot
import pulse_actions.handlers.treeherder_resultset as treeherder_resultset
import pulse_actions.handlers.treeherder_runnable as treeherder_runnable
import pulse_actions.handlers.talos as talos

from pulse_actions.utils.log_util import setup_logging

from mozci.mozci import disable_validations
from mozci.utils import transfer
from replay import create_consumer, replay_messages

# This changes the behaviour of mozci in transfer.py
transfer.MEMORY_SAVING_MODE = True
transfer.SHOW_PROGRESS_BAR = False

LOG = None


def main():
    global LOG
    options = parse_args()

    if options.debug:
        LOG = setup_logging(logging.DEBUG)
    else:
        LOG = setup_logging(logging.INFO)

    # Disable mozci's validations
    disable_validations()
    if options.replay_file:
        replay_messages(options.replay_file, route, dry_run=True)
    else:
        # Normal execution path
        run_listener(config_file=options.config_file, dry_run=options.dry_run)


def route(data, message, dry_run):
    ''' We need to map every exchange/topic to a specific handler.

    We return if the request was processed succesfully or not
    '''
    # XXX: This is not ideal; we should define in the config which exchange uses which handler
    # XXX: Specify here which treeherder host
    if 'job_id' in data:
        result = treeherder_job_event.on_event(data, message, dry_run)
    elif 'buildernames' in data:
        result = treeherder_runnable.on_runnable_job_prod_event(data, message, dry_run)
    elif 'resultset_id' in data:
        result = treeherder_resultset.on_resultset_action_event(data, message, dry_run)
    elif data['_meta']['exchange'] == 'exchange/build/normalized':
        result = talos.on_event(data, message, dry_run)
    else:
        LOG.error("Exchange not supported by router (%s)." % data)

    return result


def run_listener(config_file, dry_run=True):
    # Pulse consumer's callback passes only data and message arguments
    # to the function, we need to pass dry-run to route
    def message_handler(data, message):
        # XXX: Each request has to be logged into a unique file
        # XXX: Upload each logging file into S3
        # XXX: Report the job to Treeherder as running and then as complete
        LOG.info('#### New request ####.')
        start_time = default_timer()
        result = route(data, message, dry_run)
        if not dry_run:
            message.ack()

        elapsed_time = int(default_timer() - start_time)
        LOG.info('Message {}, took {} seconds to execute'.format(data, str(elapsed_time)))

    consumer = create_consumer(
        user=os.environ['PULSE_USER'],
        password=os.environ['PULSE_PW'],
        config_file_path=config_file,
        process_message=message_handler,
    )

    while True:
        try:
            consumer.listen()
        except KeyboardInterrupt:
            sys.exit(1)
        except:
            traceback.print_exc()


def parse_args(argv=None):
    parser = ArgumentParser()
    parser.add_argument('--config-file', dest="config_file", type=str)

    parser.add_argument('--debug', action="store_true", dest="debug",
                        help="Record debug messages.")

    parser.add_argument('--dry-run', action="store_true", dest="dry_run",
                        help="Test without actual making changes.")

    parser.add_argument('--replay-file', dest="replay_file", type=str,
                        help='You can specify a file with saved pulse_messages to process')

    options = parser.parse_args(argv)
    return options


if __name__ == '__main__':
    main()
