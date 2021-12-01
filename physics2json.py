#!/usr/bin/env python

import argparse
import struct
import json
import xmltodict
import sys

FIXED_FRACTIONAL_BITS = 16
FIXED_ONE = 1<<FIXED_FRACTIONAL_BITS
FIXED_ONE_HALF = 1<<(FIXED_FRACTIONAL_BITS-1)

WORLD_FRACTIONAL_BITS = 10
WORLD_ONE = 1<<WORLD_FRACTIONAL_BITS

# typedef Uint8 uint8;
# typedef Sint8 int8;
# typedef Uint16 uint16;
# typedef Sint16 int16;
# typedef Uint32 uint32;
# typedef Sint32 int32;
# typedef time_t TimeType;
# typedef int32 _fixed;
# // Hmmm, this should be removed one day...
# typedef uint8 byte;

# typedef int16 angle;
# typedef _fixed fixed_angle; // angle with _fixed precision
# typedef int16 world_distance;

# typedef uint16 shape_descriptor; # [clut.3] [collection.5] [shape.8]

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

_monster_is_omniscent= 0x1 # ignores line-of-sight during find_closest_appropriate_target()
_monster_flys= 0x2
_monster_is_alien= 0x4 # moves slower on lower levels, etc.
_monster_major= 0x8 # type -1 is minor
_monster_minor= 0x10 # type +1 is major
_monster_cannot_be_dropped= 0x20 # low levels cannot skip this monster
_monster_floats= 0x40 # exclusive from flys; forces the monster to take +∂h gradually
_monster_cannot_attack= 0x80 # monster has no weapons and cannot attack (runs constantly to safety)
_monster_uses_sniper_ledges= 0x100 # sit on ledges and hurl shit at the player (ranged attack monsters only)
_monster_is_invisible= 0x200 # this monster uses _xfer_invisibility
_monster_is_subtly_invisible= 0x400 # this monster uses _xfer_subtle_invisibility
_monster_is_kamakazi= 0x800 # monster does shrapnel damage and will suicide if close enough to target
_monster_is_berserker= 0x1000 # below 1/4 vitality this monster goes berserk
_monster_is_enlarged= 0x2000 # monster is 1.25 times normal height
_monster_has_delayed_hard_death= 0x4000 # always dies soft, then switches to hard
_monster_fires_symmetrically= 0x8000 # fires at ±dy, simultaneously
_monster_has_nuclear_hard_death= 0x10000 # player’s screen whites out and slowly recovers
_monster_cant_fire_backwards= 0x20000 # monster can’t turn more than 135° to fire
_monster_can_die_in_flames= 0x40000 # uses humanoid flaming body shape
_monster_waits_with_clear_shot= 0x80000 # will sit and fire (slowly) if we have a clear shot
_monster_is_tiny= 0x100000 # 0.25-size normal height
_monster_attacks_immediately= 0x200000 # monster will try an attack immediately
_monster_is_not_afraid_of_water= 0x400000
_monster_is_not_afraid_of_sewage= 0x800000
_monster_is_not_afraid_of_lava= 0x1000000
_monster_is_not_afraid_of_goo= 0x2000000
_monster_can_teleport_under_media= 0x4000000
_monster_chooses_weapons_randomly= 0x8000000
# monsters unable to open doors have door retry masks of NONE
# monsters unable to switch levels have min,max ledge deltas of 0
# monsters unstopped by bullets have hit frames of NONE

# pseudo flags set when reading Marathon 1 physics
_monster_weaknesses_cause_soft_death = 0x10000000
_monster_screams_when_crushed = 0x20000000
_monster_makes_sound_when_activated = 0x40000000 # instead of when locking on a target
_monster_can_grenade_climb = 0x80000000 # only applies to player

# weapon flags
_no_flags= 0x0
_weapon_is_automatic= 0x01
_weapon_disappears_after_use= 0x02
_weapon_plays_instant_shell_casing_sound= 0x04
_weapon_overloads= 0x08
_weapon_has_random_ammo_on_pickup= 0x10
_powerup_is_temporary= 0x20
_weapon_reloads_in_one_hand= 0x40
_weapon_fires_out_of_phase= 0x80
_weapon_fires_under_media= 0x100
_weapon_triggers_share_ammo= 0x200
_weapon_secondary_has_angular_flipping= 0x400

# definitions for Marathon compatibility
_weapon_disappears_after_use_m1 = 0x04
_weapon_is_marathon_1 = 0x1000
_weapon_flutters_while_firing = 0x2000

# weapon classes
_melee_class = 0x0 # normal weapon, no ammunition, both triggers do the same thing
_normal_class = 0x1 # normal weapon, one ammunition type, both triggers do the same thing
_dual_function_class = 0x2 # normal weapon, one ammunition type, trigger does something different
_twofisted_pistol_class = 0x3 # two can be held at once (differnet triggers), same ammunition
# two weapons in one (assault rifle, grenade launcher), two different
# ammunition types with two separate triggers; secondary ammunition is discrete
# (i.e., it is never loaded explicitly but appears in the weapon)
_multipurpose_class = 0x4

# Weapons
_weapon_fist = 0x0
_weapon_pistol = 0x1
_weapon_plasma_pistol = 0x2
_weapon_assault_rifle = 0x3
_weapon_missile_launcher = 0x4
_weapon_flamethrower = 0x5
_weapon_alien_shotgun = 0x6
_weapon_shotgun = 0x7
_weapon_ball = 0x8 # or something
# LP addition:
_weapon_smg = 0x9
MAXIMUM_NUMBER_OF_WEAPONS = 0xa

_weapon_doublefisted_pistols = MAXIMUM_NUMBER_OF_WEAPONS # This is a pseudo-weapon
_weapon_doublefisted_shotguns = 0xb
PLAYER_TORSO_SHAPE_COUNT = 0xc


def ReadUint32(buffer):
    return ReadPacked('>L', 4, buffer)

def ReadSint32(buffer):
    return ReadPacked('>l', 4, buffer)

def ReadUint16(buffer):
    return ReadPacked('>H', 2, buffer)

def ReadSint16(buffer):
    return ReadPacked('>h', 2, buffer)

def ReadUint8(buffer):
    return ReadPacked('B', 1, buffer)

def ReadFixed(buffer):
    return ReadSint32(buffer) / 65536.0

def ReadWorldDistance(buffer):
    return ReadSint16(buffer) / 1024.0

def ReadShapeDescriptor(buffer):
    return ReadUint16(buffer)

def ReadPadding(size, buffer):
    ReadRaw(size, buffer)

def ReadPacked(template, size, buffer):
    return struct.unpack(template, buffer.read(size))[0]

def ReadFixedString(size, buffer):
    if size <= 0:
        return ''
    return ReadRaw(size, buffer).rstrip(b'\0').decode('Macroman')

def ReadRaw(size, buffer):
    return struct.unpack('{}s'.format(size), buffer.read(size))[0]

def parse_monster(record_index, f):
    data = {}
    data['collection'] = ReadSint16(f)

    data['vitality'] = ReadSint16(f)
    data['immunities'] = ReadUint32(f)
    data['weaknesses'] = ReadUint32(f)
    data['flags'] = ReadUint32(f)
    data['_class'] = ReadSint32(f)
    data['friends'] = ReadSint32(f)
    data['enemies'] = ReadSint32(f) # bit fields of what classes we consider friendly and what types we don’t like

    data['sound_pitch'] = ReadSint32(f)
    data['activation_sound'] = ReadSint16(f)
    data['friendly_activation_sound'] = ReadSint16(f)
    data['clear_sound'] = ReadSint16(f)
    data['kill_sound'] = ReadSint16(f)
    data['apology_sound'] = ReadSint16(f)
    data['friendly_fire_sound'] = ReadSint16(f)

    data['flaming_sound'] = ReadSint16(f) # the scream we play when we go down in flames
    data['random_sound'] = ReadSint16(f)
    data['random_sound_mask'] = ReadSint16(f) # if moving and locked play this sound if we get time and our mask comes up

    data['carrying_item_type'] = ReadSint16(f) # an item type we might drop if we don’t explode

    data['radius'] = ReadWorldDistance(f)
    data['height'] = ReadWorldDistance(f)
    data['preferred_hover_height'] = ReadWorldDistance(f)
    data['minimum_ledge_delta'] = ReadWorldDistance(f)
    data['maximum_ledge_delta'] = ReadWorldDistance(f)
    data['external_velocity_scale'] = ReadFixed(f)

    data['impact_effect'] = ReadSint16(f)
    data['melee_impact_effect'] = ReadSint16(f)
    data['contrail_effect'] = ReadSint16(f)

    data['half_visual_arc'] = ReadSint16(f)
    data['half_vertical_visual_arc'] = ReadSint16(f)
    data['visual_range'] = ReadWorldDistance(f)
    data['dark_visual_range'] = ReadWorldDistance(f)
    data['intelligence'] = ReadSint16(f)
    data['speed'] = ReadSint16(f)
    data['gravity'] = ReadSint16(f)
    data['terminal_velocity'] = ReadSint16(f)
    data['door_retry_mask'] = ReadSint16(f)
    data['shrapnel_radius'] = ReadSint16(f) # no shrapnel if NONE

    data['shapnel_damage'] = unpack_damage_definition(1, f)

    # shape_descriptor
    data['hit_shapes'] = ReadShapeDescriptor(f)
    data['hard_dying_shape'] = ReadShapeDescriptor(f)
    data['soft_dying_shape'] = ReadShapeDescriptor(f) # minus dead frame
    data['hard_dead_shapes'] = ReadShapeDescriptor(f)
    data['soft_dead_shapes'] = ReadShapeDescriptor(f) # NONE for vanishing
    data['stationary_shape'] = ReadShapeDescriptor(f)
    data['moving_shape'] = ReadShapeDescriptor(f)
    data['teleport_in_shape'] = ReadShapeDescriptor(f)
    data['teleport_out_shape'] = ReadShapeDescriptor(f)

    # which type of attack the monster actually uses is determined at attack time; typically
    # melee attacks will occur twice as often as ranged attacks because the monster will be
    # stopped (and stationary monsters attack twice as often as moving ones)
    data['attack_frequency'] = ReadSint16(f)

    data['melee_attack'] = unpack_attack_definition(f)
    data['ranged_attack'] = unpack_attack_definition(f)

    unpack_shape_info(data)

    return data

def parse_effects(record_index, f):
    return {
        'collection': ReadSint16(f),
        'shape': ReadSint16(f),

        'sound_pitch': ReadSint32(f),

        'flags': ReadUint16(f),
        'delay': ReadSint16(f),
        'delay_sound': ReadSint16(f),
    }

def parse_projectile(record_index, f):
    return {
        'collection': ReadSint16(f), # collection can be NONE (invisible)
        'shape': ReadSint16(f),
        'detonation_effect': ReadSint16(f),
        'media_detonation_effect': ReadSint16(f),

        'contrail_effect': ReadSint16(f),
        'ticks_between_contrails': ReadSint16(f),
        'maximum_contrails': ReadSint16(f), # maximum of NONE is infinite

        'media_projectile_promotion': ReadSint16(f),

        'radius': ReadWorldDistance(f), # can be zero and will still hit
        'area_of_effect': ReadWorldDistance(f), # one target if ==0
        'damage': unpack_damage_definition(1,f)[0],

        'flags': ReadUint32(f),

        'speed': ReadWorldDistance(f),
        'maximum_range': ReadWorldDistance(f),

        'sound_pitch': ReadFixed(f),
        'flyby_sound': ReadSint16(f),
        'rebound_sound': ReadSint16(f),
    }

def parse_physics(record_index, f):
    data = parse_common_physics(record_index, f)
    data['splash_height'] = ReadFixed(f)
    data['half_camera_separation'] = ReadFixed(f)
    return data

NUMBER_OF_TRIGGERS = 2

def parse_weapons(record_index, f):
    data = {}

    for k in [
        'item_type',
        'powerup_type',
        'weapon_class',
        'flags',
    ]:
        data[k] = ReadSint16(f)

    data['firing_light_intensity'] = ReadFixed(f)
    data['firing_intensity_decay_ticks'] = ReadSint16(f)

    # weapon will come up to FIXED_ONE when fired; idle_height±bob_amplitude
    # should be in the range [0,FIXED_ONE]
    for k in [
        'idle_height',
        'bob_amplitude',
        'kick_height',
        'reload_height',
        'idle_width',
        'horizontal_amplitude',
    ]:
        data[k] = ReadFixed(f)

    # each weapon has three basic animations: idle, firing and reloading.
    # sounds and frames are pulled from the shape collection.  for automatic
    # weapons the firing animation loops until the trigger is released or the
    # gun is empty and the gun begins rising as soon as the trigger is
    # depressed and is not lowered until the firing animation stops.  for
    # single shot weapons the animation loops once; the weapon is raised and
    # lowered as soon as the firing animation terminates
    for k in [
        'collection',
        'idle_shape',
        'firing_shape',
        'reloading_shape',
        'unused',
        'charging_shape',
        'charged_shape',
    ]:
        data[k] = ReadSint16(f)

    # How long does it take to ready the weapon?
    # load_rounds_tick is the point which you actually load them.
    for k in [
        'ready_ticks',
        'await_reload_ticks',
        'loading_ticks',
        'finish_loading_ticks',
        'powerup_ticks',
    ]:
        data[k] = ReadSint16(f)

    data['weapons_by_trigger'] = []
    for i in range(NUMBER_OF_TRIGGERS):
        data['weapons_by_trigger'].append(unpack_trigger_definitions(f))

    return data

def unpack_trigger_definitions(f):
    return {
        'rounds_per_magazine': ReadSint16(f),
        'ammunition_type': ReadSint16(f),
        'ticks_per_round': ReadSint16(f),
        'recovery_ticks': ReadSint16(f),
        'charging_ticks': ReadSint16(f),
        'recoil_magnitude': ReadWorldDistance(f),
        'firing_sound': ReadSint16(f),
        'click_sound': ReadSint16(f),
        'charging_sound': ReadSint16(f),
        'shell_casing_sound': ReadSint16(f),
        'reloading_sound': ReadSint16(f),
        'charged_sound': ReadSint16(f),
        'projectile_type': ReadSint16(f),
        'theta_error': ReadSint16(f),
        'dx': ReadSint16(f),
        'dz': ReadSint16(f),
        'shell_casing_type': ReadSint16(f),
        'burst_count': ReadSint16(f),
        'sound_activation_range': 0 # for Marathon compatibility
    }


def parse_m1_monster(record_index, f):
    data = {}
    data['collection'] = ReadSint16(f)

    data['vitality'] = ReadSint16(f)
    data['immunities'] = ReadUint32(f)
    data['weaknesses'] = ReadUint32(f)
    data['flags'] = ReadUint32(f)
    data['_class'] = ReadSint32(f)
    data['friends'] = ReadSint32(f)
    data['enemies'] = ReadSint32(f) # bit fields of what classes we consider friendly and what types we don’t like

    data['sound_pitch'] = FIXED_ONE
    data['activation_sound'] = ReadSint16(f)
    data['conversation_sound'] = ReadSint16(f)

    # Marathon doesn't have these
    data['friendly_activation_sound'] = None
    data['clear_sound'] = None
    data['kill_sound'] = None
    data['apology_sound'] = None
    data['friendly_fire_sound'] = None

    data['flaming_sound'] = ReadSint16(f) # the scream we play when we go down in flames
    data['random_sound'] = ReadSint16(f)
    data['random_sound_mask'] = ReadSint16(f) # if moving and locked play this sound if we get time and our mask comes up

    data['carrying_item_type'] = ReadSint16(f) # an item type we might drop if we don’t explode

    data['radius'] = ReadWorldDistance(f)
    data['height'] = ReadWorldDistance(f)
    data['preferred_hover_height'] = ReadWorldDistance(f)
    data['minimum_ledge_delta'] = ReadWorldDistance(f)
    data['maximum_ledge_delta'] = ReadWorldDistance(f)
    data['external_velocity_scale'] = ReadFixed(f)

    data['impact_effect'] = ReadSint16(f)
    data['melee_impact_effect'] = ReadSint16(f)
    data['contrail_effect'] = None

    data['half_visual_arc'] = ReadSint16(f)
    data['half_vertical_visual_arc'] = ReadSint16(f)
    data['visual_range'] = ReadWorldDistance(f)
    data['dark_visual_range'] = ReadWorldDistance(f)
    data['intelligence'] = ReadSint16(f)
    data['speed'] = ReadSint16(f)
    data['gravity'] = ReadSint16(f)
    data['terminal_velocity'] = ReadSint16(f)
    data['door_retry_mask'] = ReadSint16(f)
    data['shrapnel_radius'] = ReadSint16(f) # no shrapnel if NONE

    data['shapnel_damage'] = unpack_damage_definition(1, f)

    # shape_descriptor
    data['hit_shapes'] = ReadShapeDescriptor(f)
    data['hard_dying_shape'] = ReadShapeDescriptor(f)
    data['soft_dying_shape'] = ReadShapeDescriptor(f) # minus dead frame
    data['hard_dead_shapes'] = ReadShapeDescriptor(f)
    data['soft_dead_shapes'] = ReadShapeDescriptor(f) # NONE for vanishing
    data['stationary_shape'] = ReadShapeDescriptor(f)
    data['moving_shape'] = ReadShapeDescriptor(f)
    data['teleport_in_shape'] = data['stationary_shape']
    data['teleport_out_shape'] = data['teleport_in_shape']

    # which type of attack the monster actually uses is determined at attack time; typically
    # melee attacks will occur twice as often as ranged attacks because the monster will be
    # stopped (and stationary monsters attack twice as often as moving ones)
    data['attack_frequency'] = ReadSint16(f)

    data['melee_attack'] = unpack_attack_definition(f)
    data['ranged_attack'] = unpack_attack_definition(f)

    data['flags'] |= _monster_weaknesses_cause_soft_death
    data['flags'] |= _monster_screams_when_crushed
    data['flags'] |= _monster_makes_sound_when_activated
    data['flags'] |= _monster_can_grenade_climb

    unpack_shape_info(data)

    return data

def unpack_shape_info(data):
    data['shape_info'] = {}
    data['shape_info']['general'] = {
        'collection': get_collection(data['collection']),
        'clut': get_collection_clut(data['collection']),
    }
    for shape in [
        'hit_shapes',
        'hard_dying_shape',
        'soft_dying_shape',
        'hard_dead_shapes',
        'soft_dead_shapes',
        'stationary_shape',
        'moving_shape',
        'teleport_in_shape',
        'teleport_out_shape',
    ]:
        data['shape_info'][shape] = {
            'shape': get_descriptor_shape(data[shape]),
            'collection': get_descriptor_collection(data[shape]),
        }

def unpack_attack_definition(f):
    data = {}
    data['type'] = ReadSint16(f)
    data['repetitions'] = ReadSint16(f)
    data['error'] = ReadSint16(f) # ±error is added to the firing angle
    data['range'] = ReadWorldDistance(f) # beyond which we cannot attack
    data['attack_shape'] = ReadSint16(f) # attack occurs when keyframe is displayed
    data['dx'] = ReadWorldDistance(f)
    data['dy'] = ReadWorldDistance(f)
    data['dz'] = ReadWorldDistance(f) # +dy is right, +dx is out, +dz is up
    return data

def unpack_damage_definition(record_count, f):
    data = []
    for i in range(record_count):
        data.append({
            'type': ReadSint16(f),
            'flags': ReadSint16(f),
            'base': ReadSint16(f),
            'random': ReadSint16(f),
            'scale': ReadFixed(f),
        })
    return data

def parse_m1_effects(record_index, f):
    return {
        'collection': ReadSint16(f),
        'shape': ReadSint16(f),

        'sound_pitch': FIXED_ONE,

        'flags': ReadUint16(f),
        'delay': 0,
        'delay_sound': None,
    }

_damage_projectile = 0x02
_bleeding_projectile = 0x20000

def parse_m1_projectile(record_index, f):
    data = {}
    data['collection'] = ReadSint16(f) # collection can be NONE (invisible)
    data['shape'] = ReadSint16(f)
    data['detonation_effect'] = ReadSint16(f)
    data['media_detonation_effect'] = None

    data['contrail_effect'] = ReadSint16(f)
    data['ticks_between_contrails'] = ReadSint16(f)
    data['maximum_contrails'] = ReadSint16(f) # maximum of NONE is infinite

    data['media_projectile_promotion'] = 0

    data['radius'] = ReadWorldDistance(f) # can be zero and will still hit
    data['area_of_effect'] = ReadWorldDistance(f) # one target if ==0

    data['damage'] = unpack_damage_definition(1, f)[0]

    data['flags'] = ReadUint16(f)

    data['speed'] = ReadWorldDistance(f)
    data['maximum_range'] = ReadWorldDistance(f)

    data['sound_pitch'] = FIXED_ONE
    data['flyby_sound'] = ReadSint16(f)
    data['rebound_sound'] = None

    if data['damage']['type'] == _damage_projectile:
        data['flags'] |= _bleeding_projectile;

    return data

def parse_common_physics(record_index, f):
    physics_keys = [
        'maximum_forward_velocity',
        'maximum_backward_velocity',
        'maximum_perpendicular_velocity',

         # forward, backward and perpendicular
        'acceleration',
        'deceleration',
        'airborne_deceleration',

        'gravitational_acceleration',
        'climbing_acceleration',
        'terminal_velocity',

        'external_deceleration',

        'angular_acceleration',
        'angular_deceleration',
        'maximum_angular_velocity',
        'angular_recentering_velocity',

        # for head movements
        'fast_angular_velocity',
        'fast_angular_maximum',

        # positive and negative
        'maximum_elevation',
        'external_angular_deceleration',

        # step_length is distance between adjacent nodes in the actor’s phase
        'step_delta',
        'step_amplitude',
        'radius',
        'height',
        'dead_height',
        'camera_height',
    ]
    return {k:ReadFixed(f) for k in physics_keys}

def parse_m1_physics(record_index, f):
    data = parse_common_physics(record_index, f)
    data['splash_height'] = 0
    data['half_camera_separation'] = ReadFixed(f)
    return data

def parse_m1_weapons(record_index, f):
    data = {}
    data['weapons_by_trigger'] = []

    data['item_type'] = ReadSint16(f)
    data['powerup_type'] = None
    data['weapon_class'] = ReadSint16(f)
    data['flags'] = ReadSint16(f)

    data['weapons_by_trigger'].append({})
    data['weapons_by_trigger'].append({})
    data['weapons_by_trigger'][0]['ammunition_type'] = ReadSint16(f)
    data['weapons_by_trigger'][0]['rounds_per_magazine'] = ReadSint16(f)
    data['weapons_by_trigger'][1]['ammunition_type'] = ReadSint16(f)
    data['weapons_by_trigger'][1]['rounds_per_magazine'] = ReadSint16(f)

    data['firing_light_intensity'] = ReadFixed(f)
    data['firing_intensity_decay_ticks'] = ReadSint16(f)

    # weapon will come up to FIXED_ONE when fired; idle_height±bob_amplitude
    # should be in the range [0,FIXED_ONE]
    data['idle_height'] = ReadFixed(f)
    data['bob_amplitude'] = ReadFixed(f)
    data['kick_height'] = ReadFixed(f)
    data['reload_height'] = ReadFixed(f)
    data['idle_width'] = ReadFixed(f)
    data['horizontal_amplitude'] = ReadFixed(f)

    # each weapon has three basic animations: idle, firing and reloading.
    # sounds and frames are pulled from the shape collection.  for automatic
    # weapons the firing animation loops until the trigger is released or the
    # gun is empty and the gun begins rising as soon as the trigger is
    # depressed and is not lowered until the firing animation stops.  for
    # single shot weapons the animation loops once; the weapon is raised and
    # lowered as soon as the firing animation terminates
    data['collection'] = ReadSint16(f)
    data['idle_shape'] = ReadSint16(f)
    data['firing_shape'] = ReadSint16(f)
    data['reloading_shape'] = ReadSint16(f)
    data['unused'] = ReadSint16(f)
    data['charging_shape'] = ReadSint16(f)
    data['charged_shape'] = ReadSint16(f)

    data['weapons_by_trigger'][0]['ticks_per_round'] = ReadSint16(f)
    data['weapons_by_trigger'][1]['ticks_per_round'] = ReadSint16(f)

    # How long does it take to ready the weapon?
    # load_rounds_tick is the point which you actually load them.
    data['await_reload_ticks'] = ReadSint16(f)
    data['ready_ticks'] = ReadSint16(f)
    data['loading_ticks'] = 0
    data['finish_loading_ticks'] = 0

    data['weapons_by_trigger'][0]['recovery_ticks'] = ReadSint16(f)
    data['weapons_by_trigger'][1]['recovery_ticks'] = ReadSint16(f)
    data['weapons_by_trigger'][0]['charging_ticks'] = ReadSint16(f)
    data['weapons_by_trigger'][1]['charging_ticks'] = ReadSint16(f)

    data['weapons_by_trigger'][0]['recoil_magnitude'] = ReadSint16(f)
    data['weapons_by_trigger'][1]['recoil_magnitude'] = ReadSint16(f)

    data['weapons_by_trigger'][0]['firing_sound'] = ReadSint16(f)
    data['weapons_by_trigger'][1]['firing_sound'] = ReadSint16(f)
    data['weapons_by_trigger'][0]['click_sound'] = ReadSint16(f)
    data['weapons_by_trigger'][1]['click_sound'] = ReadSint16(f)

    data['weapons_by_trigger'][0]['reloading_sound'] = ReadSint16(f)
    data['weapons_by_trigger'][1]['reloading_sound'] = None

    data['weapons_by_trigger'][0]['charging_sound'] = ReadSint16(f)
    data['weapons_by_trigger'][1]['charging_sound'] = data['weapons_by_trigger'][0]['charging_sound']

    data['weapons_by_trigger'][0]['shell_casing_sound'] = ReadSint16(f)
    data['weapons_by_trigger'][1]['shell_casing_sound'] = ReadSint16(f)

    data['weapons_by_trigger'][0]['sound_activation_range'] = ReadSint16(f)
    data['weapons_by_trigger'][1]['sound_activation_range'] = ReadSint16(f)

    data['weapons_by_trigger'][0]['projectile_type'] = ReadSint16(f)
    data['weapons_by_trigger'][1]['projectile_type'] = ReadSint16(f)

    data['weapons_by_trigger'][0]['theta_error'] = ReadSint16(f)
    data['weapons_by_trigger'][1]['theta_error'] = ReadSint16(f)

    data['weapons_by_trigger'][0]['dx'] = ReadSint16(f)
    data['weapons_by_trigger'][0]['dz'] = ReadSint16(f)
    data['weapons_by_trigger'][1]['dx'] = ReadSint16(f)
    data['weapons_by_trigger'][1]['dz'] = ReadSint16(f)

    data['weapons_by_trigger'][0]['burst_count'] = ReadSint16(f)
    data['weapons_by_trigger'][1]['burst_count'] = ReadSint16(f)

    ReadPadding(2,f) # instant reload tick

    data['weapons_by_trigger'][0]['charged_sound'] = None
    data['weapons_by_trigger'][1]['charged_sound'] = None
    data['weapons_by_trigger'][0]['shell_casing_type'] = None
    data['weapons_by_trigger'][1]['shell_casing_type'] = None

    if data['flags'] & _weapon_disappears_after_use_m1:
        data['flags'] |= _weapon_disappears_after_use
        data['flags'] &= ~_weapon_disappears_after_use_m1

    if data['weapon_class'] == _twofisted_pistol_class:
        # Marathon's settings for trigger 1 are mostly empty
        data['flags'] |= _weapon_fires_out_of_phase
        dx = data['weapons_by_trigger'][1]['dx']
        dz = data['weapons_by_trigger'][1]['dz']
        data['weapons_by_trigger'][1] = data['weapons_by_trigger'][0]
        data['weapons_by_trigger'][1]['dx'] = dx
        data['weapons_by_trigger'][1]['dz'] = dz

    elif data['weapon_class'] == _dual_function_class:
        # triggers share ammo must have been
        # hard-coded for dual function weapons in
        # Marathon; also, Marathon 2 expects rounds
        # per magazine and ammunition type to match
        data['flags'] |= _weapon_triggers_share_ammo
        data['weapons_by_trigger'][1]['rounds_per_magazine'] = data['weapons_by_trigger'][0]['rounds_per_magazine']
        data['weapons_by_trigger'][1]['ammunition_type'] = data['weapons_by_trigger'][0]['ammunition_type']

    # automatic weapons in Marathon flutter while firing
    if data['flags'] & _weapon_is_automatic:
        data['flags'] |= _weapon_flutters_while_firing

    # this makes the TOZT render correctly, but we don't
    # want it to flutter so apply after the above statement
    if data['weapons_by_trigger'][0]['recovery_ticks'] == 0:
        data['flags'] |= _weapon_is_automatic

    # SPNKR doesn't have a firing shape, just use idle
    if data['firing_shape'] == None:
        data['firing_shape'] = data['idle_shape']

    if record_index == _weapon_alien_shotgun:
        # is there a better way?
        data['flags'] |= _weapon_has_random_ammo_on_pickup

    data['flags'] |= _weapon_is_marathon_1

    return data

M1_TAGS = [
    'mons',
    'effe',
    'proj',
    'phys',
    'weap',
]

TAG_MAP = {
    'MNpx': {'label':'monster', 'parser': parse_monster},
    'FXpx': {'label':'effects', 'parser': parse_effects},
    'PRpx': {'label':'projectile', 'parser': parse_projectile},
    'PXpx': {'label':'physics', 'parser': parse_physics},
    'WPpx': {'label':'weapons', 'parser': parse_weapons},

    'mons': {'label':'monster', 'parser': parse_m1_monster},
    'effe': {'label':'effects', 'parser': parse_m1_effects},
    'proj': {'label':'projectile', 'parser': parse_m1_projectile},
    'phys': {'label':'physics', 'parser': parse_m1_physics},
    'weap': {'label':'weapons', 'parser': parse_m1_weapons},
}

def read_physics(args, f):
    f.seek(0, 2)
    eof = f.tell()
    f.seek(0, 0)

    tag = ReadRaw(4, f).decode('Macroman')
    f.seek(0, 0)

    if tag in M1_TAGS:
        read_physics_m1(f, eof)
        return
    read_physics_(f, eof)

def read_physics_m1(f, eof):
    data = {}
    while (True):
        print ('of:{}'.format(f.tell()))
        tag = ReadRaw(4, f).decode('Macroman')

        if tag not in TAG_MAP:
            print ('error: offset: {}, tag: {}'.format(f.tell(), tag.encode()))
            sys.exit()
        label = TAG_MAP[tag]['label']

        ReadPadding(4, f) # unused
        record_count = ReadUint16(f)
        size = ReadUint16(f)

        data[tag] = {
            'count': record_count,
            'size': size,
            label: [],
        }

        for i in range(record_count):
            data[tag][label].append(TAG_MAP[tag]['parser'](i, f))
            if not data[tag][label][-1]:
#                 print ('skipping: {}'.format(size))
                f.seek(size, 1)
                continue
            data[tag][label][-1]['index'] = i

#         if tag == 'phys':
#             data[tag][label].pop(0)

        if f.tell() == eof:
            break

    if 'json' == args.output:
        print (json.dumps(data))
        return
    if 'xml' == args.output:
        print (dict2xml(data, root_node='physics'))
        return

# enum /* monster types */
# {
# 	_monster_marine,
# 	_monster_tick_energy,
# 	_monster_tick_oxygen,
# 	_monster_tick_kamakazi,
# 	_monster_compiler_minor,
# 	_monster_compiler_major,
# 	_monster_compiler_minor_invisible,
# 	_monster_compiler_major_invisible,
# 	_monster_fighter_minor,
# 	_monster_fighter_major,
# 	_monster_fighter_minor_projectile,
# 	_monster_fighter_major_projectile,
# 	_civilian_crew,
# 	_civilian_science,
# 	_civilian_security,
# 	_civilian_assimilated,
# 	_monster_hummer_minor, // slow hummer
# 	_monster_hummer_major, // fast hummer
# 	_monster_hummer_big_minor, // big hummer
# 	_monster_hummer_big_major, // angry hummer
# 	_monster_hummer_possessed, // hummer from durandal
# 	_monster_cyborg_minor,
# 	_monster_cyborg_major,
# 	_monster_cyborg_flame_minor,
# 	_monster_cyborg_flame_major,
# 	_monster_enforcer_minor,
# 	_monster_enforcer_major,
# 	_monster_hunter_minor,
# 	_monster_hunter_major,
# 	_monster_trooper_minor,
# 	_monster_trooper_major,
# 	_monster_mother_of_all_cyborgs,
# 	_monster_mother_of_all_hunters,
# 	_monster_sewage_yeti,
# 	_monster_water_yeti,
# 	_monster_lava_yeti,
# 	_monster_defender_minor,
# 	_monster_defender_major,
# 	_monster_juggernaut_minor,
# 	_monster_juggernaut_major,
# 	_monster_tiny_fighter,
# 	_monster_tiny_bob,
# 	_monster_tiny_yeti,
# 	// LP addition:
# 	_civilian_fusion_crew,
# 	_civilian_fusion_science,
# 	_civilian_fusion_security,
# 	_civilian_fusion_assimilated,
# 	NUMBER_OF_MONSTER_TYPES
# };
NUMBER_OF_MONSTER_TYPES = 47

# enum /* effect types */
# {
# 	_effect_rocket_explosion,
# 	_effect_rocket_contrail,
# 	_effect_grenade_explosion,
# 	_effect_grenade_contrail,
# 	_effect_bullet_ricochet,
# 	_effect_alien_weapon_ricochet,
# 	_effect_flamethrower_burst,
# 	_effect_fighter_blood_splash,
# 	_effect_player_blood_splash,
# 	_effect_civilian_blood_splash,
# 	_effect_assimilated_civilian_blood_splash,
# 	_effect_enforcer_blood_splash,
# 	_effect_compiler_bolt_minor_detonation,
# 	_effect_compiler_bolt_major_detonation,
# 	_effect_compiler_bolt_major_contrail,
# 	_effect_fighter_projectile_detonation,
# 	_effect_fighter_melee_detonation,
# 	_effect_hunter_projectile_detonation,
# 	_effect_hunter_spark,
# 	_effect_minor_fusion_detonation,
# 	_effect_major_fusion_detonation,
# 	_effect_major_fusion_contrail,
# 	_effect_fist_detonation,
# 	_effect_minor_defender_detonation,
# 	_effect_major_defender_detonation,
# 	_effect_defender_spark,
# 	_effect_trooper_blood_splash,
# 	_effect_water_lamp_breaking,
# 	_effect_lava_lamp_breaking,
# 	_effect_sewage_lamp_breaking,
# 	_effect_alien_lamp_breaking,
# 	_effect_metallic_clang,
# 	_effect_teleport_object_in,
# 	_effect_teleport_object_out,
# 	_effect_small_water_splash,
# 	_effect_medium_water_splash,
# 	_effect_large_water_splash,
# 	_effect_large_water_emergence,
# 	_effect_small_lava_splash,
# 	_effect_medium_lava_splash,
# 	_effect_large_lava_splash,
# 	_effect_large_lava_emergence,
# 	_effect_small_sewage_splash,
# 	_effect_medium_sewage_splash,
# 	_effect_large_sewage_splash,
# 	_effect_large_sewage_emergence,
# 	_effect_small_goo_splash,
# 	_effect_medium_goo_splash,
# 	_effect_large_goo_splash,
# 	_effect_large_goo_emergence,
# 	_effect_minor_hummer_projectile_detonation,
# 	_effect_major_hummer_projectile_detonation,
# 	_effect_durandal_hummer_projectile_detonation,
# 	_effect_hummer_spark,
# 	_effect_cyborg_projectile_detonation,
# 	_effect_cyborg_blood_splash,
# 	_effect_minor_fusion_dispersal,
# 	_effect_major_fusion_dispersal,
# 	_effect_overloaded_fusion_dispersal,
# 	_effect_sewage_yeti_blood_splash,
# 	_effect_sewage_yeti_projectile_detonation,
# 	_effect_water_yeti_blood_splash,
# 	_effect_lava_yeti_blood_splash,
# 	_effect_lava_yeti_projectile_detonation,
# 	_effect_yeti_melee_detonation,
# 	_effect_juggernaut_spark,
# 	_effect_juggernaut_missile_contrail,
# 	// LP addition: Jjaro stuff
# 	_effect_small_jjaro_splash,
# 	_effect_medium_jjaro_splash,
# 	_effect_large_jjaro_splash,
# 	_effect_large_jjaro_emergence,
# 	_effect_civilian_fusion_blood_splash,
# 	_effect_assimilated_civilian_fusion_blood_splash,
# 	NUMBER_OF_EFFECT_TYPES
# };
NUMBER_OF_EFFECT_TYPES = 73

# enum /* projectile types */
# {
# 	_projectile_rocket,
# 	_projectile_grenade,
# 	_projectile_pistol_bullet,
# 	_projectile_rifle_bullet,
# 	_projectile_shotgun_bullet,
# 	_projectile_staff,
# 	_projectile_staff_bolt,
# 	_projectile_flamethrower_burst,
# 	_projectile_compiler_bolt_minor,
# 	_projectile_compiler_bolt_major,
# 	_projectile_alien_weapon,
# 	_projectile_fusion_bolt_minor,
# 	_projectile_fusion_bolt_major,
# 	_projectile_hunter,
# 	_projectile_fist,
# 	_projectile_armageddon_sphere,
# 	_projectile_armageddon_electricity,
# 	_projectile_juggernaut_rocket,
# 	_projectile_trooper_bullet,
# 	_projectile_trooper_grenade,
# 	_projectile_minor_defender,
# 	_projectile_major_defender,
# 	_projectile_juggernaut_missile,
# 	_projectile_minor_energy_drain,
# 	_projectile_major_energy_drain,
# 	_projectile_oxygen_drain,
# 	_projectile_minor_hummer,
# 	_projectile_major_hummer,
# 	_projectile_durandal_hummer,
# 	_projectile_minor_cyborg_ball,
# 	_projectile_major_cyborg_ball,
# 	_projectile_ball,
# 	_projectile_minor_fusion_dispersal,
# 	_projectile_major_fusion_dispersal,
# 	_projectile_overloaded_fusion_dispersal,
# 	_projectile_yeti,
# 	_projectile_sewage_yeti,
# 	_projectile_lava_yeti,
# 	// LP additions:
# 	_projectile_smg_bullet,
# 	NUMBER_OF_PROJECTILE_TYPES
# };
NUMBER_OF_PROJECTILE_TYPES = 39

# enum /* models */
# {
# 	_model_game_walking,
# 	_model_game_running,
# 	NUMBER_OF_PHYSICS_MODELS
# };
NUMBER_OF_PHYSICS_MODELS = 2

# static int16 weapon_ordering_array[]= {
# 	_weapon_fist,
# 	_weapon_pistol,
# 	_weapon_plasma_pistol,
# 	_weapon_shotgun,
# 	_weapon_assault_rifle,
# 	// LP addition:
# 	_weapon_smg,
# 	_weapon_flamethrower,
# 	_weapon_missile_launcher,
# 	_weapon_alien_shotgun,
# 	_weapon_ball
# };
# #define NUMBER_OF_WEAPONS 10
NUMBER_OF_WEAPONS = 10

COUNT_MAP = {
    'MNpx': NUMBER_OF_MONSTER_TYPES,
    'FXpx': NUMBER_OF_EFFECT_TYPES,
    'PRpx': NUMBER_OF_PROJECTILE_TYPES,
    'PXpx': NUMBER_OF_PHYSICS_MODELS,
    'WPpx': NUMBER_OF_WEAPONS,
}
SIZE_MAP = {
    'MNpx': 56,
    'FXpx': 14,
    'PRpx': 48,
    'PXpx': 104,
    'WPpx': 34,
}


def read_physics_(f, eof):
    data = {}
    while (True):
        print ('of:{}'.format(f.tell()))
        tag = ReadRaw(4, f).decode('Macroman')

        if tag not in TAG_MAP:
            print ('error: offset: {}, tag: {}'.format(f.tell(), tag.encode()))
            sys.exit()
        label = TAG_MAP[tag]['label']
        print ('{}:{}'.format(tag, label))

        next_offset = ReadUint32(f)
        length = ReadUint32(f)
        offset = ReadUint32(f)

        data[tag] = {
            'count': COUNT_MAP[tag],
            'size': length,
            label: [],
        }

        for i in range(COUNT_MAP[tag]):
            record = TAG_MAP[tag]['parser'](0,f)
            data[tag][label].append(record)
            data[tag][label][-1]['index'] = i
#             print ('{}/{}'.format(f.tell(), eof))
            if f.tell() + SIZE_MAP[tag] > eof:
                print ('file limit')
                print ('remaining: {}'.format(eof-f.tell()))
                break
            if next_offset != 0 and f.tell() + SIZE_MAP[tag] > next_offset:
                print ('section limit')
                print ('remaining: {}'.format(next_offset-f.tell()))
                break
        data[tag]['actual_count'] = len(data[tag][label])

        if next_offset == 0:
            break

        f.seek(next_offset, 0)
        continue

        if f.tell() == eof:
            break

    if 'json' == args.output:
        print (json.dumps(data))
        return
    if 'xml' == args.output:
        print (dict2xml(data, root_node='physics'))
        return

def dict2xml(d, root_node=None):
# https://gist.github.com/reimund/5435343/
    wrap          =     False if None == root_node or isinstance(d, list) else True
    root          = 'objects' if None == root_node else root_node
    root_singular = root[:-1] if 's' == root[-1] and None == root_node else root
    xml           = ''
    children      = []

    if isinstance(d, dict):
        for key, value in dict.items(d):
            if isinstance(value, dict):
                children.append(dict2xml(value, key))
            elif isinstance(value, list):
                children.append(dict2xml(value, key))
            else:
                xml = xml + ' ' + key + '="' + str(value) + '"'
    else:
        if not d:
            return
        for value in d:
            children.append(dict2xml(value, root_singular))

    end_tag = '>' if 0 < len(children) else ' />'

    if wrap or isinstance(d, dict):
        xml = '<' + root + xml + end_tag

    if 0 < len(children):
        for child in children:
            xml = xml + child

        if wrap or isinstance(d, dict):
            xml = xml + '</' + root + '>'

    return xml


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Convert physics to JSON')
    parser.add_argument( metavar='path', dest='pfile', type=str, help='a phys file')
    parser.add_argument('-j', '--json', dest='output', action='store_const', const='json', default='json', help='output json')
    parser.add_argument('-x', '--xml', dest='output', action='store_const', const='xml', help='output xml')
    args = parser.parse_args()

    with open (args.pfile, 'rb') as f:
        read_physics(args, f)
