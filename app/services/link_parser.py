import re
import unicodedata

WIKILINK_RE = re.compile(r'\[\[([^\]|]+)(?:\|([^\]]+))?\]\]')
TAG_RE = re.compile(r'(?:^|\s)#([a-zA-Z][a-zA-Z0-9_/-]*)', re.MULTILINE)
FRONTMATTER_RE = re.compile(r'^---\s*\n(.*?)\n---\s*\n', re.DOTALL)


def slugify(title: str) -> str:
    text = unicodedata.normalize('NFKD', title)
    text = text.encode('ascii', 'ignore').decode('ascii')
    text = re.sub(r'[^\w\s-]', '', text.lower())
    text = re.sub(r'[-\s]+', '-', text).strip('-')
    return text or 'untitled'


def extract_links(content: str) -> list[dict]:
    results = []
    for match in WIKILINK_RE.finditer(content):
        target = match.group(1).strip()
        alias = match.group(2)
        start = max(0, match.start() - 80)
        end = min(len(content), match.end() + 80)
        context = content[start:end].replace('\n', ' ').strip()
        results.append({
            "target": slugify(target),
            "target_title": target,
            "alias": alias.strip() if alias else None,
            "context": context,
        })
    return results


def extract_tags(content: str) -> list[str]:
    tags = set()
    for match in TAG_RE.finditer(content):
        tags.add(match.group(1).lower())
    return sorted(tags)


def parse_frontmatter(content: str) -> tuple[dict, str]:
    match = FRONTMATTER_RE.match(content)
    if not match:
        return {}, content
    import yaml
    try:
        meta = yaml.safe_load(match.group(1)) or {}
    except Exception:
        meta = {}
    body = content[match.end():]
    return meta, body


def render_wikilinks_html(content: str) -> str:
    def replacer(match):
        target = match.group(1).strip()
        alias = match.group(2)
        display = alias.strip() if alias else target
        slug = slugify(target)
        return f'<a href="#/note/{slug}" class="wikilink" data-target="{slug}">{display}</a>'
    return WIKILINK_RE.sub(replacer, content)
