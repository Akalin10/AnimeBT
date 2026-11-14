#version 440
layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;
layout(binding = 1) uniform sampler2D sourceTexture;
layout(std140, binding = 0) uniform BlurUniforms {
    mat4 qt_Matrix;
    float qt_Opacity;
    vec2 direction;
    float radius;
} blur;
void main() {
    vec4 color = vec4(0.0);
    float sum = 0.0;
    for (int i = -18; i <= 18; ++i) {
        float t = float(i) / 6.0;
        float weight = exp(-0.5 * t * t);
        vec2 uv = clamp(qt_TexCoord0 + blur.direction * (t * blur.radius), vec2(0.0), vec2(1.0));
        color += texture(sourceTexture, uv) * weight;
        sum += weight;
    }
    fragColor = color * (blur.qt_Opacity / sum);
}
