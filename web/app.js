// Interfaz de la Práctica 3. Toda la física/matemática está en Python (logica/); acá solo UI.
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
let api = null;
let P = {};                         // parámetros actuales (localStorage)
const coh = {};                     // coherencia de parámetros por módulo (regla de oro)
const C = () => Plot.C;
const ESC_COL = { los: '#3be0c8', multi: '#ffc25c', nlos: '#9b8cff' };
const ESC_NOM = { los: 'LOS', multi: 'Multitrayectoria', nlos: 'NLOS corto' };

// ------------------------------------------------------------------ utilidades
const fmtHz = v => v >= 1e6 ? +(v / 1e6).toFixed(3) + ' MHz' : v >= 1e3 ? +(v / 1e3).toFixed(2) + ' kHz' : v.toFixed(0) + ' Hz';
const fmtRate = (v, u) => v >= 1e6 ? +(v / 1e6).toFixed(3) + ' M' + u : +(v / 1e3).toFixed(2) + ' k' + u;
const num = (v, d = 1) => v === null || v === undefined || !isFinite(v) ? '—' : (+v).toFixed(d);
const sgn = (v, d = 1) => v === null || v === undefined ? '—' : (v >= 0 ? '+' : '') + (+v).toFixed(d);
const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

function toast(msg, err = false) {
  const d = document.createElement('div');
  d.textContent = msg; if (err) d.className = 'e';
  $('#toast').appendChild(d);
  setTimeout(() => d.remove(), err ? 7000 : 3500);
}
function kpis(el, items) {
  el.innerHTML = items.map(([lab, val, unit, cls]) =>
    `<div class="kpi ${cls || ''}"><small>${lab}</small><b>${val}</b>${unit ? `<i>${unit}</i>` : ''}</div>`).join('');
}
function guardar() { try { localStorage.setItem('p3_params', JSON.stringify(P)); } catch (e) { } }
async function busy(btn, fn) {
  btn.classList.add('busy'); btn.disabled = true;
  try { return await fn(); } finally { btn.classList.remove('busy'); btn.disabled = false; }
}
async function llamar(btn, fn) {              // ejecuta una llamada a la API y avisa errores
  return busy(btn, async () => {
    const r = await fn();
    if (r && r.ok === false) { toast(r.error || 'Error', true); console.error(r.tb || r.error); return null; }
    return r;
  });
}

// ------------------------------------------------------------------ controles
function updateLock() {
  const ok = Object.values(coh).every(v => v !== false);
  $('#lockbar').innerHTML = `<span class="lk">🔒 Parámetros bloqueados</span>
    f<sub>c</sub> <b>${fmtHz(P.fc)}</b> · f<sub>s</sub> <b>${fmtRate(P.fs, 'Sps')}</b> · G<sub>tx</sub> <b>${P.gain_tx} dB</b> · G<sub>rx</sub> <b>${P.gain_rx} dB</b> ·
    amp <b>${P.amp}</b> · ZC <b>${P.n_zc}×${P.n_rep}</b> · T <b>${P.periodo_ms} ms</b>
    <span class="badge" style="margin-left:auto;${ok ? 'color:var(--green)' : 'color:var(--amber);border-color:var(--amber)'}">${ok ? 'serie coherente ✓' : '⚠ hay mediciones con otros parámetros'}</span>`;
}

function pintarControles() {
  $$('[data-k]').forEach(el => {
    const k = el.dataset.k, v = P[k];
    if (document.activeElement === el) return;
    if (el.classList.contains('seg')) el.querySelectorAll('button').forEach(b => b.classList.toggle('on', b.dataset.v === v));
    else if (el.dataset.scale) el.value = +(v / +el.dataset.scale).toPrecision(10);
    else el.value = v;
  });
  $$('[data-o]').forEach(o => o.textContent = P[o.dataset.o]);
  $$('[data-show]').forEach(el => {
    const neg = el.dataset.show.includes('!=');
    const [k, cond] = el.dataset.show.split(/!?=/);
    const hit = cond.split(',').includes(String(P[k]));
    el.hidden = neg ? hit : !hit;
  });
  $('#fileName').textContent = P.archivo_rx ? P.archivo_rx.split(/[\\/]/).pop() : 'ninguno';
  const lam = 299792458 / P.fc;
  $('#sFc').textContent = fmtHz(P.fc);
  $('#sFs').textContent = fmtRate(P.fs, 'Sps');
  $('#sLam').textContent = (lam * 100).toFixed(1) + ' cm';
  $('#sRes').textContent = (1e9 / P.fs).toFixed(0) + ' ns';
  $('#sSrc').textContent = { usrp: 'USRP ' + P.ip_rx, sim: 'simulado', archivo: 'archivo' }[P.rx_hw];
  updateLock();
}

const GLOBALES = ['fc', 'fs', 'n_zc', 'raiz', 'n_rep', 'periodo_ms', 'amp', 'gain_tx', 'gain_rx', 'umbral', 'duracion_ms'];
let tSenal = null;
function bindControles() {
  $$('[data-k]').forEach(el => {
    const k = el.dataset.k;
    if (el.classList.contains('seg')) {
      el.addEventListener('click', e => {
        const b = e.target.closest('button'); if (!b) return;
        P[k] = b.dataset.v; guardar(); pintarControles();
        if (k === 'canal_tab' || k === 'canal_esc') cargarPagina('canal');
      });
      return;
    }
    el.addEventListener(el.type === 'range' ? 'input' : 'change', () => {
      let v = el.value;
      if (el.type === 'number' || el.type === 'range') v = +v * (+el.dataset.scale || 1);
      P[k] = v; guardar(); pintarControles();
      if (GLOBALES.includes(k)) { clearTimeout(tSenal); tSenal = setTimeout(() => cargarPagina(paginaActual(), true), 300); }
      if (k === 'fad_nlam' || k === 'fad_frac') actualizarPlanFad();
    });
  });
}

// ------------------------------------------------------------------ navegación
const paginaActual = () => ($('nav a.active') || {}).dataset?.page;
function irA(page) {
  $$('nav a').forEach(a => a.classList.toggle('active', a.dataset.page === page));
  $$('.page').forEach(p => p.classList.toggle('active', p.id === 'page-' + page));
  cargarPagina(page);
  requestAnimationFrame(() => $$(`#page-${page} canvas`).forEach(c => c._draw && c._draw()));
}
async function cargarPagina(page, soloSenal = false) {
  try {
    if (page === 'senal' || page === 'tx') await actualizarSenal();
    if (page === 'tx') txEstado();
    if (soloSenal) return;
    if (page === 'guia') Guia.pintar();
    if (page === 'dist') pintarDist(await api.dist_listar(P));
    if (page === 'obst') pintarObst(await api.obst_listar(P));
    if (page === 'canal') {
      await actualizarPlanFad();
      pintarFad(await api.fad_listar(P));
      pintarCanal(await api.canal_listar(P));
    }
    if (page === 'analisis') analisis();
  } catch (e) { console.error(e); }
}

// ------------------------------------------------------------------ 00 conexión
const ICONO = { ok: '✓', warn: '!', ko: '✕' };
function pintarPasos(pasos, veredicto) {
  const txt = {
    ok: ['Sistema listo para medir', 'Todos los pasos son correctos.'],
    warn: ['Listo con advertencias', 'Revisa los avisos antes de iniciar una serie de medidas.'],
    ko: ['Hay problemas que impiden medir', 'Corrige los pasos en rojo.']
  }[veredicto];
  $('#verdict').innerHTML = `<div class="verdict ${veredicto}"><span style="font-size:22px">${ICONO[veredicto]}</span><div>${txt[0]}<small>${txt[1]}</small></div></div>`;
  $('#steps').innerHTML = pasos.map(p => `<div class="step ${p.estado}"><i>${ICONO[p.estado]}</i><b>${esc(p.paso)}</b><span>${esc(p.detalle)}</span></div>`).join('');
}

function plotCaptura(idEnv, idPsd, r) {
  const mx = Math.max(...r.env.v, 1e-9);
  Plot.line($(idEnv), {
    series: [
      { x: r.env.t, y: r.env.v.map(v => v / mx), color: C().cyan, label: '|x| (norm.)', alpha: .85, fill: true },
      { x: r.metrica.t, y: r.metrica.v, color: C().violet, label: 'métrica M(d)', width: 1.6 }],
    hlines: [{ y: r.metrica.umbral, color: C().amber }],
    vlines: r.marcas.length <= 60 ? r.marcas.map(t => ({ x: t, color: '#4fe39a88' })) : [],
    xlabel: 't (ms)', ylim: [0, 1.05]
  });
  Plot.line($(idPsd), { series: [{ x: r.psd.f, y: r.psd.db, color: C().cyan, fill: true }], xlabel: 'f − f_c (kHz)', ylabel: 'dBFS' });
}

async function verificar(btn, modo) {
  const r = await llamar(btn, () => api.verificar(P, modo));
  if (!r) return;
  pintarPasos(r.pasos, r.veredicto);
  if (r.kpis) {
    const k = r.kpis;
    kpis($('#conKpis'), [
      ['Ráfagas', `${k.n_det}`, `/ ${k.n_esp} esp.`, k.n_det >= k.n_esp * .8 ? 'good' : 'warn'],
      ['SNR', num(k.snr), 'dB', k.snr >= 15 ? 'good' : k.snr >= 6 ? 'warn' : 'bad'],
      ['Potencia señal', num(k.p), 'dBFS', 'acc'],
      ['Piso de ruido', num(k.ruido), 'dBFS'],
      ['Pico ADC', num(k.pico, 2), k.sat > 0.01 ? `sat ${k.sat.toFixed(2)}%` : '', k.sat > 0.1 ? 'bad' : ''],
      ['CFO', num(k.cfo, 0), 'Hz']]);
    plotCaptura('#cConEnv', '#cConPsd', r);
  }
}

// ------------------------------------------------------------------ 01 señal / 02 tx
let senalCache = null;
async function actualizarSenal() {
  const r = await api.info_senal(P);
  if (!r.ok) { toast(r.error, true); return; }
  senalCache = r;
  const s = r.resumen, nR = s.n_rep;
  const fsOk = Math.abs(s.fs_real - s.fs) < 1;
  // diagrama de la ráfaga
  let h = `<div class="f-sil" style="flex:2;min-width:0">silencio<small>ruido</small></div>`;
  for (let i = 0; i < nR; i++) h += `<div class="f-zc ${i % 2 ? 'alt' : ''}" style="flex:1;min-width:0;padding:0">${nR <= 10 ? 'ZC' : ''}<small>${nR <= 10 ? (i + 1) : ''}</small></div>`;
  h += `<div class="f-sil" style="flex:3;min-width:0">silencio hasta completar el periodo<small>${s.n_periodo - s.n_rafaga} muestras</small></div>`;
  $('#frameDiagram').innerHTML = h;
  $('#frameTable tbody').innerHTML = [
    ['Silencio previo', `≈ ${(s.n_periodo - s.n_rafaga) / 1e3 | 0}k muestras`, 'sin señal',
      'El receptor mide aquí el piso de ruido: potencia de señal = potencia total − ruido. Su calidad define la SNR.'],
    [`ZC × ${nR}`, `${s.n_zc} × ${nR} = ${s.n_rafaga} muestras`, `Zadoff-Chu N=${s.n_zc}, u=${P.raiz}`,
      `Amplitud constante (potencia estable, sin saturar). Repetida: permite detectar sin conocer la señal (Schmidl-Cox), estimar CFO por la fase entre copias y promediar ${nR - 1} copias para estimar el canal.`],
    ['Periodo', `${s.n_periodo} muestras = ${P.periodo_ms} ms`, `ciclo de trabajo ${s.duty_pct.toFixed(2)} %`,
      'Debe ser > 2× la ráfaga y mayor que el retardo máximo esperado. Suficientes ráfagas por captura para promediar.']
  ].map(c => `<tr><td class="k">${c[0]}</td><td class="k" style="color:var(--cyan);font-family:var(--mono)">${c[1]}</td><td>${c[2]}</td><td class="muted">${c[3]}</td></tr>`).join('');
  kpis($('#senKpis'), [
    ['f<sub>s</sub> real N210', fmtRate(s.fs_real, 'Sps'), '', fsOk ? 'good' : 'warn'],
    ['Resolución temporal', num(s.resol_t_ns, 0), 'ns', 'acc'],
    ['Resolución espacial', num(s.resol_d_m, 0), 'm', 'acc'],
    ['Duración de ráfaga', num(s.t_rafaga_us, 0), 'µs'],
    ['Ciclo de trabajo', num(s.duty_pct, 2), '%'],
    ['Ganancia de procesado', num(s.gp_db, 1), 'dB'],
    ['Rango de CFO', '±' + num(s.rango_cfo_hz, 0), 'Hz'],
    ['Span del canal', num(s.span_canal_us, 1), 'µs'],
    ['λ', num(s.lambda_cm, 1), 'cm']]);
  $('#senNota').innerHTML = `Dos ecos separados menos de <b>${num(s.resol_d_m, 0)} m</b> de camino extra no se distinguen: para ver ecos de interior (decenas de ns) hay que subir f<sub>s</sub>. ` +
    (fsOk ? '' : `<span class="wa">El N210 solo da f<sub>s</sub> = 100 MHz/D: se usará ${fmtRate(s.fs_real, 'Sps')}.</span>`);
  Plot.line($('#cZcFase'), { series: [{ x: r.zc.k, y: r.zc.fase, color: C().violet, points: true, r: 1.8 }], xlabel: 'k', ylabel: 'fase (rad)' });
  const both = [{ x: r.tiempo.t, y: r.tiempo.i, color: C().cyan, label: 'I' }, { x: r.tiempo.t, y: r.tiempo.q, color: C().violet, label: 'Q', alpha: .85 }];
  Plot.line($('#cZcIq'), { series: both, xlabel: 't (µs)', ylabel: 'amplitud' });
  Plot.line($('#cZcAc'), { series: [{ x: r.acorr.lag, y: r.acorr.db, color: C().green, stem: true, r: 2.2 }], xlabel: 'desplazamiento (muestras)', ylabel: 'dB', ylim: [-85, 5] });
  Plot.line($('#cZcMf'), { series: [{ x: r.mf.lag, y: r.mf.db, color: C().cyan, fill: true }], xlabel: 'lag (muestras)', ylabel: 'dB', ylim: [-60, 3] });
  Plot.line($('#cZcPsd'), { series: [{ x: r.psd.f, y: r.psd.db, color: C().cyan, fill: true }], xlabel: 'f − f_c (kHz)', ylabel: 'dB', ylim: [-60, 3] });
  // transmisor
  kpis($('#txCfg'), [['Periodo', P.periodo_ms, 'ms'], ['Ráfagas/s', num(1000 / P.periodo_ms, 0)], ['Duración', num(s.t_rafaga_us, 0), 'µs'], ['f<sub>s</sub> real', fmtRate(s.fs_real, 'Sps')]]);
  Plot.line($('#cTxTren'), { series: [{ x: r.tren.t, y: r.tren.v, color: C().cyan, fill: true }], xlabel: 't (ms)', ylabel: '|x|', ylim: [0, 1] });
  Plot.line($('#cTxIq'), { series: both, xlabel: 't (µs)', ylabel: 'amplitud' });
  Plot.line($('#cTxPsd'), { series: [{ x: r.psd.f, y: r.psd.db, color: C().violet, fill: true }], xlabel: 'f − f_c (kHz)', ylabel: 'dB', ylim: [-60, 3] });
}

let txPoll = null;
async function txGo() {
  const r = await llamar($('#btnTxGo'), () => api.tx_iniciar(P));
  if (!r) return;
  toast(r.msg);
  clearInterval(txPoll); txPoll = setInterval(txEstado, 500); txEstado();
}
async function txEstado() {
  const s = await api.tx_estado();
  $('#txDot').classList.toggle('on', s.activo);
  $('#txStatus').textContent = s.activo ? 'TRANSMITIENDO' : 'TX inactivo';
  $('#btnTxStop').disabled = !s.activo; $('#btnTxGo').disabled = s.activo;
  $('#txState').innerHTML = s.error ? `<div class="err">⚠ ${esc(s.error)}</div>` :
    (s.activo || s.enviadas ? `muestras enviadas: ${s.enviadas.toLocaleString('es')}<br>ráfagas: ${s.rafagas}` + (s.fs_real ? `<br>f<sub>s</sub> real: ${fmtRate(s.fs_real, 'Sps')}` : '') : '');
  if (!s.activo) clearInterval(txPoll);
  if (s.error) toast(s.error, true);
}

// ------------------------------------------------------------------ 03 receptor
let rxBusy = false;
async function rxCapturar() {
  if (rxBusy) return;
  rxBusy = true; $('#btnRx').classList.add('busy');
  try {
    const r = await api.rx_capturar(P);
    if (!r.ok) { toast(r.error, true); console.error(r.tb); $('#rxLoop').checked = false; return; }
    pintarRx(r);
  } finally {
    $('#btnRx').classList.remove('busy'); rxBusy = false;
    if ($('#rxLoop').checked && paginaActual() === 'rx') setTimeout(rxCapturar, 150);
  }
}
function pintarRx(r) {
  const rs = r.rafagas, m = a => rs.length ? rs.reduce((s, x) => s + x[a], 0) / rs.length : null;
  const snr = m('snr_db'), sat = r.sat_pct > 0.01;
  kpis($('#rxKpis'), [
    ['Ráfagas detectadas', r.n_det, `/ ${r.n_esp} esp.`, r.n_det >= r.n_esp * .8 ? 'good' : r.n_det ? 'warn' : 'bad'],
    ['Potencia señal', num(m('p_dbfs')), 'dBFS', 'acc'],
    ['SNR', num(snr), 'dB', snr === null ? '' : snr >= 15 ? 'good' : snr >= 6 ? 'warn' : 'bad'],
    ['Piso de ruido', num(r.ruido_dbfs), 'dBFS'],
    ['CFO medio', num(m('cfo_hz'), 0), 'Hz'],
    ['Pico ADC', num(r.pico, 2), sat ? `sat ${r.sat_pct.toFixed(2)}%` : '', sat ? 'bad' : r.pico < .02 ? 'warn' : ''],
    ['Tiempos', `${(r.t_captura * 1e3).toFixed(0)}+${(r.t_proceso * 1e3).toFixed(0)}`, 'ms']]);
  if (r.overflow) toast(`Overflow en RX (${r.overflow}): baja f_s o cierra otros programas`, true);
  plotCaptura('#cRxEnv', '#cRxPsd', r);
  $('#rxTable tbody').innerHTML = rs.length ? rs.map((x, i) => `<tr><td>${i + 1}</td><td>${x.t_ms.toFixed(2)}</td><td>${x.M.toFixed(2)}</td>
    <td>${x.cfo_hz.toFixed(0)}</td><td>${x.p_tot_dbfs.toFixed(2)}</td><td>${x.p_dbfs.toFixed(2)}</td><td>${x.snr_db.toFixed(1)}</td></tr>`).join('')
    : '<tr><td colspan="7" class="muted c">No se detectó ninguna ráfaga. Revisa TX, ganancia, frecuencia o el umbral.</td></tr>';
  const sel = $('#rxSel');
  sel.innerHTML = rs.map((x, i) => `<option value="${i}">#${i + 1} · ${x.t_ms.toFixed(1)} ms</option>`).join('');
  if (r.detalle) pintarDetalle(r.detalle); else ['#cDetIq', '#cDetMf', '#cDetFase', '#cDetAmp'].forEach(c => Plot.empty($(c), 'sin ráfagas'));
}
function pintarDetalle(d) {
  $('#rxDetSel').textContent = `ráfaga #${d.idx + 1}`;
  Plot.line($('#cDetIq'), {
    series: [{ x: d.t_us, y: d.i, color: C().cyan, label: 'I' }, { x: d.t_us, y: d.q, color: C().violet, label: 'Q', alpha: .85 }],
    vlines: [{ x: d.inicio_us, color: C().green }, { x: d.fin_us, color: C().red }], xlabel: 't (µs)', ylabel: 'amplitud'
  });
  Plot.line($('#cDetMf'), { series: [{ x: d.t_mf_us, y: d.mf, color: C().amber, fill: true }], vlines: [{ x: d.inicio_us, color: C().green }], xlabel: 't (µs)', ylabel: '|c|' });
  const idx = d.fase_copias.map((_, i) => i + 1);
  Plot.line($('#cDetFase'), { series: [{ x: idx, y: d.fase_copias, color: C().violet, points: true }], xlabel: 'copia', ylabel: 'fase (°)', ylim: [-180, 180] });
  Plot.line($('#cDetAmp'), { series: [{ x: idx, y: d.amp_copias, color: C().cyan, points: true }], xlabel: 'copia', ylabel: '|c|' });
}

// ------------------------------------------------------------------ tablas con borrado
function coherencia(clave, r) {
  coh[clave] = !r.filas.length || r.filas.every(f => f.firma === r.firma_actual);
  updateLock();
}
const estadoTag = (f, firma) => f.firma !== firma ? '<span class="tag wa" title="parámetros distintos a los actuales">≠ params</span>'
  : (f.valido ? '<span class="tag ok">OK</span>' : '<span class="tag ko" title="SNR bajo o saturación">excluido</span>');
const delBtn = (clave, id) => `<button class="del" data-del="${clave}:${id}" title="borrar">✕</button>`;

// ------------------------------------------------------------------ 04 distancia
function pintarDist(r) {
  coherencia('dist', r);
  const filas = r.filas, aj = r.ajuste;
  $('#distAviso').innerHTML = r.aviso ? `<p class="note wa">${esc(r.aviso)}</p>` : '';
  if (aj) {
    const nCls = Math.abs(aj.n - 2) < .3 ? 'good' : '';
    kpis($('#distKpis'), [
      ['Exponente n', num(aj.n, 2), '± ' + num(aj.ic95, 2), nCls || 'acc'], ['P₀ (d₀=1 m)', num(aj.p0, 1), 'dB'],
      ['σ sombreado', num(aj.sigma, 2), 'dB', aj.sigma > 6 ? 'warn' : ''], ['R²', num(aj.r2, 3), '', aj.r2 > .9 ? 'good' : 'warn'],
      ['Puntos / dist.', `${filas.filter(f => f.valido).length}`, `/ ${new Set(filas.map(f => f.d)).size} dist.`]]);
  } else kpis($('#distKpis'), [['Puntos', filas.length], ['Se necesitan', '≥ 2', 'distancias distintas', 'warn']]);
  const val = filas.filter(f => f.valido), inv = filas.filter(f => !f.valido);
  const pts = (arr, col, tf) => ({ x: arr.map(f => tf(f.d)), y: arr.map(f => f.p_db), err: arr.map(f => f.std_db), color: col, pointsOnly: true, r: 4.5 });
  const lin = [], log = [];
  if (aj && r.curva) {
    lin.push({ x: r.curva.d, y: r.curva.p, color: C().cyan, label: `ajuste n=${num(aj.n, 2)}`, width: 2 });
    lin.push({ x: r.curva.d, y: r.curva.p_fs, color: C().amber, dash: [6, 4], label: 'n = 2 (espacio libre)' });
    log.push({ x: r.curva.d.map(d => 10 * Math.log10(d)), y: r.curva.p, color: C().cyan, label: `pendiente −${num(aj.n * 10, 1)} dB/dec`, width: 2 });
    log.push({ x: r.curva.d.map(d => 10 * Math.log10(d)), y: r.curva.p_fs, color: C().amber, dash: [6, 4], label: 'n = 2' });
  }
  lin.push(pts(val, C().violet, d => d)); log.push(pts(val, C().violet, d => 10 * Math.log10(d)));
  if (inv.length) { lin.push({ ...pts(inv, C().red, d => d), label: 'excluido' }); log.push(pts(inv, C().red, d => 10 * Math.log10(d))); }
  Plot.line($('#cDistLin'), { series: lin, xlabel: 'distancia (m)', ylabel: 'P (dB)' });
  Plot.line($('#cDistLog'), { series: log, xlabel: '10·log₁₀(d)  (d en m)', ylabel: 'P (dB)' });
  const res = val.filter(f => f.residuo_db !== null && f.residuo_db !== undefined);
  Plot.line($('#cDistRes'), {
    series: [{ x: res.map(f => f.d), y: res.map(f => f.residuo_db), color: C().green, pointsOnly: true, r: 4.5 }],
    hlines: [{ y: 0, color: C().text }].concat(aj ? [{ y: aj.sigma, color: C().amber }, { y: -aj.sigma, color: C().amber }] : []),
    xlabel: 'distancia (m)', ylabel: 'residuo (dB)'
  });
  $('#distTable tbody').innerHTML = filas.length ? filas.map((f, i) => `<tr><td>${i + 1}</td><td>${f.d}</td><td>${f.p_db.toFixed(2)}</td><td>${f.std_db.toFixed(2)}</td>
    <td>${f.n}</td><td>${f.snr_db.toFixed(1)}</td><td>${f.residuo_db == null ? '—' : sgn(f.residuo_db, 2)}</td><td>${estadoTag(f, r.firma_actual)}</td><td>${delBtn('distancia', f.id)}</td></tr>`).join('')
    : '<tr><td colspan="9" class="muted c">Sin mediciones.</td></tr>';
}

// ------------------------------------------------------------------ 05 obstrucciones
const CLASE_COL = { referencia: '#3be0c8', despreciable: '#4fe39a', leve: '#8bd36b', moderada: '#ffc25c', fuerte: '#ff9a5c', severa: '#ff6b81' };
function pintarObst(r) {
  coherencia('obst', r);
  $('#obstAviso').innerHTML = r.aviso ? `<p class="note wa">${esc(r.aviso)}</p>` : '';
  const t = r.tabla, los = t.find(g => g.cond === 'LOS'), otras = t.filter(g => g.cond !== 'LOS');
  const peor = otras.length ? otras.reduce((a, b) => b.atenuacion_db > a.atenuacion_db ? b : a) : null;
  kpis($('#obstKpis'), [
    ['Potencia LOS', los ? num(los.p_db) : '—', 'dB', los ? 'acc' : 'warn'],
    ['Peor atenuación', peor ? num(peor.atenuacion_db) : '—', peor ? 'dB · ' + esc(peor.cond) : '', peor ? 'bad' : ''],
    ['Condiciones', r.grupos.length], ['Mediciones', r.filas.length]]);
  if (!r.hay_los && r.filas.length) toast('Falta la medición de referencia LOS', true);
  const mostrar = otras;
  if (mostrar.length) Plot.bars($('#cObstBar'), mostrar.map(g => g.cond), mostrar.map(g => Math.max(0, g.atenuacion_db)),
    { err: mostrar.map(g => g.err_db), colors: mostrar.map(g => CLASE_COL[g.clase]), fmt: v => v.toFixed(1) + ' dB', ylabel: 'atenuación (dB)' });
  else Plot.empty($('#cObstBar'), 'mide LOS y un obstáculo');
  $('#obstTexto').innerHTML = otras.length ? otras.map(g => `<li><b>${esc(g.cond)}</b>: ${g.atenuacion_db >= 0 ? '−' : '+'}${Math.abs(g.atenuacion_db).toFixed(1)} dB (${g.clase}). Equivale a alejar el RX ≈ ×${g.factor_distancia.toFixed(1)} con n = 2.</li>`).join('')
    + `<li class="muted">Diferencias menores a ~2 dB están dentro de la variación por fading y no son concluyentes. La señal conserva su forma: solo pierde energía.</li>`
    : '<li class="muted">Mide LOS y al menos un obstáculo.</li>';
  $('#obstGrp tbody').innerHTML = t.length ? t.map(g => `<tr><td class="k" style="font-family:var(--sans)">${esc(g.cond)}</td><td>${g.p_db.toFixed(2)}</td><td>${g.std_db.toFixed(2)}</td><td>${g.n}</td>
    <td>${g.cond === 'LOS' ? '—' : g.atenuacion_db.toFixed(1) + ' ± ' + g.err_db.toFixed(1)}</td><td>${g.clase}</td><td>${g.cond === 'LOS' ? '—' : '×' + g.factor_distancia.toFixed(1)}</td></tr>`).join('')
    : '<tr><td colspan="7" class="muted c">Sin datos o falta LOS.</td></tr>';
  $('#obstTable tbody').innerHTML = r.filas.length ? r.filas.map((f, i) => `<tr><td>${i + 1}</td><td style="font-family:var(--sans)">${esc(f.cond)}</td><td>${f.d}</td><td>${f.p_db.toFixed(2)}</td>
    <td>${f.std_db.toFixed(2)}</td><td>${f.n}</td><td>${f.snr_db.toFixed(1)}</td><td>${estadoTag(f, r.firma_actual)}</td><td>${delBtn('obstruccion', f.id)}</td></tr>`).join('')
    : '<tr><td colspan="9" class="muted c">Sin mediciones.</td></tr>';
}

// ------------------------------------------------------------------ 06a fading
let plan = null;
async function actualizarPlanFad() {
  plan = await api.fad_plan(P);
  P.fad_idx = Math.max(0, Math.min(P.fad_idx || 0, plan.n_pos - 1));
  $('#posOut').textContent = `${P.fad_idx + 1} / ${plan.n_pos} · ${(P.fad_idx * plan.paso_m * 100).toFixed(1)} cm`;
  $('#pasoCm').textContent = (plan.paso_m * 100).toFixed(1) + ' cm (λ/' + P.fad_frac + ')';
}
function pintarFad(r) {
  coherencia('fading', r);
  const f = r.filas, s = r.stats;
  const pl = r.plan;
  const x = f.map(a => a.pos_m * 100), y = f.map(a => a.p_db);
  if (s) kpis($('#fadKpis'), [
    ['λ', num(s.lambda_cm, 1), 'cm'], ['Paso', num(pl.paso_m * 100, 1), 'cm', 'acc'], ['Posiciones', f.length, '/ ' + pl.n_pos],
    ['σ de la potencia', num(s.sigma_db, 2), 'dB'], ['Fade máximo', num(s.fade_max_db, 1), 'dB bajo mediana', s.fade_max_db > 10 ? 'bad' : 'warn'],
    ['Pico a pico', num(s.pico_pico_db, 1), 'dB'], ['Factor K', num(s.K, 1), s.K_db != null ? `(${num(s.K_db, 1)} dB)` : '', 'acc'],
    ['Modelo', s.K > 1 ? 'Rice' : 'Rayleigh', '', s.K > 1 ? 'good' : 'warn']]);
  else kpis($('#fadKpis'), [['λ', num(pl.lambda_m * 100, 1), 'cm'], ['Paso', num(pl.paso_m * 100, 1), 'cm', 'acc'],
    ['Posiciones medidas', f.length, '/ ' + pl.n_pos], ['Estadística', '≥ 8 posiciones', '', 'warn']]);
  Plot.line($('#cFadPos'), {
    series: [{ x, y, color: C().cyan, points: true, r: 3.5, width: 1.5 }],
    hlines: s ? [{ y: s.mediana_db, color: C().amber }, { y: s.mediana_db - 10, color: C().red }] : [], xlabel: 'posición del RX (cm)', ylabel: 'P (dB)'
  });
  if (s && r.hist) {
    const h = r.hist;
    Plot.line($('#cFadHist'), {
      series: [{ x: h.centros, y: h.densidad, color: C().violet, columns: h.ancho, label: 'medido' },
      { x: h.r, y: h.rayleigh, color: C().amber, label: 'Rayleigh', width: 2 }, { x: h.r, y: h.rice, color: C().cyan, label: `Rice K=${num(h.K, 1)}`, width: 2 }],
      xlabel: 'r = |h| / RMS', ylabel: 'densidad', legendRight: true
    });
    Plot.line($('#cFadRel'), {
      series: [{ x, y: y.map(v => v - s.mediana_db), color: C().green, fill: true, points: true, r: 2.5 }],
      hlines: [{ y: 0, color: C().text }, { y: -10, color: C().red }], xlabel: 'posición (cm)', ylabel: 'dB vs mediana'
    });
  } else ['#cFadHist', '#cFadRel'].forEach(c => Plot.empty($(c), 'mide ≥ 8 posiciones'));
}
async function fadMedir() {
  const r = await llamar($('#btnFadMed'), () => api.fad_medir(P));
  if (!r) return;
  P.fad_idx = Math.min(P.fad_idx + 1, plan.n_pos - 1); guardar(); await actualizarPlanFad(); pintarFad(r);
}

// ------------------------------------------------------------------ 06b canal
function pintarCanal(r) {
  coherencia('canal', r);
  const cs = r.canal, claves = Object.keys(cs);
  const act = cs[P.canal_esc] || cs[claves[claves.length - 1]];
  if (act) {
    const d = act.disp;
    kpis($('#canKpis'), [
      ['Escenario', ESC_NOM[act.esc] || act.esc, '', 'acc'], ['σ<sub>τ</sub> (dispersión RMS)', num(d.tau_rms_ns, 0), 'ns', d.tau_rms_ns > 100 ? 'warn' : 'good'],
      ['Retardo medio', num(d.tau_medio_ns, 0), 'ns'], ['B<sub>c</sub> (coherencia)', d.bc_mhz ? num(d.bc_mhz, 2) : '—', 'MHz'],
      ['Factor K', d.k_db != null ? num(d.k_db, 1) : '—', 'dB'], ['Componentes', act.comps.length, '', 'acc'],
      ['Rizado |H(f)|', num(act.rizado_db, 1), 'dB'], ['Resolución', num(act.resol_ns, 0), 'ns']]);
  } else kpis($('#canKpis'), [['Escenarios', 0, '/ 2', 'warn']]);
  const pdp = [], hf = [];
  claves.forEach(k => {
    const c = cs[k], col = ESC_COL[k] || C().blue, nom = ESC_NOM[k] || k;
    pdp.push({ x: c.tau_ns, y: c.pdp_db, color: col, label: nom, width: 1.8, fill: claves.length === 1 });
    pdp.push({ x: c.comps.map(q => q.tau_ns + 0), y: c.comps.map(q => q.p_rel_db), color: col, pointsOnly: true, r: 5 });
    hf.push({ x: c.f_khz, y: c.h_db, color: col, label: nom, width: 1.8 });
  });
  if (claves.length) {
    Plot.line($('#cCanPdp'), { series: pdp, xlabel: 'retardo (ns)', ylabel: 'potencia relativa (dB)', ylim: [-60, 3], legendRight: true });
    Plot.line($('#cCanH'), { series: hf, xlabel: 'frecuencia (kHz)', ylabel: '|H(f)|² (dB)', legendRight: true });
  } else ['#cCanPdp', '#cCanH'].forEach(c => Plot.empty($(c), 'sin estimaciones'));
  $('#canTable tbody').innerHTML = claves.length ? claves.flatMap(k => cs[k].comps.map((q, i) => `<tr><td style="font-family:var(--sans)"><span style="color:${ESC_COL[k]}">●</span> ${ESC_NOM[k] || k}</td>
    <td>${i + 1}</td><td>${q.tau_ns.toFixed(0)}</td><td>${q.exceso_m.toFixed(1)}</td><td>${q.p_rel_db.toFixed(1)}</td></tr>`)).join('')
    : '<tr><td colspan="5" class="muted c">Sin estimaciones.</td></tr>';
}

// ------------------------------------------------------------------ 07 análisis
async function analisis() {
  const r = await api.analisis(P);
  if (!r.ok) return toast(r.error, true);
  const n = r.n;
  kpis($('#anaChips'), [['Distancia', n.distancia, 'mediciones', n.distancia >= 5 ? 'good' : 'warn'], ['Obstrucciones', n.obstruccion, 'mediciones', n.obstruccion >= 2 ? 'good' : 'warn'],
    ['Fading', n.fading, 'posiciones', n.fading >= 8 ? 'good' : 'warn'], ['Canal', n.canal, '/ 2 escenarios', n.canal >= 2 ? 'good' : 'warn']]);
  const F = r.filas, col = ['#5aa8ff', '#ff9a5c', '#9b8cff', '#ffc25c'];
  const nom = ['Distancia', 'Obstrucción', 'Fading', 'Multitrayecto'];
  Plot.bars($('#cAnaBar'), nom, F.map(f => f.mag_db === null ? null : Math.max(0, f.mag_db)), { colors: col, fmt: v => v.toFixed(1) + ' dB', ylabel: 'dB' });
  $('#anaTable tbody').innerHTML = F.map((f, i) => `<tr><td class="k"><span style="color:${col[i]}">●</span> ${f.efecto}</td><td>${f.escala}</td>
    <td class="num">${f.mag_db === null ? '—' : f.mag_db.toFixed(1) + ' dB'}</td><td class="muted">${f.detalle}</td>
    <td><span class="tag ${f.tipo === 'Hardware' ? 'ok' : f.tipo === 'DSP' ? 'ko' : 'wa'}">${f.tipo}</span></td><td class="muted">${f.como}</td></tr>`).join('');
  const hay = F.filter(f => f.mag_db !== null);
  const L = [];
  if (hay.length) {
    const mayor = hay.reduce((a, b) => b.mag_db > a.mag_db ? b : a);
    L.push(`El efecto de mayor magnitud medido es <b>${mayor.efecto.toLowerCase()}</b> (${mayor.mag_db.toFixed(1)} dB), pero la magnitud no decide la solución: importa si la señal solo pierde energía o también cambia de forma.`);
    L.push('<b>Atenuación (distancia, obstrucciones)</b>: la forma de la señal se conserva; se recupera con más potencia, más ganancia, mejores antenas o reubicando.');
  }
  const fa = F[2], mp = F[3];
  if (fa.mag_db !== null) L.push(`<b>Fading</b>: ${fa.mag_db.toFixed(1)} dB de variación en ≈${(r.fad.lambda_cm / 2).toFixed(0)} cm. Compensarlo con potencia exige un margen enorme; se combate con diversidad (antenas, frecuencia, tiempo) y codificación.`);
  if (mp.mag_db !== null) {
    const c = r.canal.multi || r.canal.los;
    L.push(`<b>Multitrayectoria</b>: σ<sub>τ</sub> = ${c.disp.tau_rms_ns.toFixed(0)} ns ⇒ B<sub>c</sub> ≈ ${c.disp.bc_mhz ? c.disp.bc_mhz.toFixed(2) : '—'} MHz. Una señal con ancho de banda mayor sufrirá interferencia entre símbolos: subir la potencia amplifica también los ecos; hace falta ecualización, OFDM o RAKE.`);
  }
  $('#anaTexto').innerHTML = L.length ? L.map(t => `<li>${t}</li>`).join('') : '<li class="muted">Completa los módulos 04–06.</li>';
}

// ------------------------------------------------------------------ exportar PNG de figuras
function pngButtons() {
  $$('.plot canvas').forEach(cv => {
    const plot = cv.parentElement;
    const b = document.createElement('button');
    b.className = 'pngbtn'; b.textContent = 'PNG'; b.title = 'guardar figura en exportados/';
    b.onclick = async () => {
      const t = (plot.parentElement.querySelector('h3,h2') || plot.closest('.card').querySelector('h3,h2'));
      const nombre = (t ? t.textContent : 'figura').trim();
      const o = document.createElement('canvas'); o.width = cv.width; o.height = cv.height;
      const g = o.getContext('2d'); g.fillStyle = '#0a0f1d'; g.fillRect(0, 0, o.width, o.height); g.drawImage(cv, 0, 0);
      const r = await api.guardar_png(nombre, o.toDataURL('image/png'));
      toast(r.ok ? 'Figura guardada: ' + r.ruta : r.error, !r.ok);
    };
    plot.appendChild(b);
  });
}

// ------------------------------------------------------------------ init
function conectar() {
  $$('nav a').forEach(a => a.onclick = () => irA(a.dataset.page));
  $('#btnVerTx').onclick = e => verificar(e.currentTarget, 'tx');
  $('#btnVerRx').onclick = e => verificar(e.currentTarget, 'rx');
  $('#btnVerEnlace').onclick = e => verificar(e.currentTarget, 'enlace');
  $('#btnFile').onclick = async () => { const f = await api.elegir_archivo(); if (f) { P.archivo_rx = f; guardar(); pintarControles(); } };
  $('#btnTxGo').onclick = txGo;
  $('#btnTxStop').onclick = async () => { await api.tx_detener(); txEstado(); };
  $('#btnRx').onclick = rxCapturar;
  $('#rxLoop').onchange = e => { if (e.target.checked) rxCapturar(); };
  $('#rxSel').onchange = async e => { const d = await api.rx_detalle(+e.target.value); if (d) pintarDetalle(d); };
  // 04
  $('#btnDistMed').onclick = async e => { const r = await llamar(e.currentTarget, () => api.dist_medir(P)); if (r) pintarDist(r); };
  $('#btnDistClr').onclick = async () => { await api.limpiar('distancia'); cargarPagina('dist'); };
  $('#btnDistCsv').onclick = () => exportar('distancia');
  // 05
  $('#obstChips').innerHTML = ['LOS', 'Pared', 'Persona', 'Metal', 'Vidrio', 'Puerta'].map(c => `<button class="chip" data-chip="${c}">${c}</button>`).join('');
  $('#obstChips').onclick = e => { const c = e.target.closest('[data-chip]'); if (c) { P.obst_cond = c.dataset.chip; guardar(); pintarControles(); } };
  $('#btnObstMed').onclick = async e => { const r = await llamar(e.currentTarget, () => api.obst_medir(P)); if (r) pintarObst(r); };
  $('#btnObstClr').onclick = async () => { await api.limpiar('obstruccion'); cargarPagina('obst'); };
  $('#btnObstCsv').onclick = () => exportar('obstruccion');
  // 06
  $('#btnPosPrev').onclick = () => { P.fad_idx = Math.max(0, P.fad_idx - 1); guardar(); actualizarPlanFad(); };
  $('#btnPosNext').onclick = () => { P.fad_idx = Math.min(plan.n_pos - 1, P.fad_idx + 1); guardar(); actualizarPlanFad(); };
  $('#btnFadMed').onclick = fadMedir;
  $('#btnFadSim').onclick = async e => { const r = await llamar(e.currentTarget, () => api.fad_barrido_sim(P)); if (r) pintarFad(r); };
  $('#btnFadClr').onclick = async () => { await api.limpiar('fading'); P.fad_idx = 0; await actualizarPlanFad(); cargarPagina('canal'); };
  $('#btnFadCsv').onclick = () => exportar('fading');
  $('#btnCanMed').onclick = async e => { const r = await llamar(e.currentTarget, () => api.canal_medir(P)); if (r) pintarCanal(r); };
  $('#btnCanClr').onclick = async () => { const k = P.canal_esc; await api.borrar('canal', k); cargarPagina('canal'); };
  $('#btnCanCsv').onclick = () => exportar('canal');
  // 07
  $('#btnAna').onclick = analisis;
  $$('[data-csv]').forEach(b => b.onclick = () => exportar(b.dataset.csv));
  document.addEventListener('click', async e => {
    const d = e.target.closest('[data-del]'); if (!d) return;
    const [clave, id] = d.dataset.del.split(':');
    await api.borrar(clave, id); cargarPagina(paginaActual());
  });
}
async function exportar(clave) {
  const r = await api.exportar_csv(clave);
  toast(r.ok ? 'CSV guardado: ' + r.ruta : r.error, !r.ok);
}

async function init() {
  api = window.pywebview.api;
  const def = await api.defaults();
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem('p3_params') || '{}'); } catch (e) { }
  P = { ...def, ...saved };
  conectar(); bindControles(); pintarControles(); pngButtons(); Guia.iniciar();
  irA('guia');
}
window.addEventListener('pywebviewready', init);
