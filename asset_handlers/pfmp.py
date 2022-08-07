import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Any, List, Optional, Dict

import bpy
import numpy as np
from mathutils import Vector, Quaternion, Matrix

from .pmap import import_pmap
from .pmdl import import_pmdl
from ..content_managment import ContentManager
from ..pragma_udm_wrapper import UDM, ElementProperty, convert_pragma_matrix, pose_to_matrix
from ..pragma_udm_wrapper.type_wrappers.pfmp import PragmaFilmMakerProject
from ..utils import get_new_unique_collection, transform_vec3, ROTN90_X, node, ROT180_Y, ROTN90_Y, ROT90_Y, ROT90_X, \
    ROTN90_Z

CM = ContentManager()


@dataclass(slots=True)
class Actor:
    name: str
    visible: bool = field(default=True)
    data: Optional[bpy.types.ID] = field(default=None)
    matrix: Matrix = field(default_factory=lambda: Matrix.Identity(4))
    components: List[ElementProperty] = field(default_factory=list)
    child_objects: List[bpy.types.Object] = field(default_factory=list)
    object: Optional[bpy.types.Object] = field(default=None)

def convert_loc(x): return Vector([x[0], -x[2], x[1]])
def convert_quat(q): return Quaternion([q[3], q[0], -q[2], q[1]])

class PFMPLoader:

    def __init__(self, path: Path, scale=1.0):
        self.path = path
        self._udm_file = UDM()
        self.scale = scale
        assert self._udm_file.load(path), f'Failed to load "{path}"'

        self.project = PragmaFilmMakerProject(self._udm_file)
        self._actors: Dict[str, Actor] = {}
        self.master_collection = get_new_unique_collection(self.session_name + '_session', bpy.context.scene.collection)
        self.props_collection = get_new_unique_collection(self.session_name + '_props', self.master_collection)
        self._component_handlers = {
            'pfm_actor': self._actor_component,
            'pfm_sky': self._sky_component,
            'pfm_camera': self._camera_component,
            'camera': self._camera_data_component,
            'optical_camera': self._camera_optical_data_component,
            'pfm_model': self._model_component,
            'model': self._model_data_component,
            'render': self._render_component,
            'color': self._color_component,
            'light': self._light_component,
            'radius': self._radius_component,
            'light_point': self._light_point_component,
            'light_map_receiver': self._light_map_receiver_component,
            'skybox': self._skybox_component,
        }

        self._scene_root = bpy.data.objects.new(self.session_name + '_scene_root', None)
        self.master_collection.objects.link(self._scene_root)
        self._scene_root.matrix_basis = self._convert_transform(self.active_clip.scene['transform'])

    def _convert_transform(self, scene_transform):
        return self._compose_matrix(transform_vec3(scene_transform[0:3], ROTN90_X),
                                    scene_transform[3:7],
                                    scene_transform[7:10])

    def _compose_matrix(self, position, rotation, scale):
        position = Vector(transform_vec3(position, ROTN90_X)) * self.scale
        x, z, y, w = rotation
        # noinspection PyTypeChecker
        rot = Quaternion((w, x, y, z))
        mat = Matrix.Translation(position) @ rot.to_matrix().to_4x4() @ Matrix.Scale(1, 4, Vector(scale))
        return mat

    @property
    def session_name(self):
        return self.project.session.name or "UNNAMED_SESSION"

    def _get_clip_by_id(self, clip_id: str):
        for clip in self.project.session.clips:
            if clip.unique_id == clip_id:
                return clip
        return None

    @property
    def active_clip(self):
        return self._get_clip_by_id(self.project.session.active_clip)

    def load_map(self):
        active_clip = self.active_clip
        if active_clip.map_name:
            if map_file := CM.find_path(active_clip.map_name, 'maps', '.pmap'):
                import_pmap(map_file)

    def load_actors(self):
        active_clip = self.active_clip
        for track_group in active_clip.track_groups:
            for track in track_group.tracks:
                for film_clip in track.film_clips:
                    scene = film_clip['scene']
                    for actor in scene['actors']:
                        self._process_actor(actor)
                    for group in scene['groups']:
                        for actor in group['actors']:
                            self._process_actor(actor)
                    for track_group2 in film_clip['trackGroups']:
                        for track2 in track_group2['tracks']:
                            for animation_clip in track2['animationClips']:
                                actor = self._actors[animation_clip['actor']]
                                animation = animation_clip['animation']
                                animation_data = animation['assetData']

                                animation_action = bpy.data.actions.new(f'{film_clip["name"]}_{actor.name}_ACTION')

                                if not actor.object.animation_data:
                                    actor.object.animation_data_create()

                                actor.object.animation_data.action = animation_action
                                actor.object.animation_data.action = animation_action
                                actor.object.animation_data.action = animation_action
                                actor.object.animation_data.action = animation_action

                                for channel in animation_data['channels']:
                                    values = channel['values'].value()
                                    times = channel['times'].value()
                                    values = values[times > 0]
                                    times = times[times > 0]
                                    if len(values) == 0 or len(times) == 0:
                                        continue
                                    path = channel['targetPath'].split('/')
                                    assert path[0] == 'ec'
                                    if path[1] == 'flex':
                                        pass  # TODO: flex animation
                                    elif path[1] == 'animated' and path[2] == 'bone':
                                        self._load_bone_animation(animation_action, path[3], path[4], values, times)
                                    elif path[1] == 'pfm_actor':
                                        pass  # TODO: actor transforms
                                    else:
                                        raise NotImplementedError(channel['targetPath'])

    def _convert_rotation(self, rot):
        return convert_quat(rot)

    def _load_bone_animation(self, action: bpy.types.Action, bone_name: str, channel: str,
                             values: np.ndarray, times: np.ndarray):
        group = action.groups.get(bone_name, False) or action.groups.new(bone_name)
        if channel == 'rotation':
            x = values[:, 0].copy()
            y = values[:, 1].copy()
            z = values[:, 2].copy()
            w = values[:, 3].copy()
            values[:, 0], values[:, 1], values[:, 2], values[:, 3] = w, x, y, z
            curve_count = 4
            curve_channel = 'rotation_quaternion'
        elif channel == 'position':
            values *= self.scale
            curve_count = 3
            curve_channel = 'location'
        else:
            raise NotImplementedError(channel)
        curves = []
        for i in range(curve_count):
            curve = action.fcurves.new(data_path=f'pose.bones["{bone_name}"].{curve_channel}', index=i)
            curve.keyframe_points.add(len(times))
            curve.group = group
            curves.append(curve)

        scene_fps = bpy.context.scene.render.fps
        if channel == 'rotation':
            for keyframe_id, (time, value) in enumerate(zip(times, values)):
                frame_id = int(time * scene_fps)
                #print('Frame ', frame_id)
                #print('WXYZ', value.round(1))
                value = [value[1],value[2],value[3],value[0]]
                value = convert_quat(value)

                # TODO: Get these from pskel
                rotBefore = Quaternion((0.7071068286895752, 0.0, 0.0, -0.7071068286895752))
                rotAfter = Quaternion((0.7071068286895752, 0.0, 0.0, 0.7071068286895752))
                value = rotAfter @ value @ rotBefore

                #print('WXYZ converted', value)
                #print('========')
                for i in range(curve_count):
                    frame = curves[i].keyframe_points[keyframe_id]
                    frame.co = (frame_id, value[i])
                    frame.interpolation = 'LINEAR'
        else:
            for keyframe_id, (time, value) in enumerate(zip(times, values)):
                frame_id = int(time * scene_fps)
                #value = convert_loc(value)

                for i in range(curve_count):
                    frame = curves[i].keyframe_points[keyframe_id]
                    frame.co = (frame_id, value[i])
                    frame.interpolation = 'LINEAR'

    def _process_actor(self, actor):
        actor_name = actor['name']
        actor_container = Actor(actor_name)
        self._actors[actor['uniqueId']] = actor_container
        for component in actor['components']:
            component_type = component['type']
            handler: Callable[[bpy.types.Object, ElementProperty], None]
            handler = self._component_handlers.get(component_type, self._dummy_component)
            handler(actor_container, component)
        actor_object = bpy.data.objects.new(actor_container.name, actor_container.data)
        actor_object.hide_viewport = not actor_container.visible
        actor_object.hide_render = not actor_container.visible
        actor_object.parent = self._scene_root
        actor_object.matrix_local = actor_container.matrix
        if actor_container.child_objects:
            for child in actor_container.child_objects:
                child.hide_viewport = not actor_container.visible
                child.hide_render = not actor_container.visible
                child.parent = actor_object
        actor_container.object = actor_object
        self.master_collection.objects.link(actor_object)

    def _dummy_component(self, actor_object: Actor, component: ElementProperty):
        print('Unhandled component:', component['type'])

    def _actor_component(self, actor_object: Actor, component: ElementProperty):
        properties = component['properties']
        matrix = self._compose_matrix(properties['position'], properties['rotation'], properties['scale'])
        actor_object.matrix = matrix
        actor_object.visible = bool(properties['visible'])

    def _sky_component(self, actor_object: Actor, component: ElementProperty):
        properties = component['properties']
        texture_path = CM.find_path(properties['skyTexture'], 'materials')
        if texture_path is None:
            print('Failed to load sky')
            return
        sky_name = self.session_name + '_SKY'
        world = bpy.data.worlds.get(sky_name, False) or bpy.data.worlds.new(sky_name)

        world.use_nodes = True
        node.clean_nodes(world)
        world['udm_loaded'] = True

        material_output = node.create_node(world, node.Nodes.ShaderNodeOutputWorld)
        shader = node.create_node(world, node.Nodes.ShaderNodeBackground)
        node.connect_nodes(world, shader.outputs['Background'], material_output.inputs['Surface'])

        texture = node.create_node(world, node.Nodes.ShaderNodeTexEnvironment)
        texture.image = node.create_texture(texture_path)
        node.connect_nodes(world, texture.outputs['Color'], shader.inputs['Color'])

        bpy.context.scene.world = world

    def _camera_component(self, actor_object: Actor, component: ElementProperty):
        camera_data = bpy.data.cameras.new(name=actor_object.name + "_DATA")
        actor_object.data = camera_data
        actor_object.matrix @= ROT180_Y
        actor_object.matrix @= ROTN90_X

    def _camera_data_component(self, actor_object: Actor, component: ElementProperty):
        properties = component['properties']
        camera_data = actor_object.data
        if camera_data is None:
            raise ValueError('Expected camera data')
        camera_data.lens_unit = 'FOV'
        camera_data.angle = math.radians(properties['fov'])

    def _camera_optical_data_component(self, actor_object: Actor, component: ElementProperty):
        properties = component['properties']
        camera_data = actor_object.data
        if camera_data is None:
            raise ValueError('Expected camera data')
        camera_data.lens_unit = 'MILLIMETERS'
        camera_data.lens = properties['focalLength']
        camera_data.sensor_width = properties['sensorSize']
        camera_data.dof.aperture_blades = properties['ringCount']
        camera_data.dof.aperture_fstop = properties['fstop']
        camera_data.dof.aperture_rotation = properties['apertureBladesRotation']
        camera_data.dof.focus_distance = properties['focalDistance'] * self.scale
        camera_data.dof.use_dof = True

    def _model_component(self, actor_object: Actor, component: ElementProperty):
        return

    def _model_data_component(self, actor_object: Actor, component: ElementProperty):
        properties = component['properties']
        model = CM.find_path(Path(properties['model']), 'models', '.pmdl')
        if model is None:
            print('Failed to load Actor model data')
            return
        loader = import_pmdl(model, self.scale, self.props_collection, True)
        if loader.armature:
            actor_object.child_objects.append(loader.armature)
        else:
            actor_object.child_objects.extend(loader.objects)

    def _render_component(self, actor_object: Actor, component: ElementProperty):
        return

    def _skybox_component(self, actor_object: Actor, component: ElementProperty):
        actor_object.visible = False

    def _light_map_receiver_component(self, actor_object: Actor, component: ElementProperty):
        return

    def _light_component(self, actor_object: Actor, component: ElementProperty):
        properties = component['properties']
        actor_object.data = bpy.data.lights.new(actor_object.name, 'POINT')
        intensity_type = properties['intensityType']
        intensity = properties['intensity']
        if intensity_type == 0:
            intensity *= 0.1
        elif intensity_type == 1:
            intensity *= 0.1 * 12.57
        else:
            print(f'Unknown intensity type: {intensity_type}')
            return
        actor_object.data.energy = intensity * 10000 * self.scale

    def _radius_component(self, actor_object: Actor, component: ElementProperty):
        properties = component['properties']
        actor_object.data.shadow_soft_size = properties['radius'] * self.scale

    def _light_point_component(self, actor_object: Actor, component: ElementProperty):
        actor_object.data.type = 'POINT'

    # bpy.context.object.data.type = 'SUN'
    # bpy.context.object.data.type = 'SPOT'
    # bpy.context.object.data.type = 'AREA'
    # bpy.context.object.data.type = 'POINT'

    def _color_component(self, actor_object: Actor, component: ElementProperty):
        properties = component['properties']
        if actor_object.data is None:
            print(f'Actor:{actor_object} does not have any data assigned')
            return
        elif isinstance(actor_object.data, bpy.types.Mesh):
            print(f'Actor:{actor_object} mesh not supporter right now')
            return
        elif isinstance(actor_object.data, bpy.types.Light):
            actor_object.data.color = properties['color']
