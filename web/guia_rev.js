// Paradas de revisión del laboratorio guiado: gráficas y valores de cada punto del enunciado.
// Cada función dibuja en `el` y devuelve true si hay datos suficientes para dar el punto por revisado.
const Revision = (() => {
  const plots = lista => `<div class="grid g2">${lista.map(([id, t, ancho]) =>
    `<div class="card ${ancho ? 'span2' : ''}"><h3>${t}</h3><div class="plot tall"><canvas id="${id}"></canvas></div></div>`).join('')}</div>`;
  const tabla = (cab, filas) => `<div class="card"><div class="table-wrap scroll"><table class="tbl mono"><thead><tr>${cab.map(c => `<th>${c}</th>`).join('')}</tr></thead>
    <tbody>${filas.map(f => `<tr>${f.map(c => `<td>${c}</td>`).join('')}</tr>`).join('')}</tbody></table></div></div>`;
  const explica = a => `<div class="theory"><b>Para explicarlo</b><ul>${a.map(t => `<li>${t}</li>`).join('')}</ul></div>`;
  const falta = (el, t) => { el.innerHTML = `<div class="verdict warn"><div>Faltan datos<small>${t}</small></div></div>`; return false; };
  const aviso = r => r.aviso ? `<p class="note wa">${esc(r.aviso)}</p>` : '';
  const caja = (el, html) => { el.innerHTML = `<div class="grid g1">${html}</div>`; };

  async function senal(el, vigente) {
    const r = await api.info_senal(P);
    if (!vigente()) return false;
    if (!r.ok) return falta(el, esc(r.error));
    const s = r.resumen;
    caja(el, `<div class="kpis" id="rvK"></div>` + explica([
      `Ráfaga: secuencia Zadoff-Chu de N = ${s.n_zc} (raíz ${P.raiz}) repetida ${s.n_rep} veces, una cada ${P.periodo_ms} ms.`,
      'Amplitud constante: la potencia se mide bien y no satura. Autocorrelación en impulso: permite localizar la ráfaga y estimar el canal.',
      'Las repeticiones permiten detectar y estimar el offset de frecuencia; el silencio sirve para medir el ruido.']) +
      plots([['rvTren', 'Transmisión periódica (3 periodos)', true], ['rvAc', 'Autocorrelación periódica (dB)'], ['rvMf', 'Filtro adaptado sobre la ráfaga (dB)']]));
    kpis($('#rvK'), [['f<sub>c</sub>', fmtHz(P.fc), '', 'acc'], ['f<sub>s</sub> real', fmtRate(s.fs_real, 'Sps')], ['Ráfaga', num(s.t_rafaga_us, 0), 'µs'],
      ['Ganancia de procesado', num(s.gp_db), 'dB'], ['Resolución', num(s.resol_t_ns, 0), 'ns']]);
    Plot.line($('#rvTren'), { series: [{ x: r.tren.t, y: r.tren.v, color: C().cyan, fill: true }], xlabel: 't (ms)', ylabel: '|x|', ylim: [0, 1] });
    Plot.line($('#rvAc'), { series: [{ x: r.acorr.lag, y: r.acorr.db, color: C().green, stem: true, r: 2.2 }], xlabel: 'desplazamiento (muestras)', ylabel: 'dB', ylim: [-85, 5] });
    Plot.line($('#rvMf'), { series: [{ x: r.mf.lag, y: r.mf.db, color: C().cyan, fill: true }], xlabel: 'lag (muestras)', ylabel: 'dB', ylim: [-60, 3] });
    return true;
  }

  // r es el resultado de api.rx_capturar
  function rx(el, r) {
    if (!r.rafagas.length) return falta(el, 'No se detectó ninguna ráfaga: comprueba el transmisor y vuelve a capturar.');
    const rs = r.rafagas, media = k => rs.reduce((a, x) => a + x[k], 0) / rs.length;
    // la potencia media se promedia en lineal, igual que en logica/potencia.py
    const pMed = 10 * Math.log10(rs.reduce((a, x) => a + 10 ** (x.p_dbfs / 10), 0) / rs.length);
    caja(el, `<div class="kpis" id="rvK"></div>` + explica([
      'Detección automática: se compara cada copia con la siguiente (métrica M(d)); no depende del offset de frecuencia.',
      'Potencia de cada ráfaga = potencia total − piso de ruido medido en el silencio.']) +
      plots([['rvEnv', 'Muestras I/Q capturadas: envolvente y métrica de detección', true], ['rvPsd', 'Espectro de la captura', true]]) +
      tabla(['#', 't (ms)', 'M', 'CFO (Hz)', 'P señal (dBFS)', 'SNR (dB)'],
        rs.map((x, i) => [i + 1, x.t_ms.toFixed(2), x.M.toFixed(2), x.cfo_hz.toFixed(0), x.p_dbfs.toFixed(2), x.snr_db.toFixed(1)])));
    kpis($('#rvK'), [['Ráfagas detectadas', r.n_det, `/ ${r.n_esp} esp.`, 'acc'], ['Potencia media', num(pMed), 'dBFS'], ['SNR media', num(media('snr_db')), 'dB'], ['Piso de ruido', num(r.ruido_dbfs), 'dBFS']]);
    plotCaptura('#rvEnv', '#rvPsd', r);
    return true;
  }

  async function dist(el, vigente) {
    const r = await api.dist_listar(P);
    if (!vigente()) return false;
    const aj = r.ajuste;
    if (!aj) return falta(el, 'Se necesitan medidas válidas en al menos 2 distancias distintas.');
    const ok = r.filas.filter(f => f.valido);
    caja(el, aviso(r) + `<div class="kpis" id="rvK"></div>` + explica([
      `Modelo ajustado: <b>P(d) = ${num(aj.p0)} − 10·${num(aj.n, 2)}·log₁₀(d)</b> dB. ${esc(aj.interpreta)}`,
      `Comparación con las medidas: desviación σ = ${num(aj.sigma, 2)} dB y R² = ${num(aj.r2, 3)}.`,
      ok.length < 5 ? 'Con menos de 5 puntos el exponente tiene mucha incertidumbre: conviene medir más distancias.' : `Incertidumbre del exponente: ±${num(aj.ic95, 2)}.`]) +
      plots([['rvDist', 'Potencia recibida vs distancia', true]]) +
      tabla(['d (m)', 'medido (dB)', 'modelo (dB)', 'residuo (dB)'], ok.map(f => [f.d, f.p_db.toFixed(2), (f.p_db - f.residuo_db).toFixed(2), sgn(f.residuo_db, 2)])));
    kpis($('#rvK'), [['Exponente n', num(aj.n, 2), '', 'acc'], ['P₀ (1 m)', num(aj.p0), 'dB'], ['σ', num(aj.sigma, 2), 'dB'], ['R²', num(aj.r2, 3)]]);
    Plot.line($('#rvDist'), {
      series: [{ x: r.curva.d, y: r.curva.p, color: C().cyan, label: `modelo n=${num(aj.n, 2)}` }, { x: r.curva.d, y: r.curva.p_fs, color: C().amber, dash: [6, 4], label: 'n = 2' },
        { x: ok.map(f => f.d), y: ok.map(f => f.p_db), color: C().violet, pointsOnly: true, r: 4.5, label: 'medido' }], xlabel: 'distancia (m)', ylabel: 'P (dB)'
    });
    return true;
  }

  async function obst(el, vigente) {
    const r = await api.obst_listar(P);
    if (!vigente()) return false;
    const otras = r.tabla.filter(g => g.cond !== 'LOS');
    if (!r.hay_los || !otras.length) return falta(el, 'Se necesita la referencia LOS y al menos un obstáculo.');
    const orden = [...otras].sort((a, b) => b.atenuacion_db - a.atenuacion_db);
    caja(el, aviso(r) + explica([
      `El que más atenúa es <b>${esc(orden[0].cond)}</b> (${num(orden[0].atenuacion_db)} dB).`,
      'Una obstrucción resta energía: a la misma distancia baja la potencia y la SNR. Se compensa con potencia, ganancia o reubicando.',
      'Diferencias menores a unos 2 dB no son concluyentes.']) +
      plots([['rvObst', 'Atenuación respecto a LOS (dB)', true]]) +
      tabla(['Condición', 'P (dB)', 'σ (dB)', 'Atenuación (dB)', 'Clase'],
        r.tabla.map(g => [esc(g.cond), g.p_db.toFixed(2), g.std_db.toFixed(2), g.cond === 'LOS' ? '—' : g.atenuacion_db.toFixed(1), g.clase])));
    Plot.bars($('#rvObst'), otras.map(g => g.cond), otras.map(g => Math.max(0, g.atenuacion_db)),
      { err: otras.map(g => g.err_db), colors: otras.map(g => CLASE_COL[g.clase]), fmt: v => v.toFixed(1) + ' dB', ylabel: 'atenuación (dB)' });
    return true;
  }

  async function fad(el, vigente, d) {
    const [r, rd] = await Promise.all([api.fad_listar(P), api.dist_listar(P)]);
    if (!vigente()) return false;
    const s = r.stats;
    if (!s) return falta(el, 'Se necesitan al menos 8 posiciones medidas.');
    const x = r.filas.map(f => f.pos_m * 100), y = r.filas.map(f => f.p_db), largo = Math.max(...x) / 100;
    const n = rd.ajuste ? rd.ajuste.n : 2, porDist = 10 * Math.abs(n) * Math.log10((d + largo) / d);
    caja(el, `<div class="kpis" id="rvK"></div>` + explica([
      `Al mover el RX ${num(largo * 100, 0)} cm la potencia varió <b>${num(s.pico_pico_db)} dB</b>. Por pérdida de propagación, alejarse eso desde ${d} m daría como mucho ${num(porDist)} dB (n = ${num(n, 2)}).`,
      'El desvanecimiento es interferencia entre caminos y cambia en centímetros (≈ λ/2); la pérdida de propagación es una tendencia suave en metros.',
      `Distribución más compatible: ${esc(s.tipo)}, K = ${num(s.K)}.`]) +
      plots([['rvFad', 'Potencia recibida vs posición', true], ['rvHist', 'Distribución de la envolvente', true]]));
    kpis($('#rvK'), [['λ', num(s.lambda_cm), 'cm'], ['Pico a pico', num(s.pico_pico_db), 'dB', 'acc'], ['σ', num(s.sigma_db, 2), 'dB'], ['Fade máximo', num(s.fade_max_db), 'dB']]);
    Plot.line($('#rvFad'), { series: [{ x, y, color: C().cyan, points: true, r: 3.5 }], hlines: [{ y: s.mediana_db, color: C().amber }], xlabel: 'posición (cm)', ylabel: 'P (dB)' });
    const h = r.hist;
    Plot.line($('#rvHist'), {
      series: [{ x: h.centros, y: h.densidad, color: C().violet, columns: h.ancho, label: 'medido' }, { x: h.r, y: h.rayleigh, color: C().amber, label: 'Rayleigh' },
        { x: h.r, y: h.rice, color: C().cyan, label: 'Rice' }], xlabel: 'r = |h| / RMS', ylabel: 'densidad', legendRight: true
    });
    return true;
  }

  async function canal(el, vigente) {
    const r = await api.canal_listar(P);
    if (!vigente()) return false;
    const { los, multi } = r.canal;
    if (!los || !multi) return falta(el, 'Se necesitan los dos escenarios: línea de vista y multitrayectoria.');
    const par = [['los', los], ['multi', multi]];
    caja(el, explica([
      'Estimación: H = Y / X con la secuencia conocida; la IFFT da la respuesta al impulso.',
      `Dispersión de retardo: ${num(los.disp.tau_rms_ns, 0)} ns en LOS y ${num(multi.disp.tau_rms_ns, 0)} ns con multitrayectoria; rizado de ${num(los.rizado_db)} y ${num(multi.rizado_db)} dB.`,
      `Cada pico del perfil es una componente. Ecos separados menos de ${num(los.resol_ns, 0)} ns no se distinguen.`]) +
      plots([['rvPdp', 'Perfil de potencia-retardo (dB)', true], ['rvH', 'Respuesta en frecuencia |H(f)| (dB)', true]]) +
      tabla(['Escenario', '#', 'Retardo (ns)', 'Camino extra (m)', 'Potencia rel. (dB)'],
        par.flatMap(([k, c]) => c.comps.map((q, i) => [ESC_NOM[k], i + 1, q.tau_ns.toFixed(0), q.exceso_m.toFixed(1), q.p_rel_db.toFixed(1)]))));
    Plot.line($('#rvPdp'), { series: par.map(([k, c]) => ({ x: c.tau_ns, y: c.pdp_db, color: ESC_COL[k], label: ESC_NOM[k] })), xlabel: 'retardo (ns)', ylabel: 'dB', ylim: [-60, 3], legendRight: true });
    Plot.line($('#rvH'), { series: par.map(([k, c]) => ({ x: c.f_khz, y: c.h_db, color: ESC_COL[k], label: ESC_NOM[k] })), xlabel: 'frecuencia (kHz)', ylabel: 'dB', legendRight: true });
    return true;
  }

  async function final(el, vigente) {
    const r = await api.analisis(P);
    if (!vigente()) return false;
    if (!r.ok) return falta(el, esc(r.error));
    const F = r.filas;
    caja(el, plots([['rvAna', 'Magnitud de cada efecto (dB)', true]]) +
      `<div class="card"><div class="table-wrap"><table class="tbl"><thead><tr><th>Efecto</th><th>Escala</th><th>Magnitud</th><th>Resultado medido</th><th>Se compensa con</th><th>Cómo</th></tr></thead><tbody>
      ${F.map(f => `<tr><td class="k">${esc(f.efecto)}</td><td>${esc(f.escala)}</td><td class="num">${f.mag_db === null ? '—' : f.mag_db.toFixed(1) + ' dB'}</td>
        <td>${esc(f.detalle)}</td><td>${esc(f.tipo)}</td><td>${esc(f.como)}</td></tr>`).join('')}</tbody></table></div></div>` +
      explica(['<b>Con potencia o ganancia</b> se compensan distancia y obstrucciones: la señal solo pierde energía.',
        '<b>Requieren procesamiento</b> el desvanecimiento (diversidad, codificación) y la multitrayectoria (ecualización, OFDM, RAKE): subir potencia amplifica también los ecos.']));
    Plot.bars($('#rvAna'), ['Distancia', 'Obstrucción', 'Fading', 'Multitrayecto'], F.map(f => f.mag_db === null ? null : Math.max(0, f.mag_db)),
      { colors: ['#5aa8ff', '#ff9a5c', '#9b8cff', '#ffc25c'], fmt: v => v.toFixed(1) + ' dB', ylabel: 'dB' });
    return F.every(f => f.mag_db !== null);
  }

  return { senal, rx, dist, obst, fad, canal, final };
})();
