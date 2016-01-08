import os
import dateutil.parser
import datetime
import math
import json
import time
from flask import abort, Blueprint
from functools import wraps

from lxml import etree
import xmltodict

from zipfile import ZipFile
import urllib2
from io import BytesIO


# opf writing
DC = "http://purl.org/dc/elements/1.1/"
DCNS = "{http://purl.org/dc/elements/1.1/}"
OPF = 'http://www.idpf.org/2007/opf'

# Caching
def cached(app, timeout=5 * 60, key='view/%s'):
    '''http://flask.pocoo.org/docs/patterns/viewdecorators/#caching-decorator'''
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            cache_key = key % request.path
            rv = app.cache.get(cache_key)
            if rv is not None:
                return rv
            rv = f(*args, **kwargs)
            app.cache.set(cache_key, rv, timeout=timeout)
            return rv
        return decorated_function
    return decorator

# Custom Template Filters
def datetimeformat(value):
    delta = datetime.datetime.now() - value
    if delta.days == 0:
        formatting = 'today'
    elif delta.days < 10:
        formatting = '{0} days ago'.format(delta.days)
    elif delta.days < 28:
        formatting = '{0} weeks ago'.format(int(math.ceil(delta.days/7.0)))
    elif value.year == datetime.datetime.now().year:
        formatting = '%d %b'
    else:
        formatting = '%d %b %Y'
    return value.strftime(formatting)

keyspace = "wf59eorpma2vnxb07kiqt83_u6lgzs41-ycdjh"

def int_str(val):
    """ Turn a positive integer into a string. """
    assert val >= 0
    out = ""
    while val > 0:
        val, digit = divmod(val, len(keyspace))
        out += keyspace[digit]
    return out[::-1]

def str_int(val):
    """ Turn a string into a positive integer. """
    out = 0
    for c in val:
        out = out * len(keyspace) + keyspace.index(c)
    return out

def chaffify(val, chaff_val = 25978):
    """ Add chaff to the given positive integer. """
    return val * chaff_val

def dechaffify(chaffy_val, chaff_val = 25978):
    """ Dechaffs the given chaffed value. If the value does not seem to be correctly chaffed, raises a ValueError. """
    val, chaff = divmod(chaffy_val, chaff_val)
    if chaff != 0:
        raise ValueError("Invalid chaff in value")
    return val

def encode_id(val):
    """
     Encodes ID into semi random set of strings
    """
    return int_str(chaffify(val))

def decode_id(val):
    return dechaffify(str_int(val))

def escapejs(val):
    return json.dumps(str(val))

def nl2br(val): 
    return val.replace('\n','<br>\n')

def parse_pos(s):
    '''
    Position should be in one of the following formats:
    a) 123.1 => vertical only
    b) 123.1-124.2 => vertical range
    c) 11.1,123.1 => a point
    d) 11.1,123.1-200.9,124.2 => range between 2 points
    '''
    def parse_point(x):
        if ',' in x:
            return map(float, x.split(','))
        else:
            return [None, float(x)]

    try:
        if '-' in s:
            a, b = map(parse_point, s.split('-'))
        else:
            a, b = parse_point(s), [None, None] 
    except:
        return None, None, None, None
    
    if b[1] is not None and a[1]>b[1]:
        return b[0], b[1], a[0], a[1]
    elif a[1]==b[1] and a[0] is not None and b[0] is not None and a[0]>b[0]:
        return b[0], b[1], a[0], a[1]
    else:
        return a[0], a[1], b[0], b[1]

def merge_dicts(*dict_args):
    result = {}
    for dictionary in dict_args:
        result.update(dictionary)
    return result


def write_opf(meta_info, primary_id=None, path=None):
    if primary_id is None:
        for k, v, a in meta_info:
            if k == DCNS + 'identifier':
                primary_id = a.setdefault('id', 'primary_id')
                break

    root = etree.Element('package', {
        'xmlns' : OPF,
        'unique-identifier' : primary_id,
        'version' : '2.0'
        }, nsmap = {'dc' : DC, 'opf' : OPF})

    metadata = etree.SubElement(root, 'metadata')
    for key, text, attrs in meta_info:
        el = etree.SubElement(metadata, key, attrs)
        el.text = text

    guide = etree.SubElement(root, 'guide')
    el = etree.SubElement(guide, 'reference', {'href':'cover.jpg','type':'cover','title':'Cover'})

    tree_str = etree.tostring(root, pretty_print=True, encoding='utf-8')
    if path:
        with open(path, 'w') as f:
            f.write(tree_str)
        return path
    else:
        return tree_str

def thing2opf(thing, path=None):
    d = datetime.datetime.now()
    meta = [
        ('{%s}identifier'%DC,'Unknown',{'{%s}scheme'%OPF:'uuid', 'id':'uuid_id'}),
        ('{%s}identifier'%DC,'%s.1'%str(thing.id),{'{%s}scheme'%OPF:'ARG'}),
        ('{%s}title'%DC,thing.title,{}),
        ('{%s}date'%DC,d.strftime('%Y-%m-%dT%H:%M:%S+00:00'),{}),
    ]
    if thing.description:
        meta.append(('{%s}description'%DC,thing.description,{}))
    makers = [(m.maker.display_name, m.maker.sort_by) for m in thing.makers]
    for display, sort_by in makers:
        meta.append(('{%s}creator'%DC,display,{'{%s}file-as'%OPF:sort_by, '{%s}role'%OPF:'aut'}))
    return write_opf(meta, None, path)

def opf2dict(opf_str):
    opf_str = opf_str.replace("<?xml version='1.0' encoding='utf-8'?>","")
    try:
        return xmltodict.parse(opf_str)
    except:
        return {}

""" Given some text (.opf file as xml), this looks for an aaaarg id """
def opf2id(opf_str):
    try:
        d = opf2dict(opf_str)
        ids = d['package']['metadata']['dc:identifier']
        for id in ids:
            if id['@opf:scheme']=='ARG':
                return id['#text'].split('.')[0]
    except:
        return None
    return None

""" Given some text (.opf file as xml), this looks for its revision """
def opf_version(opf_str):
    try:
        d = opf2dict(opf_str)
        ids = d['package']['metadata']['dc:identifier']
        for id in ids:
            if id['@opf:scheme']=='ARG':
                return int(id['#text'].split('.')[1])
    except:
        return 0
    return 0

""" Given some text (.opf file as xml), this looks for its date """
def opf_date(opf_str):
    d = opf2dict(opf_str)
    try:
        # check for calibre timestamp first
        for m in d['package']['metadata']['meta']:
            if m['@name']=='calibre:timestamp':
                ts = time.strptime(m['@content'],'%Y-%m-%dT%H:%M:%S.%f+00:00')
                return datetime.datetime(*ts[:6])
    except:
        pass
    try:
        # this is the arg timestamp given on creation
        ts = time.strptime(d['package']['metadata']['dc:date'],'%Y-%m-%dT%H:%M:%S+00:00')
        return datetime.datetime(*ts[:6])
    except:
        return None
    return None


""" Given a list of things to put in a folder """
def archive_things(things):
    s = BytesIO()
    with ZipFile(s, "w") as zf:
        for thing in things:
            archive_thing(thing, zf)
    return s.getvalue()


""" Given a thing, create a calibre folder... if a zipfile is provided, simply add to it """
def archive_thing(thing, zip_file=None):
    from flask_application.models import Metadata
    if not zip_file:
        s = BytesIO()
        zf = ZipFile(s, "w")
        cover_file = 'cover.jpg'
        opf_file = 'metadata.opf'
    else:
        zf = zip_file
        cover_file = os.path.join(str(thing.id), 'cover.jpg')
        opf_file = os.path.join(str(thing.id), 'metadata.opf')
    # Put in the content
    try:
        metadata = Metadata.objects.get(thing=thing)
    except:
        metadata = Metadata(thing=thing)
        metadata.reload()
    opf = metadata.opf.encode('utf-8')
    zf.writestr(opf_file, opf)
    preview = thing.preview(filename="x500-0.jpg")
    if preview:
        try:
            image_file = BytesIO(urllib2.urlopen(url_for('reference.preview', filename=preview, _external=True), timeout=2).read())
            zf.writestr(cover_file, image_file.getvalue())
        except:
            print "Failed to load image: ", preview
    if not zip_file:
        return s.getvalue()
    
