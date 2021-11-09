#!/usr/bin/env python

import argparse
import xml.etree.ElementTree as ET
from collections import defaultdict
import json
import os
import errno

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

def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc: # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else: raise

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
    generate_svg(level_name, level_dict)

def process_chunk(chunk_root):
    chunk_dict = defaultdict(list)
    for entry in chunk_root:
        chunk_dict[entry.tag].append(entry.attrib)
        if int(chunk_dict[entry.tag][-1]['index']) != len(chunk_dict[entry.tag])-1:
            print (chunk_dict[entry.tag])
    return chunk_dict

def generate_svg(level_name, level_dict):
    out_path = os.path.join(args.output_directory, '{}.svg'.format(level_name))
    level_svg = ''
    min_x = 0
    min_y = 0
    max_x = 0
    max_y = 0
    for point in level_dict['EPNT']['endpoint']:
        level_svg += '<circle cx="{}" cy="{}" id="endpoint-{}" class="endpoint"/>\n'.format(point['x'], point['y'], point['index'])
        min_x = min(min_x, float(point['x']))
        min_y = min(min_y, float(point['y']))
        max_x = max(max_x, float(point['x']))
        max_y = max(max_y, float(point['y']))
    level_svg = '<svg height="{}" width="{}">\n'.format(max_x, max_y) + level_svg
    level_svg += '</svg>'
    write_data(os.path.join(args.output_directory, '{}.json'.format(level_name)), json.dumps(level_dict, indent=2))
    write_data(out_path, level_svg)
    pass

def write_data(path, data):
    mkdir_p(os.path.dirname(path))
    with open(path, 'w') as f:
        f.write(data)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Convert maps to SVG')
    parser.add_argument('-d', '--dir',  dest='output_directory', help='specify the output directory')
    parser.add_argument('map_xml', metavar='map.xml', type=str, nargs='+', help='a map XML file')
    args = parser.parse_args()

    for map_xml_path in args.map_xml:
        process_map_file(map_xml_path)
