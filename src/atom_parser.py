# Copyright 2010-2011 Florent Le Coz <louiz@louiz.org>
#
# This file is part of Poezio.
#
# Poezio is free software: you can redistribute it and/or modify
# it under the terms of the zlib license. See the COPYING file.

"""
Defines a function returning a dict containing the values from an
atom entry contained in a pubsub entry
"""

ATOM_XMLNS = "http://www.w3.org/2005/Atom"

def parse_atom_entry(pubsub_item):
    """
    Takes a pubsub ET.Element item and returns a dict containing
    all needed values from the atom entry element.
    Returns None if the item does not contain an atom entry.
    """
    entry_elem = pubsub_item.find('{%s}entry' % (ATOM_XMLNS,))
    if entry_elem is None:
        return None
    res = {'author':{}}
    author_elem = entry_elem.find('{%s}author' % (ATOM_XMLNS,))
    if author_elem is not None:
        for sub in ('name', 'uri'):
            sub_elem = author_elem.find('{%s}%s' % (ATOM_XMLNS, sub,))
            if sub_elem is not None:
                res['author'][sub] = sub_elem.text
    for elem_name in {'title':'text', 'updated':'date', 'published': 'date',
                      'summary':'text'}:
        elem = entry_elem.find('{%s}%s' % (ATOM_XMLNS, elem_name,))
        if elem is not None:
            res[elem_name] = elem.text
    link_elem = entry_elem.find('{%s}link' % (ATOM_XMLNS,))
    if link_elem is not None:
        res['link_href'] = link_elem.attrib.get('href') or ''
    return res
