#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: Receptor FSK - HackRF One (Fase 4 v2: medicion BER, Rx liviano)
# Description: Receptor FSK con instrumentacion BER (e_EbN0_Sweep + e_BER_Curve) y verificacion del texto de telemetria
# GNU Radio version: 3.10.12.0

from PyQt5 import Qt
from gnuradio import qtgui
from PyQt5 import QtCore
from gnuradio import analog
import math
from gnuradio import blocks
from gnuradio import digital
from gnuradio import filter
from gnuradio import eng_notation
from gnuradio.filter import firdes
from gnuradio import gr
from gnuradio.fft import window
import sys
import signal
from PyQt5 import Qt
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
import Receptor_FSK_HackRF_Fase4_v2_e_BER_CSV as e_BER_CSV  # embedded python block
import Receptor_FSK_HackRF_Fase4_v2_e_BER_Curve as e_BER_Curve  # embedded python block
import Receptor_FSK_HackRF_Fase4_v2_e_EbN0_Sweep as e_EbN0_Sweep  # embedded python block
import Receptor_FSK_HackRF_Fase4_v2_e_Ref_Alineada as e_Ref_Alineada  # embedded python block
import Receptor_FSK_HackRF_Fase4_v2_e_Texto_Rx as e_Texto_Rx  # embedded python block
import Receptor_FSK_HackRF_Fase4_v2_trama_telemetria as trama_telemetria  # embedded python module
import osmosdr
import time
import sip
import threading



class Receptor_FSK_HackRF_Fase4_v2(gr.top_block, Qt.QWidget):

    def __init__(self):
        gr.top_block.__init__(self, "Receptor FSK - HackRF One (Fase 4 v2: medicion BER, Rx liviano)", catch_exceptions=True)
        Qt.QWidget.__init__(self)
        self.setWindowTitle("Receptor FSK - HackRF One (Fase 4 v2: medicion BER, Rx liviano)")
        qtgui.util.check_set_qss()
        try:
            self.setWindowIcon(Qt.QIcon.fromTheme('gnuradio-grc'))
        except BaseException as exc:
            print(f"Qt GUI: Could not set Icon: {str(exc)}", file=sys.stderr)
        self.top_scroll_layout = Qt.QVBoxLayout()
        self.setLayout(self.top_scroll_layout)
        self.top_scroll = Qt.QScrollArea()
        self.top_scroll.setFrameStyle(Qt.QFrame.NoFrame)
        self.top_scroll_layout.addWidget(self.top_scroll)
        self.top_scroll.setWidgetResizable(True)
        self.top_widget = Qt.QWidget()
        self.top_scroll.setWidget(self.top_widget)
        self.top_layout = Qt.QVBoxLayout(self.top_widget)
        self.top_grid_layout = Qt.QGridLayout()
        self.top_layout.addLayout(self.top_grid_layout)

        self.settings = Qt.QSettings("gnuradio/flowgraphs", "Receptor_FSK_HackRF_Fase4_v2")

        try:
            geometry = self.settings.value("geometry")
            if geometry:
                self.restoreGeometry(geometry)
        except BaseException as exc:
            print(f"Qt GUI: Could not restore geometry: {str(exc)}", file=sys.stderr)
        self.flowgraph_started = threading.Event()

        ##################################################
        # Variables
        ##################################################
        self.hackrf_rate = hackrf_rate = 4e6
        self.decim = decim = 4
        self.sps = sps = 100
        self.samp_rate = samp_rate = hackrf_rate/decim
        self.texto_probe = texto_probe = ""
        self.symbol_rate = symbol_rate = samp_rate/sps
        self.pn9 = pn9 = 1
        self.mensaje = mensaje = "ID:S01;T:24.5C;HR:15%;ALT:2500msnm;P:184kPa;NIV:72%;Q:3.4m3/h"
        self.estado_probe = estado_probe = ""
        self.EbN0_step = EbN0_step = 1.0
        self.EbN0_min = EbN0_min = 0
        self.EbN0_max = EbN0_max = 18
        self.vga_gain = vga_gain = 20
        self.update_every = update_every = 1000
        self.trama_bits = trama_bits = trama_telemetria.construir_trama(mensaje, pn9)
        self.texto_rx = texto_rx = texto_probe
        self.lo_offset = lo_offset = 200000
        self.lna_gain = lna_gain = 16
        self.fsk_deviation = fsk_deviation = 20e3
        self.freq_corr = freq_corr = -6500
        self.fc = fc = 870e6
        self.estado_rx = estado_rx = estado_probe
        self.delay_bits = delay_bits = 0
        self.bits_por_punto = bits_por_punto = 100000
        self.bits_guardia = bits_guardia = 1000
        self.bb_rate = bb_rate = samp_rate
        self.Rb = Rb = symbol_rate
        self.N_EbN0 = N_EbN0 = int(round((EbN0_max-EbN0_min)/EbN0_step))+1

        ##################################################
        # Blocks
        ##################################################

        self._vga_gain_range = qtgui.Range(0, 62, 2, 20, 200)
        self._vga_gain_win = qtgui.RangeWidget(self._vga_gain_range, self.set_vga_gain, "Ganancia VGA (dB)", "counter_slider", float, QtCore.Qt.Horizontal)
        self.top_layout.addWidget(self._vga_gain_win)
        self._lo_offset_range = qtgui.Range(0, 2000000, 10000, 200000, 200)
        self._lo_offset_win = qtgui.RangeWidget(self._lo_offset_range, self.set_lo_offset, "Desplazamiento del pico DC del HackRF (Hz)", "counter_slider", float, QtCore.Qt.Horizontal)
        self.top_layout.addWidget(self._lo_offset_win)
        self._lna_gain_range = qtgui.Range(0, 40, 8, 16, 200)
        self._lna_gain_win = qtgui.RangeWidget(self._lna_gain_range, self.set_lna_gain, "Ganancia LNA (dB)", "counter_slider", float, QtCore.Qt.Horizontal)
        self.top_layout.addWidget(self._lna_gain_win)
        self._freq_corr_range = qtgui.Range(-40000, 40000, 100, -6500, 200)
        self._freq_corr_win = qtgui.RangeWidget(self._freq_corr_range, self.set_freq_corr, "Corrección de frecuencia (Hz)", "counter_slider", float, QtCore.Qt.Horizontal)
        self.top_layout.addWidget(self._freq_corr_win)
        self.e_Texto_Rx = e_Texto_Rx.blk(mensaje=mensaje, pn9=pn9, max_errores_sincronia=2, imprimir_cada=1.0)
        self._texto_rx_tool_bar = Qt.QToolBar(self)

        if None:
            self._texto_rx_formatter = None
        else:
            self._texto_rx_formatter = lambda x: str(x)

        self._texto_rx_tool_bar.addWidget(Qt.QLabel("Texto recibido"))
        self._texto_rx_label = Qt.QLabel(str(self._texto_rx_formatter(self.texto_rx)))
        self._texto_rx_tool_bar.addWidget(self._texto_rx_label)
        self.top_layout.addWidget(self._texto_rx_tool_bar)
        def _texto_probe_probe():
          self.flowgraph_started.wait()
          while True:

            val = self.e_Texto_Rx.texto()
            try:
              try:
                self.doc.add_next_tick_callback(functools.partial(self.set_texto_probe,val))
              except AttributeError:
                self.set_texto_probe(val)
            except AttributeError:
              pass
            time.sleep(1.0 / (4))
        _texto_probe_thread = threading.Thread(target=_texto_probe_probe)
        _texto_probe_thread.daemon = True
        _texto_probe_thread.start()
        self.symbol_sync = digital.symbol_sync_ff(
            digital.TED_GARDNER,
            sps,
            0.005,
            1.0,
            1.0,
            0.05,
            1,
            digital.constellation_bpsk().base(),
            digital.IR_MMSE_8TAP,
            128,
            [])
        self.slicer = digital.binary_slicer_fb()
        self.rate_adapt = filter.freq_xlating_fir_filter_ccc(decim, firdes.low_pass(1.0, hackrf_rate, 300e3, 100e3), (lo_offset + freq_corr), hackrf_rate)
        self.hackrf_source = osmosdr.source(
            args="numchan=" + str(1) + " " + "hackrf=0"
        )
        self.hackrf_source.set_sample_rate(hackrf_rate)
        self.hackrf_source.set_center_freq((fc - lo_offset), 0)
        self.hackrf_source.set_freq_corr(0, 0)
        self.hackrf_source.set_dc_offset_mode(0, 0)
        self.hackrf_source.set_iq_balance_mode(0, 0)
        self.hackrf_source.set_gain_mode(False, 0)
        self.hackrf_source.set_gain(0, 0)
        self.hackrf_source.set_if_gain(lna_gain, 0)
        self.hackrf_source.set_bb_gain(vga_gain, 0)
        self.hackrf_source.set_antenna('', 0)
        self.hackrf_source.set_bandwidth(0, 0)
        self.fsk_demod = analog.quadrature_demod_cf((samp_rate/(2*math.pi*fsk_deviation)))
        self._estado_rx_tool_bar = Qt.QToolBar(self)

        if None:
            self._estado_rx_formatter = None
        else:
            self._estado_rx_formatter = lambda x: str(x)

        self._estado_rx_tool_bar.addWidget(Qt.QLabel("Verificacion"))
        self._estado_rx_label = Qt.QLabel(str(self._estado_rx_formatter(self.estado_rx)))
        self._estado_rx_tool_bar.addWidget(self._estado_rx_label)
        self.top_layout.addWidget(self._estado_rx_tool_bar)
        def _estado_probe_probe():
          self.flowgraph_started.wait()
          while True:

            val = self.e_Texto_Rx.estado()
            try:
              try:
                self.doc.add_next_tick_callback(functools.partial(self.set_estado_probe,val))
              except AttributeError:
                self.set_estado_probe(val)
            except AttributeError:
              pass
            time.sleep(1.0 / (4))
        _estado_probe_thread = threading.Thread(target=_estado_probe_probe)
        _estado_probe_thread.daemon = True
        _estado_probe_thread.start()
        self.ebn0_actual = qtgui.number_sink(
            gr.sizeof_float,
            0,
            qtgui.NUM_GRAPH_HORIZ,
            1,
            None # parent
        )
        self.ebn0_actual.set_update_time(0.25)
        self.ebn0_actual.set_title("Punto actual del barrido")

        labels = ["Eb/N0 aplicado", '', '', '', '',
            '', '', '', '', '']
        units = ["dB", '', '', '', '',
            '', '', '', '', '']
        colors = [("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"),
            ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black")]
        factor = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]

        for i in range(1):
            self.ebn0_actual.set_min(i, EbN0_min)
            self.ebn0_actual.set_max(i, EbN0_max)
            self.ebn0_actual.set_color(i, colors[i][0], colors[i][1])
            if len(labels[i]) == 0:
                self.ebn0_actual.set_label(i, "Data {0}".format(i))
            else:
                self.ebn0_actual.set_label(i, labels[i])
            self.ebn0_actual.set_unit(i, units[i])
            self.ebn0_actual.set_factor(i, factor[i])

        self.ebn0_actual.enable_autoscale(False)
        self._ebn0_actual_win = sip.wrapinstance(self.ebn0_actual.qwidget(), Qt.QWidget)
        self.top_layout.addWidget(self._ebn0_actual_win)
        self.e_Ref_Alineada = e_Ref_Alineada.blk(trama=trama_bits, z_min=10.0, max_salto=3, min_bits=2000, max_bits=20000)
        self.e_EbN0_Sweep = e_EbN0_Sweep.blk(EbN0_min=EbN0_min, EbN0_max=EbN0_max, EbN0_step=EbN0_step, samp_rate=bb_rate, bit_rate=Rb, bits_por_punto=bits_por_punto, bits_guardia=bits_guardia, signal_power=0.0, seed=2026)
        self.e_BER_Curve = e_BER_Curve.blk(EbN0_min=EbN0_min, EbN0_max=EbN0_max, EbN0_step=EbN0_step, bits_por_punto=bits_por_punto, bits_guardia=bits_guardia, delay_bits=delay_bits, update_every=update_every, segmentos_arranque=3, descartar_antes=8000, descartar_despues=1000)
        self.e_BER_CSV = e_BER_CSV.blk(EbN0_min=EbN0_min, EbN0_max=EbN0_max, EbN0_step=EbN0_step, nombre_archivo="curva_BER.csv", guardar_cada=2.0)
        self.dc_blocker = filter.dc_blocker_ff(3200, True)
        self.data_filter = blocks.moving_average_ff(sps, (1.0/sps), 4000, 1)
        self.curva_ber = qtgui.vector_sink_f(
            N_EbN0,
            EbN0_min,
            EbN0_step,
            "Eb/N0 [dB]",
            "log10(BER)",
            "Curva BER experimental vs Eb/N0",
            1, # Number of inputs
            None # parent
        )
        self.curva_ber.set_update_time(0.2)
        self.curva_ber.set_y_axis((-7), 0)
        self.curva_ber.enable_autoscale(False)
        self.curva_ber.enable_grid(True)
        self.curva_ber.set_x_axis_units("dB")
        self.curva_ber.set_y_axis_units("")
        self.curva_ber.set_ref_level(0)


        labels = ["BER", '', '', '', '',
            '', '', '', '', '']
        widths = [3, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ["blue", "red", "green", "black", "cyan",
            "magenta", "yellow", "dark red", "dark green", "dark blue"]
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]

        for i in range(1):
            if len(labels[i]) == 0:
                self.curva_ber.set_line_label(i, "Data {0}".format(i))
            else:
                self.curva_ber.set_line_label(i, labels[i])
            self.curva_ber.set_line_width(i, widths[i])
            self.curva_ber.set_line_color(i, colors[i])
            self.curva_ber.set_line_alpha(i, alphas[i])

        self._curva_ber_win = sip.wrapinstance(self.curva_ber.qwidget(), Qt.QWidget)
        self.top_layout.addWidget(self._curva_ber_win)
        self.channel_filter = filter.fir_filter_ccf(
            1,
            firdes.low_pass(
                1.0,
                samp_rate,
                35e3,
                10e3,
                window.WIN_HAMMING,
                6.76))


        ##################################################
        # Connections
        ##################################################
        self.connect((self.channel_filter, 0), (self.fsk_demod, 0))
        self.connect((self.data_filter, 0), (self.symbol_sync, 0))
        self.connect((self.dc_blocker, 0), (self.data_filter, 0))
        self.connect((self.e_BER_Curve, 1), (self.curva_ber, 0))
        self.connect((self.e_BER_Curve, 0), (self.e_BER_CSV, 0))
        self.connect((self.e_BER_Curve, 1), (self.e_BER_CSV, 1))
        self.connect((self.e_EbN0_Sweep, 0), (self.channel_filter, 0))
        self.connect((self.e_EbN0_Sweep, 1), (self.ebn0_actual, 0))
        self.connect((self.e_Ref_Alineada, 0), (self.e_BER_Curve, 0))
        self.connect((self.fsk_demod, 0), (self.dc_blocker, 0))
        self.connect((self.hackrf_source, 0), (self.rate_adapt, 0))
        self.connect((self.rate_adapt, 0), (self.e_EbN0_Sweep, 0))
        self.connect((self.slicer, 0), (self.e_BER_Curve, 1))
        self.connect((self.slicer, 0), (self.e_Ref_Alineada, 0))
        self.connect((self.slicer, 0), (self.e_Texto_Rx, 0))
        self.connect((self.symbol_sync, 0), (self.slicer, 0))


    def closeEvent(self, event):
        self.settings = Qt.QSettings("gnuradio/flowgraphs", "Receptor_FSK_HackRF_Fase4_v2")
        self.settings.setValue("geometry", self.saveGeometry())
        self.stop()
        self.wait()

        event.accept()

    def get_hackrf_rate(self):
        return self.hackrf_rate

    def set_hackrf_rate(self, hackrf_rate):
        self.hackrf_rate = hackrf_rate
        self.set_samp_rate(self.hackrf_rate/self.decim)
        self.hackrf_source.set_sample_rate(self.hackrf_rate)
        self.rate_adapt.set_taps(firdes.low_pass(1.0, self.hackrf_rate, 300e3, 100e3))

    def get_decim(self):
        return self.decim

    def set_decim(self, decim):
        self.decim = decim
        self.set_samp_rate(self.hackrf_rate/self.decim)

    def get_sps(self):
        return self.sps

    def set_sps(self, sps):
        self.sps = sps
        self.set_symbol_rate(self.samp_rate/self.sps)
        self.data_filter.set_length_and_scale(self.sps, (1.0/self.sps))
        self.symbol_sync.set_sps(self.sps)

    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        self.samp_rate = samp_rate
        self.set_bb_rate(self.samp_rate)
        self.set_symbol_rate(self.samp_rate/self.sps)
        self.channel_filter.set_taps(firdes.low_pass(1.0, self.samp_rate, 35e3, 10e3, window.WIN_HAMMING, 6.76))
        self.fsk_demod.set_gain((self.samp_rate/(2*math.pi*self.fsk_deviation)))

    def get_texto_probe(self):
        return self.texto_probe

    def set_texto_probe(self, texto_probe):
        self.texto_probe = texto_probe
        self.set_texto_rx(self.texto_probe)

    def get_symbol_rate(self):
        return self.symbol_rate

    def set_symbol_rate(self, symbol_rate):
        self.symbol_rate = symbol_rate
        self.set_Rb(self.symbol_rate)

    def get_pn9(self):
        return self.pn9

    def set_pn9(self, pn9):
        self.pn9 = pn9
        self.set_trama_bits(trama_telemetria.construir_trama(self.mensaje, self.pn9))
        self.e_Texto_Rx.pn9 = self.pn9

    def get_mensaje(self):
        return self.mensaje

    def set_mensaje(self, mensaje):
        self.mensaje = mensaje
        self.set_trama_bits(trama_telemetria.construir_trama(self.mensaje, self.pn9))
        self.e_Texto_Rx.mensaje = self.mensaje

    def get_estado_probe(self):
        return self.estado_probe

    def set_estado_probe(self, estado_probe):
        self.estado_probe = estado_probe
        self.set_estado_rx(self.estado_probe)

    def get_EbN0_step(self):
        return self.EbN0_step

    def set_EbN0_step(self, EbN0_step):
        self.EbN0_step = EbN0_step
        self.set_N_EbN0(int(round((self.EbN0_max-self.EbN0_min)/self.EbN0_step))+1)
        self.curva_ber.set_x_axis(self.EbN0_min, self.EbN0_step)
        self.e_BER_CSV.EbN0_step = self.EbN0_step
        self.e_BER_Curve.EbN0_step = self.EbN0_step
        self.e_EbN0_Sweep.EbN0_step = self.EbN0_step

    def get_EbN0_min(self):
        return self.EbN0_min

    def set_EbN0_min(self, EbN0_min):
        self.EbN0_min = EbN0_min
        self.set_N_EbN0(int(round((self.EbN0_max-self.EbN0_min)/self.EbN0_step))+1)
        self.curva_ber.set_x_axis(self.EbN0_min, self.EbN0_step)
        self.e_BER_CSV.EbN0_min = self.EbN0_min
        self.e_BER_Curve.EbN0_min = self.EbN0_min
        self.e_EbN0_Sweep.EbN0_min = self.EbN0_min

    def get_EbN0_max(self):
        return self.EbN0_max

    def set_EbN0_max(self, EbN0_max):
        self.EbN0_max = EbN0_max
        self.set_N_EbN0(int(round((self.EbN0_max-self.EbN0_min)/self.EbN0_step))+1)
        self.e_BER_CSV.EbN0_max = self.EbN0_max
        self.e_BER_Curve.EbN0_max = self.EbN0_max
        self.e_EbN0_Sweep.EbN0_max = self.EbN0_max

    def get_vga_gain(self):
        return self.vga_gain

    def set_vga_gain(self, vga_gain):
        self.vga_gain = vga_gain
        self.hackrf_source.set_bb_gain(self.vga_gain, 0)

    def get_update_every(self):
        return self.update_every

    def set_update_every(self, update_every):
        self.update_every = update_every
        self.e_BER_Curve.update_every = self.update_every

    def get_trama_bits(self):
        return self.trama_bits

    def set_trama_bits(self, trama_bits):
        self.trama_bits = trama_bits
        self.e_Ref_Alineada.trama = self.trama_bits

    def get_texto_rx(self):
        return self.texto_rx

    def set_texto_rx(self, texto_rx):
        self.texto_rx = texto_rx
        Qt.QMetaObject.invokeMethod(self._texto_rx_label, "setText", Qt.Q_ARG("QString", str(self._texto_rx_formatter(self.texto_rx))))

    def get_lo_offset(self):
        return self.lo_offset

    def set_lo_offset(self, lo_offset):
        self.lo_offset = lo_offset
        self.hackrf_source.set_center_freq((self.fc - self.lo_offset), 0)
        self.rate_adapt.set_center_freq((self.lo_offset + self.freq_corr))

    def get_lna_gain(self):
        return self.lna_gain

    def set_lna_gain(self, lna_gain):
        self.lna_gain = lna_gain
        self.hackrf_source.set_if_gain(self.lna_gain, 0)

    def get_fsk_deviation(self):
        return self.fsk_deviation

    def set_fsk_deviation(self, fsk_deviation):
        self.fsk_deviation = fsk_deviation
        self.fsk_demod.set_gain((self.samp_rate/(2*math.pi*self.fsk_deviation)))

    def get_freq_corr(self):
        return self.freq_corr

    def set_freq_corr(self, freq_corr):
        self.freq_corr = freq_corr
        self.rate_adapt.set_center_freq((self.lo_offset + self.freq_corr))

    def get_fc(self):
        return self.fc

    def set_fc(self, fc):
        self.fc = fc
        self.hackrf_source.set_center_freq((self.fc - self.lo_offset), 0)

    def get_estado_rx(self):
        return self.estado_rx

    def set_estado_rx(self, estado_rx):
        self.estado_rx = estado_rx
        Qt.QMetaObject.invokeMethod(self._estado_rx_label, "setText", Qt.Q_ARG("QString", str(self._estado_rx_formatter(self.estado_rx))))

    def get_delay_bits(self):
        return self.delay_bits

    def set_delay_bits(self, delay_bits):
        self.delay_bits = delay_bits
        self.e_BER_Curve.delay_bits = self.delay_bits

    def get_bits_por_punto(self):
        return self.bits_por_punto

    def set_bits_por_punto(self, bits_por_punto):
        self.bits_por_punto = bits_por_punto
        self.e_BER_Curve.bits_por_punto = self.bits_por_punto
        self.e_EbN0_Sweep.bits_por_punto = self.bits_por_punto

    def get_bits_guardia(self):
        return self.bits_guardia

    def set_bits_guardia(self, bits_guardia):
        self.bits_guardia = bits_guardia
        self.e_BER_Curve.bits_guardia = self.bits_guardia
        self.e_EbN0_Sweep.bits_guardia = self.bits_guardia

    def get_bb_rate(self):
        return self.bb_rate

    def set_bb_rate(self, bb_rate):
        self.bb_rate = bb_rate
        self.e_EbN0_Sweep.samp_rate = self.bb_rate

    def get_Rb(self):
        return self.Rb

    def set_Rb(self, Rb):
        self.Rb = Rb
        self.e_EbN0_Sweep.bit_rate = self.Rb

    def get_N_EbN0(self):
        return self.N_EbN0

    def set_N_EbN0(self, N_EbN0):
        self.N_EbN0 = N_EbN0




def main(top_block_cls=Receptor_FSK_HackRF_Fase4_v2, options=None):

    qapp = Qt.QApplication(sys.argv)

    tb = top_block_cls()

    tb.start()
    tb.flowgraph_started.set()

    tb.show()

    def sig_handler(sig=None, frame=None):
        tb.stop()
        tb.wait()

        Qt.QApplication.quit()

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    timer = Qt.QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)

    qapp.exec_()

if __name__ == '__main__':
    main()
