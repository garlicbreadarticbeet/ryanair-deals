#!/bin/bash
# Wrapper voor launchd/cron: draait 'watch' en logt naar data/watch.log
cd "$(dirname "$0")" || exit 1
mkdir -p data
exec .venv/bin/python deals.py watch >> data/watch.log 2>&1
