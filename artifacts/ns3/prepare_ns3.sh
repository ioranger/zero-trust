#!/bin/bash
# Prepare an ns-3 source tree that the distribution can build.
#
# The distribution ships GCC 9.4 and CMake 3.16, and ns-3 master requires
# GCC 11 and CMake 3.25. Rather than change the distribution, the driver
# installs a newer compiler from the Ubuntu toolchain PPA and a current CMake
# from PyPI, which lands in /usr/local/bin ahead of the distribution's copy.
#
#   bash prepare_ns3.sh [tag]
#
# The tag defaults to master, which is what produced the traces reported in
# the manuscript: ns-3 master at commit bd2e108, built with g++-12 and CMake
# 4.4.4. The tag is printed on the last line so the caller can record which
# simulator produced the traces. An older release such as ns-3.45 is also
# accepted, and the fetch loop below retries it, but the traces in the
# manuscript come from master.

set -uo pipefail

NS3_DIR="${NS3_DIR:-$HOME/ns3}"
TAG="${1:-master}"

cd "$NS3_DIR" || { echo "no ns-3 tree at $NS3_DIR" >&2; exit 1; }

if ! git rev-parse -q --verify "refs/tags/$TAG" >/dev/null; then
    if [ "$TAG" != "master" ] && [ "$TAG" != "main" ]; then
        echo "fetching tag $TAG"
        for attempt in 1 2 3 4 5; do
            if timeout 300 git fetch --depth 1 origin "tag" "$TAG" >/dev/null 2>&1; then
                break
            fi
            echo "  fetch attempt $attempt failed, backing off"
            sleep $((attempt * 15))
        done
    fi
fi

if [ "$TAG" = "master" ] || [ "$TAG" = "main" ]; then
    git checkout -f "origin/$TAG" >/dev/null 2>&1
    echo "checked out $TAG"
    git log --oneline -1
    echo "NS3_TAG=$TAG"
    exit 0
fi

if ! git rev-parse -q --verify "refs/tags/$TAG" >/dev/null; then
    echo "could not fetch $TAG" >&2
    exit 1
fi

git checkout -f "$TAG" >/dev/null 2>&1
echo "checked out $TAG"
git log --oneline -1
echo "NS3_TAG=$TAG"
