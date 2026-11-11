"""Repair legacy mail text without rewriting QWeb attributes or custom prose."""
import re
from html import escape

from lxml import etree, html

from odoo import SUPERUSER_ID, api


_INLINE_OBJECT = re.compile(r'{{\s*(object\.[^{}]*?)\s*}}')
_DATE_EXPRESSIONS = {'object.received_date', 'object.notified_date', 'object.deposit_date'}


def _format_expression(expression):
    if expression in _DATE_EXPRESSIONS:
        return "format_datetime(%s, tz=ctx.get('tz') or user.tz or 'UTC')" % expression
    return expression


def _repair_body(body):
    if not body:
        return body
    root = html.fragment_fromstring(body, create_parent='div')
    slots = []
    changed = False
    for node in root.iter():
        if not isinstance(node.tag, str):
            continue
        if node.tag not in ('script', 'style') and node.text:
            slots.append((node, None, node.text))
        if node is not root and node.tail:
            slots.append((node.getparent(), node, node.tail))
        # Format only a direct datetime output, never arbitrary attributes such
        # as t-attf-href="/my/parcels/{{ object.id }}" or customized expressions.
        for attribute in ('t-out', 't-esc'):
            expression = node.get(attribute)
            if expression in _DATE_EXPRESSIONS:
                node.set(attribute, _format_expression(expression))
                changed = True
    for parent, previous, text in slots:
        matches = list(_INLINE_OBJECT.finditer(text))
        if not matches:
            continue
        changed = True
        prefix = text[:matches[0].start()]
        if previous is None:
            parent.text = prefix
            index = 0
        else:
            previous.tail = prefix
            index = parent.index(previous) + 1
        for number, match in enumerate(matches):
            output = etree.Element('t')
            output.set('t-out', _format_expression(match[1]))
            end = matches[number + 1].start() if number + 1 < len(matches) else len(text)
            output.tail = text[match.end():end]
            parent.insert(index, output)
            index += 1
    if not changed:
        return body
    return escape(root.text or '', quote=False) + ''.join(
        etree.tostring(child, encoding='unicode') for child in root
    )


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for name in ('parcel_arrival', 'parcel_overdue', 'storage_ready'):
        template = env.ref('community_parcel.mail_template_' + name, raise_if_not_found=False)
        if not template:
            continue
        # Snapshot translations first so each customized language is preserved.
        bodies = {
            lang: template.with_context(lang=lang).body_html
            for lang in set(env['res.lang'].search([]).mapped('code') + ['en_US'])
        }
        for lang, body in bodies.items():
            repaired = _repair_body(body)
            if repaired != body:
                template.with_context(lang=lang).body_html = repaired
