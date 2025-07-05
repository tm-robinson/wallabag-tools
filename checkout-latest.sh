#!/bin/bash

# Fetch remote info
git fetch origin

# Get the most recently created remote branch (excluding HEAD)
latest_branch=$(git for-each-ref --sort=-creatordate --format='%(refname:short)' refs/remotes/origin/ | grep -vE '^origin/HEAD$' | head -n 1)

# Strip "origin/" prefix to get local branch name
local_branch=${latest_branch#origin/}

# Create local branch tracking the remote and check it out
git checkout -b "$local_branch" --track "$latest_branch"
