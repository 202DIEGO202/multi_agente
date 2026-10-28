// Parser incremental: conserva caracteres UTF-8 y tramas partidas entre paquetes.
export function createSSEParser(onEvent) {
  let buffer = '';
  return (text) => {
    buffer = (buffer + text).replace(/\r\n/g, '\n');
    let end;
    while ((end = buffer.indexOf('\n\n')) >= 0) {
      const frame = buffer.slice(0, end);
      buffer = buffer.slice(end + 2);
      let name = 'message', id = '', data = [];
      for (const line of frame.split('\n')) {
        if (line.startsWith('event:')) name = line.slice(6).trim();
        if (line.startsWith('id:')) id = line.slice(3).trim();
        if (line.startsWith('data:')) data.push(line.slice(5).trimStart());
      }
      if (data.length) onEvent({ name, id, data: JSON.parse(data.join('\n')) });
    }
  };
}
