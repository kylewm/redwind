# Copyright © 2013, 2014 Kyle Mahan
# This file is part of Red Wind.
#
# Red Wind is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Red Wind is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Red Wind.  If not, see <http://www.gnu.org/licenses/>.


from bs4 import BeautifulSoup
from urllib.parse import urljoin
import itertools
import re

DATE_RE = r'(\d{4})-(\d{2})-(\d{2})'
TIME_RE = r'(\d{2}):(\d{2})(?::(\d{2}))?(?:(Z)|([+-]\d{2}:?\d{2}))?'
DATETIME_RE = DATE_RE + 'T' + TIME_RE


def parse(text, url):
    soup = BeautifulSoup(text, 'html5lib')

    base_url = url
    base_element = soup.find('base')
    if base_element and base_element.has_attr('href'):
        base_url = urljoin(base_url, base_element['href'])

    result = {}
    result['items'] = parse_microformats(base_url, soup)

    rels, alternates = parse_rels(base_url, soup)
    result['rels'] = rels
    if alternates:
        result['alternates'] = alternates

    return result


def parse_rels(url, root):
    results = {}
    alternates = []

    for a in root.find_all(('a', 'link')):
        href = a.get('href')
        if href:
            href = normalize_url(url, href)
            rels = a.get('rel', [])
            if 'alternate' not in rels:
                for rel in rels:
                    multimap_put(results, rel, href)
            else:
                alternate = {
                    'rels': ' '.join(rel for rel in rels
                                     if rel != 'alternate'),
                    'url': href
                }
                for attr in ('media', 'hreflang', 'type'):
                    if a.has_attr(attr):
                        alternate[attr] = a[attr]
                alternates.append(alternate)

    return results, alternates


def classes_by_prefix_fn(prefix):
    def get_classes(element):
        """workaround for bug parsing <html> multivalued class attribute"""
        classes = element.get('class', [])
        if element.name == 'html' and not isinstance(classes, list):
            classes = classes.split()
        return classes

    return lambda element: [(c, c[len(prefix):])
                            for c in get_classes(element)
                            if c.startswith(prefix)]


p_classes = classes_by_prefix_fn('p-')
dt_classes = classes_by_prefix_fn('dt-')
u_classes = classes_by_prefix_fn('u-')
e_classes = classes_by_prefix_fn('e-')
h_classes = classes_by_prefix_fn('h-')


def property_classes(element):
    return itertools.chain(
        p_classes(element), dt_classes(element),
        u_classes(element), e_classes(element))


def parse_microformats(url, root):
    """returns a list of microformat objects"""
    results = []

    types = h_classes(root)
    if types:
        children = []
        properties = {}
        for child in root.find_all(True, recursive=False):
            props, children = parse_properties(url, child)
            properties.update(props)
            children += children
        parse_implied_properties(url, root, properties)

        result = {
            'type': [cls for cls, typ in types],
            'properties': properties,
        }

        if children:
            result['children'] = children

        results.append(result)

    else:
        for child in root.find_all(True, recursive=False):
            results += parse_microformats(url, child)

    return results


def parse_implied_properties(url, root, properties):
    def get_only_child(element):
        children = element.find_all(True, recursive=False)
        if len(children) == 1:
            return children[0]

    def img_alt_or_abbr_title(element, depth):
        if element.name == 'img':
            return element.get('alt')
        if element.name == 'abbr' and element.has_attr('title'):
            return element['title']
        if depth > 0:
            child = get_only_child(element)
            return child and img_alt_or_abbr_title(child, depth-1)

    def img_src_or_object_data(element, depth):
        if element.name == 'img':
            return element.get('src')
        elif element.name == 'object' and element.has_attr('data'):
            return element['data']
        if depth > 0:
            child = get_only_child(element)
            if child and not h_classes(child):
                return img_src_or_object_data(child, depth-1)

    if 'name' not in properties:
        imp_name = (img_alt_or_abbr_title(root, 3) or
                    root.get_text().strip())
        multimap_put(properties, 'name', imp_name)

    if 'photo' not in properties:
        photo_url = normalize_url(url,
                                  img_src_or_object_data(root, 3))
        if photo_url:
            multimap_put(properties, 'photo', photo_url)

    if 'url' not in properties:
        if root.name == 'a' and root.has_attr('href'):
            multimap_put(properties, 'url',
                         normalize_url(url, root.get('href')))

        else:
            for a in root.find_all('a', recursive=False):
                if not h_classes(a) and a.has_attr('href'):
                    multimap_put(properties, 'url',
                                 normalize_url(url, a.get('href')))
                    break


def multimap_put(m, k, v):
    if k not in m:
        m[k] = []
    m[k].append(v)


def multimap_extend(m, k, vs):
    if k not in m:
        m[k] = vs
    else:
        m[k] += vs


def parse_properties(url, root):
    properties = {}
    children = []

    if h_classes(root):
        #nested microformat -- get property names
        mfvalues = parse_microformats(url, root)
        propclasses = property_classes(root)
        if propclasses:
            for _, mfprop in propclasses:
                multimap_extend(properties, mfprop, mfvalues)
        else:
            children.append(children)
    else:
        for _, text_prop in p_classes(root):
            multimap_put(properties, text_prop, text_property_value(root))

        for _, dt_prop in dt_classes(root):
            multimap_put(properties, dt_prop, dt_property_value(root))

        for _, url_prop in u_classes(root):
            multimap_put(properties, url_prop, url_property_value(url, root))

        for _, e_prop in e_classes(root):
            multimap_put(properties, e_prop, e_property_value(root))

        for child in root.find_all(True, recursive=False):
            subprops, children = parse_properties(url, child)
            properties.update(subprops)
            children += children

    return properties, children


def text_property_value(element):
    def get_values():
        for value_element in element.find_all(class_='value'):
            if (value_element.name in ('img', 'area')
                    and value_element.has_attr('alt')):
                yield value_element['alt']

            elif (value_element.name in ('data', 'input')
                    and value_element.has_attr('value')):
                yield value_element['value']

            elif value_element.name == 'abbr':
                yield value_element.get('title') or value_element.get_text()

            else:
                yield value_element.get_text(strip=True)

    values = list(get_values())
    if values:
        return ''.join(values)

    if element.name == 'abbr' and element.has_attr('title'):
        return element['title']

    if element.name in ('data', 'input') and element.has_attr('value'):
        return element['value']

    if element.name in ('img', 'area') and element.has_attr('alt'):
        return element['alt']

    return _get_text_sub_img_for_alt(element)


def url_property_value(base_url, element):
    if element.name in ('a', 'area') and element.has_attr('href'):
        return normalize_url(base_url, element['href'])
    if element.name == 'img' and element.has_attr('src'):
        return normalize_url(base_url, element['src'])
    if element.name == 'object' and element.has_attr('data'):
        return normalize_url(base_url, element['data'])
    #TODO value-class-pattern
    if element.name == 'abbr' and element.has_attr('title'):
        return normalize_url(base_url, element['title'])
    if element.name in ('data', 'input') and element.has_attr('value'):
        return normalize_url(base_url, element['value'])
    return normalize_url(base_url, element.get_text())


def normalize_url(base_url, relative_url):
    return relative_url and urljoin(base_url, relative_url)


def dt_property_value(element):
    # handle value-class-pattern
    value_els = element.find_all(class_='value')
    if value_els:
        date_parts = []
        for value_el in value_els:
            if value_el.name in ('img', 'area'):
                alt = value_el.get('alt') or (value_el.string
                                              and value_el.string.strip())
                if alt:
                    date_parts.append(alt)
            elif value_el.name == 'data':
                val = value_el.get('value') or (value_el.string
                                                and value_el.string.strip())
                if val:
                    date_parts.append(val)
            elif value_el.name == 'abbr':
                title = value_el.get('title') or (value_el.string
                                                  and value_el.string.strip())
                if title:
                    date_parts.append(title)
            elif value_el.name in ('del', 'ins', 'time'):
                dt = value_el.get('datetime') or (value_el.string
                                                  and value_el.string.strip())
                if dt:
                    date_parts.append(dt)
            else:
                val = value_el.string and value_el.string.strip()
                if val:
                    date_parts.append(val)

        date_part = ''
        time_part = ''
        date_time_value = ''
        for part in date_parts:
            if re.match(DATETIME_RE, part):
                # if it's a full datetime, then we're done
                date_time_value = part
                break
            else:
                if re.match(TIME_RE, part):
                    time_part = part
                elif re.match(DATE_RE, part):
                    date_part = part
                date_time_value = (date_part.strip().rstrip('T')
                                   + 'T' + time_part.strip())
        return date_time_value

    if element.name in ('time', 'ins', 'del') and element.has_attr('datetime'):
        return element['datetime']

    if element.name == 'abbr' and element.has_attr('title'):
        return element['title']

    if element.name in ('data', 'input') and element.has_attr('value'):
        return element['value']

    return element.get_text(strip=True)


def e_property_value(element):
    return {
        'html': ''.join(str(child) for child in element.children),
        'value': _get_text_sub_img_for_alt(element)
    }


def _get_text_sub_img_for_alt(element):
    for img in element.find_all('img'):
        if img.has_attr('alt'):
            img.replace_with(img['alt'])
        elif img.has_attr('src'):
            img.replace_with(img['src'])

    return element.get_text().strip()


if __name__ == '__main__':
    import requests
    import json

    urls = [
        'https://snarfed.org/2014-03-10_re-kyle-mahan',
        'https://brid-gy.appspot.com/like/facebook/12802152/10100820912531629/1347771058',
        'https://brid-gy.appspot.com/comment/googleplus/109622249060170703374/z12vyphidxaodbb0223qdj0pwkvuytpja04/z12vyphidxaodbb0223qdj0pwkvuytpja04.1334830661177000',
        'http://tantek.com/2014/030/t1/handmade-art-indieweb-reply-webmention-want',
        'http://tantek.com/2014/067/b2/mockups-people-focused-mobile-communication',
        'https://brid-gy.appspot.com/comment/twitter/kyle_wm/443763597160636417/443787536108761088',
        'https://snarfed.org/2014-03-10_re-kyle-mahan-5',
        'http://tommorris.org/posts/2550'
    ]

    for url in urls:
        print("parsing url", url)
        txt = requests.get(url).content
        result = parse(txt, url)
        print(json.dumps(result, indent=True))
        print()
