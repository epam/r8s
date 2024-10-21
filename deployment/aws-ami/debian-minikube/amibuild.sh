#!/bin/bash

sudo chmod +x /usr/local/bin/r8s-run.sh

sudo systemctl daemon-reload
sudo systemctl enable r8s-run.service
