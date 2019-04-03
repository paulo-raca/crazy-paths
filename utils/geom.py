import math
import functools
from shapely.geometry import *

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
    def draw_coords(coords, close):
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
                draw_coords(interior.coords, close=True)

    draw_internal(shape)
