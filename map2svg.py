#!/usr/bin/env python

import argparse
import xml.etree.ElementTree as ET
from collections import defaultdict
import json

CHUNK_TYPES = [
    'NAME', # map name
    'NOTE', # map annotations
    'EPNT', # points
    'LINS', # lines
    'POLY', # polygons
    'SIDS', # polygon sides
    'OBJS', # objects
    'plac', # monsters and items
    'plat', # platforms
    'PLAT', # platforms
]
CHUNK_TYPES_IGNORED = [
    'LITE', # lights
    'term', # terminals
    'medi', # media
    'ambi', # ambient sounds
    'bonk', # random sounds
    'iidx', # map indices
    'Minf', # map info

    # physics related
    'MNpx',
    'FXpx',
    'PRpx',
    'PXpx',
    'WPpx',
]

def process_map_file(map_xml_path):
    print (map_xml_path)
    tree = ET.parse(map_xml_path)
    root = tree.getroot()
    if 'wadfile' != root.tag:
        return
    map_type = None
    level_count = None
    for child in root:
        # <wadinfo type="0" size="3863054" count="37">Map</wadinfo>
        if 'wadinfo' == child.tag:
            map_type = child.attrib['type']
            level_count = child.attrib['count']
            continue
        if 'entry' == child.tag:
            process_level(child)
            continue

def process_level(level_root):
    level_number = level_root.attrib['index']
    name = None
    level_dict = {}
    for chunk in level_root:
        if 'name' == chunk.tag:
            name = chunk.text
        if 'chunk' != chunk.tag or 'type' not in chunk.attrib:
            continue
        chunk_type = chunk.attrib['type']
        if chunk_type in CHUNK_TYPES_IGNORED:
            continue
        if 'NAME' == chunk_type:
            name = chunk.text
        elif chunk_type in CHUNK_TYPES:
            level_dict[chunk_type] = process_chunk(chunk)
            pass
        else:
            print (chunk.attrib)
    level_name = '{:0>2} {}'.format(level_number, name)
    print (level_name)
#     with open('{}.json'.format(level_name), 'w') as f:
#         json.dump(level_dict, f)

def process_chunk(chunk_root):
    chunk_dict = defaultdict(list)
    for entry in chunk_root:
        chunk_dict[entry.tag].append(entry.attrib)
    return chunk_dict

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Convert maps to SVG')
    parser.add_argument('map_xml', metavar='map.xml', type=str, nargs='+', help='a map XML file')
    args = parser.parse_args()

    for map_xml_path in args.map_xml:
        process_map_file(map_xml_path)
