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
piece_outer_spacing = 2*piece_spacing
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
handle_size=10

total_width = grid_size * piece_size + (grid_size+3) * piece_spacing
total_height = total_width + slots_height + (piece_spacing if slots_height else 0)

# Piece layout:
#     |  |
#     0  1
# --4      6--
#
# --5      7--
#     2  3
#     |  |
default_piece_links = [
  ((0, 1), (2,3), (4,5), (6,7)),
  ((4, 0), (1,6), (7,3), (2,5)),
  ((0, 2), (1,3), (4,6), (5,7)),
  ((4, 0), (1,5), (2,6), (3,7)),
  ((0, 4), (1,5), (2,7), (3,6)),
  ((0, 5), (1,4), (2,7), (3,6)),
  ((0, 7), (1,5), (2,6), (3,4)),
  ((0, 3), (1,2), (4,7), (5,6)),
  ((0, 7), (1,5), (6,2), (3,4)),
  ((0, 3), (1,4), (6,5), (7,2)),
  ((1, 2), (0,6), (4,7), (5,3)),
  ((0, 5), (1,7), (2,4), (3,6)),
  ((0, 5), (1,7), (2,6), (3,4)),
  ((0, 7), (1,4), (6,3), (5,2)),
]
#random.shuffle(default_piece_links)

def random_piece_links():
    perm = list(range(8))
    random.shuffle(perm)

    return [
        (perm[i], perm[i+1])
        for i in range(0, len(perm), 2)
    ]

def enum_pieces():
    for i in range(grid_size):
        for j in range(grid_size):
            x = [ 2 * piece_spacing + (piece_size + piece_spacing) * j,  2 * piece_spacing + (piece_size + piece_spacing) * j + piece_size ]
            y = [ 2 * piece_spacing + (piece_size + piece_spacing) * i,  2 * piece_spacing + (piece_size + piece_spacing) * i + piece_size ]
            yield x, y

def enum_piece_links():
    yield from default_piece_links
    while True:
        yield random_piece_links()

def connection_paths():
    # Horizontal lines
    for i in range(grid_size):
        for j in range(grid_size+1):
            x0 = path_to_edge_distance if j == 0 else (piece_spacing + piece_size) * j + piece_spacing
            x1 = total_width - path_to_edge_distance if j == grid_size else (piece_spacing + piece_size) * j + 2 * piece_spacing
            y = 2 * piece_spacing + i * (piece_spacing + piece_size)

            for pos in (piece_size - entry_distance) / 2, (piece_size + entry_distance) / 2:
                yield bezier((x0, y+pos), (x1, y+pos))
                yield bezier((y+pos, x0), (y+pos, x1))


def piece_paths(piece_x, piece_y, piece_links):
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

    for link in piece_links:
        a, b = entries[link[0]], entries[link[1]]
        scale = max(abs(a[0][0] - b[0][0]), abs(a[0][1] - b[0][1]))
        if a[1] == b[1]:
            scale *= .75
        else:
            scale *= 0.5

        yield bezier(
            (a[0][0], a[0][1]),
            (a[0][0] + scale * a[1][0], a[0][1] + scale * a[1][1]),
            (b[0][0] + scale * b[1][0], b[0][1] + scale * b[1][1]),
            (b[0][0], b[0][1])
        )



def get_outline(border=True):
    outline = rect([0, total_width], [0, total_height])
    outline = rounded(outline, radius=2 * piece_spacing)

    inner_outline = outline.buffer(-piece_spacing)
    inner_outline = rounded(inner_outline, radius=piece_spacing + grid_arc)


    handles = compose([
        rect([0, piece_spacing], [total_height-piece_spacing, total_height]),
        rect([total_width, total_width-piece_spacing], [total_height-piece_spacing, total_height]),
    ]).buffer(handle_size - piece_spacing) & outline

    outline -= handles
    inner_outline |= handles
    inner_outline = rounded(inner_outline, -piece_spacing)

    if not border:
        return MultiPolygon([outline])
    else:
        return compose(inner_outline, outline - inner_outline)

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
            (1.5*piece_spacing + .5 * entry_distance, total_height - 2*piece_spacing - slots_height / 2),
            (total_width - 1.5*piece_spacing - .5 * entry_distance, total_height - 2*piece_spacing - slots_height / 2),
        ])
        slot_pieces = [
            Point(
                1.5*piece_spacing + (i+.5)*entry_distance,
                total_height - 2*piece_spacing - slots_height / 2
            ).buffer(slots_height / 2)
            for i in range(3*grid_size)
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
    title = compose(
        text("Caminhos   ", scale=1, translate=(2.5*total_width, .4 * total_height)),
        text("   Malucos", scale=1, translate=(2.5*total_width,  .6 * total_height)),
    )

    all_paths = list(connection_paths()) + [title]

    for (piece_x, piece_y), piece_links in zip(enum_pieces(), enum_piece_links()):
        all_paths += list(piece_paths(piece_x, piece_y, piece_links))

    all_paths = unary_union(all_paths)


    ret = [all_paths]
    for offset in parallel_distances:
        ret.append(all_paths.buffer(offset).boundary)

    signature = text("Tio Paulo - Junho/2019", scale=.2, translate=(3*total_width - handle_size - 2 * piece_spacing, total_height - 2 * piece_spacing), align=-1, valign=-1)

    slot_piece_labels = [
        text(chr(ord("A") + i),
             scale=.2,
             translate=(
                1.5*piece_spacing + (i+.5)*entry_distance,
                total_height - 2*piece_spacing - slots_height / 2
            )
        )
        for i in range(3*grid_size)
    ]

    return compose(ret, signature, slot_piece_labels)


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
