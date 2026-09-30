#!/usr/bin/env bash

for ((iq=0;iq<=30;iq++)); do
    wc elg_$iq/*.elg
done
