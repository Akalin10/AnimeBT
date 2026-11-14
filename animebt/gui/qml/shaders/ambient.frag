#version 440
layout(location=0) in vec2 uv;
layout(location=0) out vec4 fragColor;
layout(std140,binding=0) uniform U {mat4 qt_Matrix;float qt_Opacity;float dark;float corner;float strength;vec2 size;vec4 topColor;vec4 bottomColor;} u;
void main(){
 vec2 p=uv*u.size;vec2 h=u.size*.5;float r=min(u.corner,min(h.x,h.y));
 vec2 q=abs(p-h)-h+r;float d=length(max(q,0.0))+min(max(q.x,q.y),0.0)-r;
 float a=(1.-smoothstep(-.8,.8,d))*u.qt_Opacity;
 vec3 base=mix(u.topColor.rgb,u.bottomColor.rgb,smoothstep(0.,1.,uv.y));
 vec2 v=uv-vec2(.04,-.35);
 float arc=length(v/vec2(1.10,1.50))-1.;
 vec2 w=uv-vec2(.81,.46);w=mat2(.90,.435,-.435,.90)*w;
 float second=length(w/vec2(.40,.73))-1.;
 float band=exp(-arc*arc*60.);float glow=exp(-arc*arc*7.);
 float rim=exp(-pow((arc+.022)*24.,2.));
 float ridge=exp(-pow((arc+.016)*62.,2.));
 float other=exp(-second*second*46.);
 vec3 pink=u.dark>.5?vec3(.36,.13,.27):vec3(.07,.015,.055);
 vec3 mauve=u.dark>.5?vec3(.12,.105,.15):vec3(.01,.018,.055);
 float gate=smoothstep(.12,.82,uv.y);
 base*=1.-.13*exp(-pow((arc+.085)*13.,2.))*gate;
 base+=u.strength*vec3(.20,.09,.17)*ridge*gate;
 base+=u.strength*(pink*(.20*glow+.30*band+.11*rim)*gate+mauve*other*.28);
 // Broad pink pools provide soft lighting, while the curved ridge gives the
 // optical sampler real spatial structure. This is application artwork, not
 // a claimed desktop capture or a substitute for the refraction shader.
 base+=u.strength*vec3(.07,.018,.045)*exp(-dot((uv-vec2(.17,.23))*vec2(3.,4.),(uv-vec2(.17,.23))*vec2(3.,4.)));
 base+=u.strength*vec3(.06,.018,.05)*exp(-dot((uv-vec2(.86,.86))*3.,(uv-vec2(.86,.86))*3.));
 fragColor=vec4(clamp(base,0.,1.)*a,a);
}
