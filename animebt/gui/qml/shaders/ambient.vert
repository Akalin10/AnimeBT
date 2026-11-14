#version 440
layout(location=0) in vec4 qt_Vertex;
layout(location=1) in vec2 qt_MultiTexCoord0;
layout(location=0) out vec2 uv;
layout(std140,binding=0) uniform U {mat4 qt_Matrix;float qt_Opacity;float dark;float corner;float strength;vec2 size;vec4 topColor;vec4 bottomColor;} u;
void main(){uv=qt_MultiTexCoord0;gl_Position=u.qt_Matrix*qt_Vertex;}
