import bpy
import numpy as np


def texture_from_data(name, rgba_data, image_width, image_height, update):
    if bpy.data.images.get(name, None) and not update:
        return bpy.data.images.get(name)
    pixels = np.divide(rgba_data, 255, dtype=np.float32).flatten()
    image = bpy.data.images.get(name, None) or bpy.data.images.new(
        name,
        width=image_width,
        height=image_height,
        alpha=True,
    )
    image.filepath = name + '.tga'
    image.alpha_mode = 'CHANNEL_PACKED'
    image.file_format = 'TARGA'

    if bpy.app.version > (2, 83, 0):
        image.pixels.foreach_set(pixels)
    else:
        image.pixels[:] = pixels.tolist()
    image.pack()
    return image
