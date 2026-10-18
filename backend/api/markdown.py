"""One fixed Markdown outline, with fence-aware section extraction."""
import re
from backend.domain import Problem

HEADINGS = ['Overview', 'Details', 'Next steps']
TEMPLATE = '\n\n'.join(f'## {heading}' for heading in HEADINGS).strip() + '\n'


def sections(content):
    result, lines, heading, fence = [], [], None, None
    for line in content.splitlines():
        marker = re.match(r'^ {0,3}(`{3,}|~{3,})(.*)$', line)
        if marker:
            token, suffix = marker.groups()
            if fence is None:
                fence = (token[0], len(token))
            elif token[0] == fence[0] and len(token) >= fence[1] and not suffix.strip():
                fence = None
        match = re.match(r'^## (.+)$', line) if fence is None and not marker else None
        if match:
            if heading is not None or any(part.strip() for part in lines):
                result.append({'key': str(len(result)), 'heading': heading or 'Content', 'body': '\n'.join(lines).strip()})
            heading, lines = match[1], []
        else:
            if fence is None and not marker and re.match(r'^ {0,3}#{1,2}(?:\s|$)', line):
                raise Problem('Use the fixed ## Overview, ## Details and ## Next steps headings; use ### for subheadings.', 422)
            lines.append(line)
    if heading is not None or any(part.strip() for part in lines):
        result.append({'key': str(len(result)), 'heading': heading or 'Content', 'body': '\n'.join(lines).strip()})
    return result


def validate(content):
    if '\x00' in content or len(content.encode('utf-8')) > 12000:
        raise Problem('Markdown must fit within 12,000 UTF-8 bytes and contain no null characters.', 422)
    if [part['heading'] for part in sections(content)] != HEADINGS:
        raise Problem('Keep the fixed Markdown outline: ## Overview, ## Details, ## Next steps, in that order.', 422)
