#!/usr/bin/env python3

import cairo
import shapely
import random
from shapely.affinity import translate
from shapely.geometry import *
from shapely.ops import unary_union, polygonize, linemerge
import itertools
from utils.geom import *

piece_size=45
piece_spacing=3
piece_outer_spacing=7.5
piece_arc=10
grid_arc=3
grid_size=6
piece_distance=0
entry_distance = piece_size/3

total_size = grid_size * piece_size + (grid_size-1) * piece_spacing + 2 * piece_outer_spacing

def enum_pieces():
    for i in range(grid_size):
        for j in range(grid_size):
            x = [ piece_outer_spacing + (piece_size + piece_spacing) * j,  piece_outer_spacing + (piece_size + piece_spacing) * j + piece_size ]
            y = [ piece_outer_spacing + (piece_size + piece_spacing) * i,  piece_outer_spacing + (piece_size + piece_spacing) * i + piece_size ]
            yield x, y

def connection_paths():
    # Horizontal lines
    for i in range(grid_size):
        for j in range(grid_size+1):
            x0 = 0 if j == 0 else (piece_spacing + piece_size) * j + piece_outer_spacing - piece_spacing
            x1 = total_size if j == grid_size else (piece_spacing + piece_size) * j + piece_outer_spacing
            y = piece_outer_spacing + i * (piece_spacing + piece_size)

            for pos in (piece_size - entry_distance) / 2, (piece_size + entry_distance) / 2:
                yield bezier((x0, y+pos), (x1, y+pos))
                yield bezier((y+pos, x0), (y+pos, x1))

def piece_paths(piece_x, piece_y):
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

        yield bezier(
            (a[0][0], a[0][1]),
            (a[0][0] + scale * a[1][0], a[0][1] + scale * a[1][1]),
            (b[0][0] + scale * b[1][0], b[0][1] + scale * b[1][1]),
            (b[0][0], b[0][1])
        )



def get_outline(hole_size=1.5, notches=True):
    outline = rect([0, total_size], [0, total_size])
    if notches:
        handles = []
        for i in range(grid_size):
            p = piece_outer_spacing + piece_size/2 + i * (piece_spacing + piece_size)
            for pos in [p + entry_distance / 2, p - entry_distance / 2]:
                handles += [
                    Point(-1, pos),
                    Point(total_size+1, pos),
                    Point(pos, -1),
                    Point(pos, total_size+1),
                ]
        outline -= MultiPoint(handles).buffer(3)
    outline = rounded(outline, radius=piece_outer_spacing/2)

    if hole_size:
        for hx in (piece_outer_spacing/2, total_size-piece_outer_spacing/2):
            for hy in (piece_outer_spacing/2, total_size-piece_outer_spacing/2):
                outline -= Point(hx, hy).buffer(hole_size/2)
    return outline

def get_cuts():
    outline = get_outline()

    holes = []
    pieces = []
    for piece_x, piece_y in enum_pieces():
        piece = rect(piece_x, piece_y)
        holes.append(rounded(piece, radius=grid_arc))
        pieces.append(rounded(piece.buffer(-piece_distance), radius=piece_arc))

    return MultiPolygon([outline.difference(unary_union(holes)), translate(outline, xoff=total_size), translate(get_outline(hole_size=1,  notches=False), xoff=2*total_size)] + pieces)


def get_all_paths():
    outline = get_outline(hole_size=2)
    all_paths = list(outline.boundary.geoms)
    all_paths += connection_paths()

    for piece_x, piece_y in enum_pieces():
        all_paths += piece_paths(piece_x, piece_y)

    all_paths = linemerge(all_paths)
    polygons = GeometryCollection(list(polygonize(unary_union(all_paths))))

    ret = [all_paths]
    for offset in [.75, 1.5]:
        ret.append(polygons.buffer(-offset).boundary)

    return outline.intersection(unary_union(ret)) - outline.boundary


def main():
    cuts = get_cuts()
    paths = get_all_paths()

    with cairo.SVGSurface("pretty.svg", 3*total_size, total_size) as surface:
        surface.set_document_unit(cairo.SVGUnit.MM)
        context = cairo.Context(surface)

        draw_shape(context, cuts)
        context.set_source_rgba(.82, .71, .55, 1)
        context.fill()

        draw_shape(context, cuts.boundary)
        context.set_source_rgba(0, 0, 0, 1)
        context.set_line_width(.2)
        context.stroke()

        draw_shape(context, paths)
        context.set_source_rgba(0, 0, 1, .5)
        context.set_line_width(.2)
        context.stroke()

    with cairo.SVGSurface("cuts.svg", 3*total_size, total_size) as surface:
        surface.set_document_unit(cairo.SVGUnit.MM)
        context = cairo.Context(surface)

        draw_shape(context, unary_union(cuts.boundary))
        context.set_source_rgba(0, 0, 0, 1)
        context.set_line_width(.1)
        context.stroke()


    with cairo.SVGSurface("paths.svg", 3*total_size, total_size) as surface:
        surface.set_document_unit(cairo.SVGUnit.MM)
        context = cairo.Context(surface)

        draw_shape(context, paths)
        context.set_source_rgba(0, 0, 1, 1)
        context.set_line_width(.2)
        context.stroke()

main()
