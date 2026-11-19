// Capture PCM on the audio rendering thread; outputs remain silent.
class PcmCapture extends AudioWorkletProcessor {
  process(inputs) {
    const channels = inputs[0];
    if (channels?.length) this.port.postMessage(channels.map(channel => new Float32Array(channel)));
    return true;
  }
}
registerProcessor('pcm-capture', PcmCapture);
