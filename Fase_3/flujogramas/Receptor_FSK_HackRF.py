#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: Receptor FSK - HackRF One
# Description: Receptor FSK binario con HackRF One
# GNU Radio version: 3.10.12.0

from PyQt5 import Qt
from gnuradio import qtgui
from PyQt5 import QtCore
from gnuradio import analog
import math
from gnuradio import blocks
from gnuradio import digital
from gnuradio import filter
from gnuradio.filter import firdes
from gnuradio import gr
from gnuradio.fft import window
import sys
import signal
from PyQt5 import Qt
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import eng_notation
import osmosdr
import time
import sip
import threading



class Receptor_FSK_HackRF(gr.top_block, Qt.QWidget):

    def __init__(self):
        gr.top_block.__init__(self, "Receptor FSK - HackRF One", catch_exceptions=True)
        Qt.QWidget.__init__(self)
        self.setWindowTitle("Receptor FSK - HackRF One")
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

        self.settings = Qt.QSettings("gnuradio/flowgraphs", "Receptor_FSK_HackRF")

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
        self.hackrf_rate = hackrf_rate = 8e6
        self.decim = decim = 8
        self.sps = sps = 100
        self.samp_rate = samp_rate = hackrf_rate/decim
        self.vga_gain = vga_gain = 20
        self.symbol_rate = symbol_rate = samp_rate/sps
        self.sample_delay = sample_delay = 50
        self.lo_offset = lo_offset = 200e3
        self.lna_gain = lna_gain = 16
        self.fsk_deviation = fsk_deviation = 20e3
        self.freq_corr = freq_corr = 0
        self.fc = fc = 880e6

        ##################################################
        # Blocks
        ##################################################

        self._vga_gain_range = qtgui.Range(0, 62, 2, 20, 200)
        self._vga_gain_win = qtgui.RangeWidget(self._vga_gain_range, self.set_vga_gain, "Ganancia VGA (dB)", "counter_slider", float, QtCore.Qt.Horizontal)
        self.top_layout.addWidget(self._vga_gain_win)
        self._sample_delay_range = qtgui.Range(0, (sps-1), 1, 50, 200)
        self._sample_delay_win = qtgui.RangeWidget(self._sample_delay_range, self.set_sample_delay, "Retardo de muestreo (muestras)", "counter_slider", int, QtCore.Qt.Horizontal)
        self.top_layout.addWidget(self._sample_delay_win)
        self._lna_gain_range = qtgui.Range(0, 40, 8, 16, 200)
        self._lna_gain_win = qtgui.RangeWidget(self._lna_gain_range, self.set_lna_gain, "Ganancia LNA (dB)", "counter_slider", float, QtCore.Qt.Horizontal)
        self.top_layout.addWidget(self._lna_gain_win)
        self._freq_corr_range = qtgui.Range(-40000, 40000, 100, 0, 200)
        self._freq_corr_win = qtgui.RangeWidget(self._freq_corr_range, self.set_freq_corr, "Corrección de frecuencia (Hz)", "counter_slider", float, QtCore.Qt.Horizontal)
        self.top_layout.addWidget(self._freq_corr_win)
        self.symbol_sampler = blocks.keep_one_in_n(gr.sizeof_float*1, sps)
        self.slicer = digital.binary_slicer_fb()
        self.sample_align = blocks.delay(gr.sizeof_float*1, sample_delay)
        self.raw_spectrum = qtgui.freq_sink_c(
            4096, #size
            window.WIN_BLACKMAN_hARRIS, #wintype
            (fc - lo_offset), #fc
            hackrf_rate, #bw
            "Espectro recibido (HackRF, 8 MS/s)", #name
            1,
            None # parent
        )
        self.raw_spectrum.set_update_time(0.10)
        self.raw_spectrum.set_y_axis((-120), 0)
        self.raw_spectrum.set_y_label('Relative Gain', 'dB')
        self.raw_spectrum.set_trigger_mode(qtgui.TRIG_MODE_FREE, 0.0, 0, "")
        self.raw_spectrum.enable_autoscale(False)
        self.raw_spectrum.enable_grid(True)
        self.raw_spectrum.set_fft_average(0.2)
        self.raw_spectrum.enable_axis_labels(True)
        self.raw_spectrum.enable_control_panel(False)
        self.raw_spectrum.set_fft_window_normalized(False)



        labels = ['HackRF', '', '', '', '',
            '', '', '', '', '']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ["blue", "red", "green", "black", "cyan",
            "magenta", "yellow", "dark red", "dark green", "dark blue"]
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]

        for i in range(1):
            if len(labels[i]) == 0:
                self.raw_spectrum.set_line_label(i, "Data {0}".format(i))
            else:
                self.raw_spectrum.set_line_label(i, labels[i])
            self.raw_spectrum.set_line_width(i, widths[i])
            self.raw_spectrum.set_line_color(i, colors[i])
            self.raw_spectrum.set_line_alpha(i, alphas[i])

        self._raw_spectrum_win = sip.wrapinstance(self.raw_spectrum.qwidget(), Qt.QWidget)
        self.top_layout.addWidget(self._raw_spectrum_win)
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
        self.freq_inst = qtgui.time_sink_f(
            2000, #size
            samp_rate, #samp_rate
            "Frecuencia instantanea filtrada", #name
            1, #number of inputs
            None # parent
        )
        self.freq_inst.set_update_time(0.10)
        self.freq_inst.set_y_axis(-2, 2)

        self.freq_inst.set_y_label('Amplitud', "")

        self.freq_inst.enable_tags(True)
        self.freq_inst.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, 0, "")
        self.freq_inst.enable_autoscale(False)
        self.freq_inst.enable_grid(True)
        self.freq_inst.enable_axis_labels(True)
        self.freq_inst.enable_control_panel(False)
        self.freq_inst.enable_stem_plot(False)


        labels = ['Demodulada', 'Signal 2', 'Signal 3', 'Signal 4', 'Signal 5',
            'Signal 6', 'Signal 7', 'Signal 8', 'Signal 9', 'Signal 10']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ['blue', 'red', 'green', 'black', 'cyan',
            'magenta', 'yellow', 'dark red', 'dark green', 'dark blue']
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]
        styles = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        markers = [-1, -1, -1, -1, -1,
            -1, -1, -1, -1, -1]


        for i in range(1):
            if len(labels[i]) == 0:
                self.freq_inst.set_line_label(i, "Data {0}".format(i))
            else:
                self.freq_inst.set_line_label(i, labels[i])
            self.freq_inst.set_line_width(i, widths[i])
            self.freq_inst.set_line_color(i, colors[i])
            self.freq_inst.set_line_style(i, styles[i])
            self.freq_inst.set_line_marker(i, markers[i])
            self.freq_inst.set_line_alpha(i, alphas[i])

        self._freq_inst_win = sip.wrapinstance(self.freq_inst.qwidget(), Qt.QWidget)
        self.top_layout.addWidget(self._freq_inst_win)
        self.eye_rx = qtgui.eye_sink_f(
            2000, #size
            samp_rate, #samp_rate
            1, #number of inputs
            None
        )
        self.eye_rx.set_update_time(0.10)
        self.eye_rx.set_samp_per_symbol(sps)
        self.eye_rx.set_y_axis(-2, 2)

        self.eye_rx.set_y_label('Amplitud', "")

        self.eye_rx.enable_tags(True)
        self.eye_rx.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, 0, "")
        self.eye_rx.enable_autoscale(False)
        self.eye_rx.enable_grid(False)
        self.eye_rx.enable_axis_labels(True)
        self.eye_rx.enable_control_panel(False)


        labels = ['Salida filtrada', 'Signal 2', 'Signal 3', 'Signal 4', 'Signal 5',
            'Signal 6', 'Signal 7', 'Signal 8', 'Signal 9', 'Signal 10']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ['blue', 'blue', 'blue', 'blue', 'blue',
            'blue', 'blue', 'blue', 'blue', 'blue']
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]
        styles = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        markers = [-1, -1, -1, -1, -1,
            -1, -1, -1, -1, -1]


        for i in range(1):
            if len(labels[i]) == 0:
                self.eye_rx.set_line_label(i, "Eye[Data {0}]".format(i))
            else:
                self.eye_rx.set_line_label(i, labels[i])
            self.eye_rx.set_line_width(i, widths[i])
            self.eye_rx.set_line_color(i, colors[i])
            self.eye_rx.set_line_style(i, styles[i])
            self.eye_rx.set_line_marker(i, markers[i])
            self.eye_rx.set_line_alpha(i, alphas[i])

        self._eye_rx_win = sip.wrapinstance(self.eye_rx.qwidget(), Qt.QWidget)
        self.top_layout.addWidget(self._eye_rx_win)
        self.dc_blocker = filter.dc_blocker_ff(3200, True)
        self.data_filter = filter.fir_filter_fff(
            1,
            firdes.low_pass(
                1,
                samp_rate,
                symbol_rate,
                (symbol_rate/2),
                window.WIN_HAMMING,
                6.76))
        self.channel_spectrum = qtgui.freq_sink_c(
            2048, #size
            window.WIN_BLACKMAN_hARRIS, #wintype
            fc, #fc
            samp_rate, #bw
            "Canal FSK centrado (debe verse simetrico en fc)", #name
            1,
            None # parent
        )
        self.channel_spectrum.set_update_time(0.10)
        self.channel_spectrum.set_y_axis((-120), 0)
        self.channel_spectrum.set_y_label('Relative Gain', 'dB')
        self.channel_spectrum.set_trigger_mode(qtgui.TRIG_MODE_FREE, 0.0, 0, "")
        self.channel_spectrum.enable_autoscale(False)
        self.channel_spectrum.enable_grid(True)
        self.channel_spectrum.set_fft_average(0.2)
        self.channel_spectrum.enable_axis_labels(True)
        self.channel_spectrum.enable_control_panel(False)
        self.channel_spectrum.set_fft_window_normalized(False)



        labels = ['Canal', '', '', '', '',
            '', '', '', '', '']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ["blue", "red", "green", "black", "cyan",
            "magenta", "yellow", "dark red", "dark green", "dark blue"]
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]

        for i in range(1):
            if len(labels[i]) == 0:
                self.channel_spectrum.set_line_label(i, "Data {0}".format(i))
            else:
                self.channel_spectrum.set_line_label(i, labels[i])
            self.channel_spectrum.set_line_width(i, widths[i])
            self.channel_spectrum.set_line_color(i, colors[i])
            self.channel_spectrum.set_line_alpha(i, alphas[i])

        self._channel_spectrum_win = sip.wrapinstance(self.channel_spectrum.qwidget(), Qt.QWidget)
        self.top_layout.addWidget(self._channel_spectrum_win)
        self.channel_filter = filter.freq_xlating_fir_filter_ccc(decim, firdes.low_pass(1.0, hackrf_rate, 60e3, 40e3), (lo_offset + freq_corr), hackrf_rate)
        self.bits_to_float = blocks.char_to_float(1, 1)
        self.bits_rx = qtgui.time_sink_f(
            32, #size
            symbol_rate, #samp_rate
            "Bits recuperados", #name
            1, #number of inputs
            None # parent
        )
        self.bits_rx.set_update_time(0.10)
        self.bits_rx.set_y_axis(-0.2, 1.2)

        self.bits_rx.set_y_label('Bit', "")

        self.bits_rx.enable_tags(True)
        self.bits_rx.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, 0, "")
        self.bits_rx.enable_autoscale(False)
        self.bits_rx.enable_grid(True)
        self.bits_rx.enable_axis_labels(True)
        self.bits_rx.enable_control_panel(False)
        self.bits_rx.enable_stem_plot(True)


        labels = ['Bits recuperados', 'Signal 2', 'Signal 3', 'Signal 4', 'Signal 5',
            'Signal 6', 'Signal 7', 'Signal 8', 'Signal 9', 'Signal 10']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ['blue', 'red', 'green', 'black', 'cyan',
            'magenta', 'yellow', 'dark red', 'dark green', 'dark blue']
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]
        styles = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        markers = [0, -1, -1, -1, -1,
            -1, -1, -1, -1, -1]


        for i in range(1):
            if len(labels[i]) == 0:
                self.bits_rx.set_line_label(i, "Data {0}".format(i))
            else:
                self.bits_rx.set_line_label(i, labels[i])
            self.bits_rx.set_line_width(i, widths[i])
            self.bits_rx.set_line_color(i, colors[i])
            self.bits_rx.set_line_style(i, styles[i])
            self.bits_rx.set_line_marker(i, markers[i])
            self.bits_rx.set_line_alpha(i, alphas[i])

        self._bits_rx_win = sip.wrapinstance(self.bits_rx.qwidget(), Qt.QWidget)
        self.top_layout.addWidget(self._bits_rx_win)


        ##################################################
        # Connections
        ##################################################
        self.connect((self.bits_to_float, 0), (self.bits_rx, 0))
        self.connect((self.channel_filter, 0), (self.channel_spectrum, 0))
        self.connect((self.channel_filter, 0), (self.fsk_demod, 0))
        self.connect((self.data_filter, 0), (self.freq_inst, 0))
        self.connect((self.data_filter, 0), (self.sample_align, 0))
        self.connect((self.dc_blocker, 0), (self.data_filter, 0))
        self.connect((self.fsk_demod, 0), (self.dc_blocker, 0))
        self.connect((self.hackrf_source, 0), (self.channel_filter, 0))
        self.connect((self.hackrf_source, 0), (self.raw_spectrum, 0))
        self.connect((self.sample_align, 0), (self.eye_rx, 0))
        self.connect((self.sample_align, 0), (self.symbol_sampler, 0))
        self.connect((self.slicer, 0), (self.bits_to_float, 0))
        self.connect((self.symbol_sampler, 0), (self.slicer, 0))


    def closeEvent(self, event):
        self.settings = Qt.QSettings("gnuradio/flowgraphs", "Receptor_FSK_HackRF")
        self.settings.setValue("geometry", self.saveGeometry())
        self.stop()
        self.wait()

        event.accept()

    def get_hackrf_rate(self):
        return self.hackrf_rate

    def set_hackrf_rate(self, hackrf_rate):
        self.hackrf_rate = hackrf_rate
        self.set_samp_rate(self.hackrf_rate/self.decim)
        self.channel_filter.set_taps(firdes.low_pass(1.0, self.hackrf_rate, 60e3, 40e3))
        self.hackrf_source.set_sample_rate(self.hackrf_rate)
        self.raw_spectrum.set_frequency_range((self.fc - self.lo_offset), self.hackrf_rate)

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
        self.eye_rx.set_samp_per_symbol(self.sps)
        self.symbol_sampler.set_n(self.sps)

    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        self.samp_rate = samp_rate
        self.set_symbol_rate(self.samp_rate/self.sps)
        self.channel_spectrum.set_frequency_range(self.fc, self.samp_rate)
        self.data_filter.set_taps(firdes.low_pass(1, self.samp_rate, self.symbol_rate, (self.symbol_rate/2), window.WIN_HAMMING, 6.76))
        self.eye_rx.set_samp_rate(self.samp_rate)
        self.freq_inst.set_samp_rate(self.samp_rate)
        self.fsk_demod.set_gain((self.samp_rate/(2*math.pi*self.fsk_deviation)))

    def get_vga_gain(self):
        return self.vga_gain

    def set_vga_gain(self, vga_gain):
        self.vga_gain = vga_gain
        self.hackrf_source.set_bb_gain(self.vga_gain, 0)

    def get_symbol_rate(self):
        return self.symbol_rate

    def set_symbol_rate(self, symbol_rate):
        self.symbol_rate = symbol_rate
        self.bits_rx.set_samp_rate(self.symbol_rate)
        self.data_filter.set_taps(firdes.low_pass(1, self.samp_rate, self.symbol_rate, (self.symbol_rate/2), window.WIN_HAMMING, 6.76))

    def get_sample_delay(self):
        return self.sample_delay

    def set_sample_delay(self, sample_delay):
        self.sample_delay = sample_delay
        self.sample_align.set_dly(int(self.sample_delay))

    def get_lo_offset(self):
        return self.lo_offset

    def set_lo_offset(self, lo_offset):
        self.lo_offset = lo_offset
        self.channel_filter.set_center_freq((self.lo_offset + self.freq_corr))
        self.hackrf_source.set_center_freq((self.fc - self.lo_offset), 0)
        self.raw_spectrum.set_frequency_range((self.fc - self.lo_offset), self.hackrf_rate)

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
        self.channel_filter.set_center_freq((self.lo_offset + self.freq_corr))

    def get_fc(self):
        return self.fc

    def set_fc(self, fc):
        self.fc = fc
        self.channel_spectrum.set_frequency_range(self.fc, self.samp_rate)
        self.hackrf_source.set_center_freq((self.fc - self.lo_offset), 0)
        self.raw_spectrum.set_frequency_range((self.fc - self.lo_offset), self.hackrf_rate)




def main(top_block_cls=Receptor_FSK_HackRF, options=None):

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
