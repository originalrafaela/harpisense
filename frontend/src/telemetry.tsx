import {useState} from 'react';
import {telemetry, stale, type Row} from './api';
import {Badge, Empty, Panel, Records, show} from './components';

export function Telemetry({rows, assets, compact=false}: {rows: Row[]; assets: Row[]; compact?:boolean}) {
  const [device, setDevice] = useState('');
  const list = rows.filter(row => !device || telemetry(row).device === device);
  const devices = [...new Set(list.map(row => telemetry(row).device))];
  return <>
    <Panel title="Postes · última leitura conhecida">
      <label>Dispositivo<select value={device} onChange={event => setDevice(event.target.value)}>
        <option value="">Todos os dispositivos</option>
        {[...new Set(rows.map(row => telemetry(row).device))].map(id => <option key={id}>{id}</option>)}
      </select></label>
      <div className="cards">{devices.map(id => {
        const candidates = list.filter(row => telemetry(row).device === id).sort((a, b) => {
          const time = (row: Row) => Date.parse(telemetry(row).observed || row.created_at || '');
          const x = time(a), y = time(b);
          return Number.isFinite(x) && Number.isFinite(y) ? y - x : 0;
        });
        const row = candidates[0];
        const value = telemetry(row);
        const asset = assets.find(asset => asset.data.device_id === id);
        return <article className="metric telemetry-record" key={id} aria-label={`Telemetria de ${id}`}>
          <h3>{id}</h3><Badge>{asset ? show(asset.data.type) : 'Tipo de dispositivo não informado pela API'}</Badge>
          <dl>
            <dt>ID do registro</dt><dd>{row.id}</dd>
            <dt>Origem da projeção</dt><dd>{show(row.source)}</dd>
            <dt>Revisão</dt><dd>{show(row.revision)}</dd>
            <dt>Registrado na projeção</dt><dd>{value.recorded || 'Não informado'}</dd>
            <dt>Última observação</dt><dd>{value.observed || 'Não informada'}</dd>
            <dt>Recebido pelo backend</dt><dd>{value.received || 'Não informado'}</dd>
            <dt>Luminosidade</dt><dd>{value.light}</dd>
            <dt>LED na leitura</dt><dd>{value.led}</dd>
            {value.provisionalTemperature !== null && <><dt>Temperatura do payload provisório (unidade não informada)</dt><dd>{value.provisionalTemperature}</dd></>}
            {typeof row.data.tipo === 'string' && <><dt>Tipo do payload</dt><dd>{row.data.tipo}</dd></>}
          </dl>
          <p>{stale(value.observed) ? '◷ Leitura desatualizada ou horário de observação desconhecido' : '◷ Leitura recente'}</p>
          <small>Estado atual não confirmado. O horário da projeção não substitui o horário da medição. Histórico limitado à página consultada.</small>
        </article>;
      })}</div>
      {!list.length && <Empty/>}
      <p className="muted">LDR bruto não é lux. O campo luminosity sem unidade é exibido como recebido, sem conversão. Temperatura provisória não representa luminosidade. Identificadores são preservados como recebidos, sem renomear poste2.</p>
    </Panel>
    {!compact&&<Panel title="Histórico de telemetria"><Records rows={list} columns={[
      ['id', 'ID do registro'], ['device_id', 'Dispositivo'], ['created_at', 'Registrado na projeção'],
      ['observed_at', 'Observado em'], ['temperatura', 'Temperatura provisória · unidade não informada'],
      ['tipo', 'Tipo do payload'], ['luminosity', 'Luminosidade · unidade não informada'], ['led_state', 'LED informado no payload'], ['measurements', 'Medições originais'], ['status', 'Estado na leitura'],
    ]}/></Panel>}
  </>;
}
