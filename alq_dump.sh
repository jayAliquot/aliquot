#!/usr/bin/env bash

now=$(date +%H%M_%m%d%Y)
filename=db_dump_${now}.sql
pg_dump -Z gzip aliquot > $filename
