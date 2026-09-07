import QtQuick
import QtQuick.Controls as Controls
import qs.Commons
import qs.Ui

Controls.ComboBox {
  id: root
  property color foreground: Color.foreground
  background: Rectangle {
    color: Util.alpha(root.foreground, root.hovered ? 0.12 : 0.04)
    Behavior on color { ColorAnimation { duration: 120 } }
    radius: Style.space(4)
    border.width: 1
    border.color: Util.alpha(root.foreground, root.enabled ? 0.6 : 0.3)
  }
  delegate: Controls.ItemDelegate {
    required property int index
    width: root.width
    text: root.model[index].label
    highlighted: root.highlightedIndex === index
    contentItem: Text {
      text: parent.text
      color: root.foreground
      font: root.font
      elide: Text.ElideRight
      verticalAlignment: Text.AlignVCenter
    }
    background: Rectangle {
      color: Util.alpha(root.foreground, parent.hovered || parent.highlighted ? 0.14 : 0.02)
      Behavior on color { ColorAnimation { duration: 120 } }
    }
  }
  textRole: "label"
  valueRole: "value"
  implicitHeight: Style.spacing.controlHeight
  font.family: Style.font.family
  font.pixelSize: Style.font.body
  contentItem: Text {
    textFormat: Text.PlainText
    text: root.displayText
    color: root.foreground
    font: root.font
    verticalAlignment: Text.AlignVCenter
    leftPadding: Style.space(10)
    elide: Text.ElideRight
  }
}
