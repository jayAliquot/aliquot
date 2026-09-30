#!/usr/bin/env python

""" Finds chances of ecm being successful when run at a higher level.

For a large collection of numbers from series, we remove factors less that a given value to
give a cofactor.  For that size cofactor we add whether we find a larger cofactor 5 or 10
digits above the value.
"""

import logging
import argparse

import aliquot_util

logger = logging.getLogger(__name__)

def calc_ecm_ratios(min_seq:int, max_seq:int) -> None:
    """Calc ecm ratios from existing series
    
    Args:
        sql_connection: postgres sql connection.
        min_seq: Minimum sequence to verify.
        max_seq: Maximum sequence to verify.
    """

    logger.info('Verify range %s to %s', min_seq, max_seq)

    count = 0
    ratios = {}
    tables = {5, 10}
    digits = list(range(50, 220, 5))
    ecm_levels = list(range(10, 70, 5))
    for table in tables:
        ratios[table] = {}
        for digit in digits:
            ratios[table][digit] = {}
            for level in ecm_levels:
                ratios[table][digit][level] = {
                    'has_factor': 0,
                    'total': 0
                }
    for seq in range(min_seq, max_seq+1):
        if seq % 10000 == 0:
            print(f'{seq}: {count} lines')
        subd = seq // aliquot_util.INTERVAL

        for extension in ['elf', 'elg']:
            file_name = f'elf_{subd}/alq_{seq}.{extension}'
            lines = aliquot_util.get_lines(file_name)
            if lines:
                lines = lines[:-1]
                for line in lines:
                    count += 1
                    add_ecm_ratios(line, ratios, tables, ecm_levels)
    for table in [5, 10]:
        file_name = f'ECM_plus_{table}.txt'
        file_name_percent = f'ECM_plus_{table}_percent.txt'
        with open(file_name, 'w', encoding='ascii') as file:
            with open(file_name_percent, 'w', encoding='ascii') as file2:            
                title_line1 = ' digits'
                title_line2 = title_line1
                for level in ecm_levels:
                    ecm_title1 = f'ecm{level}=>{level+table}'.center(17)
                    ecm_title2 = f'ecm{level}=>{level+table}'.center(9)
                    title_line1 += f', {ecm_title1}'
                    title_line2 += f', {ecm_title2}'                    
                file.write(f'{title_line1}\n')
                file2.write(f'{title_line2}\n')                
                for digit in digits:
                    row1 = f'{digit}-{digit+4}'.center(7)
                    row2 = row1
                    for level in ecm_levels:
                        if ratios[table][digit][level]['total'] == 0:
                            pair_string = '-/-'.center(17)
                            percent_string = '-.-%'.center(9)
                        else:
                            factor_count = get_num_string(ratios[table][digit][level]['has_factor'])
                            total =  get_num_string(ratios[table][digit][level]['total'])
                            pair_string = f'{factor_count}/{total}'.center(17)
                            milent = (ratios[table][digit][level]['has_factor'] * 1000
                                      // ratios[table][digit][level]['total'])
                            percent = milent // 10
                            rem = milent - 10*percent
                            percent_string = f'{percent}.{rem}%'.center(9)
                        row1 += f', {pair_string}'
                        row2 += f', {percent_string}'
                    file.write(f'{row1}\n')
                    file2.write(f'{row2}\n')                    

def get_num_string(num):
    num_str = '-'
    if num < 1000000:
        num_str = f'{num:,}'
    else:
        num_M = num // 1000000
        num_k = num - num_M // 1000
        num_str = f'{num_M}.{num_k}M'
    return num_str

def add_ecm_ratios(line, ratios, tables, ecm_levels):
    data = aliquot_util.parse_elf_line(line)
    factors = aliquot_util.to_factors(data['factor_string'])
    for table in tables:
        for level in ecm_levels:
            # Keep factors with more than level digits
            larger_factors = aliquot_util.get_larger_factors(factors, level + 1)
            if sum(larger_factors.values()) >= 2:
                factor_digits = len(str(aliquot_util.find_divisor(larger_factors)))
                digit = (factor_digits // 5) * 5
                if 50 <= digit <= 215:
                    ratios[table][digit][level]['total'] += 1
                    ecm_found_factors = aliquot_util.get_smaller_factors(larger_factors,
                                                                         level + table)
                    if len(ecm_found_factors) > 0:
                        ratios[table][digit][level]['has_factor'] += 1

if __name__ == "__main__":
    logging.basicConfig(filename='alq_report_broken.log', level=logging.INFO)
    logger.info('Started')

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('min', type=int, help='Minimum value of the range')
    parser.add_argument('max', type=int, help='Maximum value of the range')
    argv = parser.parse_args()

    calc_ecm_ratios(argv.min, argv.max)

    logger.info('finished')
