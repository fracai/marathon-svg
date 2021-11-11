#!/usr/bin/env bash

./map2svg.py -d ../data/m1map/svg2 -m ../data/m1.map.xml -i ../marathon-utils/map-extras/M1_ignored_polys.txt
./map2svg.py -d ../data/m2map/svg2 -m ../data/m2.map.xml -i ../marathon-utils/map-extras/M2_ignored_polys.txt
./map2svg.py -d ../data/m3map/svg2 -m ../data/m3.map.xml -i ../marathon-utils/map-extras/M3_ignored_polys.txt
