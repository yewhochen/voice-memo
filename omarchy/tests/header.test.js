const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

test('panel header icon is enlarged independently of the bar icon', () => {
  const panel = fs.readFileSync(path.join(__dirname, '..', 'Panel.qml'), 'utf8');
  const header = panel.slice(panel.indexOf('id: headerMic'), panel.indexOf('width: parent.width - headerMic.implicitWidth'));
  assert.ok(header.includes('font.pixelSize: Style.font.display * 1.25'));
  const bar = fs.readFileSync(path.join(__dirname, '..', 'BarWidget.qml'), 'utf8');
  assert.ok(bar.includes('fontSize: Style.bar.iconFont * 1.2'));
});
