#!/usr/bin/env python

""" Given a list of bak_longer extensions, find if any will help extend the elf."""

import argparse
import logging
from pathlib import Path
from sql import SQL
from aliquot_main import AliquotMain
import aliquot_util

logger = logging.getLogger(__name__)

class HandleLonger:
    """Extend elf based on bak_longer if applicable"""
    def __init__(self, sql):
        """Initialize aliquot

        Attributes:
            aliquot: For calling extend
        """
        self.aliquot_main = AliquotMain(sql)

    def _get_longer_list(self, file_name):
        """List of sequences that have bak_longer from file.

        Might switch to ls to get list later if we reuse this.
        """

        longer_list = []
        with open(file_name, 'r', encoding='ascii') as file:
            for line in file:
                trim = line.strip()
                if trim.isdigit():
                    longer_list.append(int(trim))
                else:
                    print(f'Input: {line} is not a positive integer.')
        return longer_list

    def update(self):
        """Update sequences"""
        parser = argparse.ArgumentParser(description =__doc__)
        parser.add_argument('file_name', help='File name with seq that have bak_longer extension')
        argv = parser.parse_args()
        longer_file_name = argv.file_name
        longer_list = []
        if Path(longer_file_name).is_file():
            longer_list = self._get_longer_list(longer_file_name)
        else:
            print(f'File {longer_file_name} not found')
            return
        for seq in longer_list:
            subd = seq // aliquot_util.INTERVAL
            elf_name = f'elf_{subd}/alq_{seq}.elf'
            bak_name = f'elf_{subd}/alq_{seq}.bak_longer'
            ext_name = f'elf_{subd}/alq_{seq}.ext'
            if Path(elf_name).is_file() and Path(bak_name).is_file():
                elf_lines = aliquot_util.get_line_count(elf_name)
                bak_lines = aliquot_util.get_line_count(bak_name)
                if bak_lines > elf_lines:
                    self.generate_ext(bak_name, ext_name, elf_lines)
                    self.aliquot_main.extend_elf(seq)

    def generate_ext(self, bak_name, ext_name, elf_lines):
        """Create ext file for extend elf to use."""
        index = 0
        with open(bak_name, 'r', encoding='ascii') as bak_file:
            with open(ext_name, 'w', encoding='ascii') as ext_file:
                for line in bak_file:
                    if index >= elf_lines -1:
                        ext_file.write(line)
                    index += 1

if __name__ == "__main__":
    logging.basicConfig(filename='alq_handle_longer.log', level=logging.INFO)
    logger.info('Started')
    pg = SQL()
    handle_longer = HandleLonger(pg)
    handle_longer.update()
    logger.info('finished')
