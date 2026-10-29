#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: Modulacion_FSK_AWGN
# Description: FSK con AWGN: comparación de envolvente compleja, PSD y frecuencia instantánea
# GNU Radio version: 3.10.12.0

from PyQt5 import Qt
from gnuradio import qtgui
from PyQt5 import QtCore
from gnuradio import analog
from gnuradio import blocks
from gnuradio import digital
from gnuradio import gr
from gnuradio.filter import firdes
from gnuradio.fft import window
import sys
import signal
from PyQt5 import Qt
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import eng_notation
from gnuradio import uhd
import time
import math
import threading



class Modulacion_FSK_AWGN(gr.top_block, Qt.QWidget):

    def __init__(self):
        gr.top_block.__init__(self, "Modulacion_FSK_AWGN", catch_exceptions=True)
        Qt.QWidget.__init__(self)
        self.setWindowTitle("Modulacion_FSK_AWGN")
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

        self.settings = Qt.QSettings("gnuradio/flowgraphs", "Modulacion_FSK_AWGN")

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
        self.sps = sps = 100
        self.samp_rate = samp_rate = 1e6
        self.symbol_rate = symbol_rate = samp_rate/sps
        self.samp_rate2_0 = samp_rate2_0 = 12.5e6
        self.samp_rate2 = samp_rate2 = 12.5e6
        self.noise_voltage = noise_voltage = 0.1
        self.fsk_deviation = fsk_deviation = 20000
        self.fc = fc = 880e6
        self.amp = amp = 0

        ##################################################
        # Blocks
        ##################################################

        self._fsk_deviation_range = qtgui.Range(5000, 100000, 1000, 20000, 200)
        self._fsk_deviation_win = qtgui.RangeWidget(self._fsk_deviation_range, self.set_fsk_deviation, "Desviación FSK (Hz)", "counter_slider", float, QtCore.Qt.Horizontal)
        self.top_layout.addWidget(self._fsk_deviation_win)
        self._amp_range = qtgui.Range(-10, 10, 0.01, 0, 200)
        self._amp_win = qtgui.RangeWidget(self._amp_range, self.set_amp, "GAIN", "counter_slider", float, QtCore.Qt.Horizontal)
        self.top_layout.addWidget(self._amp_win)
        self.uhd_usrp_sink_0 = uhd.usrp_sink(
            ",".join(("", '')),
            uhd.stream_args(
                cpu_format="fc32",
                args='',
                channels=list(range(0,1)),
            ),
            "",
        )
        self.uhd_usrp_sink_0.set_samp_rate(samp_rate2)
        # Set the time to GPS time on next PPS
        # get_mboard_sensor("gps_time") returns just after the PPS edge,
        # thus add one second and set the time on the next PPS
        self.uhd_usrp_sink_0.set_time_next_pps(uhd.time_spec(self.uhd_usrp_sink_0.get_mboard_sensor("gps_time").to_int() + 1.0))
        # Sleep 1 second to ensure next PPS has come
        time.sleep(1)

        self.uhd_usrp_sink_0.set_center_freq(fc, 0)
        self.uhd_usrp_sink_0.set_antenna("TX/RX", 0)
        self.uhd_usrp_sink_0.set_bandwidth(500e3, 0)
        self.uhd_usrp_sink_0.set_gain(amp, 0)
        self.symbol_repeat = blocks.repeat(gr.sizeof_float*1, sps)
        self.nrz_mapper = digital.chunks_to_symbols_bf([-1.0, 1.0], 1)
        self._noise_voltage_range = qtgui.Range(0.0, 1.0, 0.01, 0.1, 200)
        self._noise_voltage_win = qtgui.RangeWidget(self._noise_voltage_range, self.set_noise_voltage, "Noise voltage", "counter_slider", float, QtCore.Qt.Horizontal)
        self.top_layout.addWidget(self._noise_voltage_win)
        self.fsk_modulator = analog.frequency_modulator_fc((2*math.pi*fsk_deviation/samp_rate))
        self.bit_source = blocks.vector_source_b([0,1,0,0,1,1,0,1,1,1,0,0,1,0,1,0], True, 1, [])


        ##################################################
        # Connections
        ##################################################
        self.connect((self.bit_source, 0), (self.nrz_mapper, 0))
        self.connect((self.fsk_modulator, 0), (self.uhd_usrp_sink_0, 0))
        self.connect((self.nrz_mapper, 0), (self.symbol_repeat, 0))
        self.connect((self.symbol_repeat, 0), (self.fsk_modulator, 0))


    def closeEvent(self, event):
        self.settings = Qt.QSettings("gnuradio/flowgraphs", "Modulacion_FSK_AWGN")
        self.settings.setValue("geometry", self.saveGeometry())
        self.stop()
        self.wait()

        event.accept()

    def get_sps(self):
        return self.sps

    def set_sps(self, sps):
        self.sps = sps
        self.set_symbol_rate(self.samp_rate/self.sps)
        self.symbol_repeat.set_interpolation(self.sps)

    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        self.samp_rate = samp_rate
        self.set_symbol_rate(self.samp_rate/self.sps)
        self.fsk_modulator.set_sensitivity((2*math.pi*self.fsk_deviation/self.samp_rate))

    def get_symbol_rate(self):
        return self.symbol_rate

    def set_symbol_rate(self, symbol_rate):
        self.symbol_rate = symbol_rate

    def get_samp_rate2_0(self):
        return self.samp_rate2_0

    def set_samp_rate2_0(self, samp_rate2_0):
        self.samp_rate2_0 = samp_rate2_0

    def get_samp_rate2(self):
        return self.samp_rate2

    def set_samp_rate2(self, samp_rate2):
        self.samp_rate2 = samp_rate2
        self.uhd_usrp_sink_0.set_samp_rate(self.samp_rate2)

    def get_noise_voltage(self):
        return self.noise_voltage

    def set_noise_voltage(self, noise_voltage):
        self.noise_voltage = noise_voltage

    def get_fsk_deviation(self):
        return self.fsk_deviation

    def set_fsk_deviation(self, fsk_deviation):
        self.fsk_deviation = fsk_deviation
        self.fsk_modulator.set_sensitivity((2*math.pi*self.fsk_deviation/self.samp_rate))

    def get_fc(self):
        return self.fc

    def set_fc(self, fc):
        self.fc = fc
        self.uhd_usrp_sink_0.set_center_freq(self.fc, 0)

    def get_amp(self):
        return self.amp

    def set_amp(self, amp):
        self.amp = amp
        self.uhd_usrp_sink_0.set_gain(self.amp, 0)




def main(top_block_cls=Modulacion_FSK_AWGN, options=None):

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
