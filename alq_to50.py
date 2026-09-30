#!/usr/bin/env python

""" Output is a sript to increase series to 50 digits.

"""
import logging
from sql import SQL
from alq_to60 import AliqueitScript

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logging.basicConfig(filename='alq_to50.log', level=logging.INFO)
    logger.info('Started')

    pg = SQL()

    aliqueit_script = AliqueitScript(pg, 'alq50', 50, 60)
    aliqueit_script.output_db_status()

    logger.info('finished')
