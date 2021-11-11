#!/usr/bin/env python

import argparse
import xml.etree.ElementTree as ET
from collections import defaultdict
import json
import os
import errno
import sys
import re
import math

IGNORE_RE = re.compile('(?P<level>\d+): (?P<poly>[\d ]+)')

MAX_POS=32768

CHUNK_TYPES = [
    'NAME', # map name
    'NOTE', # map annotations
    'EPNT', # points
    'PNTS', # points
    'LINS', # lines
    'POLY', # polygons
    'SIDS', # polygon sides
    'OBJS', # objects
    'plac', # monsters and items
    'plat', # platforms
    'PLAT', # platforms
    'medi', # media
]
CHUNK_TYPES_IGNORED = [
    'LITE', # lights
    'term', # terminals
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

preview_header = '''\
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN"
                      "http://www.w3.org/TR/html4/loose.dtd">
<html lang="en"><head>
<title>Level Preview</title>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8">
<style type="text/css">
body {
    background: black;
    color: #0f0;
    text-align: center;
    font-family: Monaco, ProFont;
}
</style>
</head>
<body>
'''

def process_map_file(map_xml_path, ignore_file):
    print (map_xml_path)
    ignore_map = dict()
    if ignore_file:
        with open(ignore_file, 'r') as f:
            while True:
                line = f.readline()
                if not line:
                    break
                match = IGNORE_RE.match(line)
                if match:
                    ignore_map[int(match['level'])] = list(map(int, match['poly'].split(' ')))
    tree = ET.parse(map_xml_path)
    root = tree.getroot()
    if 'wadfile' != root.tag:
        return
    map_type = None
    level_count = None
    preview = ''
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
        if level_index not in ignore_map:
            ignore_map[level_index] = []
        level_name, svg_name = process_level(map_type, child, ignore_map[level_index])
        preview += '<h3>{}</h3><p><object type="image/svg+xml" data="{}"></object></p>\n'.format(level_name,svg_name)
    preview = preview_header + preview + '</body></html>'
    out_path = os.path.join(args.output_directory, '_preview.html')
    write_data(out_path, preview)

def process_level(map_type, level_root, ignore_polys):
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
    for chunk_type in CHUNK_TYPES:
        if chunk_type not in level_dict:
            level_dict[chunk_type] = defaultdict(list)
    level_name = '{:0>2} {}'.format(level_number, name)
    print (level_name)
    return level_name, generate_svg(map_type, level_name, level_dict, ignore_polys)

def process_chunk(chunk_root):
    chunk_dict = defaultdict(list)
    for entry in chunk_root:
        chunk_dict[entry.tag].append(entry.attrib)
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
        if chunk_dict[entry.tag][-1]['index'] != len(chunk_dict[entry.tag])-1:
            print (chunk_dict[entry.tag])
    return chunk_dict

def build_platform_map(platforms):
    plat_map = dict()
    for platform in platforms['platform']:
        plat_map[platform['polygon_index']] = platform
    return plat_map

def generate_grid():
    grid_svg = '<g id="background-grid">\n'
    major_step_count = int(MAX_POS/1024) # 1WU = 1024, 32 WU in each direction
    minor_step_interval = 10 # .1 WU
    tics = major_step_count * minor_step_interval
    for grid in range(0, tics + 1):
        css_class = 'grid_minor'
        x = grid/tics
        if 0 == grid % minor_step_interval:
            css_class = 'grid_major'
        if 0 == grid:
            css_class = 'grid_origin'
        grid_svg += '<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" class="{css_class}" />\n'.format(
            x1=x, y1=1, x2=x, y2=-1,
            css_class=css_class
        )
        grid_svg += '<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" class="{css_class}" />\n'.format(
            x1=1, y1=x, x2=-1, y2=x,
            css_class=css_class
        )
        if grid != 0:
            grid_svg += '<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" class="{css_class}" />\n'.format(
                x1=-x, y1=1, x2=-x, y2=-1,
                css_class=css_class
            )
            grid_svg += '<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" class="{css_class}" />\n'.format(
                x1=1, y1=-x, x2=-1, y2=-x,
                css_class=css_class
            )
    grid_svg += '<!-- end group: "background-grid" -->\n</g>\n'
    return grid_svg

def generate_polygons(level_dict, platform_map, ignore_polys, map_type):
    poly_svg = '<g id="polygons">\n'
    (min_x, min_y, max_x, max_y) = level_dict['__dimensions']
    for poly in level_dict['POLY']['polygon']:
        type='line'
        list_key='LINS'
        type='endpoint'
        list_key='EPNT'
        css_class = calculate_poly_class(poly, platform_map, ignore_polys, level_dict['medi']['media'], map_type)
        for index in range(0,poly['vertex_count']):
            reference = poly['{}_index_{}'.format(type, index)]
            entry = level_dict[list_key][type][reference]
            x = entry['x']/MAX_POS
            y = entry['y']/MAX_POS
            if css_class not in ['ignore', 'landscape_']:
                (min_x, min_y, max_x, max_y) = (min(min_x, x), min(min_y, y), max(max_x, x), max(max_y, y))
        points = range(0,poly['vertex_count'])
        points = map(lambda p: poly['{}_index_{}'.format(type, p)], points)
        points = map(lambda p: level_dict[list_key][type][p], points)
        points = map(lambda p: (p['x']/MAX_POS, p['y']/MAX_POS), points)
        points = map(lambda p: (str(p[0]),str(p[1])),points)
        points = map(' '.join, points)
        extra = 'onmousemove="showTooltip(evt, \'{tooltip}\', {x}, {y});" onmouseout="hideTooltip();"'.format(
            x=poly['center_x']/MAX_POS,
            y=poly['center_y']/MAX_POS,
            tooltip='poly:{poly_index}'.format(
                poly_index=poly['index']
            )
        )
        extra = ''
        poly_svg += '<path d="{path}" id="{css_id}" class="{css_class}" floor="{floor}" ceiling="{ceiling}" {extra}/>\n'.format(
            path='M ' + ' L '.join(points) + ' Z',
            css_id='poly_{}'.format(poly['index']),
            css_class=css_class,
            floor=poly['floor_height']/MAX_POS,
            ceiling=poly['ceiling_height']/MAX_POS,
            extra=extra,
        )
    poly_svg += '<!-- end group: "polygons" -->\n</g>\n'
    level_dict['__dimensions'] = (min_x, min_y, max_x, max_y)
    return poly_svg

def generate_lines(level_dict, platform_map, ignore_polys):
    lines_svg = '<g id="lines">\n'
    lines = defaultdict(list)
    for line in level_dict['LINS']['line']:
        endpoint1_ref = line['endpoint1']
        endpoint2_ref = line['endpoint2']
        x1 = level_dict['EPNT']['endpoint'][endpoint1_ref]['x']/MAX_POS
        y1 = level_dict['EPNT']['endpoint'][endpoint1_ref]['y']/MAX_POS
        x2 = level_dict['EPNT']['endpoint'][endpoint2_ref]['x']/MAX_POS
        y2 = level_dict['EPNT']['endpoint'][endpoint2_ref]['y']/MAX_POS
        css_class = calculate_line_class(line, level_dict['SIDS']['side'], level_dict['POLY']['polygon'], platform_map, ignore_polys)
        if x1 == x2 and y1 == y2:
            css_class = 'pointless'
        line_svg = '<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" id="{css_id}" class="{css_class}" />'.format(
            x1=x1, y1=y1, x2=x2, y2=y2,
            css_id='line_{}'.format(line['index']),
            css_class=css_class
        )
        lines[css_class].append(line_svg)
    for line_type in ['pointless', 'ignore', 'landscape_', 'plain', 'elevation', 'solid']:
        for line in lines[line_type]:
            lines_svg += line + '\n'
        del lines[line_type]
    if lines.keys():
        print (set(lines.keys()))
    lines_svg += '<!-- end group: "lines" -->\n</g>\n'
    return lines_svg

def generate_annotations(notes):
    notes_svg = '<g id="annotations">\n'
    for note in notes:
        notes_svg += '<text x="{x}" y="{y}" id="{css_id}" class="{css_class}">{note}</text>\n'.format(
            x=note['location_x']/MAX_POS,
            y=note['location_y']/MAX_POS,
            css_class='annotation',
            css_id='annotation_{}'.format(note['index']),
            note=note['text'],
        )
    notes_svg += '<!-- end group: "annotations" -->\n</g>\n'
    return notes_svg

PANELS_m1 = [
    'oxygen_refuel', 'shield_refuel', 'double_shield_refuel',
    'triple_shield_refuel', 'light_switch', 'platform_switch',
    'pattern_buffer', 'tag_switch', 'computer_terminal', 'tag_switch',
    'double_shield_refuel', 'triple_shield_refuel', 'platform_switch',
    'pattern_buffer',
]
PANELS = [
    'oxygen_refuel', 'shield_refuel', 'double_shield_refuel', 'tag_switch',
    'light_switch', 'platform_switch', 'tag_switch', 'pattern_buffer',
    'computer_terminal', 'tag_switch',

    'shield_refuel', 'double_shield_refuel', 'triple_shield_refuel',
    'light_switch', 'platform_switch', 'tag_switch', 'pattern_buffer',
    'computer_terminal', 'oxygen_refuel', 'tag_switch', 'tag_switch',

    'shield_refuel', 'double_shield_refuel', 'triple_shield_refuel',
    'light_switch', 'platform_switch', 'tag_switch', 'pattern_buffer',
    'computer_terminal', 'oxygen_refuel', 'tag_switch', 'tag_switch',

    'shield_refuel', 'double_shield_refuel', 'triple_shield_refuel',
    'light_switch', 'platform_switch', 'tag_switch', 'pattern_buffer',
    'computer_terminal', 'oxygen_refuel', 'tag_switch', 'tag_switch',

    'shield_refuel', 'double_shield_refuel', 'triple_shield_refuel',
    'light_switch', 'platform_switch', 'tag_switch', 'pattern_buffer',
    'computer_terminal', 'oxygen_refuel', 'tag_switch', 'tag_switch',
]

def generate_panels(level_dict, ignore_polys, map_type):
    panel_types = PANELS
    if map_type < 2:
        panel_types = PANELS_m1
    panel_svg = '<g id="panels">\n'
    for side in level_dict['SIDS']['side']:
        if not side['flags'] & 0x2:
            continue
#         if side['poly'] < len(level_dict['POLY']['polygon']) and is_hidden_poly(level_dict['POLY']['polygon'][side['poly']], ignore_polys):
#             continue
        line = level_dict['LINS']['line'][side['line']]
        x1 = level_dict['EPNT']['endpoint'][line['endpoint1']]['x']
        y1 = level_dict['EPNT']['endpoint'][line['endpoint1']]['y']
        x2 = level_dict['EPNT']['endpoint'][line['endpoint2']]['x']
        y2 = level_dict['EPNT']['endpoint'][line['endpoint2']]['y']
        css_class = 'panel-{}'.format(panel_types[side['panel_type']])
        panel_svg += '<use xlink:href="_panel_ring.svg#panel" x="{cx}" y="{cy}" class="{css_class}" />\n'.format(
            cx = (x1 + x2) / 2 / MAX_POS,
            cy = (y1 + y2) / 2 / MAX_POS,
            css_id='side_{}'.format(side['index']),
            css_class = css_class,
        )
    panel_svg += '<!-- end group: "panels" -->\n</g>\n'
    return panel_svg

def generate_svg(map_type, level_name, level_dict, ignore_polys):
    level_name = level_name.replace(' ','_')
    level_name = re.sub('[^a-zA-Z0-9]', '_', level_name)
    level_name = re.sub('_+', '_', level_name)
    out_path = os.path.join(args.output_directory, '{}.svg'.format(level_name))
    json_path = os.path.join(args.output_directory, '{}.json'.format(level_name))

    platform_map = dict()
    if 0 < len(level_dict['plat']):
        platform_map = build_platform_map(level_dict['plat'])
    if 0 < len(level_dict['PLAT']):
        platform_map = build_platform_map(level_dict['PLAT'])

    level_dict['__dimensions'] = (1,1,-1,-1)
    level_svg = ''

    level_svg += generate_grid()
    level_svg += generate_polygons(level_dict, platform_map, ignore_polys, map_type)
    level_svg += generate_lines(level_dict, platform_map, ignore_polys)
    level_svg += generate_panels(level_dict, ignore_polys, map_type)
    level_svg += generate_annotations(level_dict['NOTE']['annotation'])

    # round min/max coordinates to the nearest WU, +1
    (min_x, min_y, max_x, max_y) = level_dict['__dimensions']
    min_x = max(-1, math.floor(min_x * 32 - 1)/32)
    min_y = max(-1, math.floor(min_y * 32 - 1)/32)
    max_x = min( 1, math.ceil( max_x * 32 + 1)/32)
    max_y = min( 1, math.ceil( max_y * 32 + 1)/32)

    svg_js = ''
#     svg_js = '''\
# <script type="text/javascript" href="_script.js"></script>
# <text id="tooltip" display="none" fill="red" font-size=".03" style="position: absolute; display: none;"></text>
# '''

    svg_prefix = '<?xml version="1.0" encoding="UTF-8"?>\n'
    svg_prefix += '<!-- generated by map2svg: github.com/fracai/marathon-utils -->\n'
    svg_prefix += '''\
<svg
    xmlns="http://www.w3.org/2000/svg"
    xmlns:xlink="http://www.w3.org/1999/xlink"
    version="1.1"
    '''
    svg_style = '<link xmlns="http://www.w3.org/1999/xhtml" rel="stylesheet" href="_styles.css" type="text/css"/>\n'
    svg_size = 'width="{width}" height="{height}" viewBox="{vbminx} {vbminy} {vbheight} {vbwidth}">\n'.format(
        width=(max_x-min_x)/2 * 1000,
        height=(max_y-min_y)/2 * 1000,
        vbminx=min_x,
        vbminy=min_y,
        vbheight=max_x-min_x,
        vbwidth=max_y-min_y,
    )
    svg_end = '</svg>'
    level_svg = svg_prefix + svg_size + svg_style + level_svg + svg_js + svg_end
#     write_data(json_path, json.dumps(level_dict, indent=2))
    write_data(out_path, level_svg)
    return os.path.basename(out_path)

media_map = {
    0: 'water',
    1: 'lava',
    2: 'pfhor',
    3: 'sewage',
    4: 'jjaro',
}

def calculate_poly_class(poly, platform_map, ignore_polys, liquids, map_type):
    if is_ignored_poly(poly, ignore_polys):
        return 'ignore'
    if map_type < 2:
        if poly['type'] == 3:
            return 'minor_ouch'
        if poly['type'] == 4:
            return 'major_ouch'
    else:
        if poly['type'] == 3:
            return 'hill'
        if poly['type'] == 19:
            return 'minor_ouch'
        if poly['type'] == 20:
            return 'major_ouch'
        if 0 < len(liquids) and poly['media_index'] >= 0:
            media = liquids[poly['media_index']]
            if poly['floor_height'] < media['low']:
                if media['type'] in media_map:
                    return media_map[media['type']]
    if is_landscape_poly(poly):
        return 'landscape_'
    if poly['index'] in platform_map:
        if platform_map[poly['index']]['static_flags'] & 0x2000000:
            return 'secret_platform'
        else:
            return 'platform'
    if poly['type'] == 5:
        return 'platform'
    return 'plain'

def calculate_line_class(line, sides, polygons, platform_map, ignore_polys):
    if line['cw_side'] < 0 and line['ccw_side'] < 0:
        return 'ignore'
    if line['cw_poly'] < 0 and line['ccw_poly'] < 0:
        return 'ignore'
    cw_poly_ref = line['cw_poly']
    ccw_poly_ref = line['ccw_poly']
    cw_poly = polygons[cw_poly_ref] if cw_poly_ref >= 0 else None
    ccw_poly = polygons[ccw_poly_ref] if ccw_poly_ref >= 0 else None
    if (not cw_poly or is_ignored_poly(cw_poly, ignore_polys)) and (not ccw_poly or is_ignored_poly(ccw_poly, ignore_polys)):
        return 'ignore'
    if is_landscape_line(line, sides):
        return 'landscape_'
    if line['flags'] & 0x4000 or not cw_poly or not ccw_poly or 5 == cw_poly['type'] or 5 == ccw_poly['type']:
        return 'solid'
    if cw_poly['floor_height'] == ccw_poly['floor_height']:
        return 'plain'
    if (cw_poly and cw_poly['index'] in platform_map) or (ccw_poly and ccw_poly['index'] in platform_map):
        return 'solid'
    return 'elevation'

def is_landscape_line(line, sides):
    return is_landscape_side(line,'cw_side', sides) or is_landscape_side(line,'ccw_side', sides)

def is_landscape_side(line, side_type, sides):
    if line[side_type] < 0:
        return False
    return 9 == sides[line[side_type]]['primary_transfer']

def is_landscape_poly(poly):
    return 9 == poly['floor_transfer_mode'] and 9 == poly['ceiling_transfer_mode']

def is_unseen_poly(poly):
    return poly['type'] != 5 and poly['floor_height'] == poly['ceiling_height']

def is_ignored_poly(poly, ignore_polys):
    return poly['index'] in ignore_polys;

def is_hidden_poly(poly, ignore_polys):
    return islandscape_poly(poly) or is_unseen_poly(poly) or is_ignored_poly(poly, ignore_polys)

def write_data(path, data):
    mkdir_p(os.path.dirname(path))
    with open(path, 'w') as f:
        f.write(data)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Convert maps to SVG')
    parser.add_argument('-d', '--dir', dest='output_directory', help='specify the output directory')
    parser.add_argument('-m', '--map', dest='map', type=str, help='a map XML file')
    parser.add_argument('-i', '--ignore', dest='ignores', type=str, help='a file of polygons to ignore')
    parser.add_argument('-l', '--level', dest='levels', type=int, nargs='+', help='which levels to generate')
    args = parser.parse_args()

    process_map_file(args.map, args.ignores)
    print ('done')

