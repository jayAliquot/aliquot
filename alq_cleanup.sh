#!/usr/bin/env bash

for ((iq=0;iq<=50;iq++)); do
    mv elf_$iq/*.merge elf_$iq/merge
    rm elf_$iq/*.bak
    rm elf_$iq/*.log    
    ls elf_$iq | grep -v "\.elf"
    mv elg_$iq/*.merge elg_$iq/merge
    rm elg_$iq/*.bak
    rm elg_$iq/*.log    
    ls elg_$iq | grep -v "\.elg"
done
