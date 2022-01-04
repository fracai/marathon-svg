'use strict';

var maps_json = null;
var levels_json = null;
var level_json = null;
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
            console.log(err.message);
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
    var select = document.getElementById('select_map');
    select.options.length = 0;
    let map_tokens = [null,-1];
    if (null != selection) {
        let split_tokens = selection.split(':');
        let parsed = parseInt(split_tokens[1], 10);
        if (!isNaN(parsed)) {
            map_tokens = [split_tokens[0], parsed]
        }
    }
    var first = -1;
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
    var select = document.getElementById('select_level');
    select.options.length = 0;
    var first = -1;
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
    let map_object = document.getElementById('map_object');
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
    const overlay_string = process_overlay_types(overlay_json.types);
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
        let checkbox_string = null;
        let group_string = `<li><label><input type="checkbox" onchange="toggle_checkbox(this)" class="overlay" /> ${display}</label></li>\n`;
        let hover = ` onmouseover="hover_line(this, null, 'block')" onmouseout="hover_line(this, null, 'none')"`;
        if (level_json.overlays.classes.includes(type.class)) {
            if (type.class.endsWith('-computer_terminal')) {
                hover = ` onmouseover="hover_line(this, 'panel-terminal_teleport', 'block')" onmouseout="hover_line(this, 'panel-terminal_teleport', 'none')"`;
            } else if (type.class.endsWith('_switch')) {
                hover = ` onmouseover="hover_line(this, '${type.class}', 'block')" onmouseout="hover_line(this, '${type.class}', 'none')"`;
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
        let max_height = content.scrollHeight;
        max_height = 32768;
        content.style.maxHeight = max_height + "px";
    }
}
function apply_collapsible() {
    // https://www.w3schools.com/howto/howto_js_collapsible.asp
    var coll = document.getElementsByClassName("collapsible");
    for (const section of coll) {
        section.removeEventListener("click", handle_toggle_click);
        section.addEventListener("click", handle_toggle_click);
    }
}
function load_level(base_path) {
    var svg_path = base_path+'.svg';
    var json_path = base_path+'.json';
    load_json(json_path, value => {
        level_json = value;
        display_svg(svg_path);
        set_initial_elevation();
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
    let floor = level_json.elevation.floor;
    let ceiling = level_json.elevation.ceiling;
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
    let slider = document.getElementById('elevation-slider');
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
    var nodes = [
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
    let floor = level_json.player[0].elevation * 32;
    // set ceiling to players height above the floor
    let ceiling = floor + 819 / 1024;
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
    let map_object = document.getElementById('map_object');
    map_object.data = svg;
}
function map_selection(dropdown) {
    var selected_index = dropdown.selectedIndex;
    var value = dropdown.options[selected_index].value;
    var map_info = maps_json[value].map_info
    load_levels(map_info);
}
function level_selection(dropdown) {
    var selected_index = dropdown.selectedIndex;
    var value = Number(dropdown.options[selected_index].value);
    var level_info = levels_json.levels[value].base_name;
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
function generate_dynamic_style() {
    let checkboxes = document.querySelectorAll('input.overlay[type=checkbox]');
    let style_content = '';
    for (const cb of checkboxes) {
        let reference = cb.id;
        if (!reference) {
            continue;
        }
        const selector = checkbox_id_to_css_selector(reference);
        let styles = overlay_json.style;
        const overlay = overlay_style_map[reference];
        if (overlay) {
            styles = overlay;
        }
        style_content += selector + ' {' + styles[cb.checked ? 1 : 0] + '}\n';
    }
    style_content += process_polygons()+'\n';
    return style_content;
}
function checkbox_id_to_css_selector(id) {
    for (const [type, prefix] of Object.entries(selectors)) {
        if (id.startsWith(type+'_')) {
            return prefix + id.slice(type.length + 1);
        }
    }
    return null;
}
function process_polygons() {
    const slider = document.getElementById('elevation-slider');
    const values = slider.noUiSlider.get(true);
    const floor = values[0] /32;
    const ceiling = values[1] / 32;
    const elevation_type = document.querySelector('input[name="elevation"]:checked').value;
    let enabled = new Set();
    let disabled = new Set();
    for (const poly of Object.values(level_json.polygons)) {
        let visible = true;
        if ('intersection' == elevation_type && (floor > poly.ceiling_height || ceiling < poly.floor_height)) {
            visible = false;
        }
        else if ('contained' == elevation_type && (floor > poly.floor_height || ceiling < poly.ceiling_height)) {
            visible = false;
        }
        else if ('ceiling' == elevation_type && (floor > poly.ceiling_height || ceiling < poly.ceiling_height)) {
            visible = false;
        }
        else if ('floor' == elevation_type && (floor > poly.floor_height || ceiling < poly.floor_height)) {
            visible = false;
        }
        if (visible) {
            for (const c of poly.connections) {
                enabled.add(c);
            }
        } else {
            for (const c of poly.connections) {
                disabled.add(c);
            }
        }
    }
    const to_disable = new Set([...disabled].filter(x => !enabled.has(x)));
    if (to_disable.size == 0) {
        return '';
    }
    return [...to_disable].map(item => '#' + item + ' {display: none;}').reduce((result, item) => item + '\n' + result, '');
}
function update_svg_style() {
    let svg_obj = document.getElementById('map_object');
    if (null == svg_obj) {return;}
    let svg_doc = svg_obj.contentDocument;
    if (null == svg_doc) {return;}
    let old_style = svg_doc.getElementById('dynamic-style');
    let new_style = generate_dynamic_style();
    if (null == old_style || null == new_style) {
        return;
    }
    old_style.textContent = new_style;
}
function update_url() {
    let map_selector = document.getElementById('select_map');
    let level_selector = document.getElementById('select_level');
    let map_index = map_selector.options[map_selector.selectedIndex].value;
    const map_info = maps_json[map_index];
    let level_index = level_selector.options[level_selector.selectedIndex].value;
    const level_info = levels_json.levels[level_index];
    let location = window.location.href + '';
    let base_url = location;
    let index = location.indexOf('#');
    if (index >= 0) {
        base_url = base_url.substring(0,index);
    }
    let new_url = base_url + '#' + map_info.short_name + ':' + level_info.index;
    let new_title = map_info.map_name + ': ' + level_info.index + ' ' + level_info.name;
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
function hover_line(label, id, display) {
    let svg_obj = document.getElementById('map_object');
    if (null == svg_obj) {return;}
    let svg_doc = svg_obj.contentDocument;
    if (null == svg_doc) {return;}

    if (null != id) {
        const search_id = id.replace(/-/g,'_')+'_lines_';
        const elements = svg_doc.querySelectorAll('*');
        const filtered = [...elements].filter(e => e.id.startsWith(search_id));
        filtered.forEach(e => e.style.display = display);
    }

    const checkbox = label.getElementsByTagName('INPUT')[0];
    let reference = checkbox.id;
    const selector = checkbox_id_to_css_selector(reference);

    if (checkbox.checked && 'none' == display) {
        return;
    }

    const elements = svg_doc.querySelectorAll(selector);
    elements.forEach(e => e.style.display = display);
}
function zoom(level) {
    var viewBox = level_json.viewBox[level];
    if (null == viewBox) {
        viewBox = '-1 -1 2 2';
    }
    let svg_obj = document.getElementById('map_object');
    if (null == svg_obj) {return;}
    let svg_doc = svg_obj.contentDocument;
    if (null == svg_doc) {return;}
    let svg_con = svg_doc.getElementsByTagName('svg')[0];
    gsap.to(svg_con, {
        duration: 1,
        attr: { viewBox: viewBox },
        ease: 'power3.inOut'
    });
}
