import math
import functools
import logging

from collections import defaultdict
from shapely import affinity
from shapely.geometry import *
from shapely.geometry.polygon import orient

from . import hersheydata

DEFAULT_TOLERANCE=.1

@functools.lru_cache(maxsize = None)
def binom_coefs(n):
    """ Binomial coefs needed by bezier """
    if n <= 1:
        return [1] * n

    base = binom_coefs(n-1)
    return [
        a+b
        for a, b in zip(base + [0], [0] + base)
    ]

def bezier(*points, tolerance=DEFAULT_TOLERANCE):
    size = math.sqrt(sum([
      (max([p[dimension] for p in points]) - min([p[dimension] for p in points]))**2
      for dimension in range(2)
    ]))
    npoints = max(8, int(math.ceil(size / tolerance)))
    if len(points) <= 2:
        npoints = len(points)

    bezier_coefs = binom_coefs(len(points))
    bezier_exps = [ (len(points) - j - 1, j) for j in range(len(points)) ]

    ret = []
    for i in range(npoints+1):
        t = i / npoints
        ret.append(tuple(
            sum([
                coef * ((1 - t)**exps[0]) * ((t)**exps[1]) * point[dimension]
                for coef, exps, point in zip(bezier_coefs, bezier_exps, points)
            ])
            for dimension in range(2)
        ))
    return LineString(ret).simplify(tolerance=tolerance)

def rounded(geom, radius, tolerance=DEFAULT_TOLERANCE):
    resolution = max(16, int(2 * math.pi * radius / tolerance / 4))
    return geom.buffer(-radius, resolution=resolution).buffer(+radius, resolution=resolution)

def rect(x, y):
    return Polygon([
        (x[0], y[0]),
        (x[1], y[0]),
        (x[1], y[1]),
        (x[0], y[1]),
    ])

def text(text, font="futural", scale=1, translate=(0,0), align=0, valign=0):
    font = getattr(hersheydata, font)
    spacing = 3  # spacing between letters

    x_offset = 0.
    all_outlines = []
    current_outline = None

    letter_vals = (ord(q) - 32 for q in text)
    for glyph in text:
        glyph_val = ord(glyph) - 32
        if glyph_val < 0 or glyph_val > 95:
            logging.getLogger('hershey_text').warning(f"Skipping unsupported glyph '{glyph}'")
            x_offset += 2 * spacing
        else:
            glyph_path = font[glyph_val].split(" ")
            offset1, offset2 = float(glyph_path[0]), float(glyph_path[1])

            x_offset -= offset1
            for cmd, x, y in zip(*((iter(glyph_path[2:]),)*3)):
                if cmd == 'M':
                    if current_outline:
                        all_outlines.append(current_outline)
                    current_outline = []
                current_outline.append((x_offset+float(x), float(y)))
            if current_outline:
                all_outlines.append(current_outline)
            x_offset += offset2

    ret = MultiLineString(all_outlines)
    ret = affinity.translate(ret, xoff=x_offset * .5 * (align - 1), yoff=16 * .5 * (valign - 1) )
    ret = affinity.scale(ret, xfact=scale, yfact=scale, origin=(0,0))
    ret = affinity.translate(ret, xoff=translate[0], yoff=translate[1])
    return ret

def draw_shape(cairo_context, shape):
    def draw_coords(coords, close, ccw=True):

        # Force proper orientation of lines
        if close:
            coords = orient(Polygon(coords), sign=1 if ccw else -1).exterior.coords

        for i, p in enumerate(coords):
            if i == 0:
                cairo_context.move_to(*p)
            else:
                cairo_context.line_to(*p)
        if close:
            cairo_context.close_path()

    def draw_internal(shape):
        if isinstance(shape, (MultiPoint, MultiLineString, MultiPolygon, GeometryCollection)):
            for x in shape.geoms:
                draw_internal(x)
        elif isinstance(shape, Point):
            pass # Not supported
        elif isinstance(shape, LineString):
            draw_coords(shape.coords, close=False)
        elif isinstance(shape, LinearRing):
            draw_coords(shape.coords, close=True)
        elif isinstance(shape, Polygon):
            draw_coords(shape.exterior.coords, close=True)
            for interior in shape.interiors:
                draw_coords(interior.coords, close=True, ccw=False)

    draw_internal(shape)

def all_geoms(*geoms):
    def visit(geom):
        if isinstance(geom, (Point, LineString, Polygon, LinearRing)):
            yield geom
        elif isinstance(geom, (MultiPoint, MultiLineString, MultiPolygon, GeometryCollection)):
            for x in geom.geoms:
                yield from visit(x)
        else:
            # Assume it is an iterator-of-geometries
            for x in geom:
                yield from visit(x)

    for geom in geoms:
        yield from visit(geom)

def compose(*geoms):
    geom_by_type = defaultdict(list)

    for geom in all_geoms(*geoms):
        geom_by_type[type(geom)].append(geom)

    ret = []
    for geom_type, geoms in geom_by_type.items():
        if len(geoms) == 1:
            ret += geoms
        if geom_type == Point:
            ret.append(MultiPoint(geoms))
        elif geom_type == LineString:
            ret.append(MultiLineString(geoms))
        elif geom_type == Polygon:
            ret.append(MultiPolygon(geoms))
        else:
            ret += geoms

    if len(ret) == 1:
        return ret[0]
    else:
        return GeometryCollection(ret)
