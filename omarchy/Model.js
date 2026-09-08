function clipUntil(peak, now, previous) {
  return Number(peak) >= 1 ? now + 800 : previous
}

function elapsedLabel(ms) {
  var s = Math.max(0, Math.floor(Number(ms || 0) / 1000))
  var h = Math.floor(s / 3600)
  function pad(n) { return String(n).padStart(2, "0") }
  return (h ? pad(h) + ":" : "") + pad(Math.floor(s / 60) % 60) + ":" + pad(s % 60)
}

function normalizeFormat(value) {
  var format = String(value || "").toLowerCase()
  return ["wav", "flac", "mp3"].indexOf(format) >= 0 ? format : "wav"
}

function extensionFor(format) { return normalizeFormat(format) }

function codecFor(format) {
  var normalized = normalizeFormat(format)
  if (normalized === "flac") return "flac"
  if (normalized === "mp3") return "libmp3lame"
  return "pcm_s16le"
}

function recordCommand(source, format, output) {
  return ["ffmpeg", "-hide_banner", "-loglevel", "info",
    "-f", "pulse", "-i", String(source || "default"),
    "-c:a", codecFor(format), "-n", String(output)]
}

function parseSources(raw) {
  try {
    var sources = JSON.parse(raw)
    if (Array.isArray(sources)) return sources.filter(function(s) {
      return s && s.name && !String(s.name).endsWith(".monitor")
    }).map(function(s) {
      return {value: s.name, label: (s.properties || {})["node.nick"] || s.description || (s.properties || {})["node.description"] || s.name}
    })
  } catch (e) {}
  return []
}
