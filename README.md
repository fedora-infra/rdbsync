# rdbsync
A script to sync CentOS CI ResultsDB to Fedora

## Usage

```
$ pip install git+https://github.com/jeremycline/rdbsync
$ rdbsync --help
```

To test this, you can set up your own [ResultsDB](https://pagure.io/taskotron/resultsdb)
to sync to. Once it's set up, you can sync to it with a command like:

```
rdbsync --centos-url http://resultsdb.ci.centos.org/resultsdb_api/api --fedora-url http://localhost:5000/api
```

This script can be run using cron or systemd timers, or as a systemd service by using the --poll-interval
argument.
