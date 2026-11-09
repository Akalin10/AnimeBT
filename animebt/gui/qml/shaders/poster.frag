#version 440

layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;
layout(binding = 1) uniform sampler2D coverTexture;

layout(std140, binding = 0) uniform PosterUniforms {
    mat4 qt_Matrix;
    float qt_Opacity;
    vec2 frameSize;
    vec2 imageSize;
    float corner;
    vec4 qt_SubRect_coverTexture;
} poster;

void main()
{
    float frameAspect = poster.frameSize.x / poster.frameSize.y;
    float imageAspect = poster.imageSize.x / poster.imageSize.y;
    vec2 crop = min(vec2(1.0), vec2(frameAspect / imageAspect, imageAspect / frameAspect));
    vec2 centered = qt_TexCoord0 - 0.5;
    vec2 uv = centered * crop + 0.5;
    uv = poster.qt_SubRect_coverTexture.xy + uv * poster.qt_SubRect_coverTexture.zw;

    vec2 halfSize = poster.frameSize * 0.5;
    float radius = min(poster.corner, min(halfSize.x, halfSize.y));
    vec2 edge = abs(centered * poster.frameSize) - halfSize + radius;
    float distance = length(max(edge, 0.0)) + min(max(edge.x, edge.y), 0.0) - radius;
    float antialias = max(0.001, fwidth(distance) * 0.5);
    float mask = 1.0 - smoothstep(-antialias, antialias, distance);
    fragColor = texture(coverTexture, uv) * (mask * poster.qt_Opacity);
}
