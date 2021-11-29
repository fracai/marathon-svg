var maps_json = null;
var levels_json = null;
var level_json = null;
var overlay_json = null;

function load_common(path, callback, data_extractor) {
    // fetch the path
    return fetch(path)
        // handle any errors
        .then(response => {
            if (!response.ok) {
                throw new Error('HTTP error ' + response.status);
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
            debugger;
            this.dataError = true;
        })
}

function load_json(path, callback) {
    return load_common(path, callback, r => r.json());
}
function load_path(path, callback) {
    return load_common(path, callback, r => r.body());
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
    for (let i in maps_json) {
        let map = maps_json[i];
        if (-1 == first) {
            if (null == map_tokens[0] || map_tokens[0] == map.short_name) {
                first = select.options.length;
            }
        }
        select.options[select.options.length] = new Option(
            map.map_name,
            i,
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
    for (let i in levels_json.levels) {
        let level = levels_json.levels[i];
        if ('separator' in level) {
            option = new Option(level.separator, null, false, false);
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
            i,
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
    url = window.location.href + ''
    index = url.indexOf('#')
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
        populate_overlays();
    });
    load_json(path+"/map.json", json => fill_level_menu(json, level));
}
function populate_overlays() {
    if (null == overlay_json || null == level_json) {
        return;
    }
    overlay_string = process_overlay_types(overlay_json.types);
    const overlays_div = document.getElementById('overlays');
    overlays_div.innerHTML = '';
    if ('' == overlay_string) {
        return;
    }
    overlays_div.insertAdjacentHTML('afterbegin', overlay_string);
    apply_collapsible();
}
function process_overlay_types(types) {
    type_string = '';
    for (let i in types) {
        const type = types[i];
        display = type.display;
        if (undefined == display || '' == display) {
            display = type.class;
        }
        if (level_json.overlays.includes(type.class)) {
            type_string += `<li><label><input type="checkbox" id="${type.class}" onclick="toggle_checkbox(this)"/> ${display}</label></li>\n`;
        } else if (null == type.class) {
            type_string += `<li><label><input type="checkbox" onclick="toggle_checkbox(this)"/> ${display}</label></li>\n`;
        }
        if (typeof type.types != 'undefined') {
            type_string += process_overlay_types(type.types);
        }
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
        content.style.maxHeight = content.scrollHeight + "px";
    }
}
function apply_collapsible() {
    // https://www.w3schools.com/howto/howto_js_collapsible.asp
    var coll = document.getElementsByClassName("collapsible");
    for (let i in [...coll]) {
        coll[i].removeEventListener("click", handle_toggle_click);
        coll[i].addEventListener("click", handle_toggle_click);
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
    var value = dropdown.options[selected_index].value;
    var level_info = levels_json.levels[value].base_name
    load_level(level_info);
}
function generate_dynamic_style() {
    let checkboxes = document.querySelectorAll('input[type=checkbox]');
    style_content = '';
    for (let i in checkboxes) {
        if (!checkboxes[i].id) {
            continue;
        }
        if (checkboxes[i].checked) {
            style_content += '.'+checkboxes[i].id+' {display:block;}\n';
        } else {
            style_content += '.'+checkboxes[i].id+' {display:none;}\n';
        }
    }
    style_content += process_polygons()+'\n';
    return style_content;
}
function process_polygons() {
    const slider = document.getElementById('elevation-slider');
    const values = slider.noUiSlider.get(true);
    const floor = values[0] /32;
    const ceiling = values[1] / 32;
    const elevation_type = document.querySelector('input[name="elevation"]:checked').value;
    let enabled = new Set();
    let disabled = new Set();
    for (let i in level_json.polygons) {
        poly = level_json.polygons[i];
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
            for (let c in poly.connections) {
                enabled.add(poly.connections[c]);
            }
        } else {
            for (let c in poly.connections) {
                disabled.add(poly.connections[c]);
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
    if (null == svg_obj) {
        return;
    }
    let svg_doc = svg_obj.contentDocument;
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
    map_info = maps_json[map_index];
	let level_index = level_selector.options[level_selector.selectedIndex].value;
	level_info = levels_json.levels[level_index];
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
//     console.log(checkbox.id);
//     if (checkbox.readOnly) checkbox.checked=checkbox.readOnly=false;
//     else if (!checkbox.checked) checkbox.readOnly=checkbox.indeterminate=true;
    // checked = false,true
    // indeter = true,false
    // uncheck = false,false
    const label = checkbox.parentElement;
    const li = label.parentElement;
    const ul = li.nextElementSibling;
    if (null != ul && null != ul.children) {
        for (let i in ul.children) {
            const child = ul.children[i];
            if (child.nodeName == 'LI') {
                const child_checkbox = child.getElementsByTagName('INPUT')[0];
                child_checkbox.checked = checkbox.checked;
                toggle_checkbox(child_checkbox);
            }
        }
    }
    update_svg_style();
}
function zoom(level) {
    var viewBox = level_json.viewBox[level];
    if (null == viewBox) {
        viewBox = '-1 -1 2 2';
    }
    let svg_obj = document.getElementById('map_object');
    let svg_doc = svg_obj.contentDocument;
    let svg_con = svg_doc.getElementsByTagName('svg')[0];
    svg_con.viewBox = viewBox;
    gsap.to(svg_con, {
        duration: 1,
        attr: { viewBox: viewBox },
        ease: 'power3.inOut'
    });
}
