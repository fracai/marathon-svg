#!/usr/bin/env python

import argparse
import xml.etree.ElementTree as ET
from collections import defaultdict
import json
import os
import errno
import sys
import re

CHUNK_TYPES = [
    'NAME', # map name
    'POLY', # polygons
    'term', # terminals
]
CHUNK_TYPES_IGNORED = [
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

    'NOTE', # map annotations
    'EPNT', # points
    'PNTS', # points
    'LINS', # lines
    'LITE', # lights
    'SIDS', # polygon sides
    'OBJS', # objects
    'plac', # monsters and items
    'plat', # platforms
    'PLAT', # platforms
    'medi', # media
]

DOT_HEADER='''
digraph site {
overlap=false
node [shape=box]
'''
DOT_FOOTER='}'

SUBGRAPH='''subgraph cluster_{cluster} {{
label = "{label}";
{nodes};
}}'''


def generate_subgraph(cluster, label, nodes):
    print (SUBGRAPH.format(cluster=cluster, label=label, nodes=';'.join(map(str,nodes))))

def fix_encoding(text):
    return re.sub(
        b'\xc3\xa2',
        b'\xe2',
        text.encode()
    ).replace(
        b'\xc2',
        b''
    ).decode()

def process_map_file(map_xml_path, chapters_file):
    print (DOT_HEADER)
#     print ('map: {}'.format(map_xml_path))
    tree = ET.parse(map_xml_path)
    root = tree.getroot()
    if 'wadfile' != root.tag:
        return
    map_type = None
    level_count = None
    preview = ''
    map_info = {
        'levels': []
    }
    chapters_dict = {}
    if chapters_file:
        with open(chapters_file, 'r') as f:
            while True:
                line = f.readline()
                if not line:
                    break
                level_index, chapter_name = line.strip().split(' ', 1)
                chapters_dict[int(level_index)] = chapter_name
    level_dicts = list()
    for child in root:
        # <wadinfo type="0" size="3863054" count="37">Map</wadinfo>
        if 'wadinfo' == child.tag:
            map_type = int(child.attrib['type'])
            level_count = int(child.attrib['count'])
            continue
        if 'entry' != child.tag:
            continue
        level_index = int(child.attrib['index'])
        if args.levels and level_index not in args.levels:
            continue
        level_dicts.append(process_level(map_type, child))
    chapter_starts = sorted(chapters_dict.keys())
    for index,chapter in enumerate(chapter_starts):
        try:
            end = int(chapter_starts[index+1])
        except:
            end = int(level_dicts[-1]['level_number'])+1
        generate_subgraph(chapter, chapters_dict[chapter], range(int(chapter), end))
    print ('{} [label="{}"];'.format(256, "The End"))
    for level_dict in level_dicts:
        level_number = level_dict['level_number']
        level_name = '{:0>2} {}'.format(level_number, level_dict['name'])
        print ('{} [label="{}"];'.format(level_number, level_name))
        for destination in level_dict['destinations']:
            print ('{} -> {}'.format(level_number, destination))
    print (DOT_FOOTER)

def process_level(map_type, level_root):
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
            print ('unhandled chunk: {}'.format(chunk.attrib))
    for chunk_type in CHUNK_TYPES:
        if chunk_type not in level_dict:
            level_dict[chunk_type] = defaultdict(list)
    name = fix_encoding(name)
#     print ('{:0>2} {}'.format(level_number, name))
    destinations = set()
#     print (json.dumps(level_dict, indent=2))
    for terminal in level_dict['term']['terminal']:
        for grouping in terminal['children']['grouping']:
            if grouping['type'] == 6:
                destinations.add(grouping['permutation'])
    for polygon in level_dict['POLY']['polygon']:
        if polygon['type'] == 18:
            destinations.add(polygon['permutation'])
    level_dict['destinations'] = destinations
    level_dict['name'] = name
    level_dict['level_number'] = level_number
    return level_dict

def process_chunk(chunk_root):
    chunk_dict = defaultdict(list)
    for entry in chunk_root:
        chunk_dict[entry.tag].append(entry.attrib)
        if len(list(entry)) > 0:
            chunk_dict[entry.tag][-1]['children'] = process_chunk(entry)
        for key,val in chunk_dict[entry.tag][-1].items():
            try:
                chunk_dict[entry.tag][-1][key] = int(val)
                continue
            except:
                pass
            try:
                chunk_dict[entry.tag][-1][key] = float(val)
                continue
            except:
                pass
        chunk_dict[entry.tag][-1]['text'] = entry.text
        if 'index' not in chunk_dict[entry.tag][-1]:
            chunk_dict[entry.tag][-1]['index'] = 0
        if chunk_dict[entry.tag][-1]['index'] != len(chunk_dict[entry.tag])-1:
            print ('out of order entry: {}'.format(chunk_dict[entry.tag]))
    return chunk_dict

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Convert maps to SVG')
    parser.add_argument('-m', '--map', dest='map', type=str, help='a map XML file')
    parser.add_argument('-c', '--chapters', dest='chapters', type=str, help='a file of chapter markers')
    parser.add_argument('-l', '--level', dest='levels', type=int, nargs='+', help='which levels to generate')
    args = parser.parse_args()

    process_map_file(args.map, args.chapters)
#     print ('done')

