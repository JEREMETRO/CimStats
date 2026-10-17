"""Retained, parameterized map geometry on the viewport's OpenGL context.

The scene contains world coordinates and symbolic stroke parameters. Navigation
only changes view uniforms; neither a screen path nor a raster preview is built.
Closed lane contours retain the nonzero winding rule through a stencil pass.
"""
from __future__ import annotations

import math
import numpy as np
from shiboken6 import VoidPtr
from PySide6.QtGui import QOpenGLContext
from PySide6.QtOpenGL import (QOpenGLBuffer, QOpenGLShader, QOpenGLShaderProgram,
                              QOpenGLTexture, QOpenGLVertexArrayObject)
from map_gpu_visibility import cull_commands as _cull_commands


VERTEX_SHADER = r'''#version 330
in vec2 position;
in vec2 extrusion;
in vec4 coefficients;
in vec4 meta;
in vec4 tangents;
uniform sampler2D materials;
uniform int materialTextureWidth;
uniform vec2 center;
uniform vec2 viewport;
uniform float zoom;
uniform int connectionRank;
uniform int shellPass;
out vec4 colorA;
out vec4 colorB;
out float gradientFraction;
out vec2 circlePoint;
out vec4 joinTangents;
out float arc;
flat out int role;
flat out vec2 dash;

vec4 material(int row) {
    int index = int(meta.x + .5) * 10 + row;
    return texelFetch(materials, ivec2(index % materialTextureWidth,
                                     index / materialTextureWidth), 0);
}
float roadWidth(vec4 p) {
    float transition = clamp((zoom - .10) / .35, 0., 1.);
    float width = mix(p.x, p.y, transition);
    if (zoom > .45) width = p.y * min(2.2, sqrt(zoom / .45));
    if (p.z > 0. && p.w < 5.5) {
        float blend = clamp((zoom - .10) / .15, 0., 1.);
        blend = blend * blend * (3. - 2. * blend);
        width = mix(width, p.z * zoom, blend);
    }
    return width;
}
float roadCasing(vec4 p) {
    float detail = zoom / (zoom + .25);
    return p.w < 2.5 ? .25 + 1.35 * detail : .65 + .95 * detail;
}
float routeWidth() {
    float d = zoom / (zoom + .75);
    return 1.4 + 4.6*d + 2.2*log2(1. + zoom) - .55*exp(-pow(zoom/.18, 2.));
}
void main() {
    vec4 source = material(0), target = material(1);
    vec4 settings = material(7), sizes = material(8), flags = material(9);
    int mode = int(settings.x + .5);
    if (shellPass >= 0 && (mode == 0 || mode == 2 || mode == 8)) mode += shellPass;
    role = int(meta.z + .5);
    float sourceWidth = roadWidth(source), targetWidth = roadWidth(target);
    float laneCasing = zoom < .15 ? .2 : .45;
    float width = sourceWidth;
    if (mode == 1) width += flags.y == 1. ? roadCasing(source) : min(roadCasing(source), 1.2);
    if (mode == 4) width = settings.y > 0. ? settings.y : routeWidth();
    if (mode == 5) width = settings.y > 0. ? settings.y : 2.;
    if (mode == 7) width = zoom < .15 ? .45 : .7;
    if (mode == 8 || mode == 9) {
        width = max(.5, min(sourceWidth / max(2., sizes.z), targetWidth / max(2., sizes.w)));
        if (mode == 9) width += laneCasing;
    }
    float displacement;
    if (role == 0)
        displacement = dot(coefficients, vec4(sourceWidth, targetWidth, zoom,
                                               mode == 3 ? laneCasing : 0.));
    else displacement = width * coefficients.x;
    vec2 offset = extrusion * displacement;
    if (role == 4) offset = extrusion * 64.;
    if (role == 5) offset = vec2(0.);
    vec2 screenPoint = (position - center) * zoom + offset + viewport * .5;
    bool hidden = zoom < settings.z || zoom >= settings.w;
    if (connectionRank >= 0 && role != 4 && (mode == 2 || mode == 3 || mode == 8 || mode == 9)) {
        int actualRank = int((sourceWidth <= targetWidth ? source.w : target.w) + .5);
        hidden = hidden || actualRank != connectionRank;
    }
    if (mode == 6 || mode == 7) hidden = hidden || sizes.y * zoom * zoom < .8;
    if ((mode == 0 || mode == 1) && source.w < 2.5 && zoom < .15)
        hidden = hidden || sizes.x * zoom < 1.5;
    if ((mode == 8 || mode == 9) && zoom < .15)
        hidden = hidden || sizes.x * zoom < 1.5;
    gl_Position = hidden ? vec4(2.,2.,2.,1.) :
        vec4(screenPoint.x / viewport.x * 2. - 1., 1. - screenPoint.y / viewport.y * 2., 0., 1.);
    colorA = material(2); colorB = material(3);
    bool shell = mode == 1 || mode == 3 || mode == 9;
    bool chooseSource = sourceWidth <= targetWidth;
    if (shell) {
        colorA = chooseSource ? material(4) : material(5);
        colorB = colorA;
    }
    vec4 gradient = material(6);
    float norm2 = dot(gradient.zw, gradient.zw);
    if ((mode == 2 || mode == 8) && norm2 == 0.) {
        colorA = chooseSource ? material(2) : material(3);
        colorB = colorA;
    }
    gradientFraction = norm2 > 0. ? dot(position + offset / zoom - gradient.xy, gradient.zw) / norm2 : 0.;
    circlePoint = extrusion;
    joinTangents = tangents;
    arc = meta.y * zoom;
    dash = flags.zw;
    if (shellPass >= 0 && (mode == 0 || mode == 2 || mode == 8)) dash = vec2(0.);
}
'''

FRAGMENT_SHADER = r'''#version 330
in vec4 colorA;
in vec4 colorB;
in float gradientFraction;
in vec2 circlePoint;
in vec4 joinTangents;
in float arc;
flat in int role;
flat in vec2 dash;
out vec4 fragment;
void main() {
    float coverage = 1.;
    if (role == 2 || role == 3) {
        float distance = length(circlePoint);
        float feather = max(fwidth(distance), .00001);
        coverage = 1. - smoothstep(1. - feather*.5, 1. + feather*.5, distance);
        if (coverage <= 0.) discard;
        if (role == 3 && dash.x > 0.) {
            // Flat dash caps: only the exterior round join is added to the
            // two adjoining segment rectangles, never a round dash end.
            if (dot(circlePoint, joinTangents.xy) < 0. ||
                dot(circlePoint, joinTangents.zw) > 0.) discard;
        }
    }
    if (dash.x > 0. && mod(arc, dash.x + dash.y) >= dash.x) discard;
    fragment = mix(colorA, colorB, clamp(gradientFraction, 0., 1.));
    fragment.a *= coverage;
}
'''


class GpuMapRenderer:
    """Context-owned immutable buffers plus one small set of view uniforms."""
    def __init__(self):
        self.scene = None
        self.vertex_buffer = QOpenGLBuffer(QOpenGLBuffer.Type.VertexBuffer)
        self.index_buffer = QOpenGLBuffer(QOpenGLBuffer.Type.IndexBuffer)
        self.vertex_array = QOpenGLVertexArrayObject()
        self.texture = None
        self.program = None
        self.uploaded_bytes = 0
        self._texture_width = 1024
        self._rank_zoom = None
        self._submitter = None
        self._routes_renderer = None
        self.direct_upload = True

    def initialize(self):
        program = QOpenGLShaderProgram()
        for kind, source in ((QOpenGLShader.ShaderTypeBit.Vertex, VERTEX_SHADER),
                             (QOpenGLShader.ShaderTypeBit.Fragment, FRAGMENT_SHADER)):
            if not program.addShaderFromSourceCode(kind, source):
                raise RuntimeError(program.log())
        for index, name in enumerate(('position','extrusion','coefficients','meta','tangents')):
            program.bindAttributeLocation(name,index)
        if not program.link():
            raise RuntimeError(program.log())
        if (not self.vertex_buffer.create() or not self.index_buffer.create()
                or not self.vertex_array.create()):
            raise RuntimeError('Cannot allocate retained map vertex buffers')
        self.program = program
        self._uniforms={name:program.uniformLocation(name) for name in
                        ('materials','materialTextureWidth','center','viewport','zoom','connectionRank','shellPass')}
        from map_gpu_submit import load_submitter
        self._submitter=load_submitter(QOpenGLContext.currentContext())

    def upload(self, scene):
        if self.scene is scene:
            return
        if self.program is None:
            self.initialize()
        vertices = np.asarray(scene.vertices,dtype=np.float32)
        if vertices.ndim != 2 or vertices.shape[1] != 16:
            raise ValueError('Map vertices require sixteen float attributes')
        materials = np.asarray(scene.materials,dtype=np.float32)
        if materials.ndim != 2 or materials.shape[1] != 40:
            raise ValueError('Map materials require forty float attributes')
        count = max(1, math.ceil(materials.size / (self._texture_width*4)))
        pixels = np.zeros((count,self._texture_width,4),dtype=np.float32)
        pixels.reshape(-1)[:materials.size] = materials.reshape(-1)
        texture = QOpenGLTexture(QOpenGLTexture.Target.Target2D)
        texture.setSize(self._texture_width,count)
        texture.setFormat(QOpenGLTexture.TextureFormat.RGBA32F)
        texture.setMinificationFilter(QOpenGLTexture.Filter.Nearest)
        texture.setMagnificationFilter(QOpenGLTexture.Filter.Nearest)
        texture.setWrapMode(QOpenGLTexture.WrapMode.ClampToEdge)
        texture.allocateStorage(QOpenGLTexture.PixelFormat.RGBA,QOpenGLTexture.PixelType.Float32)
        texture.setData(QOpenGLTexture.PixelFormat.RGBA,QOpenGLTexture.PixelType.Float32,
                        VoidPtr(pixels))
        self.vertex_buffer.bind()
        self.direct_upload &= _allocate_buffer(self.vertex_buffer,vertices)
        self.vertex_buffer.release()
        self.vertex_array.bind()
        self.index_buffer.bind()
        indices=np.asarray(scene.indices,dtype=np.uint32)
        self.direct_upload &= _allocate_buffer(self.index_buffer,indices)
        self.vertex_array.release()
        self.index_buffer.release()
        if self.texture is not None:
            self.texture.destroy()
        self.texture=texture
        self.scene=scene
        self._rank_zoom=None
        commands=scene.commands
        self._commands=commands
        self._screen_margin=max(40.,float(materials[:,29].max(initial=0))*.5+2.)
        self._bounds=np.asarray([c.bounds for c in commands],dtype=float).reshape(-1,4)
        self._minimum=np.asarray([c.min_zoom for c in commands],dtype=np.float32)
        self._maximum=np.asarray([c.max_zoom for c in commands],dtype=np.float32)
        self._command_rank=np.asarray([c.connection_rank for c in commands],dtype=int)
        self._rank_material=np.asarray([max(0,c.rank_material) for c in commands],dtype=int)
        parameters=np.ascontiguousarray(materials[:,:8])
        unique,inverse=np.unique(parameters.view('V32').ravel(),return_inverse=True)
        self._rank_parameters=unique.view(np.float32).reshape(-1,8).astype(float)
        self._rank_inverse=inverse
        self._draw_offsets={offset:VoidPtr(int(offset)*4) for c in commands
                            for offset in (c.start,c.cover_start)}
        self._draw_table=_draw_command_table(commands,len(indices))
        self._prepare_ordering()
        self.uploaded_bytes += vertices.nbytes + indices.nbytes + pixels.nbytes

    def _prepare_ordering(self):
        """Compile array lookups once; navigation never walks saved path lists."""
        commands=getattr(self,'_commands',self.scene.commands)
        blocks=[];tile_groups=[];members=[];groups={}
        block=-1;previous=None
        for index,command in enumerate(commands):
            if command.connection_rank>=0:
                material_index=(command.rank_material if command.rank_material>=0 else
                                int(self.scene.vertices[self.scene.indices[command.start],8]))
                material=self.scene.materials[material_index]
                shell=(command.shell_pass==1 if command.shell_pass>=0 else int(material[28]) in (1,3,9))
                phase=(int(material[37]),shell,command.connection_rank)
                kind=('connection',phase)
            else:
                material_index=0;kind=('ordinary',)
            if kind!=previous:
                block+=1;previous=kind
            blocks.append(block)
            if command.connection_rank<0:
                tile_groups.append(-1)
                continue
            key=(block,command.owner_tile)
            if key not in groups:groups[key]=len(groups)
            tile_groups.append(groups[key])
            for item in command.connection_members:
                order,box,span=item[:3]
                mid=item[3] if len(item)>3 else material_index
                members.append((index,order,*box,span,mid))
        self._blocks=np.asarray(blocks,dtype=np.int64)
        self._tile_groups=np.asarray(tile_groups,dtype=np.int64)
        self._tile_count=len(groups)
        data=np.asarray(members,dtype=float).reshape(-1,8)
        self._member_command=data[:,0].astype(np.int64)
        self._member_order=data[:,1].astype(np.int64)
        self._member_bounds=np.ascontiguousarray(data[:,2:6])
        self._member_span=data[:,6]
        self._member_material=data[:,7].astype(np.int64)

    def _ranks(self,zoom):
        if self._rank_zoom!=zoom:
            parameters=self._rank_parameters
            source=_road_widths(parameters[:,:4],zoom)
            target=_road_widths(parameters[:,4:8],zoom)
            ranks=np.where(source<=target,parameters[:,3],parameters[:,7]).astype(int)
            self._material_ranks=ranks[self._rank_inverse]
            # CPU doubles and shader float/FMA arithmetic may disagree at a
            # width crossover. Keep both candidate passes in this narrow band;
            # the shader alone makes the authoritative visible-rank decision.
            tolerance=64*np.finfo(np.float32).eps*(1+abs(source)+abs(target)+
                abs(parameters[:,2]*zoom)+abs(parameters[:,6]*zoom))
            alternatives=(1<<parameters[:,3].astype(int))|(1<<parameters[:,7].astype(int))
            masks=np.where(abs(source-target)<=tolerance,alternatives,1<<ranks)
            self._material_rank_masks=masks[self._rank_inverse]
            self._rank_zoom=zoom
        return self._material_ranks

    def _visible_indices(self,zoom,bounds):
        zoom=float(np.float32(zoom))
        boxes=self._bounds
        mask=(self._minimum<=zoom)&(zoom<self._maximum)
        mask&=(boxes[:,0]<=bounds[2])&(boxes[:,2]>=bounds[0])
        mask&=(boxes[:,1]<=bounds[3])&(boxes[:,3]>=bounds[1])
        commands=getattr(self,'_commands',self.scene.commands)
        ordinary=self._command_rank<0
        first=np.full(len(commands),np.iinfo(np.int64).max,dtype=np.int64)
        first[ordinary]=np.flatnonzero(ordinary)
        member_boxes=self._member_bounds
        visible=(member_boxes[:,0]<=bounds[2])&(member_boxes[:,2]>=bounds[0])
        visible&=(member_boxes[:,1]<=bounds[3])&(member_boxes[:,3]>=bounds[1])
        if len(self.scene.materials):
            self._ranks(zoom)
            actual=self._material_rank_masks[self._member_material]
            visible&=(actual&(1<<self._command_rank[self._member_command]))!=0
        if zoom<.15:
            span=self._member_span*zoom
            visible&=span+32*np.finfo(np.float32).eps*(1+abs(span))>=1.5
        np.minimum.at(first,self._member_command[visible],self._member_order[visible])
        mask&=ordinary|(first!=np.iinfo(np.int64).max)
        tile_first=np.full(self._tile_count,np.iinfo(np.int64).max,dtype=np.int64)
        connection=np.flatnonzero(~ordinary)
        np.minimum.at(tile_first,self._tile_groups[connection],first[connection])
        tiles=np.zeros(len(commands),dtype=np.int64)
        tiles[connection]=tile_first[self._tile_groups[connection]]
        selected=np.flatnonzero(mask)
        order=np.lexsort((selected,first[selected],tiles[selected],self._blocks[selected]))
        return selected[order]

    def _visible_commands(self,zoom,bounds):
        commands=getattr(self,'_commands',self.scene.commands)
        return (commands[index] for index in self._visible_indices(zoom,bounds))

    def paint(self, scene, center, zoom, width, height, ratio, *, clear=True):
        if hasattr(scene,'base'):
            self.paint(scene.base,center,zoom,width,height,ratio,clear=clear)
            if scene.routes.commands:
                if self._routes_renderer is None:
                    self._routes_renderer=GpuMapRenderer()
                routes=self._routes_renderer;before=routes.uploaded_bytes
                routes.paint(scene.routes,center,zoom,width,height,ratio,clear=False)
                self.uploaded_bytes+=routes.uploaded_bytes-before
            return
        self.upload(scene)
        gl=QOpenGLContext.currentContext().functions()
        gl.glViewport(0,0,round(width*ratio),round(height*ratio))
        gl.glDisable(0x0B71)  # DEPTH_TEST
        gl.glDisable(0x0B44)  # CULL_FACE: signed fans need both faces
        gl.glDisable(0x0C11)  # SCISSOR_TEST
        gl.glEnable(0x0BE2)   # BLEND
        # The map's background is opaque. Preserve destination alpha=1 at
        # coverage edges, so Qt's premultiplied widget compositor sees the
        # same pixels as the native FBO (and never uninitialized subpixels).
        gl.glBlendEquationSeparate(0x8006,0x8006)  # FUNC_ADD
        gl.glBlendFuncSeparate(0x0302,0x0303,1,0x0303)
        gl.glStencilMask(0xff)
        gl.glClearStencil(0)
        gl.glColorMask(1,1,1,1)
        gl.glClearColor(241/255,244/255,246/255,1.)
        gl.glClear((0x4000 if clear else 0) | 0x0400)  # COLOR | STENCIL
        self.vertex_array.bind()
        self.vertex_buffer.bind()
        self.index_buffer.bind()
        self.program.bind()
        for location,offset,size in ((0,0,2),(1,8,2),(2,16,4),(3,32,4),(4,48,4)):
            self.program.enableAttributeArray(location)
            self.program.setAttributeBuffer(location,0x1406,offset,size,64)
        self.texture.bind(0)
        locations=self._uniforms
        gl.glUniform1i(locations['materials'],0)
        gl.glUniform1i(locations['materialTextureWidth'],self._texture_width)
        gl.glUniform2f(locations['center'],float(center[0]),float(-center[1]))
        gl.glUniform2f(locations['viewport'],float(width),float(height))
        gl.glUniform1f(locations['zoom'],float(zoom))
        cx,cy=center[0],-center[1]
        margin=self._screen_margin/zoom
        bounds=(cx-width/(2*zoom)-margin,cy-height/(2*zoom)-margin,
                cx+width/(2*zoom)+margin,cy+height/(2*zoom)+margin)
        stencil=False
        connection_rank=None
        shell_pass=None
        draw=gl.glDrawElements;enable=gl.glEnable;disable=gl.glDisable
        stencil_func=gl.glStencilFunc;stencil_separate=gl.glStencilOpSeparate
        color_mask=gl.glColorMask;stencil_op=gl.glStencilOp
        rank_uniform=gl.glUniform1i;rank_location=locations['connectionRank']
        shell_location=locations['shellPass']
        offsets=self._draw_offsets
        visible=self._visible_indices(zoom,bounds)
        if self._submitter is not None:
            self._submitter(np.ascontiguousarray(self._draw_table[visible]),rank_location,shell_location)
        for index in (() if self._submitter is not None else visible):
            command=self._commands[index]
            if shell_pass!=command.shell_pass:
                shell_pass=command.shell_pass
                rank_uniform(shell_location,int(shell_pass))
            if connection_rank!=command.connection_rank:
                connection_rank=command.connection_rank
                rank_uniform(rank_location,int(connection_rank))
            if command.mode=='winding':
                if not stencil:
                    enable(0x0B90);stencil=True
                stencil_func(0x0207,0,0xff)  # ALWAYS
                stencil_separate(0x0404,0x1E00,0x1E00,0x8507)  # FRONT INCR_WRAP
                stencil_separate(0x0405,0x1E00,0x1E00,0x8508)  # BACK DECR_WRAP
                color_mask(0,0,0,0)
                draw(0x0004,command.count,0x1405,offsets[command.start])
                color_mask(1,1,1,1)
                stencil_func(0x0205,0,0xff)  # NOTEQUAL
                # The bounded cover paints every nonzero sample then clears
                # those samples for the next independently ordered path run.
                stencil_op(0x1E00,0x1E00,0)
                draw(0x0004,command.cover_count,0x1405,offsets[command.cover_start])
            else:
                if stencil:
                    disable(0x0B90);stencil=False
                draw(0x0004,command.count,0x1405,offsets[command.start])
        gl.glDisable(0x0B90)
        gl.glColorMask(1,1,1,1)
        self.texture.release()
        for location in range(5):
            self.program.disableAttributeArray(location)
        self.program.release()
        self.vertex_buffer.release()
        self.vertex_array.release()
        self.index_buffer.release()

    def destroy(self):
        """Call only while the owning context is current."""
        if self._routes_renderer is not None:
            self._routes_renderer.destroy();self._routes_renderer=None
        if self.texture is not None:
            self.texture.destroy();self.texture=None
        self.vertex_buffer.destroy()
        self.index_buffer.destroy()
        self.vertex_array.destroy()
        self.program=None
        self.scene=None
        self._submitter=None


def _road_widths(parameters,zoom):
    """Vectorized shared width equation, used only for small draw-order keys."""
    p=np.asarray(parameters,dtype=np.float64)
    transition=max(0.,min(1.,(zoom-.10)/.35))
    width=p[:,0]+(p[:,1]-p[:,0])*transition
    if zoom>.45:
        width=p[:,1]*min(2.2,math.sqrt(zoom/.45))
    blend=max(0.,min(1.,(zoom-.10)/.15))
    blend=blend*blend*(3-2*blend)
    return np.where((p[:,2]>0)&(p[:,3]<5.5),width*(1-blend)+p[:,2]*zoom*blend,width)


def _draw_command_table(commands,index_count):
    table=np.asarray([(c.start,c.count,int(c.mode=='winding'),c.cover_start,
                       c.cover_count,c.connection_rank,c.shell_pass) for c in commands],dtype=np.int64).reshape(-1,7)
    if any(c.mode not in ('triangles','winding') for c in commands):
        raise ValueError('Unsupported retained map primitive')
    for start,count in ((table[:,0],table[:,1]),(table[:,3],table[:,4])):
        if np.any(start<0) or np.any(count<0) or np.any(count>2147483647) or np.any(start>index_count-count):
            raise ValueError('Retained map command exceeds its index buffer')
    if np.any((table[:,5]<-1)|(table[:,5]>6)):
        raise ValueError('Invalid retained connection rank')
    if np.any((table[:,6]<-1)|(table[:,6]>1)):
        raise ValueError('Invalid retained shell pass')
    return table


def _allocate_buffer(buffer,array):
    """Upload retained contiguous arrays without a second whole-city byte copy."""
    if not array.flags.c_contiguous:raise ValueError('GPU upload must be contiguous')
    if array.nbytes>2147483647:raise ValueError('GPU buffer exceeds Qt allocation capacity')
    if not array.nbytes:
        buffer.allocate(0);return True
    try:
        buffer.allocate(VoidPtr(int(array.ctypes.data)),array.nbytes)
        return True
    except TypeError:
        buffer.allocate(array.tobytes(),array.nbytes)
        return False


