#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Render the four classic trap images with Blender 4.3.

Run: blender --background --factory-startup --python scripts/render_classic_trap.py
The normal and released views share one model. Only the two moving parts rotate.
"""

import base64
import math
from pathlib import Path
from tempfile import TemporaryDirectory

import bpy
from mathutils import Quaternion, Vector

output = Path(__file__).resolve().parents[1] / "custom_components/mousetrap_manager/frontend/images"
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)


def material(name, color, metal=0, rough=0.38):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    node = mat.node_tree.nodes.get("Principled BSDF")
    node.inputs["Base Color"].default_value = (*color, 1)
    node.inputs["Metallic"].default_value = metal
    node.inputs["Roughness"].default_value = rough
    return mat


wood = material("Honey maple", (0.55, 0.26, 0.066))
nodes = wood.node_tree.nodes
links = wood.node_tree.links
coords = nodes.new("ShaderNodeTexCoord")
stretch = nodes.new("ShaderNodeVectorMath")
stretch.operation = "MULTIPLY"
stretch.inputs[1].default_value = (2, 47, 9)
noise = nodes.new("ShaderNodeTexNoise")
noise.inputs["Scale"].default_value = 1.9
noise.inputs["Detail"].default_value = 2.0
colors = nodes.new("ShaderNodeValToRGB")
colors.color_ramp.elements[0].position = 0.19
colors.color_ramp.elements[0].color = (0.38, 0.165, 0.048, 1)
colors.color_ramp.elements[1].position = 0.81
colors.color_ramp.elements[1].color = (0.68, 0.405, 0.168, 1)
links.new(coords.outputs["Generated"], stretch.inputs[0])
links.new(stretch.outputs["Vector"], noise.inputs["Vector"])
links.new(noise.outputs["Fac"], colors.inputs["Fac"])
links.new(colors.outputs["Color"], nodes.get("Principled BSDF").inputs["Base Color"])
gunmetal = material("Dark steel", (0.116, 0.144, 0.18), 0.72, 0.27)
steel = material("Brushed steel", (0.49, 0.54, 0.61), 0.74, 0.29)
gold = material("Brass", (0.77, 0.51, 0.15), 0.61, 0.28)


def round_box(name, center, size, bevel, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=center)
    obj = bpy.context.object
    obj.name = name
    obj.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    mod = obj.modifiers.new("Rounded corners", "BEVEL")
    mod.width = bevel
    mod.segments = 5
    obj.modifiers.new("Face normals", "WEIGHTED_NORMAL")
    return obj


def tube(name, points, radius, mat):
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = radius
    curve.bevel_resolution = 5
    curve.use_fill_caps = True
    spline = curve.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for p, co in zip(spline.points, points, strict=True):
        p.co = (*co, 1)
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    return obj


def cylinder(name, start, end, radius, mat=None):
    start, end = Vector(start), Vector(end)
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=48, radius=radius, depth=(end - start).length, location=(start + end) / 2
    )
    obj = bpy.context.object
    obj.name = name
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = (end - start).to_track_quat("Z", "Y")
    if mat:
        obj.data.materials.append(mat)
    for face in obj.data.polygons:
        face.use_smooth = len(face.vertices) == 4
    return obj


aim = Vector((0, 0, 0.24))
bpy.ops.object.camera_add(location=(-8, -10, 10))
camera = bpy.context.object
camera.rotation_euler = (aim - camera.location).to_track_quat("-Z", "Y").to_euler()
camera.data.type = "ORTHO"
camera.data.ortho_scale = 7.55
camera.location -= camera.rotation_euler.to_quaternion() @ Vector((0, 0.29, 0))
bpy.context.scene.camera = camera

# One physical model. Both views share source geometry.
round_box("Maple base", (0, 0, -0.135), (5.36, 2.50, 0.27), 0.13, wood)
cylinder("Axle", (0, -1.035, 0.23), (0, 1.035, 0.23), 0.082, steel)
for y in (-0.98, 0.98):
    round_box("Axle support", (0, y, 0.163), (0.29, 0.17, 0.342), 0.07, steel)
    cylinder("Axle head", (0, y - 0.106, 0.23), (0, y + 0.106, 0.23), 0.085, gunmetal)
spring = []
for k in range(401):
    t = k / 400
    spring.append((0.13 * math.cos(t * math.tau * 15), -0.78 + 1.56 * t, 0.23 + 0.13 * math.sin(t * math.tau * 15)))
tube("Coil", spring, 0.032, steel)
round_box("Trigger plate", (-1.16, 0, 0.058), (1.38, 0.54, 0.095), 0.042, gold)
round_box("Trigger hinge", (-0.45, 0, 0.08), (0.23, 0.50, 0.13), 0.03, gold)
hinge = Vector((2.31, 0, 0.55))
tip = Vector((-1.60, 0, 0.35))
tab_x = -1.28
hole_z = hinge.z + (tip.z - hinge.z) * (tab_x - hinge.x) / (tip.x - hinge.x)
tab = round_box("Pierced trigger tab", (tab_x, 0, 0.253), (0.085, 0.49, 0.495), 0.037, gold)
bpy.context.view_layer.objects.active = tab
bpy.ops.object.modifier_apply(modifier="Rounded corners")
bpy.ops.object.modifier_remove(modifier="Face normals")
cutter = cylinder("Hole cutter", (tab_x - 0.2, 0, hole_z), (tab_x + 0.2, 0, hole_z), 0.076)
bpy.context.view_layer.objects.active = tab
hole = tab.modifiers.new("Through hole", "BOOLEAN")
hole.object = cutter
hole.operation = "DIFFERENCE"
bpy.ops.object.modifier_apply(modifier=hole.name)
bpy.data.objects.remove(cutter, do_unlink=True)
tube(
    "Centered rear staple",
    [
        (hinge.x, -0.134, 0.01),
        (hinge.x, -0.134, 0.48),
        (hinge.x, -0.114, 0.547),
        (hinge.x, -0.075, 0.576),
        (hinge.x, 0.075, 0.576),
        (hinge.x, 0.114, 0.547),
        (hinge.x, 0.134, 0.48),
        (hinge.x, 0.134, 0.01),
    ],
    0.034,
    steel,
)

radius = 0.21
half_width = 0.945
length = 1.69
u = [(0, -half_width, 0)]
for k in range(13):
    angle = -math.pi / 2 + (math.pi / 2) * k / 12
    u.append((length - radius + radius * math.cos(angle), -half_width + radius + radius * math.sin(angle), 0))
for k in range(13):
    angle = (math.pi / 2) * k / 12
    u.append((length - radius + radius * math.cos(angle), half_width - radius + radius * math.sin(angle), 0))
u.append((0, half_width, 0))
strike = tube("Single strike bar", u, 0.063, gunmetal)
strike.location.z = 0.23
rod = tube("Straight retaining rod", [(0, 0, 0), tuple(tip - hinge)], 0.035, steel)
rod.location = hinge


def light(name, pos, power, size):
    bpy.ops.object.light_add(type="AREA", location=pos)
    obj = bpy.context.object
    obj.name = name
    obj.data.energy = power
    obj.data.shape = "DISK"
    obj.data.size = size
    obj.rotation_euler = (aim - obj.location).to_track_quat("-Z", "Y").to_euler()


light("Large overhead softbox", (0, -3, 11), 1700, 10)
light("Soft fill", (-6, 4, 7), 850, 8)
light("Metal highlights", (4, 7, 7), 1400, 6)
scene = bpy.context.scene
scene.world.color = (0.28, 0.28, 0.28)
scene.render.engine = "CYCLES"
scene.cycles.samples = 128
scene.cycles.use_denoising = False

scene.render.resolution_x = 720
scene.render.resolution_y = 360
scene.render.resolution_percentage = 100
scene.render.film_transparent = True
scene.render.image_settings.file_format = "WEBP"
scene.render.image_settings.color_mode = "RGBA"
scene.render.image_settings.quality = 85
scene.view_settings.view_transform = "AgX"
# The wood rests on the ground. Only its soft shadow is rendered into the alpha channel.
bpy.ops.mesh.primitive_plane_add(size=100, location=(0, 0, -0.278))
bpy.context.object.is_shadow_catcher = True

badge_marks = {
    "normal": ("Overvåking aktiv", "#246c47", "M-11 0l7 7 15-16"),
    "pending": ("Må kontrolleres", "#986000", "M-7-8a7 7 0 1 1 12 5C2-1 0 0 0 4m0 7v1"),
    "inspection": ("Tid for inspeksjon", "#986000", "M0-16 16 12h-32ZM0-6v8m0 5v1"),
    "unavailable": ("Utilgjengelig", "#495465", "M-9-9 9 9M-9 9 9-9"),
}


def render_asset(path):
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    return base64.b64encode(path.read_bytes()).decode("ascii")


def status_image(state, image):
    label, color, mark = badge_marks[state]
    muted = ' filter="url(#muted)" opacity=".5"' if state == "unavailable" else ""
    desaturation = '<filter id="muted"><feColorMatrix type="saturate" values="0"/></filter>\n' if muted else ""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 360 180" width="720" height="360">
  <title>Klassisk klappfelle – {label}</title>
{desaturation}  <image width="360" height="180" href="data:image/webp;base64,{image}"{muted}/>
  <g transform="translate(326 34)">
    <circle r="29" fill="white"/>
    <circle r="26" fill="{color}"/>
    <path d="{mark}" fill="none" stroke="white" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/>
  </g>
</svg>
"""


with TemporaryDirectory() as temporary:
    armed = render_asset(Path(temporary) / "armed.webp")
    strike.rotation_mode = rod.rotation_mode = "QUATERNION"
    strike.rotation_quaternion = Quaternion((0, 1, 0), math.pi)
    rod.rotation_quaternion = Quaternion((0, 0, 1), math.radians(31)) @ Quaternion((0, 1, 0), math.radians(-4))
    released = render_asset(Path(temporary) / "released.webp")

for state in badge_marks:
    (output / f"snap-{state}.svg").write_text(status_image(state, released if state == "pending" else armed))
