#!/bin/bash
set -e
rm log.log
timeout 15s pipenv run python main.py mario.nes > log.log 2>&1
