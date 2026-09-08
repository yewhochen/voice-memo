const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '..', 'Model.js'), 'utf8');
const sandbox = {}; vm.createContext(sandbox); vm.runInContext(source, sandbox);

test('bar glyph gets a local optical boost without changing native slots', () => {
  const bar = fs.readFileSync(path.join(__dirname, '..', 'BarWidget.qml'), 'utf8');
  assert.ok(bar.includes('fontSize: Style.bar.iconFont * 1.2'));
  assert.doesNotMatch(bar, /\b(slotSize|opticalSize|scale)\s*:/);
  assert.equal(bar.includes('openPanelIndicatorWidth'), false, 'Use the native centered indicator extent');
});

test('idle icon uses the preferred microphone glyph', () => {
  const bar = fs.readFileSync(path.join(__dirname, '..', 'BarWidget.qml'), 'utf8');
  assert.ok(bar.includes('text: root.recording ? "󰑋" : "󰍬"'));
});

test('recording hint describes the button instead of an uninstalled shortcut', () => {
  const panel = fs.readFileSync(path.join(__dirname, '..', 'Panel.qml'), 'utf8');
  assert.ok(panel.includes('root.recording ? "Click the timer to stop and save" : "Ready to record"'));
  assert.equal(panel.includes('Press SUPER + SHIFT + R to stop'), false);
});

test('settings names the device selector Input', () => {
  const panel = fs.readFileSync(path.join(__dirname, '..', 'Panel.qml'), 'utf8');
  assert.ok(panel.includes('text: "Input"'));
  assert.equal(panel.includes('text: "Microphone"'), false);
});

test('meter runs whenever panel is open, not just while recording', () => {
  const panel = fs.readFileSync(path.join(__dirname, '..', 'Panel.qml'), 'utf8');
  assert.match(panel, /enabled: root.opened && !!root.selectedNode/);
  assert.match(panel, /running: root.opened/);
});

test('clipping uses raw full-scale peak and holds for 800ms', () => {
  assert.equal(sandbox.clipUntil(0.99, 1000, 0), 0);
  assert.equal(sandbox.clipUntil(1, 1000, 0), 1800);
  assert.equal(sandbox.clipUntil(1.2, 1200, 1800), 2000);
  assert.equal(sandbox.clipUntil(0, 1500, 1800), 1800);
  assert.equal(sandbox.clipUntil(0, 1900, 1800), 1800);
});

test('elapsed recording time formats seconds, minutes and hours', () => {
  assert.equal(sandbox.elapsedLabel(0), '00:00');
  assert.equal(sandbox.elapsedLabel(12999), '00:12');
  assert.equal(sandbox.elapsedLabel(61000), '01:01');
  assert.equal(sandbox.elapsedLabel(3601000), '01:00:01');
});

test('audio service friendly names retain stable source IDs', () => {
  const rows = sandbox.parseSources(JSON.stringify([
    {name:'alsa_input.internal',description:'Built-in Audio',properties:{'node.nick':'ALC289 Analog'}},
    {name:'alsa_input.usb',description:'DJI MIC MINI'},
    {name:'sink.monitor',description:'Monitor'}
  ]));
  assert.equal(rows.length, 2);
  assert.equal(rows[0].label, 'ALC289 Analog');
  assert.equal(rows[1].label, 'DJI MIC MINI');
  assert.equal(rows[1].value, 'alsa_input.usb');
});

test('format is restricted and extensions match', () => {
  assert.equal(sandbox.normalizeFormat('mp3'), 'mp3');
  assert.equal(sandbox.normalizeFormat('bogus'), 'wav');
  assert.equal(sandbox.extensionFor('FLAC'), 'wav');
  assert.equal(sandbox.normalizeFormat('flac'), 'wav');
  assert.equal(sandbox.codecFor('flac'), 'pcm_s16le');
  const panel = fs.readFileSync(path.join(__dirname, '..', 'Panel.qml'), 'utf8');
  assert.ok(panel.includes('model: [{value:"wav",label:"WAV"},{value:"mp3",label:"MP3"}]'));
  assert.ok(panel.includes('currentIndex: root.selectedFormat === "mp3" ? 1 : 0'));
});
test('ffmpeg command explicitly selects source and codec', () => {
  assert.deepEqual(Array.from(sandbox.recordCommand('alsa_input.test', 'mp3', '/tmp/a.mp3')), [
    'ffmpeg','-hide_banner','-loglevel','info','-f','pulse','-i','alsa_input.test',
    '-c:a','libmp3lame','-n','/tmp/a.mp3'
  ]);
  assert.equal(sandbox.recordCommand('', 'mp3', '/tmp/a.mp3')[7], 'default');
});
test('source rows parse microphones and exclude monitor sources', () => {
  const rows = sandbox.parseSources(JSON.stringify([{name:'mic.one'}, {name:'speaker.monitor'}]));
  assert.equal(rows.length, 1); assert.equal(rows[0].value, 'mic.one'); assert.match(rows[0].label, /mic.one/);
});
test('invalid source JSON fails closed', () => {
  for (const input of ['bad', '{}', 'null', '[null]', '12\tmic.one'])
    assert.equal(sandbox.parseSources(input).length, 0);
});

test('record command uses safe no-overwrite and clean stdin stop', () => {
  const command = sandbox.recordCommand('', 'wav', '/tmp/a.wav');
  assert.equal(command.includes('-nostdin'), false);
  assert.equal(command.includes('-n'), true);
  assert.equal(command.includes('-y'), false);
});
test('qml declares native anchored panel and required states', () => {
  const bar = fs.readFileSync(path.join(__dirname, '..', 'BarWidget.qml'), 'utf8');
  const panel = fs.readFileSync(path.join(__dirname, '..', 'Panel.qml'), 'utf8');
  assert.match(bar, /BarWidget\s*\{/); assert.match(panel, /KeyboardPanel\s*\{/);
  assert.match(panel, /PwNodePeakMonitor/);
  assert.match(bar, /function toggleRecording/); assert.match(panel, /persistSettings/);
});

test('removed placeholder has no UI, model helper or IPC state', () => {
  for (const file of ['Panel.qml', 'BarWidget.qml', 'Model.js']) {
    const text = fs.readFileSync(path.join(__dirname, '..', file), 'utf8');
    assert.doesNotMatch(text, /Something Else|showOther|hasSaved|otherVisible/);
  }
});
test('Setting is an outlined option below recording and no header gear remains', () => {
  const panel = fs.readFileSync(path.join(__dirname, '..', 'Panel.qml'), 'utf8');
  assert.ok(panel.indexOf('text: "Setting"') > panel.indexOf('text: root.recordButtonText'));
  assert.equal(panel.includes('text: "⚙"'), false);
  assert.match(panel, /component OutlinedButton/);
  assert.match(panel, /border.width: 1/);
});

test('history copies files to clipboard on click and has no drag', () => {
  const panel = fs.readFileSync(path.join(__dirname, '..', 'Panel.qml'), 'utf8');
  const row = fs.readFileSync(path.join(__dirname, '..', 'HistoryRow.qml'), 'utf8');
  assert.equal(panel.includes('text: "Saved: " + root.savedPath'), false);
  assert.match(panel, /text: "History"/);
  assert.match(panel, /x-special\/gnome-copied-files/);
  assert.match(row, /onClicked: root.copyRequested/);
  assert.match(row, /HoverHandler/);
  assert.match(row, /text: "Play"/);
  assert.match(row, /text: root.copied \? "Copied" : "Copy"/);
  assert.match(row, /confirmDelete/);
  assert.match(panel, /\["gio", "trash", uri\]/);
  assert.match(panel, /\["xdg-open", uri\]/);
  assert.equal(row.includes('Drag.'), false);
  assert.equal(panel.includes('externalDragActive'), false);
  assert.match(panel, /required property var modelData/);
});

test('folder button sits in title row above the recording control', () => {
  const panel = fs.readFileSync(path.join(__dirname, '..', 'Panel.qml'), 'utf8');
  assert.ok(panel.indexOf('Accessible.name: "Open Voice Notes folder"') < panel.indexOf('text: root.recordButtonText'));
  assert.equal(panel.includes('layoutDirection: Qt.RightToLeft'), false);
});

test('history and settings are exclusive and folder action is exposed', () => {
  const panel = fs.readFileSync(path.join(__dirname, '..', 'Panel.qml'), 'utf8');
  const bar = fs.readFileSync(path.join(__dirname, '..', 'BarWidget.qml'), 'utf8');
  assert.match(panel, /function showHistory/);
  assert.match(panel, /settingsOpen = false/);
  assert.match(panel, /function openFolder/);
  assert.match(panel, /xdg-open/);
  assert.match(bar, /function showHistory\(\): void/);
  assert.match(bar, /function openFolder\(\): void/);
  assert.match(panel, /Style\.space\(500\)/);
});
