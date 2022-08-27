#!/usr/bin/env python

import argparse
import xml.etree.ElementTree as ET
from collections import defaultdict
from enum import IntFlag, auto
import json
import os
import errno
import sys
import re
import math
import xmltodict
import operator
import html

IGNORE_RE = re.compile('(?P<level>\d+): (?P<poly>[\d ]+)')

SCALE=1000
MAX_INT=32768
MAX_POS=MAX_INT/SCALE
ONE_WU=32
ONE_SCALE_WU=SCALE/ONE_WU

CHUNK_TYPES = [
    'NAME', # map name
    'NOTE', # map annotations
    'EPNT', # points
    'PNTS', # points
    'LINS', # lines
    'LITE', # lights
    'POLY', # polygons
    'SIDS', # polygon sides
    'OBJS', # objects
    'plac', # monsters and items
    'plat', # platforms
    'PLAT', # platforms
    'medi', # media
    'term', # terminals
    'Minf', # map info
]
CHUNK_TYPES_IGNORED = [
    'ambi', # ambient sounds
    'bonk', # random sounds
    'iidx', # map indices

    # physics related
    'MNpx',
    'FXpx',
    'PRpx',
    'PXpx',
    'WPpx',
]

# from https://github.com/Aleph-One-Marathon/alephone/blob/1aaa23bfaeac690ce94db1a163877d8028a8d972/Source_Files/GameWorld/map.h#L823
class EnvironmentFlags(IntFlag):
#     normal = 0,
    vacuum = auto() # prevents certain weapons from working, player uses oxygen
    magnetic = auto() # motion sensor works poorly
    rebellion = auto() # makes clients fight pfhor
    low_gravity = auto() # low gravity
    glue_m1 = auto() # handle glue polygons like Marathon 1
    ouch_m1 = auto() # the floor is lava
    rebellion_m1 = auto() # use Marathon 1 rebellion (don't strip items/health)
    song_index_m1 = auto() # play music
    terminals_stop_time = auto() # solo only
    activation_ranges = auto() # Marathon 1 monster activation limits
    m1_weapons = auto() # multiple weapon pickups on TC; low gravity grenades
    UNUSED = auto()
    # the following two pseudo-environments are used to prevent items from arriving in the items.c code.
    network = auto()
    single_player = auto()


# from https://github.com/Aleph-One-Marathon/alephone/blob/e9c3c4903bb662a4d7c84e6b8cf587efc84293e3/Source_Files/GameWorld/platforms.h#L72
class PlatformFlags(IntFlag):
    is_initially_active = auto() #  otherwise inactive
    is_initially_extended = auto() #  high for floor platforms, low for ceiling platforms, closed for two-way platforms
    deactivates_at_each_level = auto() #  this platform will deactivate each time it reaches a discrete level
    deactivates_at_initial_level = auto() #  this platform will deactivate upon returning to its original position
    activates_adjacent_platforms_when_deactivating = auto() #  when deactivating, this platform activates adjacent platforms
    extends_floor_to_ceiling = auto() #  i.e., there is no empty space when the platform is fully extended
    comes_from_floor = auto() #  platform rises from floor
    comes_from_ceiling = auto() #  platform lowers from ceiling
    causes_damage = auto() #  when obstructed by monsters, this platform causes damage
    does_not_activate_parent = auto() #  does not reactive it’s parent (i.e., that platform which activated it)
    activates_only_once = auto() #  cannot be activated a second time
    activates_light = auto() #  activates floor and ceiling lightsources while activating
    deactivates_light = auto() #  deactivates floor and ceiling lightsources while deactivating
    is_player_controllable = auto() #  i.e., door: players can use action key to change the state and/or direction of this platform
    is_monster_controllable = auto() #  i.e., door: monsters can expect to be able to move this platform even if inactive
    reverses_direction_when_obstructed = auto()
    cannot_be_externally_deactivated = auto() #  when active, can only be deactivated by itself
    uses_native_polygon_heights = auto() #  complicated interpretation; uses native polygon heights during automatic min,max calculation
    delays_before_activation = auto() #  whether or not the platform begins with the maximum delay before moving
    activates_adjacent_platforms_when_activating = auto()
    deactivates_adjacent_platforms_when_activating = auto()
    deactivates_adjacent_platforms_when_deactivating = auto()
    contracts_slower = auto()
    activates_adjacent_platforms_at_each_level = auto()
    is_locked = auto()
    is_secret = auto()
    is_door = auto()
    floods_m1 = auto()

def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc: # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else: raise

def set_default(obj):
    if isinstance(obj, set):
        return sorted(list(obj))
    raise TypeError

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

# https://www.utf8-chartable.de/unicode-utf8-table.pl?start=8192&number=128

def xml_unescape(text):
    return html.unescape(
        re.sub(
            b'&#x([a-fA-F0-9]{2});',
            lambda s: bytes.fromhex(s.group(1).decode()),
            text.encode()
        ).decode()
    )

def fix_encoding(text):
    return re.sub(
        b'\xc3\xa2',
        b'\xe2',
        text.encode()
    ).replace(
        b'\xc2',
        b''
    ).decode()

def process_map_file(map_xml_path, ignore_file, chapters_file, base_prefix=''):
    print ('map: {}'.format(map_xml_path))
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
        level_name, base_name = process_level(map_type, child, ignore_map[level_index])
        if level_index in chapters_dict:
            map_info['levels'].append({'separator': chapters_dict[level_index]})
        map_info['levels'].append({
            'index': level_index,
            'name': level_name,
            'base_name': base_prefix+base_name,
        })
        preview += '<h3>{:0>2} {}</h3><p><object type="image/svg+xml" data="{}.svg"></object></p>\n'.format(
            level_index, level_name, base_name)
    preview = preview_header + preview + '</body></html>'
    out_path = os.path.join(args.output_directory, '_preview.html')
    write_data(out_path, preview)
    map_info_path = os.path.join(args.output_directory, 'map.json')
    write_data(map_info_path, json.dumps(map_info, indent=2))
    print (json.dumps({
        "map_name": None,
        "map_info": map_info_path,
    }, indent=2))

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
            print ('unhandled chunk: {}'.format(chunk.attrib))
    for chunk_type in CHUNK_TYPES:
        if chunk_type not in level_dict:
            level_dict[chunk_type] = defaultdict(list)
    name = fix_encoding(name)
    print ('{:0>2} {}'.format(level_number, name))
    base_name = re.sub('[^a-zA-Z0-9]', '', name)
    base_name = '{:0>2}_{}'.format(level_number, base_name)
    generate_svg(map_type, base_name, level_dict, ignore_polys)
    return (name, base_name)

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

def build_platform_map(platforms):
    plat_map = dict()
    for platform in platforms['platform']:
        plat_map[platform['polygon_index']] = platform
    return plat_map

def generate_grid():
    max_dim = SCALE
    width = 2 * max_dim
    height = 2 * max_dim
    major_step = max_dim / ONE_WU # 32 WU in each direction
    minor_step = major_step / 10 # .1 WU
    return '''<g id="background-grid">
<defs>
<pattern id="grid_minor" width="{minor_step}" height="{minor_step}" patternUnits="userSpaceOnUse">
<path d="M {minor_step} 0 L 0 0 0 {minor_step}" fill="none" class="grid_minor" />
</pattern>
<pattern id="grid_major" width="{major_step}" height="{major_step}" patternUnits="userSpaceOnUse">
<rect width="{major_step}" height="{major_step}" fill="url(#grid_minor)"/>
<path d="M {major_step} 0 L 0 0 0 {major_step}" fill="none" class="grid_major" />
</pattern>
</defs>
<rect x="-{max_dim}" y="-{max_dim}" width="{width}" height="{height}" fill="url(#grid_major)" />
<line x1="0" y1="{max_dim}" x2="0" y2="-{max_dim}" class="grid_origin" />
<line x1="{max_dim}" y1="0" x2="-{max_dim}" y2="0" class="grid_origin" />
<!-- end group: "background-grid" -->
</g>
'''.format(
        max_dim = max_dim,
        width = width,
        height = height,
        major_step = major_step,
        minor_step = minor_step,
    )

def merge_dimensions(level_info, dim_type_1, dim_type_2):
    dim_1 = level_info['dimensions'][dim_type_1]
    dim_2 = level_info['dimensions'][dim_type_2]
    level_info['dimensions'][dim_type_2] = (
        min(dim_1[0], dim_2[0]),
        min(dim_1[1], dim_2[1]),
        max(dim_1[2], dim_2[2]),
        max(dim_1[3], dim_2[3])
    )

def finalize_dimensions(level_info):
    # update the 'items' dimensions with those from 'map'
    merge_dimensions(level_info, 'map', 'items')
    # update the 'lines' dimensions with those from 'items'
    merge_dimensions(level_info, 'items', 'lines')
    # round min/max coordinates to the nearest WU, +1
    major_step = SCALE / ONE_WU # 32 WU in each direction
    for k,v in level_info['dimensions'].items():
        (min_x, min_y, max_x, max_y) = v
# alternate padding method that snaps to an even WU grid
#         min_x = max(-SCALE, math.floor(min_x / ONE_SCALE_WU - 1) * ONE_SCALE_WU)
#         min_y = max(-SCALE, math.floor(min_y / ONE_SCALE_WU - 1) * ONE_SCALE_WU)
#         max_x = min( SCALE, math.ceil( max_x / ONE_SCALE_WU + 1) * ONE_SCALE_WU)
#         max_y = min( SCALE, math.ceil( max_y / ONE_SCALE_WU + 1) * ONE_SCALE_WU)
        min_x = max(-SCALE, (min_x / ONE_SCALE_WU - 1) * ONE_SCALE_WU)
        min_y = max(-SCALE, (min_y / ONE_SCALE_WU - 1) * ONE_SCALE_WU)
        max_x = min( SCALE, (max_x / ONE_SCALE_WU + 1) * ONE_SCALE_WU)
        max_y = min( SCALE, (max_y / ONE_SCALE_WU + 1) * ONE_SCALE_WU)
        level_info['dimensions'][k] = (min_x, min_y, max_x, max_y)
        level_info['viewBox'][k] = ' '.join(map(str, [min_x, min_y, max_x - min_x, max_y - min_y]))

def update_dimensions(level_info, dim_type, x, y):
    current = level_info['dimensions'][dim_type]
    level_info['dimensions'][dim_type] = (
        min(current[0], x),
        min(current[1], y),
        max(current[2], x),
        max(current[3], y)
    )

def update_player_position(level_info, player, polygons):
    polygon = polygons[player['polygon_index']]
    level_info['player'].append({
        'index': player['index'],
        'elevation': polygon['floor_height'] / MAX_INT,
    })
    level_info['player'] = sorted(level_info['player'], key=operator.itemgetter('index'))

def update_overlays(level_info, classes=[], groups=[], selectors=[]):
    if not classes and not groups and not selectors:
        return
    if groups:
        if not isinstance(groups, set) and not isinstance(groups, list):
            groups = [groups]
        level_info['overlays']['ids'].update(groups)
    if classes:
        if not isinstance(classes, set) and not isinstance(classes, list):
            classes = [classes]
        level_info['overlays']['classes'].update(classes)
    if selectors:
        if not isinstance(selectors, set) and not isinstance(selectors, list):
            selectors = [selectors]
        level_info['overlays']['selectors'].update(selectors)

def update_elevations(level_info, floor, ceiling):
    current = level_info['elevation']
    level_info['elevation']['floor'] = min(current['floor'], floor)
    level_info['elevation']['ceiling'] = max(current['ceiling'], ceiling)

# based on https://github.com/Aleph-One-Marathon/alephone/blob/e9c3c4903bb662a4d7c84e6b8cf587efc84293e3/Source_Files/GameWorld/platforms.cpp#L933
def calculate_platform_extrema(level_dict, platform):
    lowest_adjacent_floor = MAX_INT
    lowest_adjacent_ceiling = MAX_INT
    highest_adjacent_floor = -MAX_INT
    highest_adjacent_ceiling = -MAX_INT
    NONE = -1
    poly = level_dict['POLY']['polygon'][platform['polygon_index']]
    if 'minimum_height' in platform:
        lowest_level = platform['minimum_height']
        highest_level = platform['maximum_height']
    elif 'minimum_floor_height' in platform:
        lowest_level = platform['minimum_floor_height']
        highest_level = platform['maximum_ceiling_height']
    else:
        return
    for adjacent_index in range(8):
        adjacent_poly_index = poly['adjacent_polygon_index_{}'.format(adjacent_index)]
        if adjacent_poly_index < 1 or adjacent_poly_index > len(level_dict['POLY']['polygon']):
            continue
        adjacent_polygon = level_dict['POLY']['polygon'][adjacent_poly_index]
        if adjacent_polygon['floor_height']<lowest_adjacent_floor:
            lowest_adjacent_floor = adjacent_polygon['floor_height']
        if adjacent_polygon['floor_height']>highest_adjacent_floor:
            highest_adjacent_floor = adjacent_polygon['floor_height']
        if adjacent_polygon['ceiling_height']<lowest_adjacent_ceiling:
            lowest_adjacent_ceiling = adjacent_polygon['ceiling_height']
        if adjacent_polygon['ceiling_height']>highest_adjacent_ceiling:
            highest_adjacent_ceiling = adjacent_polygon['ceiling_height']
    # take into account the EXTENDS_FLOOR_TO_CEILING flag
    if PlatformFlags.extends_floor_to_ceiling & platform['static_flags']:
        if poly['ceiling_height']>highest_adjacent_floor:
            highest_adjacent_floor = poly['ceiling_height']
        if poly['floor_height']<lowest_adjacent_ceiling:
            lowest_adjacent_ceiling = poly['floor_height']
    #  calculate floor and ceiling min, max values as appropriate for the platform direction
    if PlatformFlags.comes_from_floor & platform['static_flags'] and PlatformFlags.comes_from_ceiling & platform['static_flags']:
        #  split platforms always meet in the center
        platform['minimum_floor_height']= lowest_adjacent_floor if lowest_level==NONE else lowest_level
        platform['maximum_ceiling_height']= highest_adjacent_ceiling if highest_level==NONE else highest_level
        platform['maximum_floor_height']= platform['minimum_ceiling_height']=(platform['minimum_floor_height']+platform['maximum_ceiling_height'])/2
    else:
        if PlatformFlags.comes_from_floor & platform['static_flags']:
            if PlatformFlags.uses_native_polygon_heights & platform['static_flags']:
                if poly['floor_height']<lowest_adjacent_floor or PlatformFlags.extends_floor_to_ceiling & platform['static_flags']:
                    lowest_adjacent_floor= poly['floor_height']
                else:
                    highest_adjacent_floor= poly['floor_height']
            platform['minimum_floor_height']= lowest_adjacent_floor if lowest_level==NONE else lowest_level
            platform['maximum_floor_height']= highest_adjacent_floor if highest_level==NONE else highest_level
            platform['minimum_ceiling_height']= platform['maximum_ceiling_height']= poly['ceiling_height']
        elif PlatformFlags.comes_from_ceiling & platform['static_flags']:
            if PlatformFlags.uses_native_polygon_heights & platform['static_flags']:
                if poly['ceiling_height']>highest_adjacent_ceiling or PlatformFlags.extends_floor_to_ceiling & platform['static_flags']:
                    highest_adjacent_ceiling= poly['ceiling_height']
                else:
                    lowest_adjacent_ceiling= poly['ceiling_height']
            platform['minimum_ceiling_height']= lowest_adjacent_ceiling if lowest_level==NONE else lowest_level
            platform['maximum_ceiling_height']= highest_adjacent_ceiling if highest_level==NONE else highest_level
            platform['minimum_floor_height']= platform['maximum_floor_height']= poly['floor_height']

def update_poly_info(level_info, poly_index=None, poly=None, ids=None, platform=None):
    if poly_index is None and poly is not None:
        poly_index = poly['index']
    if poly_index is None and platform is not None:
        poly_index = platform['polygon_index']
    if poly_index is None:
        raise Exception('cannot update poly info without poly index or polygon')
    poly_info = level_info['polygons'][poly_index]
    if poly is not None:
        floor = poly['floor_height']/MAX_INT
        ceiling = poly['ceiling_height']/MAX_INT
        poly_info['floor_height'] = floor
        poly_info['ceiling_height'] = ceiling
        update_elevations(level_info, floor, ceiling)
    if platform is not None:
        floor = platform['minimum_floor_height']/MAX_INT
        ceiling = platform['maximum_ceiling_height']/MAX_INT
        poly_info['floor_height'] = floor
        poly_info['ceiling_height'] = ceiling
        update_elevations(level_info, floor, ceiling)
    if ids:
        poly_info['connections'].update(ids)

def generate_polygons(level_dict, platform_map, ignore_polys, map_type, level_info):
    poly_svg = '<g id="polygons">\n'
    polys = level_dict['POLY']['polygon']
    polys = sorted(polys, key=operator.itemgetter('floor_height', 'ceiling_height'))
    for poly in polys:
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
                update_dimensions(level_info, 'map', x,y)
            update_dimensions(level_info, 'lines', x,y)
        points = range(0,poly['vertex_count'])
        points = map(lambda p: poly['{}_index_{}'.format(type, p)], points)
        points = map(lambda p: level_dict[list_key][type][p], points)
        points = map(lambda p: (p['x']/MAX_POS, p['y']/MAX_POS), points)
        points = map(lambda p: (str(p[0]),str(p[1])),points)
        points = map(','.join, points)
        extra = 'onmousemove="showTooltip(evt, \'{tooltip}\', {x}, {y});" onmouseout="hideTooltip();"'.format(
            x=poly['center_x']/MAX_POS,
            y=poly['center_y']/MAX_POS,
            tooltip='poly:{poly_index}'.format(
                poly_index=poly['index']
            )
        )
        extra = ''
        css_id = 'poly_{}'.format(poly['index'])
        poly_svg += '<polygon points="{path}" id="{css_id}" class="{css_class}" {extra}/>\n'.format(
            path=' '.join(points),
            css_id=css_id,
            css_class=css_class,
            extra=extra,
        )
        update_overlays(level_info, selectors='polygon.{}'.format(css_class))
        update_poly_info(level_info, poly=poly, ids=[css_id])
        if poly['type'] == 5:
            platform = platform_map[poly['index']]
            calculate_platform_extrema(level_dict, platform)
            update_poly_info(level_info, platform=platform)
    poly_svg += '<!-- end group: "polygons" -->\n</g>\n'
    return poly_svg

def generate_trigger_lines(level_dict, poly_type, css_class_base, level_info):
    line_svg = ''
    platform_polys = []
    if 0 < len(level_dict['PLAT']):
        platform_polys = map(lambda p: p['polygon_index'], level_dict['PLAT']['platform'])
    if 0 < len(level_dict['plat']):
        platform_polys = map(lambda p: p['polygon_index'], level_dict['plat']['platform'])
    for poly in level_dict['POLY']['polygon']:
        if poly['type'] != poly_type:
            continue
        tag_ids = set()
        poly_ids = set()
        light_ids = set()
        if poly_type == 10:
            poly_ids = {poly['permutation']}
        if poly_type in [7,9]:
            # exclude any platform triggers that don't point to platforms
            poly_ids = [p['index'] for p in [level_dict['POLY']['polygon'][poly['permutation']]] if p['index'] in platform_polys or p['type'] == 5]
        if poly_type in [6,8]:
            # light triggers reference lights which might be used by multiple polygons
            light_ids = {poly['permutation']}
        line_svg += common_generate_lines(css_class_base, poly, poly_ids, light_ids, tag_ids, level_dict, level_info)
    if not line_svg:
        return ''
    gid = 'poly_{}_lines'.format(css_class_base)
    update_overlays(level_info, classes=['poly_line'], groups=[gid])
    return '<g id="{gid}">\n{content}<!-- end group: "{gid}" -->\n</g>\n'.format(
        gid=gid,
        content=line_svg
    )

def generate_panel_lines(level_dict, css_class_base, platform_map, map_type, level_info):
    line_svg = ''
    for side in level_dict['SIDS']['side']:
        if not side['flags'] & 0x2:
            continue
        panel_type = panel_to_switch(map_type, side['panel_type'])
        if not panel_type or panel_type != css_class_base:
            continue
        tag_ids = set()
        poly_ids = set()
        light_ids = set()
        if 'platform_switch' == panel_type:
            poly_ids = {side['panel_permutation']}
        if 'light_switch' == panel_type:
            # light triggers reference lights which might be used by multiple polygons
            light_ids = {side['panel_permutation']}
        if 'tag_switch' == panel_type:
            # tag triggers reference tags which might be used by multiple polygons and lights
            tag_ids = {side['panel_permutation']}
        # common lines
        line_svg += common_generate_lines(css_class_base, side, poly_ids, light_ids, tag_ids, level_dict, level_info)
    if not line_svg:
        return ''
    gid = 'panel_{}_lines'.format(css_class_base)
    # allow switch lines to be handled by level.js
#     update_overlays(level_info, classes=['panel_line'], groups=[gid])
    return '<g id="{gid}">\n{content}<!-- end group: "{gid}" -->\n</g>\n'.format(
        gid=gid,
        content=line_svg
    )

def generate_terminal_lines(level_dict, page_type, css_class_base, map_type, level_info):
    terminal_destination_map = defaultdict(list)
    for terminal in level_dict['term']['terminal']:
        for grouping in terminal['children']['grouping']:
            if grouping['type'] != page_type:
                continue
            terminal_destination_map[terminal['index']].append(grouping['permutation'])
    line_svg = ''
    for side in level_dict['SIDS']['side']:
        if not side['flags'] & 0x2:
            continue
        panel_type = panel_to_type(map_type, side['panel_type'])
        if not panel_type or panel_type != 'computer_terminal':
            continue
        terminal_id = side['panel_permutation']
        if terminal_id not in terminal_destination_map:
            continue
        tag_ids = set()
        poly_ids = set()
        if 7 == page_type:
            # teleport
            poly_ids = terminal_destination_map[terminal_id]
        if 16 == page_type:
            # tag control: reference tags which might be used by multiple polygons and lights
            tag_ids = terminal_destination_map[terminal_id]
        # common lines
        line_svg += common_generate_lines(css_class_base, side, poly_ids, set(), tag_ids, level_dict, level_info)

    if not line_svg:
        return ''
    gid = '{}_lines'.format(css_class_base)
    # allow terminal lines to be handled by level.js
#     update_overlays(level_info, classes=['terminal_line'], groups=[gid])
    return '<g id="{gid}">\n{content}<!-- end group: "{gid}" -->\n</g>\n'.format(
        gid=gid,
        content=line_svg
    )

def common_build_destinations(polygons, lights, tags, level_dict):
    tag_ids = set(tags)
    poly_ids = set(polygons)
    light_ids = set(lights)
    side_ids = set()
    media_ids = set()
    platform_ids = set()
    for tag_id in tag_ids:
        light_ids.update([l['index'] for l in level_dict['LITE']['light'] if l['tag'] == tag_id])
        if 0 < len(level_dict['PLAT']):
            platform_ids.update([p['index'] for p in level_dict['PLAT']['platform'] if p['tag'] == tag_id])
        if 0 < len(level_dict['plat']):
            platform_ids.update([p['index'] for p in level_dict['plat']['platform'] if p['tag'] == tag_id])
    for platform_id in platform_ids:
        if 0 < len(level_dict['PLAT']):
            poly_ids.update([level_dict['PLAT']['platform'][platform_id]['polygon_index']])
        if 0 < len(level_dict['plat']):
            poly_ids.update([level_dict['plat']['platform'][platform_id]['polygon_index']])
    for light_id in light_ids:
        poly_ids.update([p['index'] for p in level_dict['POLY']['polygon'] if any(map(lambda l: p[l] == light_id, ['floor_lightsource_index', 'ceiling_lightsource_index', 'media_lightsource_index']))])
        side_ids.update([s['index'] for s in level_dict['SIDS']['side'] if any(map(lambda l: s[l] == light_id, ['primary_light', 'secondary_light', 'transparent_light']))])
        media_ids.update([m['index'] for m in level_dict['medi']['media'] if m['light_index'] == light_id])
    for media_id in media_ids:
        poly_ids.update([p['index'] for p in level_dict['POLY']['polygon'] if p['media_index'] == media_id])
    dest_polys = [p for p in level_dict['POLY']['polygon'] if p['index'] in poly_ids]
    dest_sides = [s for s in level_dict['SIDS']['side'] if s['index'] in side_ids]
    return dest_polys, dest_sides

def common_generate_lines(css_class_base, source, poly_ids, light_ids, tag_ids, level_dict, level_info):
    (dest_polys, dest_sides) = common_build_destinations(poly_ids, light_ids, tag_ids, level_dict)
    line_svg = ''
    if 'vertex_count' in source:
        source_id = 'p{}'.format(source['index'])
        pcx = source['center_x'] / MAX_POS
        pcy = source['center_y'] / MAX_POS
        source_polys = [source['index']]
    if 'line' in source:
        source_id = 's{}'.format(source['index'])
        line = level_dict['LINS']['line'][source['line']]
        px1 = level_dict['EPNT']['endpoint'][line['endpoint1']]['x']
        py1 = level_dict['EPNT']['endpoint'][line['endpoint1']]['y']
        px2 = level_dict['EPNT']['endpoint'][line['endpoint2']]['x']
        py2 = level_dict['EPNT']['endpoint'][line['endpoint2']]['y']
        pcx = (px1 + px2) / 2 / MAX_POS
        pcy = (py1 + py2) / 2 / MAX_POS
        source_polys = filter(
            lambda i: i >= 0,
            map(
                lambda s: line[s],
                ['cw_poly', 'ccw_poly']))
    for dest_poly in dest_polys:
        # lines to the polys
        if 'p{}'.format(dest_poly['index']) == source_id:
            continue
        dcx=dest_poly['center_x'] / MAX_POS
        dcy=dest_poly['center_y'] / MAX_POS
        if pcx == dcx and pcy == dcy:
#             print ('skipping 0 length line')
            continue
        gid = 'panel_{}_line_group_poly_{}_p{}'.format(css_class_base, source_id, dest_poly['index'])
        group_class = 'panel_line panel_line-{css_class_base} panel_line_poly-{css_class_base}'.format(
            css_class_base=css_class_base
        )
        for source in source_polys:
            update_poly_info(level_info, poly_index=source, ids=[gid])
        update_poly_info(level_info, poly_index=dest_poly['index'], ids=[gid])
        line_svg += '<g id="{g_id}">\n'.format(
            g_id=gid
        )
        rotation = math.atan2(dcy-pcy, dcx-pcx) * 180 / math.pi
        transform = 'transform="rotate({rotation} {cx} {cy})" '.format(
            rotation=rotation,
            cx=dcx,
            cy=dcy,
        )
        line_svg += '<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" id="{css_id}" class="{css_class}" />\n'.format(
            x1=pcx, y1=pcy, x2=dcx, y2=dcy,
            css_id='panel_{}_border_{}_p{}'.format(css_class_base, source_id, dest_poly['index']),
            css_class='{}_border'.format(css_class_base)
        )
        line_svg += '<use xlink:href="../resources/svg/common.svg#{symbol}" x="{cx}" y="{cy}" id="{css_id}" class="{css_class}" {transform}/>\n'.format(
            symbol='arrow',
            cx=dcx,
            cy=dcy,
            transform=transform,
            css_id='panel_{}_head_{}_p{}'.format(css_class_base, source_id, dest_poly['index']),
            css_class='{}_line'.format(css_class_base),
        )
        line_svg += '<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" id="{css_id}" class="{css_class}" />\n'.format(
            x1=pcx, y1=pcy, x2=dcx, y2=dcy,
            css_id='panel_{}_line_{}_p{}'.format(css_class_base, source_id, dest_poly['index']),
            css_class='{}_line'.format(css_class_base)
        )
        line_svg += '<!-- end group: "{g_id}" -->\n</g>\n'.format(
            g_id=gid
        )
    for dest_side in dest_sides:
        # lines to the sides
        if 's{}'.format(dest_side['index']) == source_id:
            continue
        dest_line = level_dict['LINS']['line'][dest_side['line']]
        x1 = level_dict['EPNT']['endpoint'][dest_line['endpoint1']]['x']
        y1 = level_dict['EPNT']['endpoint'][dest_line['endpoint1']]['y']
        x2 = level_dict['EPNT']['endpoint'][dest_line['endpoint2']]['x']
        y2 = level_dict['EPNT']['endpoint'][dest_line['endpoint2']]['y']
        dcx = (x1 + x2) / 2 / MAX_POS
        dcy = (y1 + y2) / 2 / MAX_POS
        if pcx == dcx and pcy == dcy:
#             print ('skipping 0 length line')
            continue
        gid = 'panel_{}_line_group_side_{}_s{}'.format(css_class_base, source_id, dest_side['index'])
        group_class = 'panel_line panel_line-{css_class_base} panel_line_side-{css_class_base}'.format(
            css_class_base=css_class_base
        )
        side_line = level_dict['LINS']['line'][dest_side['line']]
        for source in source_polys:
            update_poly_info(level_info, poly_index=source, ids=[gid])
        dest_polys = filter(
            lambda i: i >= 0,
            map(
                lambda s: level_dict['LINS']['line'][dest_side['line']][s],
                ['cw_poly', 'ccw_poly']))
        for dest_poly in dest_polys:
            update_poly_info(level_info, poly_index=dest_poly, ids=[gid])
        line_svg += '<g id="{g_id}" class="{g_class}">\n'.format(
            g_id=gid,
            g_class=group_class
        )
        rotation = math.atan2(dcy-pcy, dcx-pcx) * 180 / math.pi
        transform = 'transform="rotate({rotation} {cx} {cy})" '.format(
            rotation=rotation,
            cx=dcx,
            cy=dcy,
        )
        line_svg += '<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" id="{css_id}" class="{css_class}" />\n'.format(
            x1=pcx, y1=pcy, x2=dcx, y2=dcy,
            css_id='panel_{}_border_{}_s{}'.format(css_class_base, source_id, dest_side['index']),
            css_class='{}_border'.format(css_class_base)
        )
        line_svg += '<use xlink:href="../resources/svg/common.svg#{symbol}" x="{cx}" y="{cy}" id="{css_id}" class="{css_class}" {transform}/>\n'.format(
            symbol='arrow',
            cx=dcx,
            cy=dcy,
            transform=transform,
            css_id='panel_{}_head_{}_s{}'.format(css_class_base, source_id, dest_side['index']),
            css_class='{}_line'.format(css_class_base),
        )
        line_svg += '<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" id="{css_id}" class="{css_class}" />\n'.format(
            x1=pcx, y1=pcy, x2=dcx, y2=dcy,
            css_id='panel_{}_line_{}_s{}'.format(css_class_base, source_id, dest_side['index']),
            css_class='{}_line'.format(css_class_base)
        )
        line_svg += '<!-- end group: "{g_id}" -->\n</g>\n'.format(
            g_id=gid
        )
    if not line_svg:
        return ''
    gid = 'panel_{}_lines_{}'.format(css_class_base, source_id)
    return '<g id="{}">\n'.format(gid) + line_svg + '<!-- end group: "{}" -->\n</g>\n'.format(gid)

def generate_lines(level_dict, platform_map, ignore_polys, level_info):
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
        if 'solid' == css_class:
            update_dimensions(level_info, 'map', x1,y1)
            update_dimensions(level_info, 'map', x2,y2)
        css_id = 'line_{}'.format(line['index'])
        line_svg = '<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" id="{css_id}" class="{css_class}" />'.format(
            x1=x1, y1=y1, x2=x2, y2=y2,
            css_id=css_id,
            css_class=css_class
        )
        lines[css_class].append(line_svg)
        polys = filter(
            lambda i: i >= 0,
            map(
                lambda s: line[s],
                ['cw_poly', 'ccw_poly']))
        for poly in polys:
            update_poly_info(level_info, poly_index=poly, ids=[css_id])
        update_dimensions(level_info, 'lines', x1, y1)
        update_dimensions(level_info, 'lines', x2, y2)
    lines_svg = '<g id="borders">\n'
    for line_type in [
        'pointless',
        'unconnected',
        'ignore',
        'landscape_',
        'plain',
        'ceiling',
        'elevation',
        'solid'
    ]:
        if not lines[line_type]:
            del lines[line_type]
            continue
        update_overlays(level_info, groups='border_'+line_type)
        lines_svg += '<g id="border_{}">\n'.format(line_type)
        for line in lines[line_type]:
            lines_svg += line + '\n'
        lines_svg += '<!-- end group: "border_{}" -->\n</g>\n'.format(line_type)
        del lines[line_type]
    if 0 < len(lines):
        print ('leftover lines: {}'.format(set(lines.keys())))
    lines_svg += '<!-- end group: "borders" -->\n</g>\n'
    return lines_svg

def generate_annotations(notes, level_info):
    notes_svg = ''
    for note in notes:
        css_id = 'annotation_{}'.format(note['index'])
        css_class = 'annotation'
        notes_svg += '<text x="{x}" y="{y}" id="{css_id}" class="{css_class}">{note}</text>\n'.format(
            x=note['location_x']/MAX_POS,
            y=note['location_y']/MAX_POS,
            css_class=css_class,
            css_id=css_id,
            note=note['text'],
        )
        update_poly_info(level_info, poly_index=note['polygon_index'], ids=[css_id])
        update_overlays(level_info, css_class)
    if not notes_svg:
        return ''
    return '<g id="annotations">\n' + notes_svg + '<!-- end group: "annotations" -->\n</g>\n'

PANELS_m1 = [
    'oxygen_refuel', 'shield_refuel', 'double_shield_refuel',
    'triple_shield_refuel', 'light_switch', 'platform_switch',
    'pattern_buffer', 'tag_switch', 'computer_terminal',
    # Originally 'tag_switch', but in M1 this appears to only be used for
    # switches that are goals and don't actually control anything.
    # Possibly altered by side flags? In every case (levels: 3, 4, 8):
    # type=0, flags=6, permutation=0
    'goal_switch',
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

def panel_to_switch(map_type, panel_type):
    panel_type = panel_to_type(map_type, panel_type)
    if not panel_type.endswith('_switch'):
        return None
    return panel_type

def panel_to_type(map_type, panel_type):
    panel_types = PANELS
    if map_type < 2:
        panel_types = PANELS_m1
    return panel_types[panel_type]

def generate_panels(level_dict, ignore_polys, map_type, level_info):
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
        css_id = 'side_{}'.format(side['index'])
        css_class = 'panel-{}'.format(panel_types[side['panel_type']])
        hover = ''
        if '_switch' in css_class or css_class == 'panel-computer_terminal':
            hover = 'onmouseover="{mouseover}" onmouseout="{mouseout}" '.format(
                mouseover="m_over('{}');".format(css_id),
                mouseout="m_out('{}');".format(css_id),
            )
        panel_svg += '<use xlink:href="../resources/svg/common.svg#panel" x="{cx}" y="{cy}" id="{css_id}" class="{css_class}" {hover}/>\n'.format(
            cx = (x1 + x2) / 2 / MAX_POS,
            cy = (y1 + y2) / 2 / MAX_POS,
            css_id=css_id,
            css_class = css_class,
            hover=hover,
        )
        source_polys = filter(
            lambda i: i >= 0,
            map(
                lambda s: line[s],
                ['cw_poly', 'ccw_poly']))
        for source in source_polys:
            update_poly_info(level_info, poly_index=source, ids=[css_id])
        update_overlays(level_info, ['panel', css_class])
    panel_svg += '<!-- end group: "panels" -->\n</g>\n'
    return panel_svg

def generate_objects(objects, polygons, ignore_polys, level_info):
    entries = defaultdict(list)
    for obj in objects:
        symbol = None
        css_class = None
        order = obj['type']
        if 0 == obj['type']:
            symbol = 'monster'
            css_class = 'monster monster-{}'.format(obj['object_index'])
            order = symbol
        if 1 == obj['type']:
            symbol = 'object'
            css_class = 'object object-{}'.format(obj['object_index'])
            order = symbol
        if 2 == obj['type']:
            symbol = 'item'
            css_class = 'item item-{}'.format(obj['object_index'])
            order = symbol
        if 3 == obj['type']:
            symbol = 'monster'
            css_class = 'player'
            order = 'player'
            update_player_position(level_info, obj, polygons)
        if 4 == obj['type']:
            symbol = 'goal'
            css_class = 'goal'
            order = symbol
        if 5 == obj['type']:
            symbol = 'sound'
            css_class = 'sound'
            css_class = 'sound sound-{}'.format(obj['object_index'])
            order = symbol
        if symbol is None:
            symbol = 'unknown'
            css_class = 'unknown'
            order = symbol
#         if is_hidden_poly(polygons[obj['polygon_index']], ignore_polys):
#             css_class += ' hidden'
        cx=obj['location_x'] / MAX_POS
        cy=obj['location_y'] / MAX_POS
        transform = ''
        if 'sound' != symbol and 0 != obj['facing']:
            transform = 'transform="rotate({rotation} {cx} {cy})" '.format(
                rotation=obj['facing'] / 512 * 360,
                cx=cx,
                cy=cy,
            )
        css_id = 'object_{}'.format(obj['index'])
        entry = '<use xlink:href="../resources/svg/common.svg#{symbol}" x="{cx}" y="{cy}" id="{css_id}" class="{css_class}" {transform}/>'.format(
            symbol=symbol,
            cx=cx,
            cy=cy,
            transform=transform,
            css_id=css_id,
            css_class=css_class,
        )
        update_poly_info(level_info, poly_index=obj['polygon_index'], ids=[css_id])
        update_dimensions(level_info, 'items', cx, cy)
        update_overlays(level_info, css_class.split(' '))
        entries[order].append(entry)
    object_svg = '<g id="objects">\n'
    for symbol in ['unknown', 'sound', 'object', 'item', 'monster', 'goal', 'player']:
        if not entries[symbol]:
            del entries[symbol]
            continue
        object_svg += '<g id="objects_{}">\n'.format(symbol)
        for entry in entries[symbol]:
            object_svg += entry + '\n'
        object_svg += '<!-- end group: "objects_{}" -->\n</g>\n'.format(symbol)
        del entries[symbol]
    if 0 < len(entries):
        print ('leftover objects: {}'.format(set(entries.keys())))
    object_svg += '<!-- end group: "objects" -->\n</g>\n'
    return object_svg

def update_level_info(map_info, level_info):
    if EnvironmentFlags.rebellion & map_info[0]['environment_flags']:
        level_info['rebellion'] = True

def generate_svg(map_type, base_name, level_dict, ignore_polys):
    out_path = os.path.join(args.output_directory, base_name+'.svg')
    json_path = os.path.join(args.output_directory, base_name+'.json')

    platform_map = dict()
    if 0 < len(level_dict['plat']):
        platform_map = build_platform_map(level_dict['plat'])
    if 0 < len(level_dict['PLAT']):
        platform_map = build_platform_map(level_dict['PLAT'])

    level_info = {
        'scale': SCALE,
        'dimensions': {
            # initial values start at the opposite extremes
            'map':   [SCALE, SCALE, -SCALE, -SCALE],
            'items': [SCALE, SCALE, -SCALE, -SCALE],
            'lines': [SCALE, SCALE, -SCALE, -SCALE],
        },
        'elevation': {
            'floor': 1,
            'ceiling': -1,
        },
        'viewBox': {},
        'player': [],
        'overlays': {
            'ids': set(),
            'classes': set(),
            'selectors': set(),
        },
        'polygons': defaultdict(lambda: {
            'floor_height': None,
            'ceiling_height': None,
            'connections': set(),
        })
    }

    update_overlays(level_info, groups='background-grid')

    level_svg = ''

    level_svg += generate_grid()
    level_svg += generate_polygons(level_dict, platform_map, ignore_polys, map_type, level_info)
    level_svg += generate_lines(level_dict, platform_map, ignore_polys, level_info)

    level_svg += generate_trigger_lines(level_dict,  6, 'light_on', level_info)
    level_svg += generate_trigger_lines(level_dict,  8, 'light_off', level_info)
    level_svg += generate_trigger_lines(level_dict,  7, 'platform_on', level_info)
    level_svg += generate_trigger_lines(level_dict,  9, 'platform_off', level_info)
    level_svg += generate_trigger_lines(level_dict, 10, 'teleporter', level_info)

    level_svg += generate_panel_lines(level_dict, 'light_switch', platform_map, map_type, level_info)
    level_svg += generate_panel_lines(level_dict, 'platform_switch', platform_map, map_type, level_info)
    level_svg += generate_panel_lines(level_dict, 'tag_switch', platform_map, map_type, level_info)

    if 'term' in level_dict:
        level_svg += generate_terminal_lines(level_dict, 7, 'terminal_teleport', map_type, level_info)
        # no actual panel tags found
        #level_svg += generate_terminal_lines(level_dict, 16, 'terminal_tag_switch', map_type)

    level_svg += generate_objects(level_dict['OBJS']['object'], level_dict['POLY']['polygon'], ignore_polys, level_info)
    level_svg += generate_panels(level_dict, ignore_polys, map_type, level_info)
    level_svg += generate_annotations(level_dict['NOTE']['annotation'], level_info)

    if 'Minf' in level_dict:
        update_level_info(level_dict['Minf']['mapinfo'], level_info)

    # update the level_info dimensions to merge the
    finalize_dimensions(level_info)

    svg_js = '\n<script xlink:href="../resources/js/level.js" ></script>\n'
#     svg_js = '''\
# <script type="text/javascript" href="_script.js"></script>
# <text id="tooltip" display="none" fill="red" font-size=".03" style="position: absolute; display: none;"></text>
# '''

    (min_x, min_y, max_x, max_y) = level_info['dimensions']['map']

    svg_prefix = '<?xml version="1.0" encoding="UTF-8"?>\n'
    svg_prefix += '<!-- generated by map2svg: github.com/fracai/marathon-svg -->\n'
    svg_prefix += '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" version="1.1"'
    svg_size = '\n    viewBox="{vbminx} {vbminy} {vbheight} {vbwidth}">\n'.format(
        vbminx=min_x,
        vbminy=min_y,
        vbheight=max_x-min_x,
        vbwidth=max_y-min_y,
    )
    svg_style = '<link xmlns="http://www.w3.org/1999/xhtml" rel="stylesheet" href="../resources/css/styles.css" type="text/css" />\n'
    svg_style += '<style id="dynamic-style" />\n'
    svg_end = '</svg>'
    level_svg = svg_prefix + svg_size + svg_style + level_svg + svg_js + svg_end
    write_data(json_path, json.dumps(level_info, default=set_default, indent=2))
    write_data(out_path, level_svg)
    return out_path

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
        if poly['type'] == 19:
            return 'minor_ouch'
        if poly['type'] == 20:
            return 'major_ouch'
        if 0 < len(liquids) and poly['media_index'] >= 0:
            media = liquids[poly['media_index']]
            if poly['floor_height'] < media['low']:
                if media['type'] in media_map:
                    return media_map[media['type']]
        if poly['type'] == 3:
            return 'hill'
    if is_landscape_poly(poly):
        return 'landscape_'
    if poly['index'] in platform_map:
        if platform_map[poly['index']]['static_flags'] & PlatformFlags.is_secret:
            return 'secret_platform'
        else:
            return 'platform'
    if poly['type'] == 5:
        return 'platform'
    if poly['type'] == 10:
        return 'teleporter'
    return 'plain'

def calculate_line_class(line, sides, polygons, platform_map, ignore_polys):
    if line['cw_poly'] < 0 and line['ccw_poly'] < 0:
        return 'unconnected'
    cw_poly_ref = line['cw_poly']
    ccw_poly_ref = line['ccw_poly']
    cw_poly = polygons[cw_poly_ref] if cw_poly_ref >= 0 else None
    ccw_poly = polygons[ccw_poly_ref] if ccw_poly_ref >= 0 else None
    if (not cw_poly or is_ignored_poly(cw_poly, ignore_polys)) and (not ccw_poly or is_ignored_poly(ccw_poly, ignore_polys)):
        return 'ignore'
    if (cw_poly and cw_poly['index'] in platform_map) or (ccw_poly and ccw_poly['index'] in platform_map):
        return 'solid'
    if line['cw_side'] < 0 and line['ccw_side'] < 0:
        return 'plain'
    if is_landscape_line(line, sides):
        return 'landscape_'
    if line['flags'] & 0x4000 or not cw_poly or not ccw_poly or 5 == cw_poly['type'] or 5 == ccw_poly['type']:
        return 'solid'
    if cw_poly['floor_height'] != ccw_poly['floor_height']:
        return 'elevation'
    if cw_poly['ceiling_height'] != ccw_poly['ceiling_height']:
        return 'ceiling'
    return 'plain'

def is_landscape_line(line, sides):
    return is_landscape_side(line,'cw_side', sides) or is_landscape_side(line,'ccw_side', sides)

def is_landscape_side(line, side_type, sides):
    if line[side_type] < 0:
        return False
    return 9 == sides[line[side_type]]['primary_transfer']

def is_landscape_floor(poly):
    return 9 == poly['floor_transfer_mode']

def is_landscape_ceiling(poly):
    return 9 == poly['ceiling_transfer_mode']

def is_landscape_poly(poly):
    return is_landscape_floor(poly) and is_landscape_ceiling(poly)

def is_unseen_poly(poly):
    return poly['type'] != 5 and poly['floor_height'] == poly['ceiling_height']

def is_ignored_poly(poly, ignore_polys):
    return poly['index'] in ignore_polys

def is_hidden_poly(poly, ignore_polys):
    return is_landscape_poly(poly) or is_unseen_poly(poly) or is_ignored_poly(poly, ignore_polys)

MML_TAGS = [
    'motion_sensor',
    'items',
    'scenery'
]

def process_mml_file(mml_path):
    print ('mml: {}'.format(mml_path))
    mml_data = None
    with open(mml_path, 'r', encoding='utf-8') as file:
        mml_data = xmltodict.parse(file.read())['marathon']
    if not mml_data:
        return None
    mml_data = {k:v for k,v in mml_data.items() if k in MML_TAGS}
    return mml_data

def write_data(path, data):
    mkdir_p(os.path.dirname(path))
    with open(path, 'w') as f:
        f.write(data)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Convert maps to SVG')
    parser.add_argument('-d', '--dir', dest='output_directory', help='specify the output directory')
    parser.add_argument('-m', '--map', dest='map', type=str, help='a map XML file')
    parser.add_argument('-M', '--mml', dest='mml', type=str, help='an MML file')
    parser.add_argument('-i', '--ignore', dest='ignores', type=str, help='a file of polygons to ignore')
    parser.add_argument('-c', '--chapters', dest='chapters', type=str, help='a file of chapter markers')
    parser.add_argument('-b', '--base_prefix', dest='base_prefix', type=str, help='base directory where map data will be found')
    parser.add_argument('-l', '--level', dest='levels', type=int, nargs='+', help='which levels to generate')
    args = parser.parse_args()

    if args.mml:
        mml_data = process_mml_file(args.mml)
        print ('mml: \n{}'.format(json.dumps(mml_data, indent=2)))
        sys.exit(0)
    process_map_file(args.map, args.ignores, args.chapters, args.base_prefix)
    print ('done')

