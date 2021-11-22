#!/usr/bin/env bash

BASE_DIR="site"

set -x
set -e

find "$BASE_DIR" -mindepth 2 -regextype egrep -regex '.*\.(svg|json)' -delete

./map2svg.py -d "$BASE_DIR"/m1 -m ../data/m1.map.xml -i ../marathon-utils/map-extras/M1_ignored_polys.txt
./map2svg.py -d "$BASE_DIR"/m2 -m ../data/m2.map.xml -i ../marathon-utils/map-extras/M2_ignored_polys.txt
./map2svg.py -d "$BASE_DIR"/m3 -m ../data/m3.map.xml -i ../marathon-utils/map-extras/M3_ignored_polys.txt
