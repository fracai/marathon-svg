'use strict';

var maps_json = null;
var levels_json = null;
var level_json = null;
var level_MNov = null;
var overlay_json = null;
var overlay_style_map = {};

function load_common(path, callback, data_extractor) {
    // fetch the path
    return fetch(path)
        // handle any errors
        .then(response => {
            if (!response.ok) {
                throw new Error('HTTP error ' + response.status + ': ' + path);
            }
            return response;
        })
        // extract the data
        .then(data_extractor)
        // send the json data to the callback
        .then(callback)
        // handle exceptions
        .catch(err => {
            console.log(err);
            if (err.message.startsWith('HTTP error')) {
                return;
            }
            debugger;
        })
}

function load_json(path, callback) {
    return load_common(path, callback, r => r.json());
}
function load_path(path, callback) {
    return load_common(path, callback, r => r.body);
}

function fill_map_menu(selection) {
    const select = document.getElementById('select_map');
    select.options.length = 0;
    let map_tokens = [null,-1];
    if (null != selection) {
        const split_tokens = selection.split(':');
        const parsed = parseInt(split_tokens[1], 10);
        if (!isNaN(parsed)) {
            map_tokens = [split_tokens[0], parsed]
        }
    }
    let first = -1;
    for (const map of maps_json) {
        if (-1 == first) {
            if (null == map_tokens[0] || map_tokens[0] == map.short_name) {
                first = select.options.length;
            }
        }
        select.options[select.options.length] = new Option(
            map.map_name,
            select.options.length,
            false,
            false);
    }
    select.options.selectedIndex = first;
    load_levels(maps_json[first].map_info, map_tokens[1]);
}
function fill_level_menu(level_info, level_token) {
    levels_json = level_info;
    const select = document.getElementById('select_level');
    select.options.length = 0;
    let first = -1;
    for (const level of levels_json.levels) {
        if ('separator' in level) {
            const option = new Option(level.separator, null, false, false);
            option.disabled = true;
            select.options[select.options.length] = option;
            continue;
        }
        if (-1 == first) {
            if (typeof level_token === 'undefined' || 0 > level_token || level_token == level.index) {
                first = select.options.length;
            }
        }
        select.options[select.options.length] = new Option(
            level.index + " " + level.name,
            select.options.length,
            false,
            false);
    }
    select.options.selectedIndex = first;
    load_level(levels_json.levels[select.options[first].value].base_name);
}

function loaded() {
//     console.clear();
    const map_object = document.getElementById('map_object');
    map_object.addEventListener('load', () => {svg_loaded()});
    const url = window.location.href + ''
    const index = url.indexOf('#')
    let selection = null;
    if (index < 0) {
        selection = null
    } else {
        selection = url.substring(index+1)
    }
    load_json('maps.json', value => {
        maps_json = value;
        fill_map_menu(selection);
    });
}

function load_levels(path, level) {
    load_json(path+"/overlays.json", json => {
        overlay_json = json;
        build_overlay_style_map(overlay_json.types);
        populate_overlays();
    });
    load_json(path+"/map.json", json => fill_level_menu(json, level));
}
function populate_overlays() {
    if (null == overlay_json || null == level_json) {
        return;
    }
    let merged_overlays = overlay_json.types;
    if (null != level_MNov) {
        for (let i=0; i<merged_overlays.length; i+=1) {
            if ('monster' == merged_overlays[i].class) {
                merged_overlays[i].types = level_MNov.types;
            }
        }
    }
    const overlay_string = process_overlay_types(merged_overlays);
    const overlays_div = document.getElementById('overlays');
    overlays_div.innerHTML = '';
    if ('' == overlay_string) {
        return;
    }
    overlays_div.insertAdjacentHTML('afterbegin', overlay_string);
    apply_collapsible();
}
function process_overlay_types(types) {
    if (undefined == types) {
        return '';
    }
    let type_string = '';
    for (const type of types) {
        let display = type.display;
        if (undefined == display || '' == display) {
            display = type.class;
        }
        if (undefined == display || '' == display) {
            display = type.id;
        }
        if (undefined == display || '' == display) {
            display = type.selector;
        }
        let level_rebellion = 'rebellion' in level_json && level_json.rebellion;
        let type_rebellion = false;
        if ('rebellion' in type) {
            type_rebellion = type.rebellion;
        } else {
            type_rebellion = level_rebellion;
        }
        if (level_rebellion != type_rebellion) {
            continue;
        }
        let checkbox_string = null;
        let hover = ` onmouseover="hover_checkbox(this, null, 1)" onmouseout="hover_checkbox(this, null, 0)"`;
        const group_string = `<li><label${hover}><input type="checkbox" onchange="toggle_checkbox(this)" class="overlay" /> ${display}</label></li>\n`;
        if (level_json.overlays.classes.includes(type.class)) {
            if (type.class.endsWith('-computer_terminal')) {
                hover = ` onmouseover="hover_checkbox(this, 'panel-terminal_teleport', 1)" onmouseout="hover_checkbox(this, 'panel-terminal_teleport', 0)"`;
            } else if (type.class.endsWith('_switch')) {
                hover = ` onmouseover="hover_checkbox(this, '${type.class}', 1)" onmouseout="hover_checkbox(this, '${type.class}', 0)"`;
            }
            checkbox_string = `<li><label${hover}><input type="checkbox" id="class_${type.class}" class="overlay" onchange="toggle_checkbox(this)" /> ${display}</label></li>\n`;
        } else if (level_json.overlays.ids.includes(type.id)) {
            checkbox_string = `<li><label${hover}><input type="checkbox" id="id_${type.id}" class="overlay" onchange="toggle_checkbox(this)" /> ${display}</label></li>\n`;
        } else if (level_json.overlays.selectors.includes(type.selector)) {
            checkbox_string = `<li><label${hover}><input type="checkbox" id="selector_${type.selector}" class="overlay" onchange="toggle_checkbox(this)" /> ${display}</label></li>\n`;
        } else {
            // debug
//             checkbox_string = `<li><label>${display}</label></li>\n`;
        }
        const sub_types = process_overlay_types(type.types);
        if (null == checkbox_string && (undefined == type.types || '' == sub_types)) {
            continue;
        }
        if (null == checkbox_string) {
            type_string += group_string;
        } else {
            type_string += checkbox_string;
        }
        type_string += sub_types;
    }
    if ('' == type_string) {
        return '';
    }
    return '<ul>' + type_string + '</ul>';
}
function handle_toggle_click() {
    this.classList.toggle("active");
    const content = this.nextElementSibling;
    if (content.style.maxHeight) {
        content.style.maxHeight = null;
    } else {
        const max_height = 32768;
        content.style.maxHeight = max_height + "px";
    }
}
function apply_collapsible() {
    // https://www.w3schools.com/howto/howto_js_collapsible.asp
    const coll = document.getElementsByClassName("collapsible");
    for (const section of coll) {
        section.removeEventListener("click", handle_toggle_click);
        section.addEventListener("click", handle_toggle_click);
    }
}
function load_level(base_path) {
    const svg_path = base_path+'.svg';
    const json_path = base_path+'.json';
    const MNov_path = base_path+'_MNov.json';
    Promise.all([
        load_json(json_path, j => j),
        load_json(MNov_path, j => j)
    ]).then(json => {
        level_json = json[0];
        level_MNov = json[1];
        display_svg(svg_path);
        set_initial_elevation();
        build_overlay_style_map(overlay_json.types);
        if (undefined != level_MNov) {
            build_overlay_style_map([level_MNov]);
        }
        populate_overlays();
    });
}
function set_initial_elevation() {
    const slider = document.getElementById('elevation-slider');
    const elevations = get_level_elevations();
    // set the slider range to the floor/ceiling range of the level
    slider.noUiSlider.setHandle(0, elevations[0] * 32);
    slider.noUiSlider.setHandle(1, elevations[1] * 32);
    slider.noUiSlider.updateOptions({
        range: get_level_slider_range()
    });
}
function get_level_elevations() {
    const floor = level_json.elevation.floor;
    const ceiling = level_json.elevation.ceiling;
    return [floor, ceiling];
}
function get_level_slider_range() {
    const elevations = get_level_elevations();
    // set the slider range to 1 rounded WU greater/less than the range of the level
    const floor = Math.max(-1, Math.floor(elevations[0] * 32 - 1)/32);
    const ceiling = Math.min(1, Math.ceil(elevations[1] * 32 + 1)/32);
    return {
        'min': floor * 32,
        'max': ceiling * 32
    };
}
function create_slider(behavior, range, start) {
    const slider = document.getElementById('elevation-slider');
    try {
        slider.noUiSlider.destroy();
    } catch (error) {
        // ignore
    }
    noUiSlider.create(slider, {
        start: start,
        range: range,
        behaviour: behavior,
    //     step: .1,
        direction: 'rtl',
        orientation: 'vertical',
        connect: true,
        pips: {
            mode: 'range',
            stepped: true,
            density: 2,
            filter: (value, type) => {
                return value % 1 ? 0 : 1;
            },
            format: wNumb({decimals: 2})
        },
    });
    const nodes = [
        document.getElementById('floor-value'),
        document.getElementById('ceiling-value')
    ];
    slider.noUiSlider.on('update', function (values, handle, unencoded, isTap, positions) {
        nodes[handle].innerHTML = values[handle];
        update_svg_style();
    });
}
function set_player_elevation() {
    const slider = document.getElementById('elevation-slider');
    const floor = level_json.player[0].elevation * 32;
    // set ceiling to players height above the floor
    const ceiling = floor + 819 / 1024;
    create_slider(
        get_behavior(),
        get_level_slider_range(),
        [floor, ceiling]
    );
}
function get_behavior() {
    const checkbox = document.getElementById('lock-handles');
    let behavior = 'drag';
    if (checkbox.checked) {
        // store fixed range
        behavior += '-fixed';
    }
    return behavior;
}
function update_handle_locks() {
    const slider = document.getElementById('elevation-slider');
    const values = slider.noUiSlider.get(true);
    create_slider(
        get_behavior(),
        get_level_slider_range(),
        values);
}
function display_svg(svg) {
    const map_object = document.getElementById('map_object');
    map_object.data = svg;
}
function map_selection(dropdown) {
    const selected_index = dropdown.selectedIndex;
    const value = dropdown.options[selected_index].value;
    const map_info = maps_json[value].map_info
    load_levels(map_info);
}
function level_selection(dropdown) {
    const selected_index = dropdown.selectedIndex;
    const value = Number(dropdown.options[selected_index].value);
    const level_info = levels_json.levels[value].base_name;
    load_level(level_info);
}
function reload_level() {
    iterate_level(0);
}
function previous_level() {
    iterate_level(-1);
}
function next_level() {
    iterate_level(1);
}
function iterate_level(increment) {
    const dropdown = document.getElementById('select_level');
    const selected_index = dropdown.selectedIndex;
    const value = Number(dropdown.options[selected_index].value);
    let new_index = value;
    do {
        new_index = (new_index + increment + levels_json.levels.length) % levels_json.levels.length;
    } while (dropdown.options[new_index].disabled);
    dropdown.value = ''+new_index;
    const level_info = levels_json.levels[new_index].base_name
    load_level(level_info);
}
function select_level(index, dropdown) {
    dropdown.value = index;
    const level_info = levels_json.levels[index].base_name
    load_level(level_info);
}
const selectors = {
    'class': '.',
    'id': '#',
    'selector': '',
}
function build_overlay_style_map(types) {
    if (undefined == types) {
        return;
    }
    for (const type of types) {
        if (type.style) {
            for (const reference_type of Object.keys(selectors)) {
                if (type[reference_type]) {
                    overlay_style_map[reference_type+'_'+type[reference_type]] = type.style;
                }
            }
        }
        build_overlay_style_map(type.types);
    }
}
function generate_dynamic_style(hovered = []) {
    const checkboxes = document.querySelectorAll('input.overlay[type=checkbox]');
    const style_content = [
        ...[...checkboxes].map(cb => selector_style(cb.id, cb.checked ? 1 : 0)),
        ...hovered.map(id => selector_style(id, 1)),
        ...process_polygons()
    ].filter(e => null!=e)
     .filter(e => ''!=e)
     .join('\n');
    return style_content;
}
function selector_style(id, style_index) {
    const reference = id;
    if (!reference) {
        return '';
    }
    const selector = checkbox_id_to_css_selector(reference);
    const overlay = overlay_style_map[reference];
    let styles = overlay_json.style;
    if (overlay) {
        styles = overlay;
    }
    return selector + ' {' + styles[style_index] + '}';
}
function checkbox_id_to_css_selector(id) {
    for (const [type, prefix] of Object.entries(selectors)) {
        if (id.startsWith(type+'_')) {
            return prefix + id.slice(type.length + 1);
        }
    }
    return null;
}
function out_of_bounds(floor, ceiling, comparison_min, comparison_max) {
    return Math.fround(floor  ) > Math.fround(comparison_min)
        || Math.fround(ceiling) < Math.fround(comparison_max);
}
function process_polygons(hovered = []) {
    const slider = document.getElementById('elevation-slider');
    const values = slider.noUiSlider.get(true);
    const floor = values[0] /32;
    const ceiling = values[1] / 32;
    const elevation_type = document.querySelector('input[name="elevation"]:checked').value;
    const enabled = new Set();
    const disabled = new Set();
    for (const [id, poly] of Object.entries(level_json.polygons)) {
        let visible = true;
        if ('intersection' == elevation_type && out_of_bounds(floor, ceiling, poly.ceiling_height, poly.floor_height)) {
            visible = false;
        }
        else if ('contained' == elevation_type && out_of_bounds(floor, ceiling, poly.floor_height, poly.ceiling_height)) {
            visible = false;
        }
        else if ('ceiling' == elevation_type && out_of_bounds(floor, ceiling, poly.ceiling_height, poly.ceiling_height)) {
            visible = false;
        }
        else if ('floor' == elevation_type && out_of_bounds(floor, ceiling, poly.floor_height, poly.floor_height)) {
            visible = false;
        }
        if (visible) {
            poly.connections.forEach(c => enabled.add(c));
        } else {
            poly.connections.forEach(c => disabled.add(c));
        }
    }
    const to_disable = new Set([...disabled].filter(x => !enabled.has(x)));
    if (to_disable.size == 0) {
        return '';
    }
    return [...to_disable].map(item => '#' + item + ' {display: none;}');
}
function update_svg_style(hovered = []) {
    const svg_obj = document.getElementById('map_object');
    if (null == svg_obj) {return;}
    const svg_doc = svg_obj.contentDocument;
    if (null == svg_doc) {return;}
    const old_style = svg_doc.getElementById('dynamic-style');
    const new_style = generate_dynamic_style(hovered);
    if (null == old_style || null == new_style) {
        return;
    }
    old_style.textContent = new_style;
}
function update_url() {
    const map_selector = document.getElementById('select_map');
    const level_selector = document.getElementById('select_level');
    const map_index = map_selector.options[map_selector.selectedIndex].value;
    const map_info = maps_json[map_index];
    const level_index = level_selector.options[level_selector.selectedIndex].value;
    const level_info = levels_json.levels[level_index];
    const location = window.location.href + '';
    let base_url = location;
    const index = location.indexOf('#');
    if (index >= 0) {
        base_url = base_url.substring(0,index);
    }
    const new_url = base_url + '#' + map_info.short_name + ':' + level_info.index;
    const new_title = map_info.map_name + ': ' + level_info.index + ' ' + level_info.name;
    window.history.replaceState({}, new_title, new_url);
    document.title = new_title;
}
function svg_loaded() {
    update_url();
    set_initial_elevation();
    update_svg_style();
}
function toggle_checkbox(checkbox) {
//     if (checkbox.readOnly) checkbox.checked=checkbox.readOnly=false;
//     else if (!checkbox.checked) checkbox.readOnly=checkbox.indeterminate=true;
    // checked = false,true
    // indeter = true,false
    // uncheck = false,false
    const label = checkbox.parentElement;
    const li = label.parentElement;
    const ul = li.nextElementSibling;
//     console.log("toggle: "+checkbox.id + " = " + checkbox.checked);
    if (null != ul && null != ul.children) {
        for (const child of ul.children) {
            if (child.nodeName == 'LI') {
                const child_checkbox = child.getElementsByTagName('INPUT')[0];
                child_checkbox.checked = checkbox.checked;
                toggle_checkbox(child_checkbox);
            }
        }
    }
    update_svg_style();
}
function hover_checkbox(label, id, display) {
    const svg_obj = document.getElementById('map_object');
    if (null == svg_obj) {return;}
    const svg_doc = svg_obj.contentDocument;
    if (null == svg_doc) {return;}

    let ids = [];
    if (0 != display) {
        ids = [...gather_hovered_lines(id), ...gather_hovered_elements(label, display)];
        ids = [...new Set(ids)];
    }
    update_svg_style(ids)
}
function gather_hovered_lines(id) {
    if (null == id) {return [];}
    const svg_obj = document.getElementById('map_object');
    if (null == svg_obj) {return [];}
    const svg_doc = svg_obj.contentDocument;
    if (null == svg_doc) {return [];}

    const search_id = id.replace(/-/g,'_')+'_lines_';
    const elements = svg_doc.querySelectorAll('g[id^='+search_id+']');
    return [...elements].map(e => e.id);
}
function gather_hovered_elements(label, display) {
    if (null == label) {return [];}
    const svg_obj = document.getElementById('map_object');
    if (null == svg_obj) {return [];}
    const svg_doc = svg_obj.contentDocument;
    if (null == svg_doc) {return [];}

    const checkbox = label.getElementsByTagName('INPUT')[0];

    if (checkbox.checked && 0 == display) {
        return [];
    }

    let ids = [checkbox.id];

    const li = label.parentElement;
    const ul = li.nextElementSibling;
    if (null != ul && null != ul.children) {
        for (const child of ul.children) {
            if (child.nodeName == 'LI') {
                const child_checkbox = child.getElementsByTagName('INPUT')[0];
                const child_label = child.getElementsByTagName('LABEL')[0];
                const child_ids = gather_hovered_elements(child_label, display);
                ids = [...ids, ...child_ids];
            }
        }
    }
    return ids;
}
function zoom(level) {
    let viewBox = level_json.viewBox[level];
    if (null == viewBox) {
        const scale = level_json.scale;
        viewBox = [-scale, -scale, scale*2, scale*2].join(' ')
    }
    const svg_obj = document.getElementById('map_object');
    if (null == svg_obj) {return;}
    const svg_doc = svg_obj.contentDocument;
    if (null == svg_doc) {return;}
    const svg_con = svg_doc.getElementsByTagName('svg')[0];
    gsap.to(svg_con, {
        duration: 1,
        attr: { viewBox: viewBox },
        ease: 'power3.inOut'
    });
}
