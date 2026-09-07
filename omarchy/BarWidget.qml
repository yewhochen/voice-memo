import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

BarWidget {
  id: root
  moduleName: "yewho.voice-note"

  readonly property bool opened: panelLoader.item ? panelLoader.item.opened === true : false
  readonly property bool recording: panelLoader.item ? panelLoader.item.recording === true : false
  readonly property bool popoutSwitchClosing: panelLoader.item ? panelLoader.item.popoutSwitchClosing === true : false
  readonly property real openPanelIndicatorWidth: button.width

  function injectPanel() {
    var target = panelLoader.item
    if (!target) return
    target.bar = root.bar
    target.settings = root.settings
    target.anchorItem = button
    target.hostWidget = root
  }
  function open() { if (panelLoader.item) panelLoader.item.open() }
  function close() { if (panelLoader.item) panelLoader.item.close() }
  function closeForPopoutSwitch() { if (panelLoader.item) panelLoader.item.closeForPopoutSwitch() }
  function togglePanel() { if (panelLoader.item) panelLoader.item.toggle() }
  function toggleRecording() {
    if (!panelLoader.item) return
    panelLoader.item.toggleRecording()
    panelLoader.item.open()
  }

  onBarChanged: injectPanel()
  onSettingsChanged: injectPanel()
  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  Loader {
    id: panelLoader
    active: true
    source: Qt.resolvedUrl("Panel.qml")
    visible: false
    onLoaded: { root.injectPanel(); Qt.callLater(root.injectPanel) }
  }

  IpcHandler {
    target: "yewho.voice-note"
    function toggleRecording(): void { root.toggleRecording() }
    function open(): void { root.open() }
    function status(): string {
      var p = panelLoader.item
      return JSON.stringify(p ? {opened:p.opened, recording:p.recording, preparing:p.preparing, finalizing:p.finalizing, level:p.liveLevel, savedPath:p.savedPath, error:p.errorText, format:p.selectedFormat, source:p.selectedSource, otherVisible:p.hasSaved, elapsedMs:p.elapsedMs, buttonText:p.recordButtonText, historyVisible:p.historyOpen, historyCount:p.historyRows.length, historyPaths:p.historyRows.map(function(row) { return row.path }), copiedUri:p.copiedUri} : {error:"panel not loaded"})
    }
    function showHistory(): void { if (panelLoader.item) panelLoader.item.showHistory() }
    function openFolder(): void { if (panelLoader.item) panelLoader.item.openFolder() }
    function close(): void { root.close() }
    function toggle(): void { root.togglePanel() }
  }

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: root.recording ? "󰑋" : "󰍬"
    tooltipText: root.recording ? "Stop and save voice note" : "Record voice note"
    foreground: root.recording ? Color.accent : root.bar.foreground
    onPressed: function(mouseButton) {
      if (mouseButton === Qt.LeftButton) root.togglePanel()
    }
  }
}
