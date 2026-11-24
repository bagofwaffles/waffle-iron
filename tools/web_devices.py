#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Draws the two units for the install page: docs/devices/.

    tools/web_devices.py

It writes op-xy.svg and op-1-field.svg, top views on one 17 x 6 key grid, and parts.json: the
center and size of each part a step may point at (a key, a knob, the power switch, the USB port),
in the drawing's own units. Every part also carries its name as an id in the drawing. Colors are
CSS variables with the unit's own color as the fallback, so a page can restyle an inlined drawing.
The OP-XY follows a photo of its front; the OP-1 Field is drawn the same way.
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
    'body': '#1e1f21', 'edge': '#09090a', 'line': '#09090a', 'key': '#2f3033', 'key-edge': '#3e4044',
    'ink': '#e6e6e3', 'screen': '#050506', 'glass': '#17181b', 'black-key': '#232427',
    'accent': '#e2412b', 'knobs': ('#3b3d42', '#7b7f87', '#b9bbbd', '#f3f3f0'), 'collar': '#0c0c0d',
    'dish': '#222325', 'dish-edge': '#0b0b0c', 'volume': '#b4b6b8', 'switch': '#d9d9d5', 'tile': '#27282a',
    'well': '#0a0a0b', 'hole': '#050506', 'mark': '#8d8f93', 'steps': ('#4b4f56', '#dcdbd6'),
    'well-depth': .95, 'dip': .3, 'sheen': .09, 'lit': (.05, .12), 'rim': .07, 'grille': 'octagon', 'tick': True,
}
FIELD = {
    'name': 'op-1-field', 'title': 'OP-1 Field',
    'body': '#dbdbd8', 'edge': '#a6a6a2', 'line': '#1b1b1c', 'key': '#f8f7f3', 'key-edge': '#d3cfc7',
    'ink': '#454543', 'screen': '#0b0b0c', 'glass': '#1a1b1d', 'black-key': '#151516',
    'accent': '#e2562b', 'knobs': ('#2b3563', '#b59a62', '#909293', '#e2562b'), 'collar': '#f8f7f3',
    'dish': '#e6e4de', 'dish-edge': '#cdc9c1', 'volume': '#f8f7f3', 'switch': '#c9c9c5', 'tile': '#eeece7',
    'well': '#c6c2b9', 'hole': '#2a2a29', 'mark': '#3b3b3a',
    'well-depth': .6, 'dip': .06, 'sheen': .6, 'lit': (.35, .02), 'rim': .6, 'grille': 'round',
    'light': True, 'stroke': 1.2, 'sub-weight': 500,
}
R = 16.5                            # a key's cap


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
        if kind == 'nib':
            return ('<g transform="translate(%s %s) rotate(45)"><path d="M0 9.5l-4.3-7.5 1.5-4.5h5.6l1.5 4.5z'
                    'M-3.2-8h6.4v3.2h-6.4z" fill="%s"/><path d="M0 8v-5.5" fill="none" stroke="%s" '
                    'stroke-width="1.1"/><circle cy="1.5" r="1.2" fill="%s"/></g>'
                    % (n(x), n(y), ink, self.var('key'), self.var('key')))
        if kind == 'metro':
            return ('<path d="M%s %sh13l-4-15h-5z" fill="%s"/><path d="M%s %sv-8" fill="none" stroke="%s" '
                    'stroke-width="1.6"/>' % (n(x - 6.5), n(y + 7.5), ink, n(x), n(y + 3), self.var('key')))
        if kind == 'sine':
            return '<path d="M%s %sc3-10 5.5-10 8 0s5 10 8 0" %s/>' % (n(x - 8), n(y - .5), line)
        if kind == 'hatch':
            return ('<rect x="%s" y="%s" width="9" height="9" fill="%s"/><path d="M%s %sl3-3M%s %sl6-6M%s %sl9-9'
                    'M%s %sl6-6M%s %sl3-3" fill="none" stroke="%s" stroke-width=".8"/>'
                    % (n(x - 4.5), n(y - 4.5), ink, n(x - 4.5), n(y - 1.5), n(x - 4.5), n(y + 1.5),
                       n(x - 4.5), n(y + 4.5), n(x - 1.5), n(y + 4.5), n(x + 1.5), n(y + 4.5), self.var('key')))
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

    def uid(self, what):
        return '%s-%s' % (self.look['name'], what)

    def shine(self, x, y, r):
        return '<circle cx="%s" cy="%s" r="%s" fill="url(#%s)"/>' % (num(x), num(y), num(r), self.uid('sheen'))

    def disc(self, x, y, r, fill):
        """A round cap in the soft dish it sits in."""
        edge = ' stroke="%s" stroke-width="1"' % self.var('key-edge') if self.look.get('light') else ''
        return ('<circle cx="%s" cy="%s" r="%s" fill="url(#%s)"/><circle cx="%s" cy="%s" r="%s" fill="%s"%s/>%s'
                % (num(x), num(y), num(r / .7), self.uid('well'), num(x), num(y), num(r), fill, edge,
                   self.shine(x, y, r)))

    def key(self, name, col, row, mark='', label='', size=13, r=R, x=None, color='ink', weight=500,
            sub='', led=False, side=''):
        """A round key in one cell; mark is a glyph, label is text. sub goes small under it, as text or
        a glyph's name; side is a small glyph right of the label; led is the hole at the cap's top."""
        x = cx(col) if x is None else x
        y = cy(row)
        up = 4 if sub else 0
        at = x - 6 if side else x
        inner = ''
        if led:
            inner += '<circle cx="%s" cy="%s" r="1.5" fill="%s" fill-opacity=".55"/>' % (
                num(x), num(y - 12), self.var('hole'))
        inner += self.glyph(mark, x, y - up, color) if mark else ''
        if label:
            inner += self.text(label, at, y - up, size, weight=weight)
        if side:
            inner += self.glyph(side, x + 6, y)
        if sub:
            small = self.glyph(sub, x, y + 8)
            inner += small or self.text(sub, x, y + 8.5, 7, weight=self.look.get('sub-weight', 500))
        self.add('<g id="%s">%s%s</g>' % (name, self.disc(x, y, r, self.var('key')), inner))
        self.part(name, x, y, 2 * r, 2 * r, 'circle')

    def tile(self, col, row, wide=1, high=1):
        return 'M%s %sh%sv%sh%sz' % (num(X0 + (col - 1) * CELL + 2.5), num(Y0 + (row - 1) * CELL + 2.5),
                                     num(wide * CELL - 5), num(high * CELL - 5), num(5 - wide * CELL))

    def bed(self):
        """What the keys sit in: separate tiles on a dark bed."""
        v = self.var
        tall = self.look.get('light')
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

    def gradients(self):
        look, v = self.look, self.var
        deep = look['well-depth']
        fade = ('<radialGradient id="%s"><stop offset=".66" stop-color="%s" stop-opacity="%s"/>'
                '<stop offset=".8" stop-color="%s" stop-opacity="%s"/>'
                '<stop offset="1" stop-color="%s" stop-opacity="0"/></radialGradient>')
        down = ('<linearGradient id="%s" x2="%s" y2="1"><stop stop-color="#fff" stop-opacity="%s"/>'
                '<stop offset="%s" stop-color="#fff" stop-opacity="0"/>'
                '<stop offset="1" stop-color="#000" stop-opacity="%s"/></linearGradient>')
        return (fade % (self.uid('well'), v('well'), deep, v('well'), num(deep * .7), v('well'))
                + fade % (self.uid('step'), '#000', .4, '#000', .24, '#000')
                + '<radialGradient id="%s"><stop offset=".55" stop-color="#000" stop-opacity="%s"/>'
                  '<stop offset="1" stop-color="#000" stop-opacity="0"/></radialGradient>'
                % (self.uid('dip'), look['dip'])
                + down % (self.uid('sheen'), 0, look['sheen'], .7, .06)
                + down % (self.uid('glass'), 1, .08, 1, 0)
                + down % (self.uid('lit'), 0, look['lit'][0], .5, look['lit'][1]))

    def knob(self, name, x, y, color):
        """An encoder on two columns: a dish in the panel, a collar, a colored top."""
        v = self.var
        edge = ' stroke="%s" stroke-width="1"' % v('key-edge') if self.look.get('light') else ''
        self.add('<g id="%s"><circle cx="%d" cy="%d" r="30" fill="%s" stroke="%s" stroke-width="1.4"/>'
                 '<circle cx="%d" cy="%d" r="30" fill="url(#%s)"/>'
                 '<circle cx="%d" cy="%d" r="18.5" fill="%s"%s/>'
                 '<circle cx="%d" cy="%d" r="14.5" fill="var(--dw-%s, %s)"/>%s</g>'
                 % (name, x, y, v('dish'), v('dish-edge'), x, y, self.uid('dip'), x, y, v('collar'), edge,
                    x, y, name, color, self.shine(x, y, 14.5)))
        self.part(name, x, y, 60, 60, 'circle')

    def frame(self):
        look, v = self.look, self.var
        self.add('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" role="img" '
                 'aria-label="The %s, seen from above" font-family="Helvetica Neue, Helvetica, Arial, '
                 'sans-serif" text-anchor="middle">' % (W, H, look['title']))
        gx, gy = X0 + CELL, Y0 + CELL
        self.add('<defs><pattern id="%s" x="%d" y="%d" width="5.5" height="5.5" patternUnits="userSpaceOnUse">'
                 '<circle cx="2.75" cy="2.75" r="1.7" fill="%s"/></pattern>%s</defs>'
                 % (self.uid('grille'), gx - 44, gy - 44, v('hole'), self.gradients()))
        # The power switch stands out of the right edge, level with the line between the bottom rows.
        px, py = BX + BW - 4, Y0 + 5 * CELL - 16
        self.add('<rect id="power" x="%d" y="%d" width="11" height="32" rx="2.5" fill="%s" stroke="%s" '
                 'stroke-width="1"/>' % (px, py, v('switch'), v('edge')))
        self.part('power', px + 5.5, py + 16, 11, 32, 'rect')
        self.add('<rect x="%d" y="%d" width="%d" height="%d" rx="10" fill="%s" stroke="%s" stroke-width="2"/>'
                 '<rect x="%d" y="%d" width="%d" height="%d" rx="9" fill="url(#%s)"/>'
                 '<rect x="%s" y="%s" width="%d" height="%d" rx="8.5" fill="none" stroke="#fff" '
                 'stroke-opacity="%s"/>'
                 % (BX, BY, BW, BH, v('body'), v('edge'), BX + 1, BY + 1, BW - 2, BH - 2, self.uid('lit'),
                    BX + 1.5, BY + 1.5, BW - 3, BH - 3, look['rim']))
        # The USB port is in the right side, behind the mark on the strip: beside the third row.
        my = Y0 + 2.27 * CELL
        ux = BX + BW - 7
        self.add('<rect id="usb" x="%d" y="%s" width="5" height="26" rx="2.5" fill="%s"/>'
                 % (ux, num(my - 13), v('edge')))
        self.part('usb', ux + 2.5, my, 5, 26, 'rect')
        self.add('<path d="M%s %sh27" fill="none" stroke="%s" stroke-width=".7"/>'
                 '<path d="M%s %sv%s" fill="none" stroke="%s" stroke-width="2.2" stroke-dasharray=".8 1.1" '
                 'stroke-opacity=".8"/>'
                 % (num(SX - 13.5), num(my), v('mark'), num(SX), num(Y0 + 1.94 * CELL), num(1.15 * CELL), v('mark')))
        if look.get('tick'):
            # The line on the front rim, under the middle of the keys.
            self.add('<rect x="%s" y="%d" width="2.4" height="%d" fill="%s"/>'
                     % (num(X0 + 9 * CELL - 1.2), GY1 + 3, BY + BH - GY1 - 4, v('ink')))
        self.bed()
        # Speaker, screen, microphone.
        if look['grille'] == 'octagon':
            side, c = 38.5, 24.75
            self.add('<path d="M%s %dh%sl%s %sv%sl-%s %sh-%sl-%s-%sv-%sz" fill="url(#%s)"/>'
                     % (num(gx - 44 + c), gy - 44, side, c, c, side, c, c, side, c, c, side, self.uid('grille')))
        else:
            self.add('<circle cx="%d" cy="%d" r="40" fill="url(#%s)"/>' % (gx, gy, self.uid('grille')))
        sx, sy, sw, sh = X0 + 4 * CELL + 1, Y0 + 1, 4 * CELL - 2, 2 * CELL - 2
        self.add('<rect id="screen" x="%d" y="%d" width="%d" height="%d" rx="3" fill="%s"/>'
                 '<rect x="%d" y="%d" width="%d" height="%d" rx="1" fill="%s"/>'
                 '<rect x="%d" y="%d" width="%d" height="%d" rx="3" fill="url(#%s)"/>'
                 '<path d="M%s %dh%sl-%s %dh-%sz" fill="#fff" fill-opacity=".035"/>'
                 % (sx, sy, sw, sh, v('glass'), sx + 10, sy + 9, sw - 20, sh - 18, v('screen'),
                    sx, sy, sw, sh, self.uid('glass'),
                    num(sx + sw * .62), sy, num(sw * .16), num(sh * .55), sh, num(sw * .16)))
        self.part('screen', sx + sw / 2, sy + sh / 2, sw, sh, 'rect')
        self.add('<circle cx="%s" cy="%s" r="1.6" fill="%s"/>' % (num(SX), num(cy(1)), v('edge')))
        for i, color in enumerate(look['knobs']):
            self.knob('knob-%d' % (i + 1), X0 + (9 + 2 * i) * CELL, Y0 + CELL, color)
        # The volume knob: a collar and a top with its mark.
        x, y = cx(3), cy(1)
        light = look.get('light')
        self.add('<g id="volume"><circle cx="%s" cy="%s" r="%s" fill="url(#%s)"/>'
                 '<circle cx="%s" cy="%s" r="12.5" fill="%s"/><circle cx="%s" cy="%s" r="10.5" fill="%s"/>%s'
                 '<circle cx="%s" cy="%s" r="1.8" fill="none" stroke="%s"/></g>'
                 % (num(x), num(y), num(12.5 / .7), self.uid('well'), num(x), num(y),
                    v('key-edge') if light else v('collar'), num(x), num(y), v('volume'), self.shine(x, y, 10.5),
                    num(x - 4), num(y - 4), v('mark') if light else '#f4f4f2'))

    def keyboard_side(self, stop='stop'):
        self.key('key-rec', 1, 5, 'rec', color='accent')
        self.key('key-play', 2, 5, 'play')
        self.key('key-stop', 3, 5, stop)
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
    d.key('key-project', 3, 2, 'nib')
    d.key('key-tempo', 4, 2, 'metro')
    d.key('key-sample', 17, 1, 'sample')
    d.key('key-com', 17, 2, label='com', size=12.5, weight=300)
    d.key('key-instrument', 1, 3, 'sine', sub='1–8')
    d.key('key-aux', 2, 3, 'plug', sub='1–8')
    d.key('key-arrange', 3, 3, 'blocks')
    d.key('key-mix', 4, 3, 'faders')
    for i in range(1, 5):
        d.key('key-m%d' % i, 4 + i, 3, label=str(i), size=19, weight=300)
    for i, side in enumerate(('blob', 'dome', 'dial', 'cv', 'kit', 'tape-s', 'fx1', 'fx2'), 1):
        d.key('key-sound-%d' % i, 8 + i, 3, label=str(i), size=13, weight=300, led=True, side=side)
    d.key('key-players', 17, 3, 'pixels')
    # The sixteen step keys run from dark to light two at a time, tile and cap alike.
    for col in range(1, 17):
        color = mix(XY['steps'][0], XY['steps'][1], ((col - 1) // 2) / 7)
        x, y, name = cx(col), cy(4), 'key-step-%d' % col
        d.add('<g id="%s"><rect x="%s" y="%s" width="%d" height="%d" rx="2.5" fill="%s"/>'
              '<circle cx="%s" cy="%s" r="%s" fill="url(#%s)"/><circle cx="%s" cy="%s" r="%s" fill="%s"/>%s'
              '<circle cx="%s" cy="%s" r="2" fill="#000" fill-opacity=".62"/></g>'
              % (name, num(x - CELL / 2 + 1), num(y - CELL / 2 + 1), CELL - 2, CELL - 2, color,
                 num(x), num(y), num(R / .7), d.uid('step'), num(x), num(y), R, color, d.shine(x, y, R),
                 num(x), num(y - 11.5)))
        d.part(name, x, y, 2 * R, 2 * R, 'circle')
    x, y = cx(17), cy(4)
    d.add('<g id="key-bar">%s%s<rect x="%s" y="%s" width="21" height="9.5" rx="1.5" fill="%s"/>'
          '<text x="%s" y="%s" font-size="7.5" font-weight="500" fill="%s">BAR</text></g>'
          % (d.disc(x, y, R, v('key')), d.text('1–4', x, y - 7.5, 6, weight=500), num(x - 10.5), num(y - 2.5),
             v('ink'), num(x), num(y + 5), v('key')))
    d.part('key-bar', x, y, 2 * R, 2 * R, 'circle')
    d.keyboard_side('hatch')
    d.key('key-minus', 1, 6, 'minus')
    d.key('key-plus', 2, 6, 'plus')
    d.add(d.text('num', X0 + 3 * CELL + 13, cy(5) - 16, 9, weight=400))
    for n, col in enumerate(BLACK):
        d.key('key-num-%d' % ((n + 1) % 10), col, 5, label=str((n + 1) % 10), size=13, weight=300,
              x=X0 + col * CELL, led=True)
    marks = ('four', 'hand', 'divide', 'ramp', 'stairs-up', 'stairs-down', '', 'notes', 'fin', 'clover',
             'into', 'wheel', 'burst', 'sun')
    for col, mark in enumerate(marks, 4):
        d.key('key-note-%d' % (col - 3), col, 6, mark, led=True,
              label='' if mark else '<tspan font-style="italic">rnd</tspan>', size=11.5, weight=400)
    d.add('<text transform="translate(%s %s) rotate(-90)" font-size="19" font-weight="300" letter-spacing="2" '
          'fill="%s">XY</text>' % (num(SX + 6.5), num(Y0 + 5.1 * CELL), v('mark')))
    d.add('<g transform="translate(%s %s) rotate(-90)"><rect x="-9" y="-7" width="18" height="14" rx="1" '
          'fill="none" stroke="%s" stroke-width=".8"/>%s</g>'
          % (num(SX), num(Y0 + 5.66 * CELL), v('mark'), d.text('OP', 0, 0, 8, 'mark', 400)))
    return d


def op_1_field():
    d = Drawing(FIELD)
    d.frame()
    v = d.var
    # The recess beside the volume knob shares its tile.
    y = cy(1)
    d.add('<rect x="%s" y="%s" width="36" height="36" rx="8" fill="%s" stroke="%s" stroke-width="1.2"/>'
          '<rect x="%s" y="%s" width="26" height="26" rx="5" fill="%s" stroke="%s" stroke-width="1"/>'
          % (num(cx(4) - 18), num(y - 18), v('tile'), v('well'), num(cx(4) - 13), num(y - 13), v('key'),
             v('key-edge')))
    d.key('key-help', 3, 2, 'help')
    d.key('key-tempo', 4, 2, 'tempo')
    d.key('key-mic', 17, 1, 'mic', color='accent')
    d.key('key-com', 17, 2, 'drum', sub='COM')
    for col, mark in enumerate(('synth', 'pad', 'tape', 'bars'), 1):
        d.key('key-mode-%d' % col, col, 3, mark)
    for i in range(1, 5):
        d.key('key-t%d' % i, 4 + i, 3, label=str(i), size=23, weight=200)
    for i, sub in enumerate(('IN', 'OUT', 'loop-s', 'tape-s', 'Я', '••••', 'M1', 'M2'), 1):
        d.key('key-%d' % i, 8 + i, 3, label=str(i), size=13, weight=300, sub=sub)
    d.key('key-sequencer', 17, 3, 'dots')
    d.key('key-lift', 1, 4, 'up')
    d.key('key-drop', 2, 4, 'down')
    d.key('key-split', 3, 4, 'cut')
    d.keyboard_side()
    d.key('key-left', 1, 6, 'left')
    d.key('key-right', 2, 6, 'right')
    # White keys are raised pills down the two bottom rows; the black keys are round, above them.
    pill = '<rect x="%s" y="%s" width="%s" height="%s" rx="%s" fill="%s"%s/>'
    for col in range(4, 18):
        x, y, w, h = cx(col) - R, Y0 + 4 * CELL + 9, 2 * R, 2 * CELL - 18
        d.add('<g id="key-note-%d">%s%s%s%s</g>' % (
            col - 3,
            pill % (num(x - 4.5), num(y - 4.5), num(w + 9), num(h + 9), R + 4.5, v('well'), ' fill-opacity=".3"'),
            pill % (num(x - 2), num(y - 2), num(w + 4), num(h + 4), R + 2, v('well'), ' fill-opacity=".6"'),
            pill % (num(x), num(y), num(w), num(h), R, v('key'), ' stroke="%s" stroke-width="1"' % v('key-edge')),
            pill % (num(x), num(y), num(w), num(h), R, 'url(#%s)' % d.uid('sheen'), '')))
    for col in BLACK:
        x, y = X0 + col * CELL, cy(4)
        d.add('<circle cx="%d" cy="%s" r="%s" fill="url(#%s)"/><circle cx="%d" cy="%s" r="%s" fill="%s"/>'
              '<circle cx="%d" cy="%s" r="%s" fill="url(#%s)" fill-opacity=".25"/>'
              % (x, num(y), num(R / .7), d.uid('well'), x, num(y), R, v('black-key'), x, num(y), R,
                 d.uid('sheen')))
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
