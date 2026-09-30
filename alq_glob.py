#!/usr/bin/env python

"""Copy merge files back to elf files to recreate elg files."""

from pathlib import Path
import shutil
import argparse
import subprocess
import re
import logging

moved_seq = []

logger = logging.getLogger(__name__)

def extract_number_from_filename(filename):
    """Match digits from file name"""
    match = re.search(r'\d+', filename)

    if match:
        # Convert to integer, or keep as string (.group()) if leading zeros matter
        return int(match.group())
    return None

def copy_and_rename_files(source_dir, dest_dir):
    """Copy merge files to elf files"""

    source = Path(source_dir)
    destination = Path(dest_dir)

    # Find all files with the .merge extension in the source directory
    # Use source.rglob("*.merge") instead if you want to include subdirectories
    count = 0
    for file_path in source.glob("*.merge"):
        # Create the new filename with the .elf extension
        new_filename = file_path.with_suffix(".elf").name
        count += 1
        if count == 4:
            break
        num = extract_number_from_filename(new_filename)
        if num:
            moved_seq.append(num)

        # Define the target path in the destination directory
        target_path = destination / new_filename

        # Copy the file to the new destination
        shutil.copy(file_path, target_path)
        print(f"Copied: {file_path.name} -> {target_path}")

def main():
    """Find merge files to remake elg files"""

    parser = argparse.ArgumentParser(description =__doc__)
    parser.add_argument('min', type=int, help='min directory to move merge')
    parser.add_argument('max', type=int, help='max directory to move merge')
    argv = parser.parse_args()
    for dir_num in range(argv.min, argv.max+1):
        source_directory = f'elf_{dir_num}/merge'
        destination_directory = f'elf_{dir_num}'
        copy_and_rename_files(source_directory, destination_directory)
    for seq in moved_seq:
        seq_string = f'{seq}'
        print(f'Fixing {seq_string}')
        subprocess.run(['python3', 'alq_elg.py', seq_string, seq_string], check=True)
        subprocess.run(['python3', 'alq_verify.py', '-c', seq_string, seq_string], check=True)

if __name__ == "__main__":
    logging.basicConfig(filename='alq_glob.log', level=logging.INFO)
    logger.info('Started')
    main()
    logger.info('finished')
