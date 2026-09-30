#!/usr/bin/env bash

for ((iq=0;iq<=30;iq++)); do
    tail -n 2 elg_$iq/*.elg
done
