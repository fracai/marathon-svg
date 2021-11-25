var maps_json = null;
var levels_json = null;
var level_json = null;

function load_json(path, callback) {
    return fetch(path)
        .then(response => {
            if (!response.ok) {
                throw new Error('HTTP error ' + response.status);
            }
            return response.json();
        })
        .then(json => {
            callback(json);
        })
        .catch(function () {
            this.dataError = true;
        })
}
function load_path(path, callback) {
    return fetch(path)
        .then(response => {
            if (!response.ok) {
                throw new Error('HTTP error ' + response.status);
            }
            return response.body();
        })
        .then(json => {
            callback(json);
        })
        .catch(function () {
            this.dataError = true;
        })
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
            if (0 > level_token || level_token == level.index) {
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
    console.clear();
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
    load_json(path, (json) => fill_level_menu(json, level));
}
function load_level(base_path) {
    var svg_path = base_path+'.svg';
    var json_path = base_path+'.json';
    load_json(json_path, value => {
        level_json = value;
        display_svg(svg_path);
    });
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
    return style_content;
}
function update_svg_style() {
    let svg_obj = document.getElementById('map_object');
    let svg_doc = svg_obj.contentDocument;
    let old_style = svg_doc.getElementById('dynamic-style');
    let new_style = generate_dynamic_style();
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
    update_svg_style();
}
function toggle_checkbox(checkbox) {
    console.log(checkbox.id);
    if (checkbox.readOnly) checkbox.checked=checkbox.readOnly=false;
    else if (!checkbox.checked) checkbox.readOnly=checkbox.indeterminate=true;
    // checked = false,true
    // indeter = true,false
    // uncheck = false,false
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
