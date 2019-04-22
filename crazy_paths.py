#!/usr/bin/env python3

import cairo
import shapely
import random
from shapely.affinity import translate
from shapely.geometry import *
from shapely.ops import unary_union, polygonize, linemerge, split
import itertools
from utils.geom import *

piece_size = 40
piece_spacing = 3
piece_outer_spacing = 6
piece_arc = 10
grid_arc = 2
grid_size = 6
piece_distance = 0
border_distance = 0
entry_distance = (piece_size + piece_spacing)/3
parallel_distances = [.75, 1.5]
path_to_edge_distance = piece_spacing + parallel_distances[-1]
slots_height = piece_size/4
slots_line_height = piece_size/10

total_width = grid_size * piece_size + (grid_size-1) * piece_spacing + 2 * piece_outer_spacing
total_height = total_width + slots_height + (piece_spacing if slots_height else 0)

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
            x0 = path_to_edge_distance if j == 0 else (piece_spacing + piece_size) * j + piece_outer_spacing - piece_spacing
            x1 = total_width - path_to_edge_distance if j == grid_size else (piece_spacing + piece_size) * j + piece_outer_spacing
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



def get_outline(notches=False, border=True, only_middle=False):
    outline = rect([0, total_width], [0, total_height])
    if notches:
        handles = []
        for i in range(grid_size):
            p = piece_outer_spacing + piece_size/2 + i * (piece_spacing + piece_size)
            for pos in parallel_distances:
                handles += [
                    Point(-1, pos),
                    Point(total_width+1, pos),
                    Point(pos, -1),
                    Point(pos, total_width+1),
                ]
        outline -= MultiPoint(handles).buffer(3)
    outline = rounded(outline, radius=piece_outer_spacing)

    if not border:
        return MultiPolygon([outline])
    else:
        inner_outline = rect([piece_outer_spacing - piece_spacing, total_width - piece_outer_spacing + piece_spacing], [piece_outer_spacing - piece_spacing, total_height - piece_outer_spacing + piece_spacing])
        inner_outline = rounded(inner_outline, radius=piece_spacing + grid_arc)

        corners = MultiPoint([(0,0), (0, total_width), (total_width, 0), (total_width, total_width)])
        corners = corners.buffer(total_width / 3) & outline.boundary
        corners = corners.buffer(piece_outer_spacing - piece_spacing) & outline
        #corners = rounded(corners, radius=(piece_outer_spacing - piece_spacing)/3)

        border_shape = corners
        border_shape = outline - inner_outline.buffer(piece_distance)

        middle = inner_outline
        outer = outline - middle.buffer(border_distance)

        if only_middle:
            return middle
        else:
            return compose(outer, middle)

def get_cuts():
    outline = get_outline()

    holes = []
    pieces = []
    for piece_x, piece_y in enum_pieces():
        piece = rect(piece_x, piece_y)
        holes.append(rounded(piece, radius=grid_arc))
        pieces.append(rounded(piece.buffer(-piece_distance), radius=piece_arc))
    holes = compose(holes)
    pieces = compose(pieces)

    if slots_height:
        slot_line = LineString([
            (1.5*piece_spacing + entry_distance/2, total_height - 2*piece_spacing - slots_height / 2),
            (total_width - 1.5*piece_spacing - entry_distance/2, total_height - 2*piece_spacing - slots_height / 2),
        ])
        slot_pieces = [
            Point(
                1.5*piece_spacing + i*entry_distance,
                total_height - 2*piece_spacing - slots_height / 2
            ).buffer(slots_height / 2)
            for i in range(1, 3*grid_size)
        ]

        holes = compose(holes, slot_line.buffer(slots_line_height / 2).union(compose(slot_pieces)).buffer(4).buffer(-4))
        pieces = compose(pieces, slot_pieces)

    return compose(
        pieces,
        [ g - holes for g in all_geoms(outline) ],
        translate(outline, xoff=total_width),
        translate(get_outline(border=False), xoff=2*total_width)
    )


def get_all_paths():
    all_paths = list(connection_paths())

    for piece_x, piece_y in enum_pieces():
        all_paths += list(piece_paths(piece_x, piece_y))

    all_paths = unary_union(all_paths)

    ret = [all_paths]
    for offset in [piece_spacing/4, 2*piece_spacing/4]:
        ret.append(all_paths.buffer(offset).boundary)

    return compose(ret) & get_outline(border = False)


def main():
    cuts = get_cuts()
    paths = get_all_paths()

    with cairo.SVGSurface("preview.svg", 3*total_width, total_height) as surface:
        surface.set_document_unit(cairo.SVGUnit.MM)
        context = cairo.Context(surface)

        draw_shape(context, cuts)
        context.set_source_rgba(.82, .71, .55, 1)
        context.fill()

        draw_shape(context, unary_union(cuts.boundary))
        context.set_source_rgba(0, 0, 0, 1)
        context.set_line_width(.2)
        context.stroke()

        draw_shape(context, paths)
        context.set_source_rgba(0, 0, 1, .5)
        context.set_line_width(.2)
        context.stroke()

    with cairo.SVGSurface("cut.svg", 3*total_width, total_height) as surface:
        surface.set_document_unit(cairo.SVGUnit.MM)
        context = cairo.Context(surface)

        draw_shape(context, unary_union(cuts.boundary))
        context.set_source_rgba(0, 0, 0, 1)
        context.set_line_width(.1)
        context.stroke()

    with cairo.SVGSurface("draw.svg", 3*total_width, total_height) as surface:
        surface.set_document_unit(cairo.SVGUnit.MM)
        context = cairo.Context(surface)

        draw_shape(context, paths)
        context.set_source_rgba(0, 0, 1, 1)
        context.set_line_width(.2)
        context.stroke()

main()
