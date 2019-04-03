#!/usr/bin/env python3

import cairo
import random

piece_size=45
piece_spacing=5
piece_arc=10
grid_arc=2
grid_size=6
piece_distance=0.5
entry_distance = piece_size/3

total_size = grid_size * piece_size + (grid_size+1) * piece_spacing

def enum_pieces(inner):
    for i in range(grid_size):
        for j in range(grid_size):
            x = [ piece_spacing * (j + 1) + piece_size * j,  piece_spacing * (j + 1) + piece_size * (j + 1), ]
            y = [ piece_spacing * (i + 1) + piece_size * i,  piece_spacing * (i + 1) + piece_size * (i + 1), ]
            if inner:
                x = [ x[0] + piece_distance, x[1] - piece_distance ]
                y = [ y[0] + piece_distance, y[1] - piece_distance ]
            yield x, y

def enum_connection_paths():
    # Horizontal lines
    for i in range(grid_size):
        for j in range(grid_size+1):
            x0 = (piece_spacing + piece_size) * j
            x1 = x0 + piece_spacing
            y = piece_spacing * (i + 1) + piece_size * i

            for pos in (piece_size - entry_distance) / 2, (piece_size + entry_distance) / 2:
                yield (x0, x1), (y+pos, y+pos)
                yield (y+pos, y+pos), (x0, x1)

def draw_rounded(context, x, y, radius, hole=False):
    """ draws rectangles with rounded (circular arc) corners """
    from math import pi

    context.move_to(x[0], y[0] + radius)
    if hole:
        context.arc_negative(x[0] + radius, y[1] - radius, radius, 2*(pi/2), 1*(pi/2))
        context.arc_negative(x[1] - radius, y[1] - radius, radius, 1*(pi/2), 0*(pi/2))
        context.arc_negative(x[1] - radius, y[0] + radius, radius, 4*(pi/2), 3*(pi/2))
        context.arc_negative(x[0] + radius, y[0] + radius, radius, 3*(pi/2), 2*(pi/2))
    else:
        context.arc(x[0] + radius, y[0] + radius, radius, 2*(pi/2), 3*(pi/2))
        context.arc(x[1] - radius, y[0] + radius, radius, 3*(pi/2), 4*(pi/2))
        context.arc(x[1] - radius, y[1] - radius, radius, 0*(pi/2), 1*(pi/2))
        context.arc(x[0] + radius, y[1] - radius, radius, 1*(pi/2), 2*(pi/2))
    context.close_path()

with cairo.SVGSurface("example.svg", total_size, total_size) as surface:
    surface.set_document_unit(cairo.SVGUnit.MM)
    context = cairo.Context(surface)

    def draw_outline():
        draw_rounded(context, x=[0,total_size], y=[0, total_size], radius=grid_arc)
        draw_rounded(context, x=[total_size,2*total_size], y=[0, total_size], radius=grid_arc)
        for piece_x, piece_y in enum_pieces(False):
            draw_rounded(context, x=piece_x, y=piece_y, radius=grid_arc, hole=True)
        for piece_x, piece_y in enum_pieces(True):
            draw_rounded(context, x=piece_x, y=piece_y, radius=piece_arc, hole=True)

    def draw_piece_paths(piece_x, piece_y):
        w = piece_x[1] - piece_x[0]
        x0 = piece_x[0]
        x1_3 = x0 + (w - entry_distance) / 2
        x2_3 = x0 + (w + entry_distance) / 2
        x1 = x0 + w

        h = piece_y[1] - piece_y[0]
        y0 = piece_y[0]
        y1_3 = y0 + (h - entry_distance) / 2
        y2_3 = y0 + (h + entry_distance) / 2
        y1 = y0 + h

        entries = [
          ((x1_3, y0), (0, 1)),
          ((x2_3, y0), (0, 1)),
          ((x1_3, y1), (0, -1)),
          ((x2_3, y1), (0, -1)),
          ((x0, y1_3), (1, 0)),
          ((x0, y2_3), (1, 0)),
          ((x1, y1_3), (-1, 0)),
          ((x1, y2_3), (-1, 0)),
        ]
        random.shuffle(entries)

        for i in range(0, len(entries), 2):
            a, b = entries[i], entries[i+1]
            scale = max(abs(a[0][0] - b[0][0]), abs(a[0][1] - b[0][1]))
            if a[1] == b[1]:
                scale *= .8
            else:
                scale *= 0.5

            context.move_to(a[0][0], a[0][1])
            context.curve_to(
              a[0][0] + scale * a[1][0], a[0][1] + scale * a[1][1],
              b[0][0] + scale * b[1][0], b[0][1] + scale * b[1][1],
              b[0][0], b[0][1])


    def draw_paths():
        for x, y in enum_connection_paths():
            context.move_to(x[0], y[0])
            context.line_to(x[1], y[1])

        for piece_x, piece_y in enum_pieces(True):
            draw_piece_paths(piece_x, piece_y)

    draw_outline()
    context.set_source_rgba(.8, .8, .8, 1)
    context.fill()

    draw_outline()
    context.set_source_rgba(0, 0, 0, 1)
    context.set_line_width(.5)
    context.stroke()

    draw_paths()
    context.set_source_rgba(0, 0, 1, .5)
    context.set_line_width(3)
    context.stroke()
