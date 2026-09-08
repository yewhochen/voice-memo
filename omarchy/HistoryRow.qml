import QtQuick
import QtQuick.Controls as Controls
import qs.Commons

Item {
  id: root
  required property string fileName
  required property string fileDate
  required property string fileUri
  property color foreground: "white"
  property string fontFamily: "sans-serif"
  property bool copied: false
  property bool confirmDelete: false
  signal copyRequested(string uri)
  signal playRequested(string uri)
  signal deleteRequested(string uri)
  implicitHeight: Style.space(58)

  HoverHandler {
    id: hover
    onHoveredChanged: if (!hovered) root.confirmDelete = false
  }
  Rectangle {
    anchors.fill: parent
    radius: Style.space(4)
    color: Util.alpha(root.foreground, hover.hovered ? 0.10 : 0.04)
    Behavior on color { ColorAnimation { duration: 120 } }
    border.width: 1
    border.color: Util.alpha(root.foreground, 0.25)
  }
  Text {
    anchors { left: parent.left; right: parent.right; top: parent.top; margins: Style.space(7) }
    textFormat: Text.PlainText
    text: root.fileName
    elide: Text.ElideMiddle
    color: root.foreground
    font.family: root.fontFamily
    font.pixelSize: Style.font.body
  }
  Text {
    opacity: actions.opacity > 0 ? 0 : 1
    Behavior on opacity { NumberAnimation { duration: 120 } }
    anchors { left: parent.left; bottom: parent.bottom; margins: Style.space(7) }
    text: root.fileDate
    color: Util.alpha(root.foreground, 0.65)
    font.family: root.fontFamily
    font.pixelSize: Style.font.caption
  }
  component Action: Controls.Button {
    id: button
    implicitHeight: Style.space(25)
    width: (actions.width - actions.spacing * 2) / 3
    contentItem: Text {
      text: button.text
      color: root.foreground
      font.family: root.fontFamily
      font.pixelSize: Style.font.body
      horizontalAlignment: Text.AlignHCenter
      verticalAlignment: Text.AlignVCenter
    }
    background: Rectangle {
      radius: Style.space(3)
      color: Util.alpha(root.foreground, button.hovered ? 0.18 : 0.04)
      Behavior on color { ColorAnimation { duration: 120 } }
    border.width: 1
      border.color: Util.alpha(root.foreground, 0.45)
    }
  }
  Row {
    id: actions
    opacity: hover.hovered || activeFocus ? 1 : 0
    visible: opacity > 0
    enabled: hover.hovered || activeFocus
    Behavior on opacity { NumberAnimation { duration: 120 } }
    anchors { left: parent.left; right: parent.right; bottom: parent.bottom; margins: Style.space(5) }
    spacing: Style.space(5)
    Action { text: "󰐊"; Accessible.name: "Play"; onClicked: root.playRequested(root.fileUri) }
    Action { text: root.copied ? "󰄬" : "󰆏"; Accessible.name: root.copied ? "Copied" : "Copy"; onClicked: root.copyRequested(root.fileUri) }
    Action {
      text: root.confirmDelete ? "󰄬" : "󰆴"
      Accessible.name: root.confirmDelete ? "Confirm move to Trash" : "Delete"
      onClicked: {
        if (!root.confirmDelete) root.confirmDelete = true
        else { root.confirmDelete = false; root.deleteRequested(root.fileUri) }
      }
    }
  }
}
