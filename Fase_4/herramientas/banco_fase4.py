"""
Banco de pruebas sin GUI ni hardware para la Fase 4.

Tx Fase 4 (1 MS/s) -> [deriva de reloj opcional] -> x8 a 8 MS/s -> desplazado +lo_offset
   -> cadena del Receptor Fase 4 (mismos bloques y parametros; los epy se cargan
      de los .py generados por grcc) -> e_EbN0_Sweep / e_BER_Curve / e_BER_CSV / e_Texto_Rx

Uso: python banco_fase4.py <dir_grcc_rx> <modo> [opciones]
  modo: calibrar | barrido | deriva
"""
import argparse
import importlib.util
import math
import sys
import time

import numpy as np
from gnuradio import analog, blocks, digital, filter, gr
from gnuradio.fft import window
from gnuradio.filter import firdes

ap = argparse.ArgumentParser()
ap.add_argument('dir_rx')
ap.add_argument('modo', choices=['calibrar', 'barrido', 'deriva'])
ap.add_argument('--pn9', type=int, default=0)
ap.add_argument('--ppm', type=float, default=0.0)
ap.add_argument('--delay_bits', type=int, default=0)
ap.add_argument('--ebn0_min', type=float, default=0.0)
ap.add_argument('--ebn0_max', type=float, default=14.0)
ap.add_argument('--bits_por_punto', type=int, default=100000)
ap.add_argument('--bits_guardia', type=int, default=1000)
ap.add_argument('--segundos', type=float, default=None, help='tiempo de senal simulado')
ap.add_argument('--sample_delay', type=int, default=50)
ap.add_argument('--ebn0_fijo', type=float, default=30.0)
ap.add_argument('--cf_cut', type=float, default=60e3)
ap.add_argument('--cf_trans', type=float, default=40e3)
ap.add_argument('--sync', choices=['manual', 'symsync'], default='manual')
ap.add_argument('--post', choices=['lpf', 'ma'], default='lpf', help='lpf = data_filter actual; ma = integrador (Fase 2)')
ap.add_argument('--loop_bw', type=float, default=0.02)
ap.add_argument('--max_dev', type=float, default=1.5)
ap.add_argument('--align', choices=['delay', 'auto'], default='delay')
ap.add_argument('--foff', type=float, default=0.0, help='error de frecuencia residual [Hz]')
ap.add_argument('--tag', default='')
a = ap.parse_args()


def cargar(nombre):
    spec = importlib.util.spec_from_file_location(
        nombre, f'{a.dir_rx}/Receptor_FSK_HackRF_Fase4_{nombre}.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


tt = cargar('trama_telemetria')
e_sweep = cargar('e_EbN0_Sweep')
e_curve = cargar('e_BER_Curve')
e_csv = cargar('e_BER_CSV')
e_texto = cargar('e_Texto_Rx')

# Parametros del Rx Fase 4
hackrf_rate, decim = 8e6, 8
samp_rate = hackrf_rate / decim
sps = 100
symbol_rate = samp_rate / sps
fsk_deviation = 20e3
lo_offset, freq_corr = 200e3, 0.0
mensaje = "ID:S01;T:24.5C;HR:15%;ALT:2500msnm;P:184kPa;NIV:72%;Q:3.4m3/h"
trama = tt.construir_trama(mensaje, a.pn9)

npts = int(round((a.ebn0_max - a.ebn0_min) / 1.0)) + 1
bits_barrido = npts * (a.bits_guardia + a.bits_por_punto)
segundos = a.segundos if a.segundos else bits_barrido / symbol_rate + 0.5
n_tx = int(segundos * samp_rate)

tb = gr.top_block()

# ---- Tx Fase 4 (igual que Transmisor_FSK_USRP_Fase4) ----
bit_source = blocks.vector_source_b(trama, True, 1, [])
nrz = digital.chunks_to_symbols_bf([-1.0, 1.0], 1)
rep = blocks.repeat(gr.sizeof_float, sps)
fm = analog.frequency_modulator_fc(2 * math.pi * fsk_deviation / samp_rate)
amp = blocks.multiply_const_cc(0.7)
head = blocks.head(gr.sizeof_gr_complex, n_tx)
tb.connect(bit_source, nrz, rep, fm, amp, head)
ultimo = head

# ---- Deriva de reloj: el Tx corre (1 + ppm) mas rapido que el Rx ----
if a.ppm:
    deriva = filter.mmse_resampler_cc(0.0, 1.0 + a.ppm * 1e-6)
    tb.connect(ultimo, deriva)
    ultimo = deriva

# ---- "Canal": a 8 MS/s y desplazado +lo_offset (lo que ve el HackRF) ----
up = filter.rational_resampler_ccc(interpolation=8, decimation=1, taps=[], fractional_bw=0.4)
lo = analog.sig_source_c(hackrf_rate, analog.GR_COS_WAVE, lo_offset + a.foff, 1.0, 0)
mix = blocks.multiply_cc()
tb.connect(ultimo, up, (mix, 0))
tb.connect(lo, (mix, 1))

# ---- Receptor Fase 4 ----
rate_adapt = filter.freq_xlating_fir_filter_ccc(
    decim, firdes.low_pass(1.0, hackrf_rate, 300e3, 100e3), lo_offset + freq_corr, hackrf_rate)

if a.modo == 'barrido':
    emin, emax = a.ebn0_min, a.ebn0_max
else:  # condicion "limpia": un solo punto a 30 dB
    emin = emax = a.ebn0_fijo
npts = int(round((emax - emin) / 1.0)) + 1

sweep = e_sweep.blk(EbN0_min=emin, EbN0_max=emax, EbN0_step=1.0, samp_rate=samp_rate,
                    bit_rate=symbol_rate, bits_por_punto=a.bits_por_punto,
                    bits_guardia=a.bits_guardia, signal_power=0.0, seed=2026)
channel_filter = filter.fir_filter_ccf(1, firdes.low_pass(1.0, samp_rate, a.cf_cut, a.cf_trans, window.WIN_HAMMING, 6.76))
demod = analog.quadrature_demod_cf(samp_rate / (2 * math.pi * fsk_deviation))
dc = filter.dc_blocker_ff(3200, True)
if a.post == 'lpf':
    data_filter = filter.fir_filter_fff(1, firdes.low_pass(1, samp_rate, symbol_rate, symbol_rate / 2, window.WIN_HAMMING, 6.76))
else:
    data_filter = blocks.moving_average_ff(sps, 1.0 / sps, 4000, 1)
if a.sync == 'manual':
    muestreo = [blocks.delay(gr.sizeof_float, a.sample_delay), blocks.keep_one_in_n(gr.sizeof_float, sps)]
else:
    muestreo = [digital.symbol_sync_ff(digital.TED_GARDNER, sps, a.loop_bw, 1.0, 1.0, a.max_dev, 1,
                                       digital.constellation_bpsk().base(), digital.IR_MMSE_8TAP, 128, [])]
slicer = digital.binary_slicer_fb()
tb.connect(mix, rate_adapt, (sweep, 0))
tb.connect((sweep, 0), channel_filter, demod, dc, data_filter, *muestreo, slicer)
tb.connect((sweep, 1), blocks.null_sink(gr.sizeof_float))

if a.align == 'delay':
    ref = blocks.vector_source_b(trama, True, 1, [])
    delay_bits = a.delay_bits
else:
    spec = importlib.util.spec_from_file_location('e_ref', f'{a.dir_rx}/Receptor_FSK_HackRF_Fase4_e_Ref_Alineada.py')
    e_ref = importlib.util.module_from_spec(spec); spec.loader.exec_module(e_ref)
    ref = e_ref.blk(trama=trama)
    tb.connect(slicer, ref)
    delay_bits = 0
curve = e_curve.blk(EbN0_min=emin, EbN0_max=emax, EbN0_step=1.0, bits_por_punto=a.bits_por_punto,
                    bits_guardia=a.bits_guardia, delay_bits=delay_bits, update_every=1000)
csv_b = e_csv.blk(EbN0_min=emin, EbN0_max=emax, EbN0_step=1.0, nombre_archivo=f'curva_BER{a.tag}.csv', guardar_cada=2.0)
texto = e_texto.blk(mensaje=mensaje, pn9=a.pn9, max_errores_sincronia=2, imprimir_cada=1e9)
tb.connect(ref, (curve, 0))
tb.connect(slicer, (curve, 1))
tb.connect((curve, 0), (csv_b, 0))
tb.connect((curve, 1), (csv_b, 1))
tb.connect(slicer, texto)

sink_rx = blocks.vector_sink_b()
sink_ber = blocks.vector_sink_f(npts)
tb.connect(slicer, sink_rx)
tb.connect((curve, 0), sink_ber)

t0 = time.time()
tb.run()
print(f'[{a.modo}{a.tag}] sync={a.sync} post={a.post} cf={a.cf_cut:.0f}/{a.cf_trans:.0f} align={a.align} pn9={a.pn9} ppm={a.ppm} foff={a.foff} delay_bits={a.delay_bits} | {segundos:.1f} s de senal en {time.time()-t0:.1f} s')

rx = np.array(sink_rx.data(), dtype=np.int8)
L = len(trama)
tr = np.array(trama, dtype=np.int8)
print(f'bits Rx: {len(rx)} | texto: {texto.estado()} | ultimo: {texto.texto()}')


def mejor_retardo(seg):
    """delay_bits d tal que rx[n] == ref[n-d] (ref periodica, ref[0] = inicio de trama)."""
    n = np.arange(len(seg[0]))
    mejores = []
    for d in range(L):
        err = np.mean(seg[1] != tr[(seg[0] - d) % L])
        mejores.append(err)
    d = int(np.argmin(mejores))
    return d, mejores[d]


if a.modo in ('calibrar', 'deriva'):
    idx = np.arange(len(rx))
    ini = 2000  # saltar el transitorio inicial
    d, e = mejor_retardo((idx[ini:], rx[ini:]))
    print(f'Retardo estimado: delay_bits = {d} (BER con ese retardo = {e:.2e})')
    if a.modo == 'deriva':
        print('Evolucion en ventanas de 1 s (retardo optimo y BER con el retardo inicial):')
        d0 = None
        for k in range(0, len(rx) - 10000 + 1, 10000):
            w = slice(max(k, ini), k + 10000)
            dk, ek = mejor_retardo((idx[w], rx[w]))
            d0 = dk if d0 is None else d0
            e0 = np.mean(rx[w] != tr[(idx[w] - d0) % L])
            print(f'  t={k/symbol_rate:5.1f}-{(k+10000)/symbol_rate:5.1f} s: retardo optimo {dk:3d} | BER con delay_bits fijo={d0}: {e0:.3f}')

ber = np.array(sink_ber.data(), dtype=np.float64).reshape(-1, npts)[-1]
print('Curva (ultimo vector de e_BER_Curve):')
for i, b in enumerate(ber):
    print(f'  Eb/N0 = {emin + i:4.1f} dB -> BER = {b:.3e}  (bits contados {curve.count[i]}, errores {curve.errors[i]})')
print('CSV en:', csv_b.ruta_csv)

if a.tag:
    import shutil
    shutil.copy(csv_b.ruta_csv, f'curva{a.tag}.csv')
if a.align == 'auto':
    print(f'e_Ref_Alineada: {ref.cambios} correcciones, desfase final {ref.desfase}')
