/* Ordered OpenGL submission, stroke tessellation and lane-strip certificates.
 * No allocation, runtime library, global GL state ownership or worker thread.
 * Only submission uses function pointers from the caller's current GL context;
 * the geometry helpers operate solely on caller-owned CPU buffers.
 */
#include <stdint.h>
#include <stddef.h>
#ifdef _WIN32
#define EXPORT __declspec(dllexport)
#define GLAPI __stdcall
#else
#define EXPORT __attribute__((visibility("default")))
#define GLAPI
#endif
typedef void (GLAPI *Draw)(unsigned,int,unsigned,const void *);
typedef void (GLAPI *Switch)(unsigned);
typedef void (GLAPI *StencilFunc)(unsigned,int,unsigned);
typedef void (GLAPI *StencilSeparate)(unsigned,unsigned,unsigned,unsigned);
typedef void (GLAPI *ColorMask)(unsigned char,unsigned char,unsigned char,unsigned char);
typedef void (GLAPI *StencilOp)(unsigned,unsigned,unsigned);
typedef void (GLAPI *Uniform)(int,int);

#ifdef _WIN32
/* No CRT initialization or thread notifications are needed. */
int __stdcall _DllMainCRTStartup(void *module,unsigned reason,void *reserved) {
    (void)module;(void)reason;(void)reserved;return 1;
}
#endif

EXPORT int map_submit_abi(void) { return 2; }

/* Seven signed int64 fields: index start/count, winding flag, cover start/count,
 * connection rank and shell pass. Caller checks its own index-buffer ranges.
 */
EXPORT int map_submit(const int64_t *rows, size_t count, const uintptr_t *functions,
                      int rank_location,int shell_location) {
    if ((!rows && count) || !functions || rank_location < 0 || shell_location < 0) return -1;
    for (size_t i=0;i<8;i++) if (!functions[i]) return -1;
    for (size_t i=0;i<count;i++) {
        const int64_t *r=rows+i*7;
        if (r[0]<0 || r[1]<0 || r[1]>2147483647 || r[2]<0 || r[2]>1 ||
            r[3]<0 || r[4]<0 || r[4]>2147483647 || r[5]<-1 || r[5]>6 ||
            (uint64_t)r[0]>UINTPTR_MAX/4 || (uint64_t)r[3]>UINTPTR_MAX/4 ||
            r[6]<-1 || r[6]>1) return -2;
    }
    Draw draw=(Draw)functions[0];Switch enable=(Switch)functions[1],disable=(Switch)functions[2];
    StencilFunc stencil_func=(StencilFunc)functions[3];
    StencilSeparate separate=(StencilSeparate)functions[4];
    ColorMask color=(ColorMask)functions[5];StencilOp stencil_op=(StencilOp)functions[6];
    Uniform uniform=(Uniform)functions[7];
    int stencil=0,rank=-99,shell=-99;
    for (size_t i=0;i<count;i++) {
        const int64_t *r=rows+i*7;
        if (rank!=(int)r[5]) { rank=(int)r[5];uniform(rank_location,rank); }
        if (shell!=(int)r[6]) { shell=(int)r[6];uniform(shell_location,shell); }
        if (r[2]) {
            if (!stencil) { enable(0x0B90);stencil=1; }
            stencil_func(0x0207,0,0xff);
            separate(0x0404,0x1E00,0x1E00,0x8507);
            separate(0x0405,0x1E00,0x1E00,0x8508);
            color(0,0,0,0);
            draw(4,(int)r[1],0x1405,(const void *)((uintptr_t)r[0]*4));
            color(1,1,1,1);
            stencil_func(0x0205,0,0xff);stencil_op(0x1E00,0x1E00,0);
            draw(4,(int)r[4],0x1405,(const void *)((uintptr_t)r[3]*4));
        } else {
            if (stencil) { disable(0x0B90);stencil=0; }
            draw(4,(int)r[1],0x1405,(const void *)((uintptr_t)r[0]*4));
        }
    }
    if (stencil) disable(0x0B90);
    return 0;
}

/* CPU-only stroke tessellation. This ABI is independent of GL submission.
 * All memory belongs to Python. Inputs are immutable during each call and no
 * pointer is retained; count/fill return before any external state is touched.
 */
#include <float.h>

EXPORT int map_stroke_abi(void) { return 1; }

typedef struct {
    size_t active, first, last, rows, indices;
    double total;
    int closed;
} StrokePlan;

static double stroke_hypot(double x,double y) {
    double a=x<0?-x:x,b=y<0?-y:y;
    double large=a>b?a:b,small=a>b?b:a;
    if (large==0) return 0;
    double ratio=small/large;
    return large*__builtin_sqrt(1+ratio*ratio);
}

static int stroke_plan(const double *points,size_t count,int material,
                       int round_caps,int dashed,StrokePlan *plan) {
    if ((!points && count) || count>SIZE_MAX/(2*sizeof(double)) || material<0 ||
        (round_caps!=0 && round_caps!=1) || (dashed!=0 && dashed!=1)) return -1;
    plan->active=0;plan->first=0;plan->last=0;plan->total=0;plan->closed=0;
    plan->rows=0;plan->indices=0;
    for (size_t i=0;i<count*2;i++) {
        double value=points[i];
        if (!__builtin_isfinite(value) || value>FLT_MAX || value<-FLT_MAX) return -2;
    }
    for (size_t i=0;i+1<count;i++) {
        double length=stroke_hypot(points[(i+1)*2]-points[i*2],
                                   points[(i+1)*2+1]-points[i*2+1]);
        if (!__builtin_isfinite(length)) return -2;
        plan->total+=length;
        if (!__builtin_isfinite(plan->total) || plan->total>FLT_MAX) return -2;
        if (length>0) {
            if (!plan->active) plan->first=i;
            plan->active++;plan->last=i;
        }
    }
    if (!plan->active) return 0;
    plan->closed=points[plan->first*2]==points[(plan->last+1)*2] &&
                 points[plan->first*2+1]==points[(plan->last+1)*2+1];
    if (plan->active>(SIZE_MAX-2)/2) return -3;
    size_t quads=plan->active+(plan->closed?plan->active:plan->active-1);
    if (round_caps && !dashed && !plan->closed) quads+=2;
    if (quads>UINT32_MAX/4 || quads>SIZE_MAX/(4*16*sizeof(float)) ||
        quads>SIZE_MAX/(6*sizeof(uint32_t))) return -3;
    plan->rows=quads*4;plan->indices=quads*6;
    return 0;
}

EXPORT int map_stroke_count(const double *points,size_t count,int material,
                            int round_caps,int dashed,size_t *rows,size_t *indices) {
    if (!rows || !indices) return -1;
    StrokePlan plan;
    int result=stroke_plan(points,count,material,round_caps,dashed,&plan);
    if (result) return result;
    *rows=plan.rows;*indices=plan.indices;
    return 0;
}

static void stroke_row(float *row,double x,double y,double ex,double ey,
                       float coefficient,float material,double arc,float role,
                       double in_x,double in_y,double out_x,double out_y) {
    row[0]=(float)x;row[1]=(float)y;row[2]=(float)ex;row[3]=(float)ey;
    row[4]=coefficient;row[5]=0;row[6]=0;row[7]=0;
    row[8]=material;row[9]=(float)arc;row[10]=role;row[11]=0;
    row[12]=(float)in_x;row[13]=(float)in_y;
    row[14]=(float)out_x;row[15]=(float)out_y;
}

static void stroke_indices(uint32_t *indices,size_t quad) {
    uint32_t base=(uint32_t)(quad*4);
    uint32_t *output=indices+quad*6;
    output[0]=base;output[1]=base+1;output[2]=base+2;
    output[3]=base;output[4]=base+2;output[5]=base+3;
}

static void stroke_disk(float *rows,uint32_t *indices,size_t quad,
                        double x,double y,float material,double arc,float role,
                        double in_x,double in_y,double out_x,double out_y) {
    for (size_t corner=0;corner<4;corner++) {
        double ex=corner==0 || corner==3?-1:1;
        double ey=corner<2?-1:1;
        stroke_row(rows+(quad*4+corner)*16,x,y,ex,ey,.5f,material,arc,role,
                   in_x,in_y,out_x,out_y);
    }
    stroke_indices(indices,quad);
}

EXPORT int map_stroke_fill(const double *points,size_t count,int material,
                           int round_caps,int dashed,float *rows,size_t row_capacity,
                           uint32_t *indices,size_t index_capacity) {
    StrokePlan plan;
    int result=stroke_plan(points,count,material,round_caps,dashed,&plan);
    if (result) return result;
    if (plan.rows>row_capacity || plan.indices>index_capacity ||
        (!rows && plan.rows) || (!indices && plan.indices)) return -4;
    if (!plan.active) return 0;
    double last_dx=points[(plan.last+1)*2]-points[plan.last*2];
    double last_dy=points[(plan.last+1)*2+1]-points[plan.last*2+1];
    double last_length=stroke_hypot(last_dx,last_dy);
    double last_tx=last_dx/last_length,last_ty=last_dy/last_length;
    double arc=0,previous_tx=0,previous_ty=0;
    size_t segment=0,join=plan.active,previous=0;
    for (size_t i=0;i+1<count;i++) {
        double dx=points[(i+1)*2]-points[i*2],dy=points[(i+1)*2+1]-points[i*2+1];
        double length=stroke_hypot(dx,dy);
        double before=arc;arc+=length;
        if (length==0) continue;
        double tx=dx/length,ty=dy/length;
        for (size_t corner=0;corner<4;corner++) {
            size_t point=corner<2?i:i+1;
            float coefficient=corner==0 || corner==3?-.5f:.5f;
            stroke_row(rows+(segment*4+corner)*16,points[point*2],points[point*2+1],
                       -ty,tx,coefficient,(float)material,corner<2?before:arc,1,0,0,0,0);
        }
        stroke_indices(indices,segment);
        if (!segment && plan.closed) {
            stroke_disk(rows,indices,join++,points[plan.first*2],points[plan.first*2+1],
                        (float)material,0,3,last_tx,last_ty,tx,ty);
        } else if (segment) {
            stroke_disk(rows,indices,join++,points[(previous+1)*2],points[(previous+1)*2+1],
                        (float)material,before,3,previous_tx,previous_ty,tx,ty);
        }
        previous=i;previous_tx=tx;previous_ty=ty;segment++;
    }
    if (round_caps && !dashed && !plan.closed) {
        stroke_disk(rows,indices,join++,points[plan.first*2],points[plan.first*2+1],
                    (float)material,0,2,0,0,0,0);
        stroke_disk(rows,indices,join,points[(plan.last+1)*2],points[(plan.last+1)*2+1],
                    (float)material,plan.total,2,0,0,0,0);
    }
    return 0;
}

/* Sufficient lane-strip certificate. No triangulation or geometry mutation.
 * All arithmetic enclosures are rounded outwards in binary64. The additional
 * 64*eps32 envelope is the shader-evaluation bound, not an acceptance epsilon.
 * Scratch belongs to Python: 32 doubles per vertex, at most 64 vertices.
 */
typedef struct { double lo,hi; } StripInterval;
typedef struct { StripInterval x,y; } StripVector;
typedef struct {
    StripInterval base[2],coefficient[2][3],position[2],box[2];
    double fixed[2],error[2];
    double original_magnitude[2][2];
} StripVertex;
_Static_assert(sizeof(StripVertex)==32*sizeof(double),"strip scratch ABI");

static double strip_abs(double x) { return x<0?-x:x; }
static double strip_min(double a,double b) { return a<b?a:b; }
static double strip_max(double a,double b) { return a>b?a:b; }
static double strip_next(double x,int up) {
    union { double d;uint64_t bits; } value;
    value.d=x;
    if (x==0) {value.bits=up?UINT64_C(1):UINT64_C(0x8000000000000001);return value.d;}
    /* Inputs here are finite; all intermediates are bounded by the domain. */
    if ((x>0)==up) value.bits++;else value.bits--;
    return value.d;
}
static StripInterval strip_out(double lo,double hi) {
    StripInterval result={strip_next(lo,0),strip_next(hi,1)};return result;
}
static StripInterval strip_exact(double x) { StripInterval result={x,x};return result; }
static StripInterval strip_add(StripInterval a,StripInterval b) {
    return strip_out(a.lo+b.lo,a.hi+b.hi);
}
static StripInterval strip_sub(StripInterval a,StripInterval b) {
    return strip_out(a.lo-b.hi,a.hi-b.lo);
}
static StripInterval strip_mul(StripInterval a,StripInterval b) {
    double p=a.lo*b.lo,q=a.lo*b.hi,r=a.hi*b.lo,s=a.hi*b.hi;
    return strip_out(strip_min(strip_min(p,q),strip_min(r,s)),
                     strip_max(strip_max(p,q),strip_max(r,s)));
}
/* Only a strictly positive constant denominator is used. */
static StripInterval strip_div(StripInterval a,double b) {
    return strip_out(a.lo/b,a.hi/b);
}
static double strip_magnitude(StripInterval a) { return strip_max(strip_abs(a.lo),strip_abs(a.hi)); }
static StripInterval strip_blend(double zoom) {
    StripInterval t=strip_div(strip_sub(strip_exact(zoom),strip_exact(.10)),.15);
    t.lo=strip_max(0,strip_min(1,t.lo));t.hi=strip_max(0,strip_min(1,t.hi));
    return strip_mul(strip_mul(t,t),strip_sub(strip_exact(3),strip_mul(strip_exact(2),t)));
}
static StripInterval strip_width(const float *p,double lo,double hi) {
    if (lo>=.25) return strip_exact(p[2]);
    StripInterval difference=strip_sub(strip_exact(p[1]),strip_exact(p[0]));
    StripInterval a=strip_sub(strip_exact(p[0]),strip_div(strip_mul(difference,strip_exact(.10)),.35));
    StripInterval b=strip_div(difference,.35);
    StripInterval first=strip_add(strip_div(a,lo),b),last=strip_add(strip_div(a,hi),b);
    StripInterval symbolic={strip_min(first.lo,last.lo),strip_max(first.hi,last.hi)};
    StripInterval start=strip_blend(lo),end=strip_blend(hi);
    StripInterval blend={start.lo,end.hi};
    return strip_add(strip_mul(symbolic,strip_sub(strip_exact(1),blend)),
                     strip_mul(strip_exact(p[2]),blend));
}
static double strip_width_magnitude(const float *p,double lo,StripInterval width) {
    /* roadWidth mixes symbolic and physical widths before division by zoom.
     * Its intermediate terms can cancel even when the final interval is tiny
     * (including blend==1 on the physical branch). Budget their original
     * absolute amplitudes, not just the net mathematical width. */
    double overview=strip_next(strip_abs(p[0])/lo,1);
    double detail=strip_next(strip_next(2.2*strip_abs(p[1]),1)/lo,1);
    double magnitude=strip_next(overview+detail,1);
    magnitude=strip_next(magnitude+strip_abs(p[2]),1);
    return strip_next(magnitude+strip_magnitude(width),1);
}

static StripInterval strip_linear(StripInterval base,const StripInterval *coeff,
                                  const StripInterval *range,double error,int shell) {
    for (int j=0;j<3;j++)
        base=strip_add(base,strip_mul(j==2&&!shell?strip_exact(0):coeff[j],range[j]));
    return strip_out(base.lo-error,base.hi+error);
}
static StripVector strip_difference(const StripVertex *v,size_t a,size_t b,
                                     const StripInterval *range,int shell) {
    StripVector result;
    for (int axis=0;axis<2;axis++) {
        /* Subtract full vector coefficients before evaluating the common
         * width interval; never multiply normal-difference by scalar-difference. */
        StripInterval coefficients[3];
        for (int j=0;j<3;j++) coefficients[j]=strip_sub(v[a].coefficient[axis][j],v[b].coefficient[axis][j]);
        double error=strip_next(v[a].error[axis]+v[b].error[axis],1);
        StripInterval bound=strip_linear(strip_sub(v[a].base[axis],v[b].base[axis]),coefficients,range,error,shell);
        if (axis==0) result.x=bound;else result.y=bound;
    }
    return result;
}
static StripInterval strip_cross(StripVector a,StripVector b) {
    return strip_sub(strip_mul(a.x,b.y),strip_mul(a.y,b.x));
}
static int strip_same_side(StripInterval a,StripInterval b) {
    return (a.lo>0&&b.lo>0)||(a.hi<0&&b.hi<0);
}
static int strip_triangle(const StripVertex *v,size_t a,size_t b,size_t c,
                           const StripInterval *range,int shell,int *orientation) {
    StripInterval cross=strip_cross(strip_difference(v,b,a,range,shell),strip_difference(v,c,a,range,shell));
    int sign=cross.lo>0?1:cross.hi<0?-1:0;
    if (!sign || (*orientation && sign!=*orientation)) return 0;
    *orientation=sign;return 1;
}
static int strip_band(StripVertex *v,size_t count,const StripInterval *range,
                       const double *width_magnitude,int shell) {
    for (size_t i=0;i<count;i++) for (int axis=0;axis<2;axis++) {
        double magnitude=v[i].fixed[axis];
        for (int j=0;j<3;j++) {
            /* Equal widths share one geometric interval, but the shader
             * still multiplies and adds both original coefficient terms. */
            double coefficient=j<2?v[i].original_magnitude[axis][j]:
                               !shell?0:strip_magnitude(v[i].coefficient[axis][j]);
            double term=strip_next(coefficient*width_magnitude[j],1);
            magnitude=strip_next(magnitude+term,1);
        }
        v[i].error[axis]=strip_next(0x1p-17*strip_next(1+magnitude,1),1);
        v[i].position[axis]=strip_linear(v[i].base[axis],v[i].coefficient[axis],range,v[i].error[axis],shell);
    }
    int orientation=0;
    for (size_t i=0;i+1<count/2;i++) {
        size_t right=count-1-i;
        if (!strip_triangle(v,i,i+1,right-1,range,shell,&orientation) ||
            !strip_triangle(v,i,right-1,right,range,shell,&orientation)) return 0;
    }
    for (size_t i=0;i<count;i++) {
        size_t end=(i+1)%count;
        for (int axis=0;axis<2;axis++) {
            v[i].box[axis].lo=strip_min(v[i].position[axis].lo,v[end].position[axis].lo);
            v[i].box[axis].hi=strip_max(v[i].position[axis].hi,v[end].position[axis].hi);
        }
    }
    for (size_t a=0;a<count;a++) for (size_t b=a+2;b<count;b++) {
        if (a==0 && b==count-1) continue;
        if (v[a].box[0].hi<v[b].box[0].lo || v[b].box[0].hi<v[a].box[0].lo ||
            v[a].box[1].hi<v[b].box[1].lo || v[b].box[1].hi<v[a].box[1].lo) continue;
        size_t ae=(a+1)%count,be=(b+1)%count;
        StripVector ab=strip_difference(v,ae,a,range,shell);
        if (strip_same_side(strip_cross(ab,strip_difference(v,b,a,range,shell)),
                            strip_cross(ab,strip_difference(v,be,a,range,shell)))) continue;
        StripVector cd=strip_difference(v,be,b,range,shell);
        if (!strip_same_side(strip_cross(cd,strip_difference(v,a,b,range,shell)),
                             strip_cross(cd,strip_difference(v,ae,b,range,shell)))) return 0;
    }
    for (size_t i=0;i<count;i++) {
        StripVector incoming=strip_difference(v,i,(i+count-1)%count,range,shell);
        StripVector outgoing=strip_difference(v,(i+1)%count,i,range,shell);
        StripInterval turn=strip_cross(incoming,outgoing);
        StripInterval dot=strip_add(strip_mul(incoming.x,outgoing.x),strip_mul(incoming.y,outgoing.y));
        if (!(turn.lo>0 || turn.hi<0 || dot.lo>0)) return 0;
    }
    return 1;
}

EXPORT int map_strip_abi(void) { return 1; }

EXPORT int map_strip_pair(const float *rows,size_t count,const float *material,
                          void *scratch,size_t scratch_bytes) {
    if (!rows || !material || !scratch || count<4 || count>64 || count%2 ||
        (uintptr_t)rows%_Alignof(float) || (uintptr_t)material%_Alignof(float) ||
        (uintptr_t)scratch%_Alignof(StripVertex) || scratch_bytes<count*sizeof(StripVertex)) return 0;
    uintptr_t rs=(uintptr_t)rows,ms=(uintptr_t)material,ss=(uintptr_t)scratch;
    size_t rb=count*16*sizeof(float),mb=40*sizeof(float),sb=count*sizeof(StripVertex);
    if (rs>UINTPTR_MAX-rb || ms>UINTPTR_MAX-mb || ss>UINTPTR_MAX-sb ||
        (ss<rs+rb && rs<ss+sb) || (ss<ms+mb && ms<ss+sb)) return 0;
    for (size_t i=0;i<count*16;i++) if (!__builtin_isfinite(rows[i])) return 0;
    /* This conservative domain also excludes overflow of float32 shader
     * intermediates, even with very large normals or width coefficients. */
    for (size_t i=0;i<count;i++) for (int j=0;j<8;j++) if (strip_abs(rows[i*16+j])>1e8) return 0;
    for (int j=0;j<8;j++) if (!__builtin_isfinite(material[j]) || strip_abs(material[j])>1e8) return 0;
    if (!(material[2]>0 && material[6]>0 && material[3]<5.5f && material[7]<5.5f)) return 0;
    int equal=1;
    for (int j=0;j<4;j++) if (material[j]!=material[j+4]) equal=0;
    StripVertex *v=(StripVertex*)scratch;
    for (size_t i=0;i<count;i++) for (int axis=0;axis<2;axis++) {
        const float *r=rows+i*16;
        StripInterval normal=strip_exact(r[2+axis]);
        StripInterval offset=strip_mul(normal,strip_exact(r[6]));
        v[i].base[axis]=strip_add(strip_exact(r[axis]),offset);
        v[i].fixed[axis]=strip_next(strip_abs(r[axis])+strip_magnitude(offset),1);
        v[i].coefficient[axis][0]=strip_mul(normal,strip_exact(r[4]));
        v[i].coefficient[axis][1]=strip_mul(normal,strip_exact(r[5]));
        v[i].coefficient[axis][2]=strip_mul(normal,strip_exact(r[7]));
        for (int j=0;j<2;j++)
            v[i].original_magnitude[axis][j]=strip_magnitude(v[i].coefficient[axis][j]);
        if (equal) {
            v[i].coefficient[axis][0]=strip_add(v[i].coefficient[axis][0],v[i].coefficient[axis][1]);
            v[i].coefficient[axis][1]=strip_exact(0);
        }
    }
    /* Same binary64 endpoints as np.linspace(.15,.25,9), plus the physical
     * constant-width domain. All endpoints belong to both neighbouring bands. */
    static const double endpoints[10]={.15,.1625,.175,.1875,.2,.2125,.225,.2375,.25,100};
    for (int band=0;band<9;band++) {
        double lo=endpoints[band],hi=endpoints[band+1];
        StripInterval range[3]={strip_width(material,lo,hi),strip_width(material+4,lo,hi),
                                strip_out(.45/hi,.45/lo)};
        double width_magnitude[3]={strip_width_magnitude(material,lo,range[0]),
                                   strip_width_magnitude(material+4,lo,range[1]),strip_magnitude(range[2])};
        if (!strip_band(v,count,range,width_magnitude,0) ||
            !strip_band(v,count,range,width_magnitude,1)) return 0;
    }
    return 1;
}
