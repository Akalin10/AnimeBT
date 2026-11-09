import QtQuick
import QtQuick.Shapes

Shape {
    id: glyph
    property string path: ""
    property color ink: "#34405b"
    implicitWidth: 20
    implicitHeight: 20
    preferredRendererType: Shape.CurveRenderer

    ShapePath {
        fillColor: "transparent"
        strokeColor: glyph.ink
        strokeWidth: 1.55
        capStyle: ShapePath.RoundCap
        joinStyle: ShapePath.RoundJoin
        PathSvg { path: glyph.path }
    }
}
