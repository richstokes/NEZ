#!/bin/bash
set -e
rm log.log || true
pipenv run python setup.py build_ext --inplace 2>&1 | tail -1
timeout 60s pipenv run python main.py mario.nes > log.log 2>&1
