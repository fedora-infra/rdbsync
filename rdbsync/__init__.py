#!/usr/bin/env python
"""
A sync script that moves ResultsDB results from CentOS CI to Fedora's ResultsDB.

It is intended to be run with cron.
"""

import logging
import time

import click
import requests


_log = logging.getLogger('rdbsync')

# TODO add a 'full-sync' option that iterates over _all_ results in CentOS
# and checks it against Fedora. This is helpful for debugging

# TODO accept an API token via the CLI or by reading a file

CENTOS_URL_DEFAULT = 'https://resultsdb.ci.centos.org/resultsdb_api/api'
CENTOS_URL_HELP = 'The URL to the CentOS CI ResultsDB API. Default: {}'.format(CENTOS_URL_DEFAULT)
FEDORA_URL_DEFAULT = 'https://taskotron.fedoraproject.org/resultsdb_api/api'
FEDORA_URL_HELP = 'The URL to the Fedora ResultsDB API. Default: {}'.format(FEDORA_URL_DEFAULT)
POLL_INTERVAL_HELP = ('If provided, the command will run continuously, sleeping for the'
                      ' provided number of seconds after each run.')
LOG_LEVEL_HELP = 'The log level to use. Options are DEBUG, INFO, WARNING, ERROR, CRITICAL.'


@click.command()
@click.option('--centos-url', default=CENTOS_URL_DEFAULT, help=CENTOS_URL_HELP)
@click.option('--fedora-url', default=FEDORA_URL_DEFAULT, help=FEDORA_URL_HELP)
@click.option('--timeout', default=15,
              help='The timeout for HTTP requests in seconds. Default: 15')
@click.option('--poll-interval', default=None, type=int, help=POLL_INTERVAL_HELP)
@click.option('--log-level', default='INFO', type=str, help=LOG_LEVEL_HELP)
def main(centos_url, fedora_url, timeout, poll_interval, log_level):
    """Synchronize the CentOS CI ResultsDB to the Fedora ResultsDB."""

    logging.basicConfig(level=log_level)

    centos_resultsdb = ResultsDb(api_url=centos_url)
    fedora_resultsdb = ResultsDb(api_url=fedora_url)

    while True:
        # Find out where to start from using the dest db
        _log.info('Attempting to discover the last sync time')
        results = fedora_resultsdb.get_results(
                centos_ci_resultsdb=True, _sort='asc:submit_time', limit=1)
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

        centos_results = centos_resultsdb.get_results(since=since, limit=50)
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
    main()
