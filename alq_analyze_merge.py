#!/usr/bin/env python

""" Attempt to understand merges to identify sequences that may self merge.

    Uses elg file endings to specify what is merged to.
"""

import argparse
import logging
from pathlib import Path
from operator import itemgetter
from sql import SQL
import aliquot_util
from aliquot_misc import AliquotMisc

logger = logging.getLogger(__name__)

class AnalyzeMerge:
    def __init__(self, sql):
        self.aliquot_misc = AliquotMisc(sql)

    def get_lines(self, file_name):
        with open(file_name, 'r', encoding='ascii') as file:
            line_count = 0
            for _ in file:
                line_count += 1
        return line_count

    def _get_spec_suffix(self, seq: int) -> str:
        """Helper to generate the format suffix for a given sequence boundary."""
        subd = seq // aliquot_util.INTERVAL
        diff = seq - subd * aliquot_util.INTERVAL
        return f'_{subd}M' if diff == 0 else f'_{subd}M_{diff}'

    def _write_analysis_report(self, anal_file, merge_stats: dict):
        """Output report to file

        Args:
            anal_file: The analysis file to write to.
            merge_stats: data to output
        """

        m_up = merge_stats['merge_up_count']
        m_down = merge_stats['merge_down_count']
        total_merges = m_up + m_down

        up_pct = (m_up * 100 / total_merges) if total_merges > 0 else 0
        down_pct = (m_down * 100 / total_merges) if total_merges > 0 else 0

        anal_file.write(f"Terminations: {merge_stats['terminations']}\n")
        anal_file.write(f"To merging seq: {merge_stats['merge_count']}\n")
        anal_file.write(f"To open seq: {merge_stats['open_count']}\n")
        anal_file.write(f"Merge is increasing: {m_up} ({up_pct:5.2f}%)\n")
        anal_file.write(f"Merge is decreasing: {m_down} ({down_pct:5.2f}%)\n")

        # Mapping sections to their respective keys, sort strategies, and labels
        sections = [
            ('\nSequences merged to:\n', 'merge_to',
             lambda k: sorted(k.items(), key=itemgetter(1), reverse=True), ':'),
            ('\nOpen sequence merges:\n', 'open',
             lambda k: sorted(k.items(), key=itemgetter(1)), ':'),
            ('\nMerging sequence merges:\n', 'merge',
             lambda k: sorted(k.items(), key=itemgetter(1)), ':'),
            ('\nValues when merging upward:\n', 'merge_step_up',
             lambda k: sorted(k.items()), '->'),
            ('\nValues when merging down:\n', 'merge_step_down',
             lambda k: sorted(k.items()), '->'),
            ('\nFactors count when merging:\n', 'factors',
             lambda k: sorted(k.items(), key=itemgetter(1), reverse=True), ':'),
            ('\nFactors less than 75%:\n', 'factors_75',
             lambda k: sorted(k.items(), key=itemgetter(1), reverse=True), ':'),
            ('\nFactors less than 100%:\n', 'factors_100',
             lambda k: sorted(k.items(), key=itemgetter(1), reverse=True), ':'),
            ('\nFactors less than 200%:\n', 'factors_200',
             lambda k: sorted(k.items(), key=itemgetter(1), reverse=True), ':'),
            ('\nFactors more than 200%:\n', 'factors_plus',
             lambda k: sorted(k.items(), key=itemgetter(1), reverse=True), ':')
        ]

        for title, key, sort_func, separator in sections:
            anal_file.write(title)
            for item in sort_func(merge_stats[key]):
                anal_file.write(f"{item[0]}{separator}{item[1]}\n")

        anal_file.flush()

    def analyze_all(self):
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument('min', type=int, help='Minimum value of the range')
        parser.add_argument('max', type=int, help='Maximum value of the range')
        argv = parser.parse_args()

        if argv.min == 0:
            spec = self._get_spec_suffix(argv.max)
        else:
            spec = f"{self._get_spec_suffix(argv.min)}{self._get_spec_suffix(argv.max)}"

        anal_file_name = f'analysis_elg{spec}.txt'

        merge_stats = {
            'terminations': 0, 'merge_count': 0, 'open_count': 0, 'merge_up_count': 0,
            'merge_down_count': 0, 'terminating': {}, 'merge_step_up': {}, 'merge_step_down': {},
            'factors': {}, 'factors_75': {}, 'factors_100': {}, 'factors_200': {},
            'factors_plus': {}, 'open': {}, 'merge': {}, 'merge_to': {}
        }

        for seq in range(argv.min, argv.max + 1):
            subd = seq // 1000000
            elg_name = f'elg_{subd}/alq_{seq}.elg'

            if Path(elg_name).is_file():
                data = self.get_pre_merge_data(elg_name)
                if data:
                    self.aliquot_misc.analyze_elg(seq, data, merge_stats)

        with open(anal_file_name, 'w+', encoding='ascii') as anal_file:
            self._write_analysis_report(anal_file, merge_stats)

        print(f'File is: {anal_file_name}')

    def get_pre_merge_data(self, elg_name):
        data = None
        with open(elg_name, 'r', encoding='ascii') as file:
            lines = file.readlines()
            if len(lines) < 2:
                print(f'Broken/short elg file: {elg_name}')
                return None
            pre_merge_line = lines[-2]
            data = aliquot_util.parse_elf_line(pre_merge_line)
        return data

if __name__ == "__main__":
    logging.basicConfig(filename='alq_analyze_merge.log', level=logging.INFO)
    logger.info('Started')
    pg = SQL()
    analyze_merge = AnalyzeMerge(pg)
    analyze_merge.analyze_all()
    logger.info('finished')
