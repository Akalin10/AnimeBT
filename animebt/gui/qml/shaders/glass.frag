#version 440
layout(location = 0) in vec2 localUV;
layout(location = 1) in vec2 sceneUV;
layout(location = 0) out vec4 fragColor;
layout(binding = 1) uniform sampler2D backdrop;
layout(binding = 2) uniform sampler2D upperBackdrop;
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
vec4 behind(vec2 uv, float lod)
{
    uv = clamp(uv, vec2(0.0), vec2(1.0));
    vec4 color = textureLod(backdrop, uv, lod);
    if (glass.upperRect.z > 0.0) {
        vec2 local = (uv - glass.upperRect.xy) / glass.upperRect.zw;
        if (all(greaterThanEqual(local, vec2(0.0))) && all(lessThanEqual(local, vec2(1.0)))) {
            vec4 upper = textureLod(upperBackdrop, uv, lod);
            color = upper + color * (1.0 - upper.a);
        }
    }
    return color;
}
void main()
{
    vec2 halfSize = max(glass.controlSize * 0.5, vec2(0.5));
    vec2 p = (localUV - 0.5) * glass.controlSize;
    float radius = clamp(glass.corner, 0.5, min(halfSize.x, halfSize.y));
    vec2 q = abs(p) - halfSize + radius;
    vec2 outside = max(q, 0.0);
    float d = length(outside) + min(max(q.x, q.y), 0.0) - radius;
    float aa = max(0.45, fwidth(d) * 0.65);
    float mask = 1.0 - smoothstep(-aa, aa, d);
    if (mask <= 0.0) {
        fragColor = vec4(0.0);
        return;
    }
    vec2 axis = q.x > q.y ? vec2(1.0, 0.0) : vec2(0.0, 1.0);
    vec2 outward = sign(p) * (length(outside) > 0.001 ? normalize(outside) : axis);
    float bevel = clamp(radius * 0.72, 5.0, 22.0);
    float rim = smoothstep(-bevel, 0.0, d);
    vec3 normal = vec3(0.0, 0.0, 1.0);
    vec2 bend = vec2(0.0);
    if (rim > 0.001) {
        float slope = 2.8 * pow(rim, 1.35);
        normal = normalize(vec3(outward * slope, 1.0));
        vec3 ray = refract(vec3(0.0, 0.0, -1.0), normal, 1.0 / 1.48);
        bend = ray.xy / max(0.15, abs(ray.z));
    }
    vec2 centerLens = (p / halfSize) * (1.0 - rim) * 0.16;
    vec2 px = 1.0 / max(glass.viewportSize, vec2(1.0));
    vec2 uv = sceneUV + (bend + centerLens) * glass.refraction * px;
    // Shared source mip pyramid performs the low-pass, not a tinted overlay.
    // Fractional LOD plus a normalized 3x3 Gaussian avoids sharp duplicate glyphs
    // from sparse wide-offset sampling, with fixed work per visible surface.
    float sigma = max(0.0, glass.blurRadius);
    float textureScale = min(1.0, min(1600.0 / max(1.0, glass.viewportSize.x), 1000.0 / max(1.0, glass.viewportSize.y)));
    float lod = max(0.0, log2(max(1.0, sigma * textureScale * 0.8)));
    vec2 blur = px * sigma * 0.75;
    vec4 sampleColor = behind(uv, lod);
    if (sigma > 0.01) {
        sampleColor *= 0.25;
        sampleColor += (behind(uv + vec2(blur.x, 0.0), lod) + behind(uv - vec2(blur.x, 0.0), lod)
                     + behind(uv + vec2(0.0, blur.y), lod) + behind(uv - vec2(0.0, blur.y), lod)) * 0.125;
        sampleColor += (behind(uv + blur, lod) + behind(uv - blur, lod)
                     + behind(uv + vec2(blur.x, -blur.y), lod) + behind(uv + vec2(-blur.x, blur.y), lod)) * 0.0625;
    }
    // Captured textures are premultiplied. Transmit their full RGB and alpha;
    // no tint, reading plate, luminance remap or opaque fallback is composited.
    vec3 rgb = sampleColor.rgb;
    // Edge-only reflection work must not run for every interior pixel.
    if (rim > 0.001) {
        float fresnel = 0.04 + 0.96 * pow(1.0 - normal.z, 5.0);
        vec3 light = normalize(vec3(-0.48, -0.66, 0.75));
        vec3 halfway = normalize(light + vec3(0.0, 0.0, 1.0));
        float specular = pow(max(dot(normal, halfway), 0.0), 46.0);
        float facing = dot(outward, normalize(vec2(-0.48, -0.66)));
        float lip = exp(-pow((d + 0.85) / 0.85, 2.0));
        float inner = exp(-pow((d + 3.0) / 1.5, 2.0));
        float response = glass.opticalStrength * (1.0 + 0.35 * glass.highlight);
        rgb += sampleColor.a * response * (fresnel * rim * (0.08 + 0.20 * max(facing, 0.0))
               + specular * rim * 0.28 + lip * (0.022 + 0.075 * max(facing, 0.0)));
    }
    float coverage = mask * glass.qt_Opacity;
    fragColor = vec4(clamp(rgb, vec3(0.0), vec3(sampleColor.a)) * coverage,
                     sampleColor.a * coverage);
}
