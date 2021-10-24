import math

import bpy
import random

import numpy as np
from mathutils import Euler

ROT90_X = Euler([math.radians(90), 0, 0]).to_matrix().to_4x4()
ROTN90_X = Euler([math.radians(-90), 0, 0]).to_matrix().to_4x4()
ROT90_Y = Euler([0, math.radians(90), 0]).to_matrix().to_4x4()
ROT90_Z = Euler([0, 0, math.radians(90)]).to_matrix().to_4x4()
ROTN90_Z = Euler([0, 0, math.radians(-90)]).to_matrix().to_4x4()


def get_material(mat_name, model_ob):
    md = model_ob.data
    mat = bpy.data.materials.get(mat_name, None)
    if mat:
        if md.materials.get(mat.name, None):
            for i, material in enumerate(md.materials):
                if material == mat:
                    return i
        else:
            md.materials.append(mat)
            return len(md.materials) - 1
    else:
        mat = bpy.data.materials.new(mat_name)
        mat.diffuse_color = [random.uniform(.4, 1) for _ in range(3)] + [1.0]
        md.materials.append(mat)
        return len(md.materials) - 1


def get_or_create_collection(name, parent: bpy.types.Collection) -> bpy.types.Collection:
    new_collection = (bpy.data.collections.get(name, None) or
                      bpy.data.collections.new(name))
    if new_collection.name not in parent.children:
        parent.children.link(new_collection)
    new_collection.name = name
    return new_collection


def get_new_unique_collection(model_name, parent_collection):
    copy_count = len([collection for collection in bpy.data.collections if model_name in collection.name])

    master_collection = get_or_create_collection(model_name + (f'_{copy_count}' if copy_count > 0 else ''),
                                                 parent_collection)
    return master_collection


def append_blend(filepath, type_name, link=False):
    with bpy.data.libraries.load(filepath, link=link) as (data_from, data_to):
        setattr(data_to, type_name, [asset for asset in getattr(data_from, type_name)])
    for o in getattr(data_to, type_name):
        o.use_fake_user = True


def transform_vec3(vec3, matrix):
    tmp = np.zeros((len(vec3), 4), dtype=vec3.dtype)
    tmp[:, :3] = vec3
    tmp = tmp @ matrix
    return tmp[:, :3]
