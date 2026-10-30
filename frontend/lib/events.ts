export async function readEvents(body: ReadableStream<Uint8Array>, onEvent: (event: any) => void) {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  const dispatch = (frame: string) => {
    const data = frame.split(/\r?\n/).filter(line => line.startsWith("data:")).map(line => line.slice(5).trimStart()).join("\n");
    if (data) onEvent(JSON.parse(data));
  };
  try {
    while (true) {
      const { done, value } = await reader.read();
      buffer += done ? decoder.decode() : decoder.decode(value, { stream: true });
      let separator: RegExpExecArray | null;
      while ((separator = /\r?\n\r?\n/.exec(buffer))) {
        dispatch(buffer.slice(0, separator.index));
        buffer = buffer.slice(separator.index + separator[0].length);
      }
      if (done) { if (buffer.trim()) dispatch(buffer); break; }
    }
  } finally {
    await reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
}
