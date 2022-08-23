#!/usr/bin/env python

import argparse
import xml.etree.ElementTree as ET
from collections import defaultdict
import json
import os
import errno
import sys
import re

FLAGS={
    0x1: 'is_omniscent', # ignores line-of-sight during find_closest_appropriate_target() */
    0x2: 'flys',
    0x4: 'is_alien', # moves slower on slower levels, etc. */
    0x8: 'major', # type -1 is minor */
    0x10: 'minor', # type +1 is major */
    0x20: 'cannot_be_dropped', # low levels cannot skip this monster */
    0x40: 'floats', # exclusive from flys; forces the monster to take +∂h gradually */
    0x80: 'cannot_attack', # monster has no weapons and cannot attack (runs constantly to safety) */
    0x100: 'uses_sniper_ledges', # sit on ledges and hurl shit at the player (ranged attack monsters only) */
    0x200: 'is_invisible', # this monster uses _xfer_invisibility */
    0x400: 'is_subtly_invisible', # this monster uses _xfer_subtle_invisibility */
    0x800: 'is_kamakazi', # monster does shrapnel damage and will suicide if close enough to target */
    0x1000: 'is_berserker', # below 1/4 vitality this monster goes berserk */
    0x2000: 'is_enlarged', # monster is 1.25 times normal height */
    0x4000: 'has_delayed_hard_death', # always dies soft, then switches to hard */
    0x8000: 'fires_symmetrically', # fires at ±dy, simultaneously */
    0x10000: 'has_nuclear_hard_death', # player’s screen whites out and slowly recovers */
    0x20000: 'cant_fire_backwards', # monster can’t turn more than 135° to fire */
    0x40000: 'can_die_in_flames', # uses humanoid flaming body shape */
    0x80000: 'waits_with_clear_shot', # will sit and fire (slowly) if we have a clear shot */
    0x100000: 'is_tiny', # 0.25-size normal height */
    0x200000: 'attacks_immediately', # monster will try an attack immediately */
    0x400000: 'is_not_afraid_of_water',
    0x800000: 'is_not_afraid_of_sewage',
    0x1000000: 'is_not_afraid_of_lava',
    0x2000000: 'is_not_afraid_of_goo',
    0x4000000: 'can_teleport_under_media',
    0x8000000: 'chooses_weapons_randomly',
    # monsters unable to open doors have door retry masks of NONE */
    # monsters unable to switch levels have min,max ledge deltas of 0 */
    # monsters unstopped by bullets have hit frames of NONE */

    # pseudo flags set when reading Marathon 1 physics
    0x10000000: 'weaknesses_cause_soft_death',
    0x20000000: 'screams_when_crushed',
    0x40000000: 'makes_sound_when_activated', # instead of when locking on a target
    0x80000000: 'can_grenade_climb', # only applies to player
}

NOTEWORTHY_FLAGS = {
    'minor': 'minor',
    'major': 'major',
    'is_invisible': 'invisible',
    'is_subtly_invisible': 'cloaked',
    'is_enlarged': 'mother of all',
    'is_tiny': 'mini',
    'has_nuclear_hard_death': 'nuke',
}

IGNORE_FLAGS = set([
    'attacks_immediately',
    'cannot_be_dropped',
    'cant_fire_backwards',
    'can_die_in_flames',
    'can_grenade_climb',
    'can_teleport_under_media',
    'chooses_weapons_randomly',
    'fires_symmetrically',
    'floats',
    'flys',
    'has_delayed_hard_death',
    'is_alien',
    'is_berserker',
    'is_kamakazi',
    'is_not_afraid_of_goo',
    'is_not_afraid_of_lava',
    'is_not_afraid_of_sewage',
    'is_not_afraid_of_water',
    'is_omniscent',
    'makes_sound_when_activated',
    'screams_when_crushed',
    'waits_with_clear_shot',
    'weaknesses_cause_soft_death',
])

def get_flags(bits):
    flags = list()
    for mask,flag in FLAGS.items():
        if flag in IGNORE_FLAGS:
            continue
        if mask & bits:
            flags.append(flag)
    return flags

DESCRIPTOR_SHAPE_BITS = 8
DESCRIPTOR_COLLECTION_BITS = 5
DESCRIPTOR_CLUT_BITS = 3

MAXIMUM_COLLECTIONS = 1<<DESCRIPTOR_COLLECTION_BITS
MAXIMUM_SHAPES_PER_COLLECTION = 1<<DESCRIPTOR_SHAPE_BITS
MAXIMUM_CLUTS_PER_COLLECTION = 1<<DESCRIPTOR_CLUT_BITS

# #define GET_DESCRIPTOR_SHAPE(d) ((d)&(uint16)(MAXIMUM_SHAPES_PER_COLLECTION-1))
# #define GET_DESCRIPTOR_COLLECTION(d) (((d)>>DESCRIPTOR_SHAPE_BITS)&(uint16)((1<<(DESCRIPTOR_COLLECTION_BITS+DESCRIPTOR_CLUT_BITS))-1))
# #define BUILD_DESCRIPTOR(collection,shape) (((collection)<<DESCRIPTOR_SHAPE_BITS)|(shape))
#
# #define BUILD_COLLECTION(collection,clut) ((collection)|(uint16)((clut)<<DESCRIPTOR_COLLECTION_BITS))
# #define GET_COLLECTION_CLUT(collection) (((collection)>>DESCRIPTOR_COLLECTION_BITS)&(uint16)(MAXIMUM_CLUTS_PER_COLLECTION-1))
# #define GET_COLLECTION(collection) ((collection)&(MAXIMUM_COLLECTIONS-1))

def get_descriptor_shape(d):
    return d & (MAXIMUM_SHAPES_PER_COLLECTION-1)

def get_descriptor_collection(d):
    return (d>>DESCRIPTOR_SHAPE_BITS) & ((1<<(DESCRIPTOR_COLLECTION_BITS+DESCRIPTOR_CLUT_BITS))-1)

def get_collection_clut(collection):
    return (collection>>DESCRIPTOR_COLLECTION_BITS) & (MAXIMUM_CLUTS_PER_COLLECTION-1)

def get_collection(collection):
    return collection & (MAXIMUM_COLLECTIONS-1)


CHUNK_TYPES = [
    'NAME', # map name
    'OBJS', # objects
    'MNpx', # monster definitions
]
CHUNK_TYPES_IGNORED = [
    'ambi', # ambient sounds
    'bonk', # random sounds
    'iidx', # map indices
    'Minf', # map info

    # physics related
    'FXpx',
    'PRpx',
    'PXpx',
    'WPpx',

    'POLY', # polygons
    'term', # terminals
    'NOTE', # map annotations
    'EPNT', # points
    'PNTS', # points
    'LINS', # lines
    'LITE', # lights
    'SIDS', # polygon sides
    'plac', # monsters and items
    'plat', # platforms
    'PLAT', # platforms
    'medi', # media
]

# {
#     "class": "monster",
#     "display": "Monsters",
#     "types": [
#         {
#             "class": null,
#             "display": "Alliance",
#             "types": [
#                 {
#                     "class": "monster-index",
#                     "display": "collection name"
#                     "tooltip": "flags, ..."
#                 },


def fix_encoding(text):
    return re.sub(
        b'\xc3\xa2',
        b'\xe2',
        text.encode()
    ).replace(
        b'\xc2',
        b''
    ).decode()

def process_map_file(map_xml_path, collections_path, base_prefix=''):
    tree = ET.parse(map_xml_path)
    root = tree.getroot()
    if 'wadfile' != root.tag:
        return
    with open(collections_path, 'r') as collections_file:
        collections = json.load(collections_file)
    map_type = None
    level_count = None
    preview = ''
    map_info = {
        'levels': []
    }
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
        process_level(map_type, child, collections, base_prefix)

def process_level(map_type, level_root, collections, base_prefix):
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
    monsters = set()
    for monster in level_dict['OBJS']['object']:
        if monster['type'] != 0:
            continue
        monsters.add(monster['object_index'])
    alliances = defaultdict(list)
    for monster_index in sorted(map(int, monsters)):
        try:
            monster_def = level_dict['MNpx']['monster_definition'][monster_index]

            packed_collection = monster_def['collection']
            clut = get_collection_clut(packed_collection)
            coll = get_collection(packed_collection)
            stationary = monster_def['stationary_shape_shape']

            flags = get_flags(monster_def['flags'])

            friend = monster_def['friends'] & 0x1
            enemy = monster_def['enemies'] & 0x1
            alliance = 'unknown'
            if friend and enemy:
                alliance = 'confused'
            elif friend:
                alliance = 'friend'
            elif enemy:
                alliance = 'enemy'
            else:
                alliance = 'neutral'
            collection_id = '{}:{}:{}'.format(coll,clut,stationary)
            collection_name = find_collection_name(collections, collection_id)
            notes = list()
            for flag,note in NOTEWORTHY_FLAGS.items():
                if flag in flags:
                    notes.append(note)
            if notes:
                collection_name += ' (' + ', '.join(notes) + ')'
            alliances[alliance].append({
                "class": 'monster-{}'.format(monster_index),
                "display": collection_name,
                "tooltip": ', '.join(flags),
            })
#             print ('{:0>2}: {} {} :: {}'.format(monster_index, alliance, collection_id, flags))
        except:
#             print ('{:0>2}: ???'.format(monster_index))
            pass
    if not alliances:
        return
    level_dict['name'] = name
    level_dict['level_number'] = level_number
    alliance_overlays = {
        "class": "monster",
        "display": "Monsters",
        "types": []
    }
    for alliance,monsters in alliances.items():
        alliance_overlays['types'].append({
            "class": None,
            "display": alliance.lower().title(),
            "types": monsters
        })
    base_name = re.sub('[^a-zA-Z0-9]', '', name)
    base_name = '{:0>2}_{}'.format(level_number, base_name)
    with open(base_prefix+base_name+'_MNov.json', 'w') as i:
       json.dump(alliance_overlays, i)

def find_collection_name(collections, key):
    for cid,name in collections.items():
        if key.startswith(cid):
            return name
    return key

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
    parser.add_argument('-b', '--base_prefix', dest='base_prefix', type=str, help='base directory where map data will be written')
    parser.add_argument('-c', '--collections', dest='collections', type=str, help='a JSON file detailing collection names')
    parser.add_argument('-l', '--level', dest='levels', type=int, nargs='+', help='which levels to generate')
    args = parser.parse_args()

    process_map_file(args.map, args.collections, args.base_prefix)
#     print ('done')

