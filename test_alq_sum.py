#!/usr/bin/env python

""" Unit test for the Aliquot_sum class this class uses numpy to factor up to 10^25.

    test_alq_sum.out must exist to compare to.
    The values can also be compared to elf_0/alq_276.elf
"""

import sys
import logging
from aliquot_sum import AliquotSum

logger = logging.getLogger(__name__)

aliquot_sum = AliquotSum()

def test_aliquot_sum():
    """Test for aliquot_sum.py, code to factor smaller values."""

    num = 276
    done = False

    with open('test_alq_sum.out', 'r', encoding='ascii') as elf_file:
        lines = elf_file.readlines()
        count = 0
        check = True
        while not done:
            seq_entry = aliquot_sum.calc_aliquot_sum(num)
            entry_str = str(seq_entry).strip()
            line = lines[count].strip()
            count += 1
            if line != entry_str:
                print(f'{line} vs {entry_str}')
                check = False
            if not seq_entry['complete']:
                done = True
            else:
                num = seq_entry['aliquot_sum']
        if not check:
            print('Issue Found')
            sys.exit(1)
        print('Check Passed')

if __name__ == "__main__":
    logging.basicConfig(filename='test_alq_sum.log', level=logging.INFO)
    logger.info('Started')
    test_aliquot_sum()
    logger.info('finished')
