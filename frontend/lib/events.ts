// Allow the backend's 15-minute deadline to send its final error before aborting transport.
export const STREAM_TRANSPORT_TIMEOUT_MS = 16 * 60 * 1000;

export async function readEvents(body: ReadableStream<Uint8Array>, onEvent: (event: any) => void | boolean) {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  const dispatch = (frame: string) => {
    const data = frame.split(/\r?\n/).filter(line => line.startsWith("data:")).map(line => line.slice(5).trimStart()).join("\n");
    if (data) return onEvent(JSON.parse(data));
  };
  try {
    while (true) {
      const { done, value } = await reader.read();
      buffer += done ? decoder.decode() : decoder.decode(value, { stream: true });
      let separator: RegExpExecArray | null;
      while ((separator = /\r?\n\r?\n/.exec(buffer))) {
        if (dispatch(buffer.slice(0, separator.index)) === false) return;
        buffer = buffer.slice(separator.index + separator[0].length);
      }
      if (done) { if (buffer.trim()) dispatch(buffer); break; }
    }
  } finally {
    await reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
}
