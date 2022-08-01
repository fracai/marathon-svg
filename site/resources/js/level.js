'use strict';

hide_lines();

function find_lines_group(id) {
    const split_id = id.split('_',2);
    const search_id = '_lines_'+split_id[0].substring(0,1)+split_id[1];
    const elements = document.querySelectorAll('g[id$='+search_id+']');
    if (elements.length <= 0) {
        return null;
    }
    return elements[0];
}
function set_display(id, display) {
    const lines = find_lines_group(id);
    if (null == lines) {
        return;
    }
    lines.style.display = display;
}
function m_over(id) {
    set_display(id, 'block');
}
function m_out(id) {
    set_display(id, 'none');
}
function hide_lines() {
    const search_id = '_lines_s';
    [...document.querySelectorAll('*')]
        .filter(e => e.id.indexOf(search_id) > -1)
        .forEach(e => e.style.display = 'none');
}
