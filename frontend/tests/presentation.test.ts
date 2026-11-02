import test from 'node:test';
import assert from 'node:assert/strict';
import {setPresentation,formatTime} from '../src/presentation.ts';

test('fuso aplicado muda somente a exibição, preservando o instante original',()=>{
 const original='2026-11-01T12:00:00Z';const epoch=Date.parse(original);
 setPresentation({verified:true,status:'verified',parameters:{display_name:'Fixture',timezone:'America/Sao_Paulo'}});
 assert.match(formatTime(original),/09:00:00/);
 assert.match(formatTime(original),/GMT-3/);
 setPresentation({verified:true,status:'verified',parameters:{display_name:'Fixture',timezone:'Asia/Tokyo'}});
 assert.match(formatTime(original),/21:00:00/);
 assert.equal(Date.parse(original),epoch);
 setPresentation({verified:false,status:'unknown',parameters:{display_name:'Unverified',timezone:'Asia/Tokyo'}});
 assert.match(formatTime(original),/12:00:00/);
 assert.equal(formatTime('Não informado'),'Não informado');
 assert.equal(formatTime('2026-11-01T12:00:00'),'2026-11-01T12:00:00');
});
