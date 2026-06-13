from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import struct


class IcoError(ValueError):
    pass


@dataclass(frozen=True)
class IconImage:
    width: int
    height: int
    color_count: int
    reserved: int
    planes: int
    bit_count: int
    data: bytes


@dataclass(frozen=True)
class IcoFile:
    images: tuple[IconImage, ...]

    @classmethod
    def from_path(cls, path: Path) -> "IcoFile":
        data = path.read_bytes()
        if len(data) < 6:
            raise IcoError(f"{path} is too small to be an ICO")

        reserved, icon_type, count = struct.unpack_from("<HHH", data, 0)
        if reserved != 0 or icon_type != 1:
            raise IcoError(f"{path} is not an icon ICO file")
        if count == 0:
            raise IcoError(f"{path} contains no icon images")

        entries_offset = 6
        entries_size = count * 16
        if len(data) < entries_offset + entries_size:
            raise IcoError(f"{path} has a truncated ICO directory")

        images: list[IconImage] = []
        for i in range(count):
            offset = entries_offset + (i * 16)
            width, height, color_count, reserved, planes, bit_count, size, image_offset = (
                struct.unpack_from("<BBBBHHII", data, offset)
            )
            if size == 0:
                raise IcoError(f"{path} has an empty image at index {i}")
            end = image_offset + size
            if image_offset < 0 or end > len(data):
                raise IcoError(f"{path} has an out-of-range image at index {i}")
            images.append(
                IconImage(
                    width=width,
                    height=height,
                    color_count=color_count,
                    reserved=reserved,
                    planes=planes,
                    bit_count=bit_count,
                    data=data[image_offset:end],
                )
            )

        return cls(tuple(images))

    def to_group_icon(self, icon_ids: list[int]) -> bytes:
        if len(icon_ids) != len(self.images):
            raise IcoError("icon id count must match image count")

        out = bytearray(struct.pack("<HHH", 0, 1, len(self.images)))
        for image, icon_id in zip(self.images, icon_ids):
            out.extend(
                struct.pack(
                    "<BBBBHHIH",
                    image.width,
                    image.height,
                    image.color_count,
                    image.reserved,
                    image.planes,
                    image.bit_count,
                    len(image.data),
                    icon_id,
                )
            )
        return bytes(out)


def parse_group_icon_ids(data: bytes) -> list[int]:
    if len(data) < 6:
        return []
    reserved, icon_type, count = struct.unpack_from("<HHH", data, 0)
    if reserved != 0 or icon_type != 1:
        return []

    ids: list[int] = []
    entry_size = 14
    for i in range(count):
        offset = 6 + (i * entry_size)
        if offset + entry_size > len(data):
            return []
        icon_id = struct.unpack_from("<H", data, offset + 12)[0]
        ids.append(icon_id)
    return ids
