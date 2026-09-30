#!/usr/bin/env bash

for filename in $1/merge/*.merge; do
	base=$(basename -s .merge $filename)
    seq=$(echo $base | cut -d _ -f 2)
    echo $seq
done
