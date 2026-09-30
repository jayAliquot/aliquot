
""" Types for aliquot project

For the more complex types returned by public functions, so appear in more than one class.
"""

from typing import TypedDict, NotRequired

class ParseFileResult(TypedDict):
    """Parse elf/elg file return

    Includes merges, errors, open series final factors, and missing final open error.
    """
    merge: bool
    index: int
    final_num: int
    elf_error: bool
    insert: bool
    open: bool
    missing_open: bool
    merge_info: list

class AlqData(TypedDict):
    """Type for returning data from local database"""
    num: int
    base: int
    index: int
    aliquot_sum: int
    factor_string: str
    complete: bool
    unfactor: NotRequired[int]

class StatsData(TypedDict):
    """Type for returning stats data from the local database"""
    num: int
    base: int
    index: int
    stats_string: str
    complete: bool
    max_digits: int
