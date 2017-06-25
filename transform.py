# coding: utf-8

import lxml.etree as ET
from lxml.html import html5parser
from lxml import objectify
import re
import datetime

import roman
import cobalt
import pycountry
import yaml


def tag(elem):
    tagname = elem.tag
    if '}' not in tagname:
        return None
    return tagname[tagname.index("}") + 1:]


def format_num(level, n):
    return '(%s)' % level_num(level, n)


def level_num(level, n):
    if level == 0:
        return int(n)
    if level in [1, 2]:
        return chr(ord('a') + int(n) - 1)
    if level in [3, 4]:
        return roman.toRoman(int(n)).lower()
    return '?? level=%s num=%s ??' % (level, n)
    raise ValueError("Formatting number for level %s??" % level)


class Transformer(object):
    num_re = re.compile('^([^\d]*)((\d+)\.?)[\s:]*(.*)', re.I)
    ns = None

    def __init__(self):
        self.xslt = ET.XSLT(ET.parse('html_to_akn.xsl'))

    def transform_all(self, fnames, language, title):
        self.act = cobalt.Act()
        for node in self.act.body.iterchildren():
            self.act.body.remove(node)

        for fname in fnames:
            print fname
            self.transform(fname)

        # do remaining transforms
        xml = self.act.to_xml()
        xml = ET.tostring(self.xslt(ET.fromstring(xml)), pretty_print=True)
        self.act = cobalt.Act(xml)

        # frbr_uri
        self.act.frbr_uri = "/za/act/1996/constitution"

        # metadata
        self.act.work_date = "1996-12-04"
        now = datetime.datetime.now()
        self.act.expression_date = now.strftime("%Y-%m-%d")
        self.act.manifestation_date = now.strftime("%Y-%m-%d")
        self.act.language = language
        self.act.title = title

        self.act.meta.identification.FRBRExpression.FRBRauthor.set('href', '#myconstitution')
        ref = self.act._make('TLCOrganization')
        ref.set('id', 'myconstitution')
        ref.set('href', 'http://myconstitution.co.za/')
        ref.set('showAs', 'MyConstitution.co.za')
        self.act.meta.references.insert(0, ref)

        self.act.meta.identification.FRBRManifestation.FRBRauthor.set('href', '#cobalt')

    def transform(self, fname):
        # sanitize into proper XML
        text = open(fname).read()
        html = html5parser.fromstring(text)
        text = ET.tostring(html)

        html = objectify.fromstring(text)
        self.ns = html.nsmap[None]
        self.nsmap = html.nsmap
        self.maker = objectify.ElementMaker(annotate=False, namespace=self.act.namespace, nsmap=self.act.act.nsmap)
        root = self.xpath(html, "//h:div[@id='wrapper']")[0]
        self.main(root)

    def main(self, root):
        context = None

        for elem in root.iterchildren():
            tagname = tag(elem)
            if not tagname:
                continue

            if tagname == 'h1':
                num = self.num_re.match(elem.text)

                if not num:
                    # assume preamble
                    try:
                        self.act.act.preamble
                        raise ValueError("Duplicate preamble?")
                    except AttributeError:
                        pass

                    preamble = self.maker.preamble()
                    self.act.act.insert(1, preamble)
                    context = preamble
                else:
                    # normal chapter
                    chapter = self.maker.chapter()
                    chapter.append(self.maker.num(num.groups()[1]))
                    chapter.append(self.maker.heading(num.groups()[3]))
                    chapter.set('id', 'chapter-%s' % num.groups()[2])
                    self.act.body.append(chapter)
                    context = chapter

            elif tagname == 'h2' or tagname == 'h3':
                num = self.num_re.match(elem.text)
                if not num:
                    context.append(self.maker.p(elem.text))
                else:
                    # section
                    section = self.maker.section()
                    section.append(self.maker.num(num.groups()[1]))
                    section.append(self.maker.heading(num.groups()[3]))
                    section.set('id', 'section-%s' % num.groups()[2])
                    chapter.append(section)
                    context = section

            else:
                # tail and node text?
                self.process(context, [elem], 0, context.get('id'))

    def xpath(self, node, xp):
        return node.xpath(xp, namespaces={'h': self.ns})

    def gather_text(self, name, elem):
        # gather all text content in elem and place it into context
        context = getattr(self.maker, name)(elem.text)

        for child in elem.iterchildren():
            if tag(child) == 'br':
                eol = self.maker.eol()
                eol.tail = child.tail
                context.append(eol)

        return context

    def process(self, context, elements, level, idprefix):
        list_count = 0

        for i, elem in enumerate(elements):
            tagname = tag(elem)

            if tagname == 'ol':
                if level > 0:
                    blockList = self.maker.blockList()
                    temp_id = idprefix + ".list%s" % list_count
                    blockList.set('id', temp_id)
                    list_count += 1
                    context.append(blockList)
                    self.process(blockList, elem.iterchildren(), level + 1, temp_id)
                else:
                    self.process(context, elem.iterchildren(), level, idprefix)

            elif tagname == 'li':
                if level == 0:
                    ss = self.maker.subsection()
                    ss.append(self.maker.num(format_num(level, i + 1)))
                    temp_id = idprefix + '.%s' % level_num(level, i + 1)
                    ss.set('id', temp_id)
                    context.append(ss)
                    item = self.maker.content()
                    ss.append(item)

                else:
                    item = self.maker.item()
                    item.append(self.maker.num(format_num(level, i + 1)))
                    temp_id = idprefix + '.%s' % level_num(level, i + 1)
                    item.set('id', temp_id)
                    context.append(item)

                if elem.text:
                    item.append(self.gather_text('p', elem))

                self.process(item, elem.iterchildren(), level + 1, temp_id)

            elif tagname == 'blockquote':
                remark = self.gather_text('remark', elem.p)
                remark.set('status', 'editorial')
                p = self.maker.p()
                p.append(remark)
                context.append(p)

            elif tagname in ['p', 'div', 'table', 'ul']:
                # let the xsl handle this
                context.append(elem)

            elif tagname == 'table':
                context.append(elem)

            else:
                raise ValueError("Unhandled tag: %s" % tagname)


def load_languages():
    config = yaml.load(open("constitution/_config.yml", "r"))

    languages = {
        x['values']['language']: x['values'] for x in config['defaults'] if len(x.get('scope', {}).get('path')) >= 2
    }

    for code in languages.iterkeys():
        if len(code) == 3:
            languages[code]['long_code'] = code
        else:
            languages[code]['long_code'] = pycountry.languages.get(alpha_2=code).alpha_3

    return languages


if __name__ == '__main__':
    langs = load_languages()

    for code, lang in langs.iteritems():
        if code not in ['en', 'xh']:
            continue
        print("Doing %s" % code)

        parts = ['0-5-preamble.html'] + ['%02d.html' % i for i in range(1, 14)]
        parts = ['constitution/_site/%s/%s' % (code, p) for p in parts]
        # TODO schedules

        tr = Transformer()
        tr.transform_all(parts, language=lang['long_code'], title=lang['book-title'])

        with open('%s.xml' % code, 'w') as f:
            f.write(tr.act.to_xml())
