// 	// Get the Object by ID
// 	var a = document.getElementById('svgObject');
// 	// Get the SVG document inside the Object tag
// 	var svgDoc = a.contentDocument;
// 	// Get one of the SVG items by ID;
// 	var svgItem = svgDoc.getElementById('svgItem');
// 	// Set the colour to something else

var map_json = null;

function load_json(path, callback) {
    return fetch(path)
    .then(response => {
        if (!response.ok) {
            throw new Error('HTTP error ' + response.status);
        }
        return response.json();
    })
    .then(json => {
        callback(json)
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
        callback(json)
    })
    .catch(function () {
        this.dataError = true;
    })
}

function fill_map_menu(maps_info) {
    var select = document.getElementById('select_map');
    select.options.length = 0
    var first = -1
    for (let i in maps_info) {
        let map = maps_info[i]
        if (-1 == first) {
            first = select.options.length
        }
        select.options[select.options.length] = new Option(map.map_name, map.map_info, false, false)
    }
    select.options.selectedIndex = first
    load_levels(select.options[first].value)
}
function fill_level_menu(level_info) {
    var select = document.getElementById('select_level');
    select.options.length = 0
    var first = -1
    for (let i in level_info.levels) {
        let level = level_info.levels[i]
        if ('separator' in level) {
            option = new Option(level.separator, null, false, false)
            option.disabled = true
            select.options[select.options.length] = option
            continue
        }
        if (-1 == first) {
            first = select.options.length
        }
        select.options[select.options.length] = new Option(level.name, level.base_name, false, false)
    }
    select.options.selectedIndex = first
    load_level(select.options[first].value)
}

function loaded() {
    console.clear()
    load_maps()
    update_svg_style()
}

function load_maps() {
    load_json('maps.json', fill_map_menu)
}
function load_levels(path) {
    load_json(path, fill_level_menu)
}
function load_level(base_path) {
    var svg_path = base_path+'.svg'
    var json_path = base_path+'.json'
    load_json(json_path, function (value) {map_json = value})
    display_svg(svg_path)
}
function display_svg(svg) {
    map_object = document.getElementById('map_object')
    map_object.data = svg
}
function map_selection(dropdown) {
    var selected_index  = dropdown.selectedIndex
    var value = dropdown.options[selected_index].value
    load_levels(value)
}
function level_selection(dropdown) {
    var selected_index  = dropdown.selectedIndex
    var value = dropdown.options[selected_index].value
    load_level(value)
}
function generate_dynamic_style() {
    let checkboxes = document.querySelectorAll('input[type=checkbox]')
    style_content = ''
    for (let i in checkboxes) {
        if (!checkboxes[i].id) {
            continue
        }
        if (checkboxes[i].checked) {
            style_content += '.'+checkboxes[i].id+' {display:block;}\n'
        } else {
            style_content += '.'+checkboxes[i].id+' {display:none;}\n'
        }
    }
    return style_content
}
function update_svg_style() {
    console.log('here')
    let svg_obj = document.getElementById('map_object')
    let svg_doc = svg_obj.contentDocument
    let old_style = svg_doc.getElementById('dynamic-style')
    let new_style = generate_dynamic_style()
    old_style.textContent = new_style
}
function toggle_checkbox(checkbox) {
    console.log(checkbox.id)
    if (checkbox.readOnly) checkbox.checked=checkbox.readOnly=false;
    else if (!checkbox.checked) checkbox.readOnly=checkbox.indeterminate=true;
    // checked = false,true
    // indeter = true,false
    // uncheck = false,false
    const dStyle = document.querySelector('style');
    console.log(dStyle)
    update_svg_style()
    if (checkbox.checked) {
        console.log('checked')
        // display: inline
        return
    }
    // display: none
    if (checkbox.readOnly) {
        // onhover
        console.log('indeterm')
        return
    }
    console.log('un-checked')
}
function zoom(level) {
    var viewBox = map_json.viewBox[level]
    if (null == viewBox) {
        viewBox = '-1 -1 2 2'
    }
    let svg_obj = document.getElementById('map_object')
    let svg_doc = svg_obj.contentDocument
    let svg_con = svg_doc.getElementsByTagName('svg')[0]
    svg_con.viewBox = viewBox
    gsap.to(svg_con, {
        duration: 1,
        attr: { viewBox: viewBox },
        ease: 'power3.inOut'
    });
}
