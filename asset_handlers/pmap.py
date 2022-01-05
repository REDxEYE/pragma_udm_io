import json
from pathlib import Path

import bpy
from mathutils import Vector, Quaternion, Matrix

from pragma_udm_io.utils import *
from .pmdl import import_pmdl
from ..pragma_udm_wrapper import UDM
from ..content_managment.content_manager import ContentManager
from ..pragma_udm_wrapper import UdmProperty

CM = ContentManager()


class PMAPLoader:
    def __init__(self, path: Path):
        self.path = path
        self._udm_file = UDM()
        assert self._udm_file.load(path), f'Failed to load "{path}"'
        self.root = self._udm_file.root

        self._objects = []
        self.master_collection = get_new_unique_collection(self.model_name + '_map', bpy.context.scene.collection)

    @property
    def model_name(self):
        return self.path.stem

    def load_mesh(self, scale):
        for ent in self.root['entities']:
            ent: UdmProperty
            transform = ent['pose']
            key_values = ent.get('keyValues', {})
            pos = Vector(transform_vec3(transform[0:3], ROTN90_X)) * scale
            x, z, y, w = transform[3:7]
            rot = Quaternion((w, x, -y, z))
            # rot.rotate(ROT90_Z)
            scl = Vector(transform[7:10])
            # mat = Matrix.Translation(pos) @ rot.to_matrix().to_4x4() @ Matrix.Scale(1, 4, scl)
            if key_values and 'model' in key_values:
                if '*' in key_values['model'] or not key_values['model']:
                    continue
                model_path = CM.find_path(key_values['model'], 'models', '.pmdl')
                if model_path is None:
                    print(f"Failed to load {key_values['model']!r}")
                    continue

                class_name = ent['className']
                type_collection = get_or_create_collection(class_name, self.master_collection)
                loader = import_pmdl(model_path, scale, type_collection,
                                     class_name.startswith('func_') or class_name.startswith('trigger_'))
                if loader.is_static_prop:
                    for obj in loader.objects:
                        obj['entity_data'] = {'entity': json.loads(key_values.to_json())}
                        obj.rotation_mode = 'QUATERNION'
                        obj.rotation_quaternion = rot
                        obj.location = pos
                        obj.scale = scl
                        # obj.matrix_basis = mat
                else:
                    loader.armature['entity_data'] = {'entity': json.loads(key_values.to_json())}
                    loader.armature.rotation_mode = 'QUATERNION'
                    loader.armature.rotation_quaternion = rot
                    loader.armature.location = pos
                    loader.armature.scale = scl
                    # loader.armature.matrix_basis = mat

        pass

    def load_textures(self):
        pass

    def finalize(self):
        pass

    def cleanup(self):
        pass


def import_pmap(path: Path, scale=1.0):
    loader = PMAPLoader(path)
    loader.load_mesh(scale)
    loader.load_textures()
    loader.finalize()
    loader.cleanup()
