import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import List
import numpy as np

import bpy
from mathutils import *

from .asset_handlers.pmesh import import_pmesh
from .pragma_udm_wrapper import UDM, UdmProperty
from .utils import get_or_create_collection, get_new_unique_collection, get_material, ROTN90_X, ROT90_X, ROTN90_Z, \
    transform_vec3


class PMDLLoader:

    def __init__(self, path: Path):
        self.path = path
        self._udm_file = UDM(True)
        assert self._udm_file.load(path), f'Failed to load "{path}"'
        self.root = self._udm_file.root

        self._armature_obj = None
        self._objects = []
        self._bone_names = []
        self.master_collection = get_new_unique_collection(self.model_name, bpy.context.scene.collection)

    @property
    def model_name(self):
        return self.path.stem

    def load_armature(self):
        assert self.root['skeleton/assetType'] == 'PSKEL'
        armature_asset = self.root['skeleton/assetData']

        armature = bpy.data.armatures.new(f"{self.model_name}_ARM_DATA")
        armature_obj = bpy.data.objects.new(f"{self.model_name}_ARM", armature)

        bpy.context.scene.collection.objects.link(armature_obj)
        armature_obj.select_set(True)
        bpy.context.view_layer.objects.active = armature_obj

        bpy.ops.object.mode_set(mode='EDIT')

        def _collect_bones(current_node, bones: List[UdmProperty]):
            bones.append(current_node)
            bone = armature.edit_bones.new(current_node.name[-63:])
            bone.tail = (Vector([0, 1, 0])) + bone.head
            transform = current_node['pose']

            pos = Vector(transform[0:3])
            rot = Quaternion([transform[6], *transform[3:6]])
            scl = Vector(transform[7:10])
            mat = Matrix.Translation(pos) @ rot.to_matrix().to_4x4() @ Matrix.Scale(1, 4, scl)
            mat = ROT90_X @ mat
            mat = mat @ ROTN90_Z
            bone.matrix = mat

            self._bone_names.append(current_node.name)

            for child in current_node.get('children', []):
                child_bone = _collect_bones(child, bones)
                child_bone.parent = bone
            return bone

        all_bones = []
        for bone in armature_asset['bones']:
            _collect_bones(bone, all_bones)

        bpy.context.scene.collection.objects.unlink(armature_obj)

        self._armature_obj = armature_obj

    def _find_flexes_by_ids(self, mesh_group_id: int, mesh_id: int, sub_mesh_id: int):
        if 'morphTargetAnimations' in self.root:
            flexes = []
            for flex in self.root['morphTargetAnimations']:
                assert flex['assetType'] == "PMORPHANI"
                flex_data = flex['assetData']
                for mesh_anim in flex_data['meshAnimations']:
                    if (mesh_anim['meshGroup'] == mesh_group_id and
                            mesh_anim['mesh'] == mesh_id and
                            mesh_anim['subMesh'] == sub_mesh_id):
                        flexes.append((flex_data['name'], mesh_anim))
            return flexes
        return []

    def load_mesh(self):
        mesh_groups = {mesh_group['index']: mesh_group for mesh_group in self.root['meshGroups']}
        if 'bodyGroups' in self.root:
            for body_group in self.root['bodyGroups']:
                for mesh_group_id in body_group['meshGroups']:
                    mesh_group = mesh_groups[mesh_group_id]
                    self._load_mesh_group(mesh_group)
        elif 'meshGroups' in self.root:
            for mesh_group in self.root['meshGroups']:
                self._load_mesh_group(mesh_group)
            pass

    def _load_mesh_group(self, mesh_group):
        mesh_group_id = mesh_group['index']
        for mesh_id, mesh in enumerate(mesh_group['meshes']):
            for sub_mesh_id, sub_mesh in enumerate(mesh['subMeshes']):
                sub_mesh_prefix = f'{mesh_group.name}_{mesh_id}'
                mesh_obj = import_pmesh(sub_mesh_prefix, sub_mesh, self.root, self._bone_names)
                mesh_data = mesh_obj.data
                flexes = self._find_flexes_by_ids(mesh_group_id, mesh_id, sub_mesh_id)
                if len(flexes) > 0:
                    vertices: np.ndarray = sub_mesh['assetData/vertices']
                    pos = transform_vec3(vertices['pos'], ROTN90_X)
                    mesh_obj.shape_key_add(name='base')
                    for flex_name, flex_data in flexes:
                        if flex_data['mesh'] != mesh_id or flex_data['subMesh'] != sub_mesh_id:
                            continue
                        flex_name = flex_name.replace('flex_', '')
                        multi_frame_mode = len(flex_data['frames']) > 0
                        for frame_num, frame in enumerate(flex_data['frames']):
                            flex_indices = frame['vertexIndices']
                            attribs = {attr['property']: attr['values'] for attr in frame['attributes']}
                            assert 'position' in attribs, f'Missing position attribute on ' \
                                                          f'"{flex_name}[{frame_num}]"'
                            full_flex_name = f"{flex_name}[{frame_num}]" if not multi_frame_mode else flex_name
                            shape_key = (mesh_data.shape_keys.key_blocks.get(full_flex_name, None) or
                                         mesh_obj.shape_key_add(name=full_flex_name))
                            flex_pos = pos.copy()
                            flex_pos[flex_indices] += transform_vec3(
                                attribs['position'].view(np.float16).reshape((-1, 4))[:, :3], ROTN90_X)
                            shape_key.data.foreach_set("co", flex_pos.reshape(-1))

                self._objects.append(mesh_obj)

    def load_textures(self):
        pass

    def finalize(self):
        self.master_collection.objects.link(self._armature_obj)
        for obj in self._objects:
            self.master_collection.objects.link(obj)
        pass

    def cleanup(self):
        # self._udm_file.destroy()
        pass


def import_udm_model(path: Path):
    loader = PMDLLoader(path)
    loader.load_armature()
    loader.load_mesh()
    loader.load_textures()
    loader.finalize()
    loader.cleanup()
