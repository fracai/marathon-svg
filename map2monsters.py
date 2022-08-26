#!/usr/bin/env python

import argparse
import xml.etree.ElementTree as ET
from collections import defaultdict
from enum import IntFlag, IntEnum, auto
import traceback
import json
import os
import errno
import sys
import re

class MonsterFlags(IntFlag):
    is_omniscent = auto() # ignores line-of-sight during find_closest_appropriate_target() */
    flys = auto()
    is_alien = auto() # moves slower on slower levels, etc. */
    major = auto() # type -1 is minor */
    minor = auto() # type +1 is major */
    cannot_be_dropped = auto() # low levels cannot skip this monster */
    floats = auto() # exclusive from flys; forces the monster to take +∂h gradually */
    cannot_attack = auto() # monster has no weapons and cannot attack (runs constantly to safety) */
    uses_sniper_ledges = auto() # sit on ledges and hurl shit at the player (ranged attack monsters only) */
    is_invisible = auto() # this monster uses _xfer_invisibility */
    is_subtly_invisible = auto() # this monster uses _xfer_subtle_invisibility */
    is_kamakazi = auto() # monster does shrapnel damage and will suicide if close enough to target */
    is_berserker = auto() # below 1/4 vitality this monster goes berserk */
    is_enlarged = auto() # monster is 1.25 times normal height */
    has_delayed_hard_death = auto() # always dies soft, then switches to hard */
    fires_symmetrically = auto() # fires at ±dy, simultaneously */
    has_nuclear_hard_death = auto() # player’s screen whites out and slowly recovers */
    cant_fire_backwards = auto() # monster can’t turn more than 135° to fire */
    can_die_in_flames = auto() # uses humanoid flaming body shape */
    waits_with_clear_shot = auto() # will sit and fire (slowly) if we have a clear shot */
    is_tiny = auto() # 0.25-size normal height */
    attacks_immediately = auto() # monster will try an attack immediately */
    is_not_afraid_of_water = auto()
    is_not_afraid_of_sewage = auto()
    is_not_afraid_of_lava = auto()
    is_not_afraid_of_goo = auto()
    can_teleport_under_media = auto()
    chooses_weapons_randomly = auto()
    # monsters unable to open doors have door retry masks of NONE */
    # monsters unable to switch levels have min,max ledge deltas of 0 */
    # monsters unstopped by bullets have hit frames of NONE */

    # pseudo flags set when reading Marathon 1 physics
    weaknesses_cause_soft_death = auto()
    screams_when_crushed = auto()
    makes_sound_when_activated = auto() # instead of when locking on a target
    can_grenade_climb = auto() # only applies to player

class MonsterClass(IntFlag):
    player = auto()
    human_civilian = auto()
    madd = auto()
    possessed_hummer = auto()

    defender = auto()

    fighter = auto()
    trooper = auto()
    hunter = auto()
    enforcer = auto()
    juggernaut = auto()
    hummer = auto()

    compiler = auto()
    cyborg = auto()
    assimilated_civilian = auto()

    tick = auto()
    yeti = auto()

    human = player|human_civilian|madd|possessed_hummer
    pfhor = fighter|trooper|hunter|enforcer|juggernaut
    client = compiler|assimilated_civilian|cyborg|hummer
    native = tick|yeti
    hostile_alien = pfhor|client
    neutral_alien = native

class AttackType(IntEnum):
    rocket = ('rocket', 0)
    grenade = ('grenade')
    pistol_bullet = ('pistol round')
    rifle_bullet = ('rifle round')
    shotgun_bullet = ('shotgun blast')
    staff = ('staff')
    staff_bolt = ('staff projectile')
    flamethrower_burst = ('flamethrower')
    compiler_bolt_minor = ('bolt')
    compiler_bolt_major = ('bolt')
    alien_weapon = ('alien weapon')
    fusion_bolt_minor = ('minor fusion bolt')
    fusion_bolt_major = ('major fusion bolt')
    hunter = ('hunter blast')
    fist = ('fist')
    armageddon_sphere = ('armageddon sphere')
    armageddon_electricity = ('armageddon electricity')
    juggernaut_rocket = ('rocket')
    trooper_bullet = ('alien round')
    trooper_grenade = ('grenade')
    minor_defender = ('bolt')
    major_defender = ('bolt')
    juggernaut_missile = ('missile')
    minor_energy_drain = ('energy drain')
    major_energy_drain = ('major energy drain')
    oxygen_drain = ('oxygen drain')
    minor_hummer = ('hummer shot')
    major_hummer = ('hummer shot')
    durandal_hummer = ('hummer shot')
    minor_cyborg_ball = ('grenade')
    major_cyborg_ball = ('grenade')
    ball = ('ball')
    minor_fusion_dispersal = ('minor fusion bolt')
    major_fusion_dispersal = ('major fusion bolt')
    overloaded_fusion_dispersal = ('overloaded fusion')
    yeti = ('claw')
    sewage_yeti = ('sewage')
    lava_yeti = ('lava')
    # LP additions:
    smg_bullet = ('fletchet round')
    NUMBER_OF_PROJECTILE_TYPES = ('')

    def __new__(cls, description, value=None):
        if value is None:
            value = list(cls.__members__.values())[-1].value + 1
        member = int.__new__(cls, value)
        member._value_ = value
        member.description = description
        return member

NOTEWORTHY_FLAGS = {
    MonsterFlags.minor: 'minor',
    MonsterFlags.major: 'major',
    MonsterFlags.is_invisible: 'invisible',
    MonsterFlags.is_subtly_invisible: 'cloaked',
    MonsterFlags.is_enlarged: 'mother of all',
    MonsterFlags.is_tiny: 'mini',
    MonsterFlags.has_nuclear_hard_death: 'nuke',
}

IGNORE_FLAGS = set([
    MonsterFlags.attacks_immediately,
    MonsterFlags.cannot_be_dropped,
    MonsterFlags.cant_fire_backwards,
    MonsterFlags.can_die_in_flames,
    MonsterFlags.can_grenade_climb,
    MonsterFlags.can_teleport_under_media,
    MonsterFlags.chooses_weapons_randomly,
    MonsterFlags.fires_symmetrically,
    MonsterFlags.floats,
    MonsterFlags.flys,
    MonsterFlags.has_delayed_hard_death,
    MonsterFlags.is_alien,
    MonsterFlags.is_berserker,
    MonsterFlags.is_kamakazi,
    MonsterFlags.is_not_afraid_of_goo,
    MonsterFlags.is_not_afraid_of_lava,
    MonsterFlags.is_not_afraid_of_sewage,
    MonsterFlags.is_not_afraid_of_water,
    MonsterFlags.is_omniscent,
    MonsterFlags.makes_sound_when_activated,
    MonsterFlags.screams_when_crushed,
    MonsterFlags.waits_with_clear_shot,
    MonsterFlags.weaknesses_cause_soft_death,
])

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
        except:
            continue
        packed_collection = monster_def['collection']
        clut = get_collection_clut(packed_collection)
        coll = get_collection(packed_collection)
        stationary = monster_def['stationary_shape_shape']

        flags = [f for f in MonsterFlags if f & monster_def['flags']]
        monster_class = [f for f in MonsterClass if f & monster_def['class']]
        print (monster_class)
        try:
            melee_attack = AttackType(monster_def['melee_attack_type'])
        except:
            melee_attack = None
        try:
            ranged_attack = AttackType(monster_def['ranged_attack_type'])
        except:
            ranged_attack = None
        attacks = {a.description:None for a in [melee_attack, ranged_attack] if a is not None}.keys()

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
        notes.extend((attacks))
        if notes:
            collection_name += ' (' + ', '.join(notes) + ')'
        alliances[alliance].append({
            "class": 'monster-{}'.format(monster_index),
            "display": collection_name,
            "tooltip": ', '.join(map(lambda f: f.name,flags)),
        })
        print ('{:0>2}: {} {} :: {}'.format(monster_index, alliance, collection_id, list(map(lambda f: f.name, flags))))
        print (json.dumps(alliances, indent=2))
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

