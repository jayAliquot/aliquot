#!/usr/bin/env bash

for filename in $1/*.elg; do
	base=$(basename -s .elg $filename)
    seq=$(echo $base | cut -d _ -f 2)
    echo $seq
done
