"""Conservative mail-body repairs shared by versioned upgrade scripts.

Preserve existing QWeb attributes and custom content; only exact legacy hrefs,
known text expressions and direct date outputs are selected for repair.
"""
import re
from html import escape, unescape
from html.parser import HTMLParser
from urllib.parse import unquote


_ATTRIBUTE = re.compile(
    r'''(?P<name>[^\s=<>/'"]+)(?:\s*=\s*(?P<value>"[^"]*"|'[^']*'|[^\s>]+))?'''
)


def repair_mail_body(body, expressions=(), date_fields=(), repair_links=False):
    replacements = {expression: expression for expression in expressions}
    dates = {
        'object.' + field: "format_datetime(object.%s, tz=ctx.get('tz') or user.tz or 'UTC')" % field
        for field in date_fields
    }
    replacements.update(dates)

    class RepairParser(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=False)
            self.output = []
            self.raw_tags = []
            self.text = []

        def _start(self, tag):
            markup = self.get_starttag_text()

            def repair_attribute(match):
                name, raw = match.group('name', 'value')
                if raw is None:
                    return match.group(0)
                value = unescape(raw[1:-1] if raw[:1] in ('"', "'") else raw)
                if repair_links and name == 'href':
                    for key in ('confirm_url', 'reject_url'):
                        expression = "ctx.get('%s', '#')" % key
                        if unquote(value) == '{{ ' + expression + ' }}':
                            return 't-att-href="' + escape(expression, quote=True) + '"'
                if name in ('t-out', 't-esc') and value in dates:
                    return 't-out="' + escape(dates[value], quote=True) + '"'
                return match.group(0)

            self.output.append(_ATTRIBUTE.sub(repair_attribute, markup))

        def handle_starttag(self, tag, attrs):
            self._flush_text()
            self._start(tag)
            if tag in ('script', 'style'):
                self.raw_tags.append(tag)

        def handle_startendtag(self, tag, attrs):
            self._flush_text()
            self._start(tag)

        def handle_endtag(self, tag):
            self._flush_text()
            self.output.append('</' + tag + '>')
            if self.raw_tags and self.raw_tags[-1] == tag:
                self.raw_tags.pop()

        def _flush_text(self):
            data = ''.join(self.text)
            self.text.clear()
            if not self.raw_tags:
                for old, new in replacements.items():
                    node = '<t t-out="' + escape(new, quote=True) + '"/>'
                    data = data.replace('{{ ' + old + ' }}', node)
                    # Repair ONLY known nodes escaped by the previous Markup
                    # migration. Never unescape arbitrary resident/custom HTML.
                    for directive in ('t-out', 't-esc'):
                        for quote in ('"', '&quot;', '&#34;', '&#x22;'):
                            for expression in (old, escape(old, quote=True)):
                                broken = '&lt;t ' + directive + '=' + quote + expression + quote + '/&gt;'
                                data = data.replace(broken, node)
            self.output.append(data)

        def handle_data(self, data):
            self.text.append(data)

        def handle_entityref(self, name):
            self.text.append('&' + name + ';')

        def handle_charref(self, name):
            self.text.append('&#' + name + ';')

        def handle_comment(self, data):
            self._flush_text()
            self.output.append('<!--' + data + '-->')

        def handle_decl(self, decl):
            self._flush_text()
            self.output.append('<!' + decl + '>')

        def handle_pi(self, data):
            self._flush_text()
            self.output.append('<?' + data + '>')

    parser = RepairParser()
    # fields.Html returns Markup; Markup.replace escapes newly inserted tags.
    parser.feed(str(body))
    parser.close()
    parser._flush_text()
    return ''.join(parser.output)


def repair_visitor_mail_templates(env):
    """Repair all stored languages, including artifacts from the former migration."""
    expressions = (
        'object.visitor_id.name', 'object.purpose_id.name', 'object.unit_id.name',
        'object.create_date', 'object.checkin_time', 'object.name', 'object.phone',
        "object.blacklist_reason or '未說明'", 'object.blacklist_date',
    )
    languages = set(env['res.lang'].search([]).mapped('code')) | {'en_US'}
    for name in ('visit_confirm_request', 'appointment_visitor_arrived', 'blacklist_alert'):
        template = env.ref('community_visitor.mail_template_' + name, raise_if_not_found=False)
        if not template:
            continue
        # Snapshot translations before writing the source language: Odoo may
        # synchronize translated HTML terms when source markup changes.
        originals = {lang: template.with_context(lang=lang).body_html or '' for lang in languages}
        for lang in sorted(languages, key=lambda lang: lang != 'en_US'):
            body = originals[lang]
            updated = repair_mail_body(
                body, expressions=expressions, date_fields=('create_date', 'checkin_time'),
                repair_links=True,
            )
            localized = template.with_context(lang=lang)
            if updated != str(localized.body_html or ''):
                localized.body_html = updated
