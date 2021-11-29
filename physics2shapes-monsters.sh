#!/usr/bin/env bash

cat ../data/m1.phys.json |\
    jq '.mons.monster |
        .[] |
        {
            "class":"monster-\(.index)",
            "display": "",
            "collection":.shape_info.general.collection,
            "clut":.shape_info.general.clut,
            "stationary_shape":.shape_info.stationary_shape.shape,
            "image":"\(.shape_info.general.collection)/\(.shape_info.general.clut)/seq00\(.shape_info.stationary_shape.shape)-stationary-0.png"
        }'
