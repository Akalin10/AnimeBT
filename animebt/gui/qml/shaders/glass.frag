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
    float highlight;
    float compact;
    float dim;
    float panel;
    vec2 readingRange;
    vec2 controlSize;
    vec2 viewportSize;
    vec4 tintColor;
    vec4 upperRect;
} glass;

vec4 behind(vec2 uv)
{
    vec4 color = texture(backdrop, uv);
    color.rgb *= 1.0 - glass.dim;
    if (glass.upperRect.z > 0.0) {
        vec2 local = (uv - glass.upperRect.xy) / glass.upperRect.zw;
        if (all(greaterThanEqual(local, vec2(0.0))) && all(lessThanEqual(local, vec2(1.0)))) {
            vec4 upper = texture(upperBackdrop, uv);
            color = upper + color * (1.0 - upper.a);
        }
    }
    return color;
}

void main()
{
    vec2 halfSize = glass.controlSize * 0.5;
    vec2 p = (localUV - 0.5) * glass.controlSize;
    float radius = clamp(glass.corner, 0.0, min(halfSize.x, halfSize.y));
    vec2 q = abs(p) - halfSize + radius;
    vec2 outer = max(q, 0.0);
    float d = length(outer) + min(max(q.x, q.y), 0.0) - radius;
    float mask = 1.0 - smoothstep(-0.75, 0.5, d);
    vec2 axis = q.x > q.y ? vec2(1.0, 0.0) : vec2(0.0, 1.0);
    vec2 normal = sign(p) * (length(outer) > 0.001 ? normalize(outer) : axis);

    float bevel = clamp(radius * 0.78, 5.0, 23.0);
    float rim = pow(clamp(1.0 + d / bevel, 0.0, 1.0), 1.6);
    vec2 px = 1.0 / max(glass.viewportSize, vec2(1.0));
    vec2 uv = sceneUV - normal * px * rim * glass.refraction;
    float protectedCenter = glass.panel * smoothstep(8.0, 28.0, -d);
    vec2 blur = px * (glass.blurRadius + 2.0 * protectedCenter);
    vec4 sampleColor = behind(uv);
    if (glass.compact < 0.5) {
        sampleColor = sampleColor * 0.40
            + (behind(uv + vec2(blur.x, 0.0)) + behind(uv - vec2(blur.x, 0.0))
               + behind(uv + vec2(0.0, blur.y)) + behind(uv - vec2(0.0, blur.y))) * 0.15;
    } else {
        sampleColor = (sampleColor + behind(uv + 0.55 * blur)) * 0.5;
    }
    vec3 rgb = sampleColor.rgb / max(0.001, sampleColor.a);
    rgb = mix(rgb, clamp(rgb, glass.readingRange.x, glass.readingRange.y), protectedCenter);
    float tint = mix(glass.tintAmount, 1.0, 0.42 * protectedCenter);
    rgb = mix(rgb, glass.tintColor.rgb / max(0.001, glass.tintColor.a), tint);
    float specular = rim * (0.035 + 0.19 * max(0.0, dot(normal, vec2(-0.6, -0.8))));
    float edge = smoothstep(-2.0, -0.5, d) * mask;
    rgb = mix(rgb, vec3(1.0), clamp((specular + 0.11 * edge) * glass.highlight, 0.0, 1.0));
    rgb = mix(clamp(rgb, glass.readingRange.x, glass.readingRange.y), rgb, edge);

    float alpha = mask * glass.qt_Opacity;
    fragColor = vec4(rgb * alpha, alpha);
}
