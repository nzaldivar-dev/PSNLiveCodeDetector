// Captura el audio del <video> de la pestaña y lo envía a Python en bloques
// de ~5 s como PCM Int16 mono (base64). Se llama: window.__psnStartAudio(binding)
(() => {
  if (window.__psnAudioInstalled) return;
  window.__psnAudioInstalled = true;
  const SECONDS = 5;
  let ctx = null, attached = null, chunks = [], total = 0;

  function flush() {
    if (!total) return;
    const pcm = new Int16Array(total);
    let o = 0;
    for (const c of chunks) { pcm.set(c, o); o += c.length; }
    chunks = []; total = 0;
    let bin = "";
    const bytes = new Uint8Array(pcm.buffer);
    for (let i = 0; i < bytes.length; i += 0x8000) {
      bin += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
    }
    window.__psnAudioSend(ctx.sampleRate, btoa(bin));
  }

  function attach(video) {
    const stream = video.captureStream ? video.captureStream() : null;
    if (!stream || !stream.getAudioTracks().length) return false;
    ctx = ctx || new AudioContext();
    const src = ctx.createMediaStreamSource(new MediaStream(stream.getAudioTracks()));
    const proc = ctx.createScriptProcessor(4096, 1, 1);
    const mute = ctx.createGain();
    mute.gain.value = 0; // el processor necesita salida, pero no duplicamos el sonido
    proc.onaudioprocess = (e) => {
      const f = e.inputBuffer.getChannelData(0);
      const i16 = new Int16Array(f.length);
      for (let i = 0; i < f.length; i++) {
        const s = Math.max(-1, Math.min(1, f[i]));
        i16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
      }
      chunks.push(i16); total += i16.length;
      if (total >= ctx.sampleRate * SECONDS) flush();
    };
    src.connect(proc); proc.connect(mute); mute.connect(ctx.destination);
    if (ctx.state === "suspended") ctx.resume();
    attached = video;
    return true;
  }

  // El video puede cambiar (YouTube es una SPA): se revisa periódicamente.
  setInterval(() => {
    const v = document.querySelector("video");
    if (v && v !== attached && v.readyState >= 1) {
      try { attach(v); } catch (e) { window.__psnAudioLog && window.__psnAudioLog(String(e)); }
    }
  }, 1500);
})();
