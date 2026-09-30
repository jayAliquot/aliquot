#!/usr/bin/env bash

for filename in $1/*.elf; do
	base=$(basename $filename .elf)
    seq=$(echo $base | cut -d _ -f 2)
    echo $seq
    cp $filename aliqueit
    cd aliqueit
    ./aliqueit.exe -d 52 -c 40 -b $seq
    cd ..
    diff $filename aliqueit/${base}.elf
done
