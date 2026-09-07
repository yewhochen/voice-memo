import QtQuick
import QtQuick.Controls as Controls
import Quickshell
import Quickshell.Io
import Quickshell.Services.Pipewire
import Quickshell.Wayland
import qs.Commons
import qs.Ui
import "Model.js" as Model

Panel {
  id: root
  moduleName: "yewho.voice-note"
  ipcTarget: "yewho.voice-note-panel"
  manageIpc: false

  property var anchorItem: null
  property var hostWidget: null
  readonly property var barIdentity: hostWidget || root
  component OutlinedButton: Controls.Button {
    id: control
    implicitHeight: Style.space(36)
    font.family: Style.font.family
    font.pixelSize: Style.font.body
    contentItem: Text {
      text: control.text
      font: control.font
      color: Util.alpha(Color.foreground, control.enabled ? 1 : 0.5)
      horizontalAlignment: Text.AlignHCenter
      verticalAlignment: Text.AlignVCenter
    }
    background: Rectangle {
      radius: Style.space(4)
      color: Util.alpha(Color.foreground, control.down ? 0.14 : (control.hovered ? 0.08 : 0.02))
      Behavior on color { ColorAnimation { duration: 120 } }
      border.width: 1
      border.color: Util.alpha(control.activeFocus ? Color.accent : Color.foreground, control.enabled ? 0.6 : 0.3)
    }
  }

  property bool sessionExitPending: false
  property bool settingsOpen: false
  property bool historyOpen: false
  property string copiedUri: ""
  property string copyPendingUri: ""
  property var historyRows: []
  property string historyError: ""
  property double recordingStartedAt: 0
  property double elapsedMs: 0
  readonly property string recordButtonText: finalizing ? "Saving…" : (recording ? Model.elapsedLabel(elapsedMs) : "Start")
  property bool recording: false
  property bool preparing: false
  property bool finalizing: false
  property bool stopRequested: false
  property string savedPath: ""
  property string errorText: ""
  readonly property bool busy: preparing || recording || finalizing
  property real liveLevel: 0
  property double clipDeadline: 0
  property bool clipping: false
  property var sourceRows: []
  property string currentOutput: ""
  readonly property string recordingFolder: Quickshell.env("HOME") + "/Music/Voice Notes"
  readonly property bool hasSaved: Model.showOther(savedPath, busy)
  readonly property string selectedFormat: Model.normalizeFormat(setting("format", "wav"))
  readonly property string selectedSource: String(setting("source", ""))
  readonly property var nodes: Pipewire.nodes ? Pipewire.nodes.values : []
  readonly property var defaultSource: Pipewire.defaultAudioSource
  readonly property var selectedNode: {
    if (selectedSource === "") return defaultSource
    for (var i = 0; i < nodes.length; i++) if (nodes[i] && String(nodes[i].name) === selectedSource) return nodes[i]
    return null
  }

  function timestamp() {
    var d = new Date()
    function pad(v) { return String(v).padStart(2, "0") }
    return d.getFullYear() + "-" + pad(d.getMonth()+1) + "-" + pad(d.getDate()) + "_" + pad(d.getHours()) + "-" + pad(d.getMinutes()) + "-" + pad(d.getSeconds())
  }
  function persistSettings(values) {
    var entry = { id: root.moduleName }
    for (var key in root.settings) if (key !== "id") entry[key] = root.settings[key]
    for (var changed in values) entry[changed] = values[changed]
    root.settings = entry
    if (root.hostWidget) root.hostWidget.settings = entry
    if (root.bar && root.bar.shell && typeof root.bar.shell.updateEntryInline === "function")
      root.bar.shell.updateEntryInline(root.moduleName, entry)
  }
  function selectedSourceAvailable() {
    if (selectedSource === "") return !!defaultSource
    for (var i = 0; i < sourceRows.length; i++) if (sourceRows[i].value === selectedSource) return true
    return false
  }
  function startRecording() {
    if (busy || recordProcess.running) return
    if (!selectedSourceAvailable()) { errorText = "Selected microphone is unavailable"; return }
    savedPath = ""
    errorText = ""
    liveLevel = 0
    preparing = true
    var base = recordingFolder
    currentOutput = base + "/Voice Note " + timestamp() + "-" + String(Date.now()) + "." + Model.extensionFor(selectedFormat)
    prepareProcess.command = ["mkdir", "-p", base]
    prepareProcess.running = true
  }
  function stopRecording() {
    if (!recording || finalizing) return
    stopRequested = true
    finalizing = true
    recordProcess.write("q\n")
    finalizeGuard.restart()
  }
  function toggleRecording() {
    if (preparing || finalizing) return
    recording ? stopRecording() : startRecording()
  }
  function open() { controller.show() }
  function close() { controller.hide() }
  function toggle() { opened ? close() : open() }
  function switchPanel(direction) {
    return root.bar && root.bar.switchPanelFrom ? root.bar.switchPanelFrom(root.barIdentity, direction) : false
  }
  function refreshSources() {
    if (!sourcesProcess.running) sourcesProcess.running = true
  }
  function helperPath() {
    var url = String(Qt.resolvedUrl("history.py"))
    return decodeURIComponent(url.replace(/^file:\/\//, ""))
  }
  function refreshHistory() {
    if (historyProcess.running) return
    historyError = ""
    historyProcess.command = ["python3", helperPath(), "--folder", recordingFolder,
                              "--current", busy ? currentOutput : ""]
    historyProcess.running = true
  }
  function showHistory() {
    settingsOpen = false
    historyOpen = true
    open()
    refreshHistory()
  }
  function toggleHistory() {
    if (historyOpen) historyOpen = false
    else showHistory()
  }
  property string trashPendingUri: ""
  function isHistoryFile(uri) {
    return historyRows.some(function(row) { return row.uri === uri })
        && !(busy && decodeURIComponent(String(uri).replace(/^file:\/\//, "")) === currentOutput)
  }
  function playFile(uri) {
    if (!isHistoryFile(uri) || playbackProcess.running) return
    playbackProcess.command = ["xdg-open", uri]
    playbackProcess.running = true
  }
  function deleteFile(uri) {
    if (!isHistoryFile(uri) || trashProcess.running) return
    trashPendingUri = uri
    trashProcess.command = ["gio", "trash", uri]
    trashProcess.running = true
  }
  Process {
    id: playbackProcess
    onExited: function(code) { if (code !== 0) root.errorText = "Could not open default player" }
  }
  Process {
    id: trashProcess
    onExited: function(code) {
      if (code !== 0) { root.errorText = "Could not move recording to Trash"; return }
      if (root.copiedUri === root.trashPendingUri) root.copiedUri = ""
      if (root.savedPath === decodeURIComponent(root.trashPendingUri.replace(/^file:\/\//, ""))) root.savedPath = ""
      root.refreshHistory()
    }
  }
  function copyFile(uri) {
    if (copyProcess.running || !String(uri).startsWith("file:///")) return
    copyPendingUri = uri
    copyProcess.command = ["wl-copy", "--type", "x-special/gnome-copied-files", "copy\n" + uri]
    copyProcess.running = true
  }
  Process {
    id: copyProcess
    onExited: function(code) {
      if (code === 0) root.copiedUri = root.copyPendingUri
      else root.errorText = "Could not copy file to clipboard"
    }
  }
  function openFolder() {
    if (!openFolderProcess.running) openFolderProcess.running = true
  }

  function resetSession() {
    if (busy) return
    savedPath = ""
    errorText = ""
    currentOutput = ""
    liveLevel = 0
    settingsOpen = false
    historyOpen = false
    copiedUri = ""
    elapsedMs = 0
    recordingStartedAt = 0
    sessionExitPending = false
  }
  function finishSession() {
    sessionExitPending = true
    if (recording) stopRecording()
    if (!busy) resetSession()
  }
  onOpenedChanged: {
    if (opened) refreshSources()
    else { clipDeadline = 0; clipping = false; finishSession() }
  }
  onBusyChanged: {
    // Defer until the completion handler has assigned savedPath/error.
    if (!busy && sessionExitPending) Qt.callLater(function() {
      if (!root.busy && root.sessionExitPending) root.resetSession()
    })
  }

  PwObjectTracker { objects: root.selectedNode ? [root.selectedNode] : [] }
  PwNodePeakMonitor {
    id: peakMonitor
    node: root.selectedNode
    enabled: root.opened && !!root.selectedNode
  }
  Timer {
    interval: 60
    repeat: true
    running: root.opened
    onTriggered: {
      var now = Date.now()
      root.clipDeadline = Model.clipUntil(peakMonitor.peak, now, root.clipDeadline)
      root.clipping = now < root.clipDeadline
      root.liveLevel = Math.max(root.liveLevel * 0.68, Math.max(0, Math.min(1, peakMonitor.peak)))
    }
  }

  Timer {
    interval: 100
    repeat: true
    running: root.recording
    onTriggered: root.elapsedMs = Math.max(0, Date.now() - root.recordingStartedAt)
  }

  Process {
    id: sourcesProcess
    command: ["pactl", "--format=json", "list", "sources"]
    stdout: StdioCollector { waitForEnd: true; onStreamFinished: root.sourceRows = Model.parseSources(text) }
  }
  Process {
    id: historyProcess
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        try { root.historyRows = JSON.parse(String(text || "[]")) }
        catch (e) { root.historyRows = []; root.historyError = "Could not read recording history" }
      }
    }
    onExited: function(code) {
      if (code !== 0) { root.historyRows = []; root.historyError = "Could not read recording history" }
    }
  }
  Process {
    id: openFolderProcess
    command: ["mkdir", "-p", root.recordingFolder]
    onExited: function(code) {
      if (code === 0) Quickshell.execDetached(["xdg-open", root.recordingFolder])
      else root.errorText = "Could not open Voice Notes folder"
    }
  }
  Process {
    id: prepareProcess
    onExited: function(code) {
      if (code !== 0) { root.preparing = false; root.errorText = "Could not create Voice Notes folder"; return }
      recordProcess.command = Model.recordCommand(root.selectedSource, root.selectedFormat, root.currentOutput)
      root.stopRequested = false
      recordProcess.running = true
    }
  }
  Process {
    id: recordProcess
    stdinEnabled: true
    onStarted: { root.recordingStartedAt = Date.now(); root.elapsedMs = 0; root.recording = true; root.preparing = false; if (root.sessionExitPending) root.stopRecording() }
    onExited: function(code) {
      root.preparing = false
      finalizeGuard.stop()
      root.recording = false
      root.liveLevel = 0
      if (root.stopRequested && code === 0 && root.currentOutput !== "") {
        verifyProcess.command = ["ffprobe", "-v", "error", "-show_entries", "format=duration,size", "-of", "default=noprint_wrappers=1", root.currentOutput]
        verifyProcess.running = true
      } else {
        root.finalizing = false
        if (code !== 0) root.errorText = "Recording failed (ffmpeg exit " + code + ")"
      }
      root.stopRequested = false
    }
  }
  Timer {
    id: finalizeGuard
    interval: 3000
    onTriggered: if (recordProcess.running) recordProcess.signal(15)
  }
  Process {
    id: verifyProcess
    stdout: StdioCollector { id: verifyOutput; waitForEnd: true }
    onExited: function(code) {
      root.finalizing = false
      var text = String(verifyOutput.text || "")
      var durationMatch = text.match(/duration=([\d.]+)/)
      var sizeMatch = text.match(/size=(\d+)/)
      if (code === 0 && durationMatch && Number(durationMatch[1]) > 0 && sizeMatch && Number(sizeMatch[1]) > 44) {
        root.savedPath = root.currentOutput
        Quickshell.execDetached(["notify-send", "Voice Note saved", root.savedPath])
        if (root.historyOpen) root.refreshHistory()
      } else {
        root.errorText = "Recording file validation failed"
        root.errorText += ": " + root.currentOutput
      }
    }
  }

  KeyboardPanel {
    id: panel
    anchorItem: root.anchorItem
    owner: root.barIdentity
    bar: root.bar
    open: root.opened
    centerOnBar: false
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(Style.space(380))
    contentHeight: panel.fittedContentHeight(contentColumn.implicitHeight, Style.space(500))


    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      onCloseRequested: root.close()
      onActivateRequested: root.toggleRecording()
      onTabRequested: function(direction) { root.switchPanel(direction) }

      Column {
        id: contentColumn
        width: parent.width
        spacing: Style.space(root.historyOpen || root.settingsOpen ? 9 : 14)

        Row {
          width: parent.width
          spacing: Style.space(12)
          Text {
            id: headerMic
            textFormat: Text.PlainText
            text: root.recording ? "󰑋" : "󰍬"
            color: root.recording ? Color.accent : root.bar.foreground
            font.family: root.bar.fontFamily
            font.pixelSize: Style.font.display
          }
          Column {
            width: parent.width - headerMic.implicitWidth - folderButton.width - parent.spacing * 2
            anchors.verticalCenter: parent.verticalCenter
            Text { textFormat: Text.PlainText; text: root.recording ? "Recording" : "Voice Note"; color: root.bar.foreground; font.family: root.bar.fontFamily; font.pixelSize: Style.font.title; font.bold: true }
            Text { textFormat: Text.PlainText; text: root.recording ? "Press SUPER + SHIFT + R to stop" : "Ready to record"; color: Qt.darker(root.bar.foreground, 1.4); font.family: root.bar.fontFamily; font.pixelSize: Style.font.caption }
          }
          OutlinedButton {
            id: folderButton
            anchors.verticalCenter: parent.verticalCenter
            width: Style.space(36)
            text: "󰉋"
            Accessible.name: "Open Voice Notes folder"
            Controls.ToolTip.visible: hovered
            Controls.ToolTip.text: "Open recording folder"
            onClicked: root.openFolder()
          }
        }

        Rectangle {
          width: parent.width
          height: Style.space(18)
          radius: height / 2
          color: Util.alpha(root.bar.foreground, 0.15)
          Rectangle {
            anchors.left: parent.left; anchors.top: parent.top; anchors.bottom: parent.bottom
            width: parent.width * root.liveLevel
            radius: parent.radius
            color: root.clipping ? "#C98282" : (root.recording ? Color.accent : root.bar.foreground)
            Behavior on width { NumberAnimation { duration: 55 } }
          }
        }

        OutlinedButton {
          width: parent.width
          enabled: !root.preparing && !root.finalizing
          text: root.recordButtonText
          Accessible.name: root.recording ? "Stop and save recording, " + text : text
          Controls.ToolTip.visible: hovered && root.recording
          Controls.ToolTip.text: "Click to stop and save"
          onClicked: root.toggleRecording()
        }

        OutlinedButton {
          width: parent.width
          text: "Setting"
          enabled: !root.busy
          onClicked: {
            root.settingsOpen = !root.settingsOpen
            if (root.settingsOpen) root.historyOpen = false
          }
        }

        OutlinedButton {
          width: parent.width
          text: "History"
          onClicked: root.toggleHistory()
        }

        Column {
          width: parent.width
          spacing: Style.space(6)
          visible: root.historyOpen
          PanelSeparator { foreground: root.bar.foreground }
          PanelSectionHeader { text: "RECENT RECORDINGS"; foreground: root.bar.foreground; fontFamily: root.bar.fontFamily }
          Text {
            visible: root.historyRows.length === 0
            width: parent.width
            text: historyProcess.running ? "Loading…" : (root.historyError || "No saved recordings")
            color: Util.alpha(root.bar.foreground, 0.7)
            font.family: root.bar.fontFamily
            font.pixelSize: Style.font.caption
          }
          Flickable {
            width: parent.width
            height: Math.min(historyList.implicitHeight, Style.space(130))
            visible: root.historyRows.length > 0
            contentWidth: width
            contentHeight: historyList.implicitHeight
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            Column {
              id: historyList
              width: parent.width
              spacing: Style.space(5)
              Repeater {
                model: root.historyRows
                HistoryRow {
                  required property var modelData
                  width: historyList.width
                  fileName: modelData.name
                  fileDate: modelData.date
                  fileUri: modelData.uri
                  foreground: root.bar.foreground
                  fontFamily: root.bar.fontFamily
                  copied: root.copiedUri === modelData.uri
                  onCopyRequested: function(uri) { root.copyFile(uri) }
                  onPlayRequested: function(uri) { root.playFile(uri) }
                  onDeleteRequested: function(uri) { root.deleteFile(uri) }
                }
              }
            }
          }
        }

        Column {
          width: parent.width
          spacing: Style.space(10)
          visible: root.settingsOpen
        PanelSeparator { foreground: root.bar.foreground }
        PanelSectionHeader { text: "SETTINGS"; foreground: root.bar.foreground; fontFamily: root.bar.fontFamily }

        Text { textFormat: Text.PlainText; text: "Microphone"; color: root.bar.foreground; font.family: root.bar.fontFamily; font.pixelSize: Style.font.caption }
        PanelDropdown {
          width: parent.width
          foreground: root.bar.foreground
          enabled: !root.busy
          model: [{value: "", label: "System default"}].concat(root.sourceRows)
          currentIndex: {
            for (var i = 0; i < model.length; i++) if (model[i].value === root.selectedSource) return i
            return 0
          }
          onActivated: root.persistSettings({source: model[index].value})
        }

        Text { textFormat: Text.PlainText; text: "Format"; color: root.bar.foreground; font.family: root.bar.fontFamily; font.pixelSize: Style.font.caption }
        PanelDropdown {
          width: parent.width
          foreground: root.bar.foreground
          enabled: !root.busy
          model: [{value:"wav",label:"WAV"},{value:"flac",label:"FLAC"},{value:"mp3",label:"MP3"}]
          currentIndex: root.selectedFormat === "flac" ? 1 : (root.selectedFormat === "mp3" ? 2 : 0)
          onActivated: root.persistSettings({format: model[index].value})
        }
        }

        OutlinedButton {
          visible: root.hasSaved
          enabled: false
          width: parent.width
          text: "Something Else?"
        }
        Text {
          textFormat: Text.PlainText
          visible: root.errorText !== ""
          width: parent.width
          wrapMode: Text.Wrap
          text: root.errorText
          color: Color.accent
          font.family: root.bar.fontFamily
          font.pixelSize: Style.font.caption
        }

      }
    }
  }
}
