#!/usr/bin/env bash

if [[ -z "$1" ]] || [[ "$1" == "-h" ]]; then
    echo "Usage: ./alq_wget.sh <number>"
    echo "Uses wget to get the sequence which appears as the cmp_<million>/alq_<number>.wget."
    echo "Will update cmp_<million>/*.elf and elf_<million>/*.elf if the new sequence is longer."
    exit 0
fi


seq=$(expr $1 / 1)
subd=$(expr "$1" / 1000000)
echo $seq


if [[ -z seq ]]; then
    echo Expected numeric argument for the sequence number to get.
    exit 1
fi

wget -a cmp_${subd}/elf.log -O cmp_${subd}/alq_${seq}.wget  http://factordb.com/elf.php?seq=${seq}&type=1
wait
if [ -f cmp_${subd}/alq_${seq}.wget ]; then
    newline=$(wc -l < cmp_${subd}/alq_${seq}.wget)

    if [ -f cmp_${subd}/alq_${seq}.elf ]; then
        cmpline=$(wc -l < cmp_${subd}/alq_${seq}.elf)
    else
        cmpline=0
    fi
    if [ -f elf_${subd}/alq_${seq}.elf ]; then
        elfline=$(wc -l < elf_${subd}/alq_${seq}.elf)
        has_elf=1
    else
        elfline=0
        has_elf=0
    fi

    if [[ ${newline} -gt ${cmpline} ]]; then
        echo Updating cmp file ${newline} vs ${cmpline}
        cp cmp_${subd}/alq_${seq}.wget cmp_${subd}/alq_${seq}.elf
    fi

    if [[ ${newline} -lt ${cmpline} ]]; then
        echo short wget file ${newline} vs ${cmpline}
    fi
    
    if [ "${has_elf}" == "1" ]; then
        if [[ ${newline} -gt ${elfline} ]]; then
            echo Updating elf file ${newline} vs ${elfline}
            cp cmp_${subd}/alq_${seq}.wget elf_${subd}/alq_${seq}.elf
            python3 main.py ${seq} ${seq}
            python3 alq_elg.py ${seq} ${seq}
        fi
    fi
    
else
    echo Issue with wget.  Try again.
fi    
