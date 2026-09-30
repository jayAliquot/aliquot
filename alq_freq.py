#!/usr/bin/env python

""" Finds the frequency of factors

    Primes less than 20. Each driver done separately
"""

import argparse
import logging
from pathlib import Path
from datetime import datetime
import aliquot_util

logger = logging.getLogger(__name__)

class PrimeFreq:
    def __init__(self):
        self.max_prime = 20

    def get_lines(self, file_name, is_elf):
        with open(file_name, 'r', encoding='ascii') as file:
            lines = file.readlines()
            if not is_elf:
                del lines[-1]
            return lines

    def add_prime(self, factors, prime, power):
        if power == '1':
            factor_string = prime
        else:
            factor_string = f'{prime}^{power}'
        if factor_string in factors:
            factors[factor_string] += 1
        else:
            factors[factor_string] = 1

    def calc_freq(self):
        parser = argparse.ArgumentParser(description =__doc__)
        parser.add_argument('min', type=int, help='Minimum value of the range')
        parser.add_argument('max', type=int, help='Maximum value of the range')

        argv = parser.parse_args()
        max_seq = argv.max
        min_seq = argv.min
        if min_seq == 0:
            min_seq = 1
        now = datetime.now()
        time_string=now.strftime('%H%M_%m%d%Y')
        freq_file_name = f'freq_{time_string}.txt'
        freq_data = {}
        for driver_string in ['0','1','2','3','4','5','6','7','8','9','A']:
            freq_data[driver_string] = {}
            freq_data[driver_string]['total'] = 0
            freq_data[driver_string]['factors'] = {}

        with open(freq_file_name, 'w', encoding='ascii') as freq_file:
            count = 0
            for seq in range(min_seq, max_seq+1):
                subd = seq // 1000000
                elf_name = f'elf_{subd}/alq_{seq}.elf'
                elg_name = f'elg_{subd}/alq_{seq}.elg'
                lines = []
                if Path(elf_name).is_file():
                    lines = self.get_lines(elf_name, True)
                elif Path(elg_name).is_file():
                    lines = self.get_lines(elg_name, False)
                if len(lines) == 0:
                    continue
                for line in lines:
                    data = aliquot_util.parse_elf_line(line.strip())
                    if not data:
                        print(f'For {seq}, invalid line in elf/elg file')
                        continue
                    if data['complete']:
                        num = data['num']
                        driver_data = aliquot_util.calc_driver(num)
                        driver = driver_data['driver']
                        factors = aliquot_util.to_factors(data['factor_string'])
                        freq_data[driver]['total'] += 1
                        for factor in factors:
                            if int(factor) <= self.max_prime:
                                self.add_prime(freq_data[driver]['factors'], factor,
                                               factors[factor])
            for driver, driver_info in freq_data.items():
                total = driver_info['total']
                total_str = f'Total for driver {driver}: {total}'
                print('')
                print(total_str)
                freq_file.write(f'\n{total_str}\n')
                for factor, count in driver_info['factors'].items:
                    percent = count * 100 / total
                    factor_str = f'Factor {factor}: {count} ({percent}%)'
                    print(factor_str)
                    freq_file.write(f'{factor_str}\n')
                freq_file.flush()

if __name__ == "__main__":
    logging.basicConfig(filename='alq_freq.log', level=logging.INFO)
    logger.info('Started')
    freq = PrimeFreq()
    freq.calc_freq()
    logger.info('finished')
