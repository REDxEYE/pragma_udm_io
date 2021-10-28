from pathlib import Path

import bpy

from pragma_udm_io.utils import get_new_unique_collection
from pragma_udm_wrapper import UDM


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

    def load_mesh(self):
        pass

    def load_textures(self):
        pass

    def finalize(self):
        pass

    def cleanup(self):
        pass


def import_pmap(path: Path):
    loader = PMAPLoader(path)
    loader.load_mesh()
    loader.load_textures()
    loader.finalize()
    loader.cleanup()
