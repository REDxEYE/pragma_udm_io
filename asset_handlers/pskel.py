from typing import List, Dict

import bpy
import numpy as np
from mathutils import Vector, Quaternion, Matrix

from ..pragma_udm_wrapper import pose_to_matrix, convert_pragma_matrix
from ..pragma_udm_wrapper.properties import ElementProperty
from pragma_udm_io.utils import ROT90_X, ROTN90_Z


def import_pskel(name: str, asset: ElementProperty, scale=1.0):
    assert asset['assetType'] == 'PSKEL'
    armature_asset = asset['assetData']

    def _collect_bones(current_node, bones: List[Dict]):
        bone_info = {'bone': current_node, 'parent': None}
        bones.append(bone_info)
        bone_names[current_node['index']] = current_node.name
        for child in current_node.get('children', {}).values():
            bone = _collect_bones(child, bones)
            bone['parent'] = current_node
        return bone_info

    bone_names = {}
    all_bones = []
    for bone in armature_asset['bones'].values():
        _collect_bones(bone, all_bones)
    if len(all_bones) == 1:
        return [], None

    armature = bpy.data.armatures.new(f"{name}_ARM_DATA")
    armature_obj = bpy.data.objects.new(f"{name}_ARM", armature)

    bpy.context.scene.collection.objects.link(armature_obj)
    armature_obj.select_set(True)
    bpy.context.view_layer.objects.active = armature_obj

    bpy.ops.object.mode_set(mode='EDIT')

    for bone_info in all_bones:
        bone = bone_info['bone']
        parent = bone_info['parent']
        bl_bone = armature.edit_bones.new(bone.name[-63:])
        bl_bone.tail = (Vector([0, 1, 0])) + bl_bone.head
        transform = bone['pose']

        pos = Vector(transform[0:3]) * scale
        rot = Quaternion([transform[6], *transform[3:6]])
        scl = Vector(transform[7:10])

        rot_scale = Matrix.LocRotScale(pos, rot, scl)
        converted = convert_pragma_matrix(np.asarray(rot_scale.transposed()))
        mat = Matrix(converted)

        bl_bone.matrix = mat
        if parent is not None:
            parent = armature.edit_bones.get(parent.name[-63:])
            bl_bone.parent = parent

    bpy.ops.object.mode_set(mode='POSE')
    for bone_info in all_bones:
        bone = bone_info['bone']
        armature_obj.pose.bones[bone.name[-63:]].rotation_mode = 'QUATERNION'

    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.context.scene.collection.objects.unlink(armature_obj)
    return bone_names, armature_obj
