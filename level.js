'use strict';

hide_lines();

function find_lines_group(id) {
    const search_id = '_lines_s'+id.split('_',2)[1];
    const elements = document.querySelectorAll('*');
    const filtered = [...elements].filter(e => e.id.endsWith(search_id));
    if (filtered.length <= 0) {
        return null;
    }
    return filtered[0];
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
