#!/usr/bin/env bash

set -x
set -e

find ../data/m{1,2,3}map/svg2/ -regextype egrep -regex '.*\.(svg|json)' -not -name '_*' -delete

./map2svg.py -d ../data/m1map/svg2 -m ../data/m1.map.xml -i ../marathon-utils/map-extras/M1_ignored_polys.txt
./map2svg.py -d ../data/m2map/svg2 -m ../data/m2.map.xml -i ../marathon-utils/map-extras/M2_ignored_polys.txt
./map2svg.py -d ../data/m3map/svg2 -m ../data/m3.map.xml -i ../marathon-utils/map-extras/M3_ignored_polys.txt
