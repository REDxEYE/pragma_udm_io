import bpy
import numpy as np


def texture_from_data(name, rgba_data, image_dimm, update):
    if bpy.data.images.get(name, None) and not update:
        return bpy.data.images.get(name)
    pixels = np.divide(rgba_data, 255, dtype=np.float32).flatten()
    image = bpy.data.images.get(name, None) or bpy.data.images.new(
        name,
        width=image_dimm[0],
        height=image_dimm[1],
        alpha=True,
    )
    image.filepath = name + '.tga'
    image.alpha_mode = 'CHANNEL_PACKED'
    image.file_format = 'TARGA'

    image.pixels.foreach_set(pixels)

    image.pack()
    return image
