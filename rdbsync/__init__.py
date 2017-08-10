#!/usr/bin/env python
"""
A sync script that moves ResultsDB results from CentOS CI to Fedora's ResultsDB.

It is intended to be run with cron.
"""

import os
import logging
import sys
import time

import click
import requests


_log = logging.getLogger(__name__)


CENTOS_URL_DEFAULT = 'https://resultsdb.ci.centos.org/resultsdb_api/api'
CENTOS_URL_HELP = 'The URL to the CentOS CI ResultsDB API. Default: {}'.format(CENTOS_URL_DEFAULT)
FEDORA_URL_DEFAULT = 'https://taskotron.fedoraproject.org/resultsdb_api/api'
FEDORA_URL_HELP = 'The URL to the Fedora ResultsDB API. Default: {}'.format(FEDORA_URL_DEFAULT)
POLL_INTERVAL_HELP = ('If provided, the command will run continuously, sleeping for the'
                      ' provided number of seconds after each run.')
LOG_LEVEL_HELP = 'The log level to use. Options are DEBUG, INFO, WARNING, ERROR, CRITICAL.'


@click.group()
def cli():
    pass


@cli.command()
@click.option('--centos-url', default=CENTOS_URL_DEFAULT, help=CENTOS_URL_HELP)
@click.option('--fedora-url', default=FEDORA_URL_DEFAULT, help=FEDORA_URL_HELP)
@click.option('--timeout', default=15,
              help='The timeout for HTTP requests in seconds. Default: 15')
@click.option('--log-level', default='INFO', type=str, help=LOG_LEVEL_HELP)
def verify(centos_url, fedora_url, timeout, log_level):

    logging.basicConfig(
        level=log_level, format='[%(asctime)s][%(name)s %(levelname)s] %(message)s')

    centos_resultsdb = ResultsDb(api_url=centos_url)
    fedora_resultsdb = ResultsDb(api_url=fedora_url)

    fedora_results = fedora_resultsdb.get_results(
        centos_ci_resultsdb=True, _sort='asc:submit_time', limit=50)

    verified_count = 0

    for fedora_result in fedora_results:
        fedora_result['data'].pop('centos_ci_resultsdb')
        centos_id = fedora_result['data'].pop('centos_ci_resultsdb_id')
        if isinstance(centos_id, list):
            # For some reason the API wraps this in a list
            centos_id = centos_id[0]
        centos_submit_time = fedora_result['data'].pop('centos_ci_resultsdb_submit_time')
        if isinstance(centos_submit_time, list):
            # For some reason the API wraps this in a list
            centos_submit_time = centos_submit_time[0]
        centos_result = centos_resultsdb.get_result(centos_id)

        if centos_result['submit_time'] != centos_submit_time:
            _log.error('CentOS CI submit_time (%s) does not match Fedora centos_submit_time (%s)',
                       centos_result['data'], fedora_result['data'])
            sys.exit(1)

        if centos_result['data'] != fedora_result['data']:
            _log.error('CentOS CI data (%r) does not match Fedora data (%r)',
                       centos_result['data'], fedora_result['data'])
            sys.exit(1)

        _log.info('CentOS Result ID %s matches Fedora Result ID %s',
                  centos_result['id'], fedora_result['id'])
        verified_count += 1

    _log.info('Verified %s results in the Fedora ResultsDB', verified_count)

    # Report when the latest results are from in both databases.
    fedora_results = fedora_resultsdb.get_results(
        centos_ci_resultsdb=True, _sort='desc:submit_time', limit=1)
    try:
        last_fedora_result = next(fedora_results)
        _log.info('The last result from CentOS CI in Fedora ResultsDB is from %s',
                  last_fedora_result['data']['centos_ci_resultsdb_submit_time'])
    except StopIteration:
        _log.info('There are no results in the Fedora ResultsDB from CentOS CI.')

    centos_results = centos_resultsdb.get_results(_sort='desc:submit_time', limit=1)
    try:
        last_centos_result = next(centos_results)
        _log.info('The latest result from CentOS CI ResultsDB is from %s',
                  last_centos_result['submit_time'])
    except StopIteration:
        _log.info('There are no results in the CentOS CI ResultsDB.')


@cli.command()
@click.option('--centos-url', default=CENTOS_URL_DEFAULT, help=CENTOS_URL_HELP)
@click.option('--fedora-url', default=FEDORA_URL_DEFAULT, help=FEDORA_URL_HELP)
@click.option('--token-file', default=None, help='The path to a file containing an API token')
@click.option('--timeout', default=15,
              help='The timeout for HTTP requests in seconds. Default: 15')
@click.option('--poll-interval', default=None, type=int, help=POLL_INTERVAL_HELP)
@click.option('--log-level', default='INFO', type=str, help=LOG_LEVEL_HELP)
def run(centos_url, fedora_url, token_file, timeout, poll_interval, log_level):
    """Synchronize the CentOS CI ResultsDB to the Fedora ResultsDB."""

    logging.basicConfig(
        level=log_level, format='[%(asctime)s][%(name)s %(levelname)s] %(message)s')

    token = None
    if token_file and os.path.exists(token_file):
        with open(token_file, 'r') as fd:
            token = fd.read()

    centos_resultsdb = ResultsDb(api_url=centos_url, auth_token=token)
    fedora_resultsdb = ResultsDb(api_url=fedora_url, auth_token=token)

    while True:
        # Find out where to start from using the dest db
        _log.info('Attempting to discover the last sync time')
        results = fedora_resultsdb.get_results(
            centos_ci_resultsdb=True, _sort='desc:submit_time', limit=1)
        last_result = None
        try:
            last_result = next(results)
            since = last_result['data']['centos_ci_resultsdb_submit_time']
            if isinstance(since, list):
                since = since[0]
            _log.info('Querying {url} for all results since {since}'.format(
                  url=centos_url, since=since))
        except StopIteration:
            # There are no CentOS CI results, so we must start from the dawn of time
            since = None
            _log.info('This appears to be the first sync. Querying {url} for all results'
                      ' since the dawn of time'.format(url=centos_url))

        centos_results = centos_resultsdb.get_results(
            _sort='asc:submit_time', since=since, limit=50)
        for result in centos_results:
            if list(fedora_resultsdb.get_results(centos_ci_resultsdb_id=result['id'])):
                # Ensure we don't insert duplicates. This is pretty expensive as it's one query
                # per potentially new result, but it does ensure we don't duplicate results.
                _log.debug('Skipping result %s from CentOS CI as it appears to be in '
                           'Fedora ResultsDB.', result['id'])
                continue
            fedora_resultsdb.create_result(result)

        _log.info('Sync complete!')

        if poll_interval is None:
            break
        else:
            _log.info('Sleeping for %s seconds before the next sync', poll_interval)
            time.sleep(poll_interval)


class ResultsDb(object):
    """
    Represents a `ResultsDB <http://docs.resultsdb20.apiary.io/>`_ instance.

    Args:
        api_url (str): The URL to the ResultsDB API. For example,
            https://taskotron-dev.fedoraproject.org/resultsdb_api/api.
        auth_token (str): The authentication token to use when creating results.
        session (requests.Session): A pre-existing requests session to use rather
            than creating a new one.
    """

    def __init__(self, api_url=None, auth_token=None, session=None):
        self.api_url = api_url
        self.auth_token = auth_token
        self.session = requests.Session() if session is None else session

    def get_result(self, id, timeout=15):
        """
        Get a single Result.

        Args:
            id (int): The Result ID.
            timeout (int): The timeout for the HTTP request.

        Returns:
            dict: A Result dictionary in the format described in the ResultsDB API.
        """
        url = '{base}/v2.0/results/{id}'.format(base=self.api_url, id=id)
        response = self.session.get(url, timeout=timeout)
        response.raise_for_status()

        return response.json()

    def get_results(self, timeout=15, **parameters):
        """
        Query ResultsDB for multiple results.

        This automatically handles pagination.

        Args:
            timeout (int): The timeout for the HTTP request.
            **parameters: Query parameters to use. Consult the `API documentation
                <http://docs.resultsdb20.apiary.io/#reference/0/results/>`_ for valid
                parameters.

        Yields:
            dict: A Result dictionary in the format described in the ResultsDB API.
        """
        url = '{base}/v2.0/results'.format(base=self.api_url)

        while url:
            response = self.session.get(url, params=parameters, timeout=timeout)
            response.raise_for_status()

            deserialized_response = response.json()
            for result in deserialized_response['data']:
                yield result
            url = deserialized_response['next']

    def create_result(self, result, timeout=15):
        """
        Create a new Result in ResultsDB.

        Args:
            result (dict): The Result to create. This should have originated from a different
                ResultsDB and is expected to already have an 'id' and 'submit_time'.
            timeout (int): The timeout for the HTTP request.
        """

        if self.auth_token is not None:
            result['_auth_token'] = self.auth_token

        # A nice bool to query on.
        result['data']['centos_ci_resultsdb'] = True
        # Map this result to the original result in CentOS CI.
        result['data']['centos_ci_resultsdb_id'] = result.pop('id')
        # Note the submission time so we can query on this later to catch up.
        result['data']['centos_ci_resultsdb_submit_time'] = result.pop('submit_time')

        url = '{base}/v2.0/results'.format(base=self.api_url)
        response = self.session.post(url, json=result, timeout=timeout)
        response.raise_for_status()


if __name__ == '__main__':
    cli()
