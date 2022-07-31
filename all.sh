#!/usr/bin/env bash

BASE_DIR="site"

set -x
set -e

find "$BASE_DIR" -mindepth 2 -regextype egrep -regex '.*\.(svg|json)' -delete

./map2svg.py -d "$BASE_DIR"/m1 -m ../data/m1.map.xml -i ../marathon-utils/map-extras/M1_ignored_polys.txt -c map_info/chapters-m1.txt -b m1/
./map2svg.py -d "$BASE_DIR"/m2 -m ../data/m2.map.xml -i ../marathon-utils/map-extras/M2_ignored_polys.txt -c map_info/chapters-m2.txt -b m2/
./map2svg.py -d "$BASE_DIR"/m3 -m ../data/m3.map.xml -i ../marathon-utils/map-extras/M3_ignored_polys.txt -c map_info/chapters-m3.txt -b m3/

for M in 1 2 3
do
    cp m$M.json site/m$M/map.json
    ln -s ../../m${M}_overlays.json site/m$M/overlays.json
done
