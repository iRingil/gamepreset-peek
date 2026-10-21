"""Small icons drawn in code: the warning sign put after a list item text."""

import math
import struct
import zlib

__all__: tuple[str, ...] = ("Icons",)

_Point = tuple[float, float]
_Rgba = tuple[int, int, int, int]


class Icons:
    """Icons as PNG data with antialiased, partly transparent edges, drawn the same at any size.

    The warning sign is a road-sign triangle: amber with a dark rim, so its outline holds on light, dark and selected
    rows alike. Corners are rounded like the other shapes of the theme; sizes are fractions of the icon side."""

    _SAMPLES: int = 4
    _AMBER: tuple[int, int, int] = (0xFF, 0xC2, 0x4B)
    # The darkest color of the app palette, for the rim and the exclamation mark.
    _INK: tuple[int, int, int] = (0x03, 0x18, 0x30)
    # Triangle corners: top, bottom right, bottom left.
    _TRIANGLE: tuple[_Point, _Point, _Point] = ((0.5, 0.04), (0.98, 0.92), (0.02, 0.92))
    _CORNER: float = 0.1
    _RIM: float = 0.06
    # Exclamation mark: the bar as a capsule from top to bottom center with its half width, and the dot.
    _BAR: tuple[_Point, _Point, float] = ((0.5, 0.38), (0.5, 0.56), 0.062)
    _DOT: tuple[_Point, float] = ((0.5, 0.735), 0.065)

    @classmethod
    def warning(cls, *, size: int) -> bytes:
        """
        Draw the warning sign: an amber rounded triangle with a dark rim and exclamation mark.

        :param size: height and width of the sign in pixels
        :return: PNG data
        """
        pixels: list[_Rgba] = [cls._pixel(x=x, y=y, size=size) for y in range(size) for x in range(size)]
        return cls._png(width=size, height=size, pixels=pixels)

    @classmethod
    def _pixel(cls, *, x: int, y: int, size: int) -> _Rgba:
        """
        Compute one pixel of the warning sign from the color of each of its samples.

        :param x: pixel column
        :param y: pixel row
        :param size: icon side in pixels
        :return: red, green, blue and alpha
        """
        # The rim is at least one pixel wide so that small icons keep their outline.
        rim: float = max(cls._RIM, 1 / size)
        ink: int = 0
        amber: int = 0
        for sub_x in range(cls._SAMPLES):
            for sub_y in range(cls._SAMPLES):
                point: _Point = (
                    (x + (sub_x + 0.5) / cls._SAMPLES) / size,
                    (y + (sub_y + 0.5) / cls._SAMPLES) / size,
                )
                distance: float = cls._sign_distance(point=point)
                if distance > 0:
                    continue
                if distance > -rim or cls._on_mark(point=point):
                    ink += 1
                else:
                    amber += 1
        covered: int = ink + amber
        if covered == 0:
            return 0, 0, 0, 0
        red, green, blue = (
            round((dark * ink + light * amber) / covered) for dark, light in zip(cls._INK, cls._AMBER, strict=True)
        )
        return red, green, blue, round(255 * covered / cls._SAMPLES**2)

    @classmethod
    def _sign_distance(cls, *, point: _Point) -> float:
        """
        Measure the signed distance from a point to the rounded triangle, negative inside.

        The triangle shrunk towards its incenter by the corner radius, then grown back by it, has rounded corners.

        :param point: x and y in fractions of the icon side
        :return: distance in fractions of the icon side
        """
        corners: tuple[_Point, _Point, _Point] = cls._TRIANGLE
        sides: list[float] = [math.dist(corners[(index + 1) % 3], corners[(index + 2) % 3]) for index in range(3)]
        perimeter: float = sum(sides)
        incenter: _Point = (
            sum(side * corner[0] for side, corner in zip(sides, corners, strict=True)) / perimeter,
            sum(side * corner[1] for side, corner in zip(sides, corners, strict=True)) / perimeter,
        )
        doubled_area: float = abs(
            (corners[1][0] - corners[0][0]) * (corners[2][1] - corners[0][1])
            - (corners[2][0] - corners[0][0]) * (corners[1][1] - corners[0][1])
        )
        # The inradius is twice the area over the perimeter.
        scale: float = 1 - cls._CORNER * perimeter / doubled_area
        inner: list[_Point] = [
            (incenter[0] + (corner[0] - incenter[0]) * scale, incenter[1] + (corner[1] - incenter[1]) * scale)
            for corner in corners
        ]
        edge: float = min(
            cls._segment_distance(point=point, start=inner[index], end=inner[(index + 1) % 3]) for index in range(3)
        )
        inside: bool = cls._in_triangle(point=point, corners=inner)
        return (-edge if inside else edge) - cls._CORNER

    @classmethod
    def _on_mark(cls, *, point: _Point) -> bool:
        """
        Tell whether a point lies on the exclamation mark.

        :param point: x and y in fractions of the icon side
        :return: True when on the bar or the dot
        """
        top, bottom, half_width = cls._BAR
        center, radius = cls._DOT
        on_bar: bool = cls._segment_distance(point=point, start=top, end=bottom) <= half_width
        return on_bar or math.dist(point, center) <= radius

    @staticmethod
    def _segment_distance(*, point: _Point, start: _Point, end: _Point) -> float:
        """
        Measure the distance from a point to a line segment.

        :param point: the point
        :param start: one end of the segment
        :param end: the other end
        :return: the distance
        """
        along_x: float = end[0] - start[0]
        along_y: float = end[1] - start[1]
        share: float = ((point[0] - start[0]) * along_x + (point[1] - start[1]) * along_y) / (along_x**2 + along_y**2)
        share = min(max(share, 0.0), 1.0)
        return math.dist(point, (start[0] + along_x * share, start[1] + along_y * share))

    @staticmethod
    def _in_triangle(*, point: _Point, corners: list[_Point]) -> bool:
        """
        Tell whether a point lies inside a triangle.

        :param point: the point
        :param corners: the three corners
        :return: True when inside or on an edge
        """
        sides: list[float] = [
            # Sign of the cross product: which side of the edge the point is on.
            (end[0] - start[0]) * (point[1] - start[1]) - (end[1] - start[1]) * (point[0] - start[0])
            for start, end in zip(corners, corners[1:] + corners[:1], strict=True)
        ]
        return all(side >= 0 for side in sides) or all(side <= 0 for side in sides)

    @classmethod
    def _png(cls, *, width: int, height: int, pixels: list[_Rgba]) -> bytes:
        """
        Encode RGBA pixels as PNG data.

        :param width: width in pixels
        :param height: height in pixels
        :param pixels: red, green, blue and alpha of each pixel, row by row
        :return: PNG data
        """
        rows: bytes = b"".join(
            # Filter type 0 (none) starts every row.
            b"\x00" + bytes(channel for pixel in pixels[row * width : (row + 1) * width] for channel in pixel)
            for row in range(height)
        )
        # 8 bits per channel, color type 6 (RGBA), no interlace.
        header: bytes = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
        return (
            b"\x89PNG\r\n\x1a\n"
            + cls._chunk(kind=b"IHDR", body=header)
            + cls._chunk(kind=b"IDAT", body=zlib.compress(rows))
            + cls._chunk(kind=b"IEND", body=b"")
        )

    @staticmethod
    def _chunk(*, kind: bytes, body: bytes) -> bytes:
        """
        Frame a PNG chunk with its length and checksum.

        :param kind: chunk type
        :param body: chunk data
        :return: the chunk
        """
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))
