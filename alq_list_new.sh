#!/usr/bin/env bash

for ((iq=0;iq<=50;iq++)); do
    ls -lt elg_$iq/*.elg | head 50 >> latest.txt
done
