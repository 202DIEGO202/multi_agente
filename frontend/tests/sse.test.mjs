import test from 'node:test';
import assert from 'node:assert/strict';
import { createSSEParser } from '../src/core/sse.mjs';

test('reconstruye eventos divididos y conserva IDs para reconexión',()=>{
  const events=[];const parse=createSSEParser(event=>events.push(event));
  parse('id: 42\nevent: actividad\ndata: {"texto":"contrase');
  assert.equal(events.length,0);
  parse('ña"}\n\nevent: fin\ndata: {"estado":"completado"}\n\n');
  assert.equal(events.length,2);assert.equal(events[0].data.texto,'contraseña');assert.equal(events[0].id,'42');assert.equal(events[1].name,'fin');
});
test('ignora keepalive y admite múltiples eventos en el mismo paquete',()=>{
  const events=[];const parse=createSSEParser(event=>events.push(event));
  parse(': keepalive\n\nid: 1\ndata: {"x":1}\n\nid: 2\ndata: {"x":2}\n\n');
  assert.deepEqual(events.map(e=>e.id),['1','2']);
});
test('admite CRLF dividido entre paquetes',()=>{
  const events=[];const parse=createSSEParser(event=>events.push(event));
  parse('id: 7\r');parse('\nevent: actividad\r\ndata: {"texto":"sí"}\r');parse('\n\r\n');
  assert.equal(events.length,1);assert.equal(events[0].id,'7');assert.equal(events[0].data.texto,'sí');
});
