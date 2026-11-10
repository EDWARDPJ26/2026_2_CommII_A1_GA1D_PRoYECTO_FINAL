"""
e_EbN0_Sweep
Instrumento para caracterización BER con un enlace SDR ya funcional.

Entrada 0 : señal compleja I/Q recibida del SDR (preferiblemente DESPUÉS
            de la adaptación radio_rate -> bb_rate).
Salida 0  : la misma señal I/Q con AWGN adicional controlado.
Salida 1  : valor instantáneo de Eb/N0 [dB] usado en el barrido.

El bloque NO sustituye el USRP/HackRF ni el receptor. Se inserta entre
la salida I/Q del SDR y la entrada del receptor digital.

El barrido se hace por segmentos contiguos. Cada punto se mantiene durante:
    bits_guardia + bits_por_punto

La potencia de ruido artificial se calcula a partir de la potencia promedio
medida ANTES de agregar el ruido:

    Eb = Ps / Rb
    N0 = Eb / (Eb/N0)
    Pn = N0 * Fs

por lo tanto:

    Pn = Ps * Fs / (Rb * 10**(EbN0_dB/10))

El ruido complejo se genera con varianza total Pn.
"""

import numpy as np
from gnuradio import gr


class blk(gr.sync_block):
    def __init__(self,
                 EbN0_min=0.0,
                 EbN0_max=14.0,
                 EbN0_step=1.0,
                 samp_rate=256000.0,
                 bit_rate=64000.0,
                 bits_por_punto=100000,
                 bits_guardia=1000,
                 signal_power=0.0,
                 seed=2026):
        gr.sync_block.__init__(
            self,
            name='e_EbN0_Sweep',
            in_sig=[np.complex64],
            out_sig=[np.complex64, np.float32]
        )

        self.EbN0_min = float(EbN0_min)
        self.EbN0_max = float(EbN0_max)
        self.EbN0_step = float(EbN0_step)
        self.samp_rate = float(samp_rate)
        self.bit_rate = float(bit_rate)
        self.bits_por_punto = max(1, int(bits_por_punto))
        self.bits_guardia = max(0, int(bits_guardia))
        self.signal_power_cfg = float(signal_power)

        if self.EbN0_step <= 0:
            raise ValueError("EbN0_step debe ser > 0")
        if self.samp_rate <= 0 or self.bit_rate <= 0:
            raise ValueError("samp_rate y bit_rate deben ser > 0")
        if self.EbN0_max < self.EbN0_min:
            raise ValueError("EbN0_max debe ser >= EbN0_min")

        npts = int(round((self.EbN0_max-self.EbN0_min)/self.EbN0_step)) + 1
        self.eb_axis = self.EbN0_min + self.EbN0_step*np.arange(npts, dtype=np.float64)
        self.segment_bits = self.bits_guardia + self.bits_por_punto

        self.sample_count = 0
        self.power_sum = 0.0
        self.power_count = 0
        self.rng = np.random.default_rng(int(seed))

    def _signal_power(self, x):
        if self.signal_power_cfg > 0:
            return self.signal_power_cfg

        # Promedio acumulado de la señal recibida ANTES del ruido artificial.
        self.power_sum += float(np.sum(np.abs(x.astype(np.complex128))**2))
        self.power_count += len(x)
        if self.power_count <= 0:
            return 0.0
        return max(self.power_sum/self.power_count, 1e-20)

    def work(self, input_items, output_items):
        x = input_items[0]
        y = output_items[0]
        eb_out = output_items[1]
        n = len(x)
        if n == 0:
            return 0

        Ps = self._signal_power(x)

        # Índice absoluto de muestra -> índice equivalente de bit.
        s = self.sample_count + np.arange(n, dtype=np.float64)
        bit_index = np.floor(s*self.bit_rate/self.samp_rate).astype(np.int64)

        segment_index = bit_index // self.segment_bits
        point_index = np.mod(segment_index, len(self.eb_axis))
        ebn0_db = self.eb_axis[point_index]
        ebn0_lin = np.power(10.0, ebn0_db/10.0)

        # Potencia total del ruido complejo por muestra.
        noise_power = Ps*self.samp_rate/(self.bit_rate*ebn0_lin)
        sigma_iq = np.sqrt(np.maximum(noise_power, 0.0)/2.0)

        noise = (
            self.rng.standard_normal(n)*sigma_iq
            + 1j*self.rng.standard_normal(n)*sigma_iq
        ).astype(np.complex64)

        y[:] = x + noise
        eb_out[:] = ebn0_db.astype(np.float32)

        self.sample_count += n
        return n
