#!/usr/bin/env python

import argparse
import sys
import xmltodict
import json
from collections import defaultdict
import base64
import struct
import PIL
from PIL import Image
import numpy as np

def process_color_table(table, _):
    colors = list()
    for color in table['color']:
        color_index = color['@value']
        record = [
            color['@red']   / 65535,
            color['@green'] / 65535,
            color['@blue']  / 65535,
            0 if color_index < 3 else 1,
        ]
        colors.append(record)
    return colors

def process_bitmap(bitmap, collection_cache):
    if not bitmap['@width'] or not bitmap['@height']:
        return None
    color_table = collection_cache['color_table'][0]
    if bitmap['@column_order']:
        rowcount = bitmap['@width']
        rowlen = bitmap['@height']
    else:
        rowcount = bitmap['@height']
        rowlen = bitmap['@width']
    rpixels = base64.b64decode(bitmap['#text'])
    pixels = rpixels
    if bitmap['@bytes_per_row'] < 0:
        pixels = b''
        offset = 0
        for col in range(rowcount):
            first_row = struct.unpack('>H', rpixels[offset:offset+2])[0]
            offset += 2
            if first_row > 0:
                pixels += b'\x00' * first_row
            last_row = struct.unpack('>H', rpixels[offset:offset+2])[0]
            offset += 2
            if last_row > first_row:
                rsize = last_row - first_row
                pixels += rpixels[offset:offset+rsize]
                offset += rsize
            if last_row < rowlen:
                pixels += b'\x00' * (rowlen - last_row)
    unpacked_pixels = struct.unpack('>{}'.format('B'*len(pixels)), pixels)
    colored_pixels = list( map( lambda p: tuple( map( lambda c: int(c*255), color_table[p] ) ), unpacked_pixels ) )
    pixel_array = np.array(colored_pixels, dtype=np.uint8)
    pixel_matrix = pixel_array.reshape(rowcount, rowlen, 4)
    if bitmap['@column_order']:
        pixel_matrix = pixel_matrix.transpose((1,0,2))
    return Image.fromarray(pixel_matrix)

def process_low_level_shape(shape, collection_cache):
    bitmaps = collection_cache['bitmap']
    si = shape['@index']
    bi = shape['@bitmap_index']
    if bi < 0:
        return None
    if bi not in bitmaps:
        print ('missing bitmap ({}) for low_level_shape ({})'.format(bi, si))
        return None
    img = bitmaps[bi]
    if shape['@x_mirror']:
        img = img.transpose(PIL.Image.FLIP_LEFT_RIGHT)
    if shape['@y_mirror']:
        img = img.transpose(PIL.Image.FLIP_TOP_BOTTOM)
    return img

def process_high_level_shape(shape, collection_cache):
    lls = collection_cache['low_level_shape']
    si = shape['@index']
    frame_count = shape['@frames_per_view']
    if frame_count < 1:
        return None
    frames = shape['frame']
    if not isinstance(frames, list):
        frames = [frames]
    fi = 0
    img_frames = []
    for frame in frames:
        llsi = frame['@index']
        if llsi not in lls:
            print ('missing lls ({}) for high_level_shape ({}:{})'.format(llsi, si, fi))
            return None
        fi += 1
        img_frames.append(lls[llsi])
    if len(img_frames) == 0:
        return None
    if len(img_frames) == 1:
        print ('one frame')
        return None
    # Save into a GIF file that loops forever
    img_frames[0].save(
        'hls-{}.gif'.format(si), format='GIF',
        append_images=img_frames[1:],
        save_all=True,
        duration=300,
        loop=0,
        transparency=0,
        disposal=2)
    pass

TYPE_MAP = {
    'color_table': 'color',
    'high_level_shape': 'frame',
    'bitmap': None,
    'low_level_shape': None,
}

def reinterpret(thing):
    if isinstance(thing, dict):
        for key,val in thing.items():
            thing[key] = reinterpret(val)
        return thing
    if isinstance(thing, list) or isinstance(thing, set):
        for i in range(len(thing)):
            thing[i] = reinterpret(thing[i])
        return thing
    try:
        return int(thing)
    except:
        pass
    try:
        return float(thing)
    except:
        pass
    return thing


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='extract images from XML shapes file')
    parser.add_argument(metavar='path', dest='sfile', type=str, help='a shapes file')
    parser.add_argument('-a', '--all', action='store_true', default=False, help='output all bitmaps, low- and high- level images, and sequences')
    parser.add_argument('-B', '--bitmaps', action='store_const', dest='bitmap', const=-2, default=-1, help='output bitmaps')
    parser.add_argument('-F', '--frames', action='store_const', dest='low_level', const=-2, default=-1, help='output frames')
    parser.add_argument('-S', '--sequences', dest='high_level', action='store_const', const=-2, default=-1, help='output sequences')
    parser.add_argument('-c', '--collection', type=int, default=-1, help='which collection to use')
    parser.add_argument('-t', '--color-table', dest='color_table', type=int, default=-1, help='which color table to use')
    parser.add_argument('-b', '--bitmap', dest='bitmap', type=int, default=-1, help='which low level image to create')
    parser.add_argument('-l', '--low-level-image', dest='low_level_shape', type=int, default=-1, help='which low level image to create')
    parser.add_argument('-g', '--high-level-image', dest='high_level_shape', type=int, default=-1, help='which high level image to create')
    parser.add_argument('-f', '--frame', dest='frame', type=int, default=-1, help='which high level image frame to create')
    args = parser.parse_args()

    shapes = None
    with open(args.sfile, 'r') as fd:
        shapes = xmltodict.parse(fd.read())['shapes']
    shapes = reinterpret(shapes)
    for collection in shapes['collection']:
        if not args.all and args.collection != collection['@index']:
            continue
        print ('coll: {}'.format(collection['@index']))
        collection_cache = defaultdict(dict)
        for item_type in ['color_table', 'bitmap', 'low_level_shape', 'high_level_shape']:
            if item_type not in collection:
                continue
            if isinstance(collection[item_type], dict):
                collection[item_type] = [collection[item_type]]
            for item in collection[item_type]:
#                 if not args.all and vars(args)[item_type] != -2 and vars(args)[item_type] != item['@index']:
#                     continue
                processer = getattr(
                    sys.modules[__name__],
                    'process_{}'.format(item_type)
                )
                result = processer(item, collection_cache)
                if result:
                    collection_cache[item_type][item['@index']] = result
            if item_type == 'color_table' and not collection_cache[item_type]:
                print ('need to select at least 1 color_table')
