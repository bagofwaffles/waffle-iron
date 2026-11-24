#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Draws the two units for the install page: docs/devices/.

    tools/web_devices.py

It writes op-xy.svg and op-1-field.svg, top views on one 17 x 6 key grid, and parts.json: the
center and size of each part a step may point at (a key, a knob, the power switch, the USB port),
in the drawing's own units. Every part also carries its name as an id in the drawing. Colors are
CSS variables with the unit's own color as the fallback, so a page can restyle an inlined drawing.
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'docs', 'devices')

W, H = 1000, 364                    # the drawing
BX, BY, BW, BH = 8, 8, 972, 348     # the body
X0, Y0, CELL = 21, 23, 53           # the key grid: 17 columns, 6 rows
COLS, ROWS = 17, 6
GX1, GY1 = X0 + COLS * CELL, Y0 + ROWS * CELL
SX = (GX1 + BX + BW) / 2            # the middle of the bare strip right of the keys
# Black keys sit on the line between two white keys: the column to their left.
BLACK = (4, 5, 6, 8, 9, 11, 12, 13, 15, 16)
# The tiles under the black keys, as the grid lines where one ends and the next starts.
BLACK_TILES = (3, 4.5, 5.5, 7, 8.5, 10, 11.5, 12.5, 14, 15.5, 17)

XY = {
    'name': 'op-xy', 'title': 'OP-XY',
    'body': '#222326', 'edge': '#0a0a0b', 'line': '#0b0b0c', 'key': '#232427', 'key-edge': '#3e4044',
    'ink': '#e6e6e3', 'dim': '#0f0f10', 'screen': '#050506', 'black-key': '#232427',
    'accent': '#e2412b', 'knobs': ('#3b3d42', '#7b7f87', '#b9bbbd', '#f3f3f0'), 'ring': '#2a2b2e',
    'switch': '#bdbdb9', 'tile': '#2d2e31', 'shade': '#121214', 'mark': '#8a8c90',
    'steps': ('#4b4f56', '#dcdbd6'),
}
FIELD = {
    'name': 'op-1-field', 'title': 'OP-1 Field',
    'body': '#cfcfcc', 'edge': '#9a9a96', 'line': '#1b1b1c', 'key': '#f2f0eb', 'key-edge': '#cbc7bf',
    'ink': '#454543', 'dim': '#3a3a38', 'screen': '#0b0b0c', 'black-key': '#151516',
    'accent': '#e2562b', 'knobs': ('#2b3563', '#b59a62', '#909293', '#e2562b'), 'ring': '#f2f0eb',
    'switch': '#bdbdb9', 'tile': '#e6e3dd', 'shade': '#bdb9b0', 'mark': '#3b3b3a',
    'tall-keys': True, 'stroke': 1.2, 'sub-weight': 500,
}


def cx(col):
    return X0 + (col - 0.5) * CELL


def cy(row):
    return Y0 + (row - 0.5) * CELL


def num(v):
    return ('%.1f' % v).rstrip('0').rstrip('.')


class Drawing:
    def __init__(self, look):
        self.look = look
        self.out = []
        self.parts = {}

    def var(self, name):
        return 'var(--dw-%s, %s)' % (name, self.look[name])

    def add(self, text):
        self.out.append(text)

    def part(self, name, x, y, w, h, shape):
        self.parts[name] = {'x': round(x, 1), 'y': round(y, 1), 'w': w, 'h': h, 'shape': shape}

    def glyph(self, kind, x, y, color='ink'):
        """A key's marking, drawn around (x, y)."""
        ink, n = self.var(color), num
        line = ('fill="none" stroke="%s" stroke-width="%s" stroke-linecap="round" stroke-linejoin="round"'
                % (ink, self.look.get('stroke', 1.6)))
        if kind == 'rec':
            return '<circle cx="%s" cy="%s" r="4.5" fill="%s"/>' % (n(x), n(y), ink)
        if kind == 'play':
            return '<path d="M%s %sv10l9-5z" fill="%s"/>' % (n(x - 3.5), n(y - 5), ink)
        if kind == 'stop':
            return '<rect x="%s" y="%s" width="9" height="9" fill="%s"/>' % (n(x - 4.5), n(y - 4.5), ink)
        if kind == 'minus':
            return '<path d="M%s %sh14" %s/>' % (n(x - 7), n(y), line)
        if kind == 'plus':
            return '<path d="M%s %sh14M%s %sv14" %s/>' % (n(x - 7), n(y), n(x), n(y - 7), line)
        if kind == 'left':
            return '<path d="M%s %sh-14m5-5l-5 5 5 5" %s/>' % (n(x + 7), n(y), line)
        if kind == 'right':
            return '<path d="M%s %sh14m-5-5l5 5-5 5" %s/>' % (n(x - 7), n(y), line)
        if kind == 'up':
            return '<path d="M%s %sv-12m-5 5l5-5 5 5M%s %sh12" %s/>' % (n(x), n(y + 4), n(x - 6), n(y + 8), line)
        if kind == 'down':
            return '<path d="M%s %sv12m-5-5l5 5 5-5M%s %sh12" %s/>' % (n(x), n(y - 8), n(x - 6), n(y + 8), line)
        if kind == 'dots':
            return ''.join('<circle cx="%s" cy="%s" r="1.6" fill="%s"/>' % (n(x + dx), n(y + dy), ink)
                           for dx, dy in ((-7.5, 2), (-2.5, -2), (2.5, 2), (7.5, 2)))
        if kind == 'wave':
            return '<path d="M%s %sq4-12 8 0t8 0" %s/>' % (n(x - 8), n(y), line)
        if kind == 'synth':
            return '<path d="M%s %sv-8h4v8h4v-8h4v8h4v-8" %s/>' % (n(x - 8), n(y + 4), line)
        if kind == 'drum':
            return '<circle cx="%s" cy="%s" r="6" %s/><circle cx="%s" cy="%s" r="1.6" fill="%s"/>' % (
                n(x), n(y), line, n(x), n(y), ink)
        if kind == 'bars':
            return '<path d="M%s %sv-6m4 6v-12m4 12v-9m4 9v-5" %s/>' % (n(x - 6), n(y + 6), line)
        if kind == 'ring':
            return '<circle cx="%s" cy="%s" r="5" %s/>' % (n(x), n(y), line)
        if kind == 'tape':
            return ('<circle cx="%s" cy="%s" r="3.5" %s/><circle cx="%s" cy="%s" r="3.5" %s/>'
                    '<path d="M%s %sh10" %s/>' % (n(x - 5), n(y), line, n(x + 5), n(y), line,
                                                  n(x - 5), n(y + 3.5), line))
        if kind == 'cut':
            return ('<circle cx="%s" cy="%s" r="2.6" %s/><circle cx="%s" cy="%s" r="2.6" %s/>'
                    '<path d="M%s %sl11.5-7.5M%s %sl11.5 7.5" %s/>'
                    % (n(x - 5.5), n(y - 4), line, n(x - 5.5), n(y + 4), line,
                       n(x - 3.5), n(y + 2.5), n(x - 3.5), n(y - 2.5), line))
        if kind == 'mic':
            return '<path d="M%s %sl8-8" %s/><circle cx="%s" cy="%s" r="2.6" fill="%s"/>' % (
                n(x - 5), n(y + 5), line, n(x + 4), n(y - 4), ink)
        if kind == 'tempo':
            return ('<path d="M%s %sh11l-3.5-14h-4zM%s %sl5.5-8.5" %s/><circle cx="%s" cy="%s" r="1.3" fill="%s"/>'
                    % (n(x - 5.5), n(y + 7.5), n(x - 0.5), n(y + 4), line, n(x + 5.6), n(y - 5.6), ink))
        if kind == 'help':
            return '<rect x="%s" y="%s" width="16" height="10" rx="5" %s/><path d="M%s %sv3.5" %s/>' % (
                n(x - 8), n(y - 6.5), line, n(x), n(y + 3.5), line)
        if kind == 'pad':
            return ('<circle cx="%s" cy="%s" r="6" %s/><circle cx="%s" cy="%s" r="1.6" fill="%s"/>'
                    '<path d="M%s %sv5" %s/>' % (n(x), n(y), line, n(x), n(y - 0.5), ink, n(x), n(y + 1), line))
        if kind == 'pen':
            return ('<path d="M%s %sl4-9 5 5zM%s %sl3.5-3.5 5 5-3.5 3.5z" fill="%s"/>'
                    % (n(x - 8), n(y + 8), n(x - 2.5), n(y - 3), ink))
        if kind == 'metro':
            return ('<path d="M%s %sh13l-4-15h-5z" fill="%s"/><path d="M%s %sv-8" fill="none" stroke="%s" '
                    'stroke-width="1.6"/>' % (n(x - 6.5), n(y + 7.5), ink, n(x), n(y + 3), self.var('key')))
        if kind == 'arch':
            return '<path d="M%s %sv-3a5 5 0 0 1 10 0v3" %s/>' % (n(x - 5), n(y + 3), line)
        if kind == 'plug':
            return ('<path d="M%s %sh19" %s/><rect x="%s" y="%s" width="9" height="5" rx="1" fill="%s"/>'
                    '<circle cx="%s" cy="%s" r="1.6" fill="%s"/>'
                    % (n(x - 10), n(y), line, n(x - 6), n(y - 2.5), ink, n(x + 9), n(y), ink))
        if kind == 'blocks':
            return ('<path d="M%s %sh7v5h-7zM%s %sh7v5h-7z" fill="none" stroke="%s" stroke-width="1.2"/>'
                    '<rect x="%s" y="%s" width="7.6" height="5.5" fill="%s"/>'
                    % (n(x - 11.5), n(y - 1.5), n(x + 4.5), n(y - 1.5), ink, n(x - 3.8), n(y - 4), ink))
        if kind == 'faders':
            return ''.join('<path d="M%s %sv14M%s %sh3.6" fill="none" stroke="%s" stroke-width="1.2"/>'
                           % (n(x + dx), n(y - 7), n(x + dx - 1.8), n(y + dy), ink)
                           for dx, dy in ((-8, 2), (-4, -3), (0, 0), (4, -4), (8, 3)))
        if kind == 'sample':
            return ''.join('<path d="M%s %sv%s" %s/>' % (n(x + dx), n(y - h / 2), n(h), line)
                           for dx, h in ((-9, 1), (-5.5, 5), (-2, 13), (1.5, 7), (5, 3), (8.5, 1)))
        if kind == 'pixels':
            return ''.join('<rect x="%s" y="%s" width="3" height="3" fill="%s"/>' % (n(x + dx), n(y + dy), ink)
                           for dx, dy in ((-10.5, 2), (-6.5, 2), (-2.5, -1.5), (1.5, -5), (5.5, -1.5), (9.5, -1.5)))
        if kind == 'four':
            return ''.join('<circle cx="%s" cy="%s" r="2.3" fill="%s"/>' % (n(x + dx), n(y), ink)
                           for dx in (-9.6, -3.2, 3.2, 9.6))
        if kind == 'hand':
            return ('<path d="M%s %sl-2.5-7M%s %sl-.8-9M%s %sl1-9M%s %sl2.8-7M%s %sl-4-3" fill="none" '
                    'stroke="%s" stroke-width="2.2" stroke-linecap="round"/>'
                    '<path d="M%s %sh9l-1 7h-6z" fill="%s" stroke="%s" stroke-width="1.5" stroke-linejoin="round"/>'
                    % (n(x - 3.5), n(y + 1), n(x - 1), n(y), n(x + 1.8), n(y), n(x + 4.5), n(y + 1),
                       n(x - 4), n(y + 5), ink, n(x - 4), n(y + 1), ink, ink))
        if kind == 'divide':
            return ('<path d="M%s %sh16" %s/><circle cx="%s" cy="%s" r="2" fill="%s"/>'
                    '<circle cx="%s" cy="%s" r="2" fill="%s"/>'
                    % (n(x - 8), n(y), line, n(x), n(y - 6), ink, n(x), n(y + 6), ink))
        if kind == 'ramp':
            return '<path d="M%s %sh20v-9z" fill="%s"/>' % (n(x - 10), n(y + 5), ink)
        if kind == 'stairs-up':
            return '<path d="M%s %sv-4h5v-4h5v-4h8v3h-5v4h-5v4h-5v1z" fill="%s"/>' % (n(x - 9), n(y + 7), ink)
        if kind == 'stairs-down':
            return '<path d="M%s %sv-4h-5v-4h-5v-4h-8v3h5v4h5v4h5v1z" fill="%s"/>' % (n(x + 9), n(y + 7), ink)
        if kind == 'notes':
            return ('<circle cx="%s" cy="%s" r="2" fill="%s"/><circle cx="%s" cy="%s" r="2" fill="%s"/>'
                    '<path d="M%s %sv-9M%s %sv-9l3 2" fill="none" stroke="%s" stroke-width="1.2"/>'
                    '<path d="M%s %sl7-4" fill="none" stroke="%s" stroke-width="1.2" stroke-dasharray="1.5 1.5"/>'
                    % (n(x - 8), n(y + 5), ink, n(x + 5), n(y + 4), ink, n(x - 6.2), n(y + 5),
                       n(x + 6.8), n(y + 4), ink, n(x - 4), n(y + 1), ink))
        if kind == 'fin':
            return ('<path d="M%s %sq1-13 9-16q-3 8 0 16zM%s %sq0-7 4-10q-1 5 3 10z" fill="%s"/>'
                    % (n(x - 8), n(y + 8), n(x + 3), n(y + 8), ink))
        if kind == 'clover':
            return ''.join('<circle cx="%s" cy="%s" r="3.6" fill="%s"/>' % (n(x + dx), n(y + dy), ink)
                           for dx, dy in ((-3.8, -3.8), (3.8, -3.8), (-3.8, 3.8), (3.8, 3.8)))
        if kind == 'into':
            return '<path d="M%s %sh12m-4-4l4 4-4 4" %s/><circle cx="%s" cy="%s" r="2.6" fill="%s"/>' % (
                n(x - 11), n(y), line, n(x + 8), n(y), ink)
        if kind == 'wheel':
            return ('<circle cx="%s" cy="%s" r="7.5" fill="%s"/><path d="M%s %sh15M%s %sv15M%s %sl10.6 10.6'
                    'M%s %sl-10.6 10.6" fill="none" stroke="%s" stroke-width="1.3"/>'
                    % (n(x), n(y), ink, n(x - 7.5), n(y), n(x), n(y - 7.5), n(x - 5.3), n(y - 5.3),
                       n(x + 5.3), n(y - 5.3), self.var('key')))
        if kind == 'burst':
            return ('<circle cx="%s" cy="%s" r="5" fill="none" stroke="%s" stroke-width="5" '
                    'stroke-dasharray="2.2 1.727"/>' % (n(x), n(y), ink))
        if kind == 'sun':
            return ('<circle cx="%s" cy="%s" r="3.6" fill="%s"/><circle cx="%s" cy="%s" r="6.5" fill="none" '
                    'stroke="%s" stroke-width="4" stroke-dasharray=".9 1.369"/>' % (n(x), n(y), ink, n(x), n(y), ink))
        if kind == 'dome':
            return '<path d="M%s %sa5 5 0 0 1 10 0zM%s %sh12v1.5h-12z" fill="%s"/>' % (
                n(x - 5), n(y + 1), n(x - 6), n(y + 2.5), ink)
        if kind == 'blob':
            return '<path d="M%s %sa5 5 0 1 1 7 4.5l-1 3.5h-3v-2.5h-2z" fill="%s"/>' % (n(x - 4), n(y + 1), ink)
        if kind == 'dial':
            return ('<circle cx="%s" cy="%s" r="4.8" fill="none" stroke="%s" stroke-width="1.2"/>'
                    '<circle cx="%s" cy="%s" r="1.5" fill="%s"/>' % (n(x), n(y), ink, n(x), n(y), ink))
        if kind == 'cv':
            return self.text('cv', x, y, 9, weight=400)
        if kind == 'kit':
            return ('<rect x="%s" y="%s" width="12" height="3" fill="%s"/><circle cx="%s" cy="%s" r="2" fill="%s"/>'
                    '<circle cx="%s" cy="%s" r="2" fill="%s"/><path d="M%s %sv-3" fill="none" stroke="%s" '
                    'stroke-width="2"/>' % (n(x - 6), n(y - 3), ink, n(x - 3), n(y + 4), ink, n(x + 3), n(y + 4), ink,
                                            n(x), n(y - 3), ink))
        if kind == 'tape-s':
            return ('<circle cx="%s" cy="%s" r="2.6" fill="none" stroke="%s" stroke-width="1.2"/>'
                    '<circle cx="%s" cy="%s" r="2.6" fill="none" stroke="%s" stroke-width="1.2"/>'
                    '<path d="M%s %sh7" fill="none" stroke="%s" stroke-width="1.2"/>'
                    % (n(x - 3.5), n(y), ink, n(x + 3.5), n(y), ink, n(x - 3.5), n(y + 2.6), ink))
        if kind == 'loop-s':
            return ('<rect x="%s" y="%s" width="10" height="5.5" rx="2.75" fill="none" stroke="%s" '
                    'stroke-width="1.2"/><path d="M%s %sl-2.5-2.5v5z" fill="%s"/>'
                    % (n(x - 5), n(y - 2.5), ink, n(x - 1.5), n(y - 2.5), ink))
        if kind in ('fx1', 'fx2'):
            return ('<rect x="%s" y="%s" width="14" height="10" fill="none" stroke="%s" stroke-width="1.1"/>%s%s'
                    % (n(x - 7), n(y - 5), ink, self.text('FX', x, y, 7.5, weight=600),
                       self.text('I' if kind == 'fx1' else 'II', x - 5, y + 12, 6, weight=600)))
        return ''

    def text(self, label, x, y, size=13, color='ink', weight=500):
        return ('<text x="%s" y="%s" font-size="%s" font-weight="%d" fill="%s">%s</text>'
                % (num(x), num(y + size * 0.35), num(size), weight, self.var(color), label))

    def disc(self, x, y, r, fill, edge='key-edge'):
        """A raised round cap, with its shadow below it where the unit's look has one."""
        shade = ''
        if 'shade' in self.look:
            shade = '<circle cx="%s" cy="%s" r="%s" fill="%s"/>' % (num(x), num(y + 2.5), num(r), self.var('shade'))
        return shade + '<circle cx="%s" cy="%s" r="%s" fill="%s" stroke="%s" stroke-width="1.2"/>' % (
            num(x), num(y), num(r), fill, self.var(edge))

    def key(self, name, col, row, mark='', label='', size=13, r=19, x=None, color='ink', weight=500,
            sub='', led=False, side=''):
        """A round key in one cell; mark is a glyph, label is text. sub goes small under it, as text or
        a glyph's name; side is a small glyph right of the label; led is the hole at the cap's top."""
        x = cx(col) if x is None else x
        y = cy(row)
        up = 4.5 if sub else 0
        at = x - 6.5 if side else x
        inner = self.glyph(mark, x, y - up, color) if mark else ''
        if label:
            inner += self.text(label, at, y - up, size, weight=weight)
        if side:
            inner += self.glyph(side, x + 6.5, y)
        if sub:
            small = self.glyph(sub, x, y + 9)
            inner += small or self.text(sub, x, y + 9, 7.5, weight=self.look.get('sub-weight', 600))
        if led:
            inner += '<circle cx="%s" cy="%s" r="2" fill="%s"/>' % (num(x), num(y - 13), self.var('line'))
        self.add('<g id="%s">%s%s</g>' % (name, self.disc(x, y, r, self.var('key')), inner))
        self.part(name, x, y, 2 * r, 2 * r, 'circle')

    def tile(self, col, row, wide=1, high=1):
        return 'M%s %sh%sv%sh%sz' % (num(X0 + (col - 1) * CELL + 2.5), num(Y0 + (row - 1) * CELL + 2.5),
                                     num(wide * CELL - 5), num(high * CELL - 5), num(5 - wide * CELL))

    def bed(self):
        """What the keys sit in: separate tiles on a dark bed."""
        v = self.var
        tall = self.look.get('tall-keys')
        d = self.tile(1, 1, 2, 2) + self.tile(3, 1, 2, 1) + self.tile(3, 2) + self.tile(4, 2)
        for col in (9, 11, 13, 15):
            d += self.tile(col, 1, 2, 2)
        d += self.tile(17, 1) + self.tile(17, 2)
        for col in range(1, COLS + 1):
            d += self.tile(col, 3)
        for row in (4, 5, 6):
            for col in (1, 2, 3):
                d += self.tile(col, row)
        # The black keys' row: the fourth where tall white keys take the two below, else the fifth.
        for a, b in zip(BLACK_TILES, BLACK_TILES[1:]):
            d += self.tile(a + 1, 4 if tall else 5, b - a)
        for col in range(4, COLS + 1):
            if tall:
                d += self.tile(col, 5, 1, 2)
            else:
                d += self.tile(col, 4) + self.tile(col, 6)
        self.add('<rect x="%d" y="%d" width="%d" height="%d" rx="4" fill="%s"/>'
                 % (X0 - 1, Y0 - 1, COLS * CELL + 2, ROWS * CELL + 2, v('line')))
        self.add('<path d="%s" fill="%s" stroke="%s" stroke-width="3" stroke-linejoin="round"/>'
                 % (d, v('tile'), v('tile')))

    def frame(self):
        look, v = self.look, self.var
        self.add('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" role="img" '
                 'aria-label="The %s, seen from above" font-family="Helvetica Neue, Helvetica, Arial, '
                 'sans-serif" text-anchor="middle">' % (W, H, look['title']))
        self.add('<defs><pattern id="%s-grille" width="6" height="6" patternUnits="userSpaceOnUse">'
                 '<circle cx="3" cy="3" r="1.5" fill="%s"/></pattern></defs>' % (look['name'], v('dim')))
        # The power switch stands out of the right edge, level with the line between the bottom rows.
        px, py = BX + BW - 4, Y0 + 5 * CELL - 17
        self.add('<rect id="power" x="%d" y="%d" width="14" height="34" rx="4" fill="%s" stroke="%s" '
                 'stroke-width="1.5"/>' % (px, py, v('switch'), v('edge')))
        self.part('power', px + 7, py + 17, 14, 34, 'rect')
        self.add('<rect x="%d" y="%d" width="%d" height="%d" rx="13" fill="%s" stroke="%s" stroke-width="2"/>'
                 % (BX, BY, BW, BH, v('body'), v('edge')))
        # The USB port is in the right side, behind the mark on the strip.
        ux, uy = BX + BW - 8, Y0 + 3.3 * CELL - 15
        self.add('<rect id="usb" x="%d" y="%s" width="6" height="30" rx="3" fill="%s"/>'
                 % (ux, num(uy), v('edge')))
        self.part('usb', ux + 3, uy + 15, 6, 30, 'rect')
        self.add('<path d="M%s %sh30M%s %sv24" fill="none" stroke="%s" stroke-width="1"/>'
                 '<path d="M%s %sv44" fill="none" stroke="%s" stroke-width="1.6" stroke-dasharray="1.2 2.4"/>'
                 % (num(SX - 15), num(uy + 15), num(SX), num(uy - 18), v('mark'), num(SX), num(uy + 8), v('mark')))
        self.bed()
        # Speaker, screen, microphone.
        self.add('<circle cx="%d" cy="%d" r="40" fill="url(#%s-grille)"/>' % (X0 + CELL, Y0 + CELL, look['name']))
        sx, sy, sw, sh = X0 + 4 * CELL + 1, Y0 + 1, 4 * CELL - 2, 2 * CELL - 2
        self.add('<rect id="screen" x="%d" y="%d" width="%d" height="%d" rx="3" fill="%s"/>'
                 % (sx, sy, sw, sh, v('screen')))
        self.part('screen', sx + sw / 2, sy + sh / 2, sw, sh, 'rect')
        self.add('<circle cx="%s" cy="%s" r="2" fill="%s"/>' % (num(SX), num(cy(1)), v('edge')))
        # The four knobs, each on two columns: a ring in the panel, a cap, a colored top.
        for i, color in enumerate(look['knobs']):
            x, y = X0 + (9 + 2 * i) * CELL, Y0 + CELL
            name = 'knob-%d' % (i + 1)
            self.add('<g id="%s"><circle cx="%d" cy="%d" r="34" fill="none" stroke="%s" stroke-width="1.2"/>'
                     '%s<circle cx="%d" cy="%d" r="13" fill="var(--dw-%s, %s)"/></g>'
                     % (name, x, y, v('key-edge'), self.disc(x, y, 22, v('ring')), x, y, name, color))
            self.part(name, x, y, 68, 68, 'circle')

    def keyboard_side(self):
        self.key('key-rec', 1, 5, 'rec', color='accent')
        self.key('key-play', 2, 5, 'play')
        self.key('key-stop', 3, 5, 'stop')
        self.key('key-shift', 3, 6, label='shift', size=11, weight=400)

    def finish(self):
        self.add('</svg>')
        return '\n'.join(self.out) + '\n'


def mix(a, b, t):
    """The color t of the way from a to b."""
    return '#' + ''.join('%02x' % round(int(a[i:i + 2], 16) + (int(b[i:i + 2], 16) - int(a[i:i + 2], 16)) * t)
                         for i in (1, 3, 5))


def op_xy():
    d = Drawing(XY)
    d.frame()
    v = d.var
    x, y = cx(3), cy(1)
    d.add('<g id="volume">%s<circle cx="%s" cy="%s" r="1.8" fill="%s"/></g>'
          % (d.disc(x, y, 17, v('key')), num(x + 4), num(y - 7), v('ink')))
    d.key('key-project', 3, 2, 'pen')
    d.key('key-tempo', 4, 2, 'metro')
    d.key('key-sample', 17, 1, 'sample')
    d.key('key-com', 17, 2, label='com', size=12.5, weight=300)
    d.key('key-instrument', 1, 3, 'arch', sub='1–8')
    d.key('key-aux', 2, 3, 'plug', sub='1–8')
    d.key('key-arrange', 3, 3, 'blocks')
    d.key('key-mix', 4, 3, 'faders')
    for i in range(1, 5):
        d.key('key-m%d' % i, 4 + i, 3, label=str(i), size=20, weight=300)
    for i, side in enumerate(('blob', 'dome', 'dial', 'cv', 'kit', 'tape-s', 'fx1', 'fx2'), 1):
        d.key('key-sound-%d' % i, 8 + i, 3, label=str(i), size=14, weight=300, led=True, side=side)
    d.key('key-players', 17, 3, 'pixels')
    # The sixteen step keys run from dark to light two at a time, tile and cap alike.
    for col in range(1, 17):
        color = mix(XY['steps'][0], XY['steps'][1], ((col - 1) // 2) / 7)
        x, y, name = cx(col), cy(4), 'key-step-%d' % col
        d.add('<g id="%s"><rect x="%s" y="%s" width="%d" height="%d" rx="3" fill="%s"/>'
              '<circle cx="%s" cy="%s" r="19" fill="#000" fill-opacity=".3"/>'
              '<circle cx="%s" cy="%s" r="19" fill="%s" stroke="#fff" stroke-opacity=".18" stroke-width="1.2"/>'
              '<circle cx="%s" cy="%s" r="2.2" fill="%s"/></g>'
              % (name, num(x - CELL / 2 + 1), num(y - CELL / 2 + 1), CELL - 2, CELL - 2, color,
                 num(x), num(y + 2.5), num(x), num(y), color, num(x), num(y - 11), v('line')))
        d.part(name, x, y, 38, 38, 'circle')
    x, y = cx(17), cy(4)
    d.add('<g id="key-bar">%s%s<rect x="%s" y="%s" width="24" height="11" rx="1.5" fill="%s"/>'
          '<text x="%s" y="%s" font-size="8.5" font-weight="600" fill="%s">BAR</text></g>'
          % (d.disc(x, y, 19, v('key')), d.text('1–4', x, y - 8, 7, weight=400), num(x - 12), num(y - 2),
             v('ink'), num(x), num(y + 6.5), v('key')))
    d.part('key-bar', x, y, 38, 38, 'circle')
    d.keyboard_side()
    d.key('key-minus', 1, 6, 'minus')
    d.key('key-plus', 2, 6, 'plus')
    d.add(d.text('num', X0 + 3 * CELL + 14, cy(5) - 15, 9, weight=400))
    for n, col in enumerate(BLACK):
        d.key('key-num-%d' % ((n + 1) % 10), col, 5, label=str((n + 1) % 10), size=14, weight=300,
              x=X0 + col * CELL, led=True)
    marks = ('four', 'hand', 'divide', 'ramp', 'stairs-up', 'stairs-down', '', 'notes', 'fin', 'clover',
             'into', 'wheel', 'burst', 'sun')
    for col, mark in enumerate(marks, 4):
        d.key('key-note-%d' % (col - 3), col, 6, mark, led=True,
              label='' if mark else '<tspan font-style="italic">rnd</tspan>', size=12, weight=400)
    d.add('<text transform="translate(%s %s) rotate(-90)" font-size="25" font-weight="300" fill="%s">XY</text>'
          % (num(SX + 8), num(cy(5) + 22), v('ink')))
    d.add('<g transform="translate(%s %s) rotate(-90)"><rect x="-10" y="-6.500" width="20" height="13" rx="2" '
          'fill="none" stroke="%s"/>%s</g>' % (num(SX), num(cy(6) + 12), v('mark'), d.text('OP', 0, 0, 8, 'mark')))
    return d


def op_1_field():
    d = Drawing(FIELD)
    d.frame()
    v = d.var
    # The volume knob and the recess beside it share one tile.
    x, y = cx(3), cy(1)
    d.add('<g id="volume">%s<circle cx="%s" cy="%s" r="1.8" fill="%s"/></g>'
          % (d.disc(x, y, 17, v('key')), num(x + 4), num(y - 7), v('ink')))
    d.add('<rect x="%s" y="%s" width="36" height="36" rx="8" fill="%s" stroke="%s" stroke-width="1.2"/>'
          '<rect x="%s" y="%s" width="26" height="26" rx="5" fill="%s" stroke="%s" stroke-width="1"/>'
          % (num(cx(4) - 18), num(y - 18), v('tile'), v('shade'), num(cx(4) - 13), num(y - 13), v('key'),
             v('key-edge')))
    d.key('key-help', 3, 2, 'help')
    d.key('key-tempo', 4, 2, 'tempo')
    d.key('key-mic', 17, 1, 'mic', color='accent')
    d.key('key-com', 17, 2, 'drum', sub='COM')
    for col, mark in enumerate(('synth', 'pad', 'tape', 'bars'), 1):
        d.key('key-mode-%d' % col, col, 3, mark)
    for i in range(1, 5):
        d.key('key-t%d' % i, 4 + i, 3, label=str(i), size=25, weight=200)
    for i, sub in enumerate(('IN', 'OUT', 'loop-s', 'tape-s', 'Я', '••••', 'M1', 'M2'), 1):
        d.key('key-%d' % i, 8 + i, 3, label=str(i), size=14, weight=300, sub=sub)
    d.key('key-sequencer', 17, 3, 'dots')
    d.key('key-lift', 1, 4, 'up')
    d.key('key-drop', 2, 4, 'down')
    d.key('key-split', 3, 4, 'cut')
    d.keyboard_side()
    d.key('key-left', 1, 6, 'left')
    d.key('key-right', 2, 6, 'right')
    # White keys are raised pills down the two bottom rows; the black keys are round, above them.
    for col in range(4, 18):
        x, y = cx(col) - 18, Y0 + 4 * CELL + 7
        d.add('<g id="key-note-%d"><rect x="%s" y="%s" width="36" height="91" rx="18" fill="%s"/>'
              '<rect x="%s" y="%s" width="36" height="91" rx="18" fill="%s" stroke="%s" stroke-width="1.2"/></g>'
              % (col - 3, num(x), num(y + 2.5), v('shade'), num(x), num(y), v('key'), v('key-edge')))
    for col in BLACK:
        d.add(d.disc(X0 + col * CELL, cy(4), 19, v('key')))
        d.add('<circle cx="%d" cy="%s" r="16" fill="%s"/>' % (X0 + col * CELL, num(cy(4)), v('black-key')))
    d.add('<text transform="translate(%s %s) rotate(-90)" font-size="24" font-weight="300" fill="%s">OP–1</text>'
          % (num(SX + 8), num(cy(5) + 18), v('ink')))
    d.add('<g><rect x="%s" y="%s" width="28" height="12" rx="2.5" fill="none" stroke="%s"/>%s</g>'
          % (num(SX - 14), num(cy(6) + 8), v('ink'), d.text('field', SX, cy(6) + 14, 8)))
    return d


def main():
    os.makedirs(OUT, exist_ok=True)
    parts = {'view': [W, H]}
    for d in (op_xy(), op_1_field()):
        with open(os.path.join(OUT, d.look['name'] + '.svg'), 'w') as f:
            f.write(d.finish())
        parts[d.look['name']] = d.parts
    with open(os.path.join(OUT, 'parts.json'), 'w') as f:
        json.dump(parts, f, indent=1, sort_keys=True)
        f.write('\n')


if __name__ == '__main__':
    main()
