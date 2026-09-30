#!/bin/bash

for file in fix_*$1.sh; do
    if [ -s "$file" ]; then
        echo "./$file"
        "./$file"
    fi
done
