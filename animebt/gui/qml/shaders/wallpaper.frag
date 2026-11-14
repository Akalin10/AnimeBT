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
    float fit;
    float shadeOpacity;
    vec4 qt_SubRect_coverTexture;
} poster;

void main()
{
    float frameAspect = poster.frameSize.x / poster.frameSize.y;
    float imageAspect = poster.imageSize.x / poster.imageSize.y;
    vec2 ratios = vec2(frameAspect / imageAspect, imageAspect / frameAspect);
    vec2 crop = poster.fit > 0.5 ? max(vec2(1.0), ratios) : min(vec2(1.0), ratios);
    vec2 centered = qt_TexCoord0 - 0.5;
    vec2 uv = centered * crop + 0.5;
    float inside = step(0.0, uv.x) * step(uv.x, 1.0) * step(0.0, uv.y) * step(uv.y, 1.0);
    uv = poster.qt_SubRect_coverTexture.xy + uv * poster.qt_SubRect_coverTexture.zw;

    vec2 halfSize = poster.frameSize * 0.5;
    float radius = min(poster.corner, min(halfSize.x, halfSize.y));
    vec2 edge = abs(centered * poster.frameSize) - halfSize + radius;
    float distance = length(max(edge, 0.0)) + min(max(edge.x, edge.y), 0.0) - radius;
    float antialias = max(0.001, fwidth(distance) * 0.5);
    float mask = 1.0 - smoothstep(-antialias, antialias, distance);
    vec4 pixel = texture(coverTexture, uv);
    // Black-over-wallpaper composition; retain alpha and never affect UI pixels.
    pixel.rgb *= 1.0 - clamp(poster.shadeOpacity, 0.0, 0.6);
    fragColor = pixel * (inside * mask * poster.qt_Opacity);
}
