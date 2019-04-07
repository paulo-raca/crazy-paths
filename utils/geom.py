import math
import functools

from collections import defaultdict
from shapely.geometry import *
from shapely.geometry.polygon import orient

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
    resolution = max(2, int(2 * math.pi * radius / tolerance / 4))
    return geom.buffer(-radius, resolution=resolution).buffer(+radius, resolution=resolution)

def rect(x, y):
    return Polygon([
        (x[0], y[0]),
        (x[1], y[0]),
        (x[1], y[1]),
        (x[0], y[1]),
    ])

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

def compose(*geoms):
    geom_by_type = defaultdict(list)

    def visit(geom):
        if isinstance(geom, (Point, LineString, Polygon, LinearRing)):
            geom_by_type[type(geom)].append(geom)
        elif isinstance(geom, (MultiPoint, MultiLineString, MultiPolygon, GeometryCollection)):
            for x in geom.geoms:
                visit(x)
        else:
            # Assume it is an iterator-of-geometries
            for x in geom:
                visit(x)

    for geom in geoms:
        visit(geom)

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
