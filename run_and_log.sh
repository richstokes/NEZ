#!/bin/bash
set -e
rm log.log || true
timeout 60s pipenv run python main.py mario.nes > log.log 2>&1
