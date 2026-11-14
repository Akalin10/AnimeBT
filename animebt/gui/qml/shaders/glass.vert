#version 440

layout(location = 0) in vec4 qt_Vertex;
layout(location = 1) in vec2 qt_MultiTexCoord0;
layout(location = 0) out vec2 localUV;
layout(location = 1) out vec2 sceneUV;

layout(std140, binding = 0) uniform GlassUniforms {
    mat4 qt_Matrix;
    float qt_Opacity;
    float corner;
    float tintAmount;
    float blurRadius;
    float refraction;
    float compact;
    float dim;
    float panel;
    float material;
    float highlight;
    float opticalStrength;
    float plateRim;
    vec2 readingRange;
    vec2 controlSize;
    vec2 viewportSize;
    vec4 tintColor;
    vec4 upperRect;
} glass;

void main()
{
    gl_Position = glass.qt_Matrix * qt_Vertex;
    localUV = qt_MultiTexCoord0;
    sceneUV = gl_Position.xy / gl_Position.w * vec2(0.5, -0.5) + 0.5;
}
