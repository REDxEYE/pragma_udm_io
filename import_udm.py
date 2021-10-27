from collections import defaultdict
from pathlib import Path
import numpy as np

import bpy

from .asset_handlers.pmat import import_pmat
from .asset_handlers.pmesh import import_pmesh
from .asset_handlers.pskel import import_pskel
from .content_managment.content_manager import ContentManager
from .pragma_udm_wrapper import UDM
from pragma_udm_io.utils import get_or_create_collection, get_new_unique_collection, ROTN90_X, transform_vec3


class PMDLLoader:

    def __init__(self, path: Path):
        self.path = path
        self._udm_file = UDM()
        assert self._udm_file.load(path), f'Failed to load "{path}"'
        self.root = self._udm_file.root

        self._armature_obj = None
        self._object_by_meshgroup = defaultdict(list)
        self._objects = []
        self._bone_names = {}
        self.master_collection = get_new_unique_collection(self.model_name + '_model', bpy.context.scene.collection)

    @property
    def model_name(self):
        return self.path.stem

    def load_armature(self):
        self._bone_names, self._armature_obj = import_pskel(self.model_name, self.root['skeleton'])

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

                self._object_by_meshgroup[mesh_group_id].append(mesh_obj)
                self._objects.append(mesh_obj)

    def load_textures(self):
        cm = ContentManager()
        for mat_root in self.root['materialPaths']:
            for mat in self.root['materials']:
                mat_path = cm.find_path(Path('materials') / mat_root / mat, extension='.pmat')
                if mat_path:
                    udm_mat = UDM()
                    udm_mat.load(mat_path)
                    import_pmat(udm_mat.root, mat)
        pass

    def finalize(self):
        self.master_collection.objects.link(self._armature_obj)
        for obj in self._objects:
            modifier = obj.modifiers.new(
                type="ARMATURE", name="Armature")
            modifier.object = self._armature_obj
            obj.parent = self._armature_obj
            # self.master_collection.objects.link(obj)
        if 'bodyGroups' in self.root:
            for body_group in self.root['bodyGroups']:
                bg_collection = get_or_create_collection(body_group.name, self.master_collection)
                for mesh_group in body_group['meshGroups']:
                    for obj in self._object_by_meshgroup[mesh_group]:
                        bg_collection.objects.link(obj)
        if 'baseMeshGroups' in self.root:
            for base_id in self.root['baseMeshGroups']:
                for obj in self._object_by_meshgroup[base_id]:
                    self.master_collection.objects.link(obj)

    def cleanup(self):
        self._udm_file.destroy()
        pass


def import_udm_model(path: Path):
    loader = PMDLLoader(path)
    loader.load_armature()
    loader.load_mesh()
    loader.load_textures()
    loader.finalize()
    loader.cleanup()
