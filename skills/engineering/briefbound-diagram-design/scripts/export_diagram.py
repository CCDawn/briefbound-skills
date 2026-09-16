"""Render checked diagram HTML to editable SVG and/or PNG using Playwright."""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--format', choices=('png', 'svg', 'both'), default='both')
    parser.add_argument('--scale', type=float, default=2)
    parser.add_argument('--browser-executable')
    parser.add_argument('--overwrite', action='store_true')
    args = parser.parse_args()
    source = args.source.resolve()
    if not source.is_file() or source.suffix.lower() != '.html':
        parser.error('source must be an existing HTML file')
    if not 0 < args.scale <= 8:
        parser.error('scale must be greater than 0 and at most 8')
    formats = ('svg', 'png') if args.format == 'both' else (args.format,)
    targets = {kind: source.with_suffix('.' + kind) for kind in formats}
    for target in targets.values():
        if target.exists() and not args.overwrite:
            parser.error(f'output already exists: {target}; use --overwrite intentionally')
    checked = subprocess.run([sys.executable, str(Path(__file__).with_name('self_check.py')), str(source)])
    if checked.returncode:
        return checked.returncode
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print('Playwright is unavailable; use an existing browser capability or install Playwright in a task-local environment.', file=sys.stderr)
        return 2
    with sync_playwright() as playwright:
        launch = {'executable_path': args.browser_executable} if args.browser_executable else {}
        browser = playwright.chromium.launch(**launch)
        try:
            page = browser.new_page(viewport={'width': 1440, 'height': 1000}, device_scale_factor=args.scale)
            page.emulate_media(reduced_motion='reduce')
            page.goto(source.as_uri() + '?motion=static', wait_until='networkidle')
            page.evaluate('document.fonts.ready')
            svg = page.locator('svg[role="img"]').first
            svg.wait_for(state='visible')
            if page.locator('[data-motion-mode]').count():
                frames = page.locator('[data-motion-mode]').evaluate_all('(nodes) => nodes.map(n => n.dataset.frame)')
                if any(frame not in (None, 'static') for frame in frames):
                    raise RuntimeError('motion root has not reached the static frame')
            if 'svg' in targets:
                serialized = svg.evaluate('''root => {
                    const copy = root.cloneNode(true);
                    const originals = [root, ...root.querySelectorAll('*')];
                    const clones = [copy, ...copy.querySelectorAll('*')];
                    const properties = ['fill','fill-opacity','stroke','stroke-width','stroke-opacity',
                        'stroke-dasharray','stroke-linecap','stroke-linejoin','opacity','color',
                        'font-family','font-size','font-weight','font-style','letter-spacing',
                        'text-anchor','dominant-baseline','visibility','display','paint-order'];
                    originals.forEach((node, i) => {
                        const style = getComputedStyle(node);
                        properties.forEach(p => clones[i].style.setProperty(p, style.getPropertyValue(p)));
                    });
                    copy.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
                    return new XMLSerializer().serializeToString(copy);
                }''')
                targets['svg'].write_text('<?xml version="1.0" encoding="UTF-8"?>\n' + serialized + '\n', encoding='utf-8')
            if 'png' in targets:
                svg.screenshot(path=str(targets['png']), omit_background=True)
        finally:
            browser.close()
    for target in targets.values():
        print(target)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
