"""
e_BER_Curve
Acumulador de curva BER para los sistemas de los estudiantes.

Entrada 0 : bits transmitidos de referencia (byte 0/1).
Entrada 1 : bits recuperados por el receptor (byte 0/1).

Salida 0  : vector BER lineal.
Salida 1  : vector log10(BER) para QT GUI Vector Sink.

El bloque usa exactamente el mismo barrido que e_EbN0_Sweep. Para cada punto:
- ignora bits_guardia al comienzo del segmento;
- compara bits_por_punto;
- cuando el barrido vuelve a un punto, sigue acumulando estadísticas.

delay_bits retrasa internamente la referencia Tx para compensar el retardo
del receptor. Se ajusta primero en una condición limpia hasta lograr BER≈0.

Cuando todavía no se observa ningún error, la salida logarítmica utiliza
3/N como cota superior aproximada para poder mostrar el punto sin afirmar
que BER=0.
"""

import numpy as np
import pmt
from collections import deque
from gnuradio import gr


class blk(gr.decim_block):  # Ajuste Fase 4: compatibilidad GNU Radio 3.10
    def __init__(self,
                 EbN0_min=0.0,
                 EbN0_max=18.0,  # Ajuste Fase 4: GRC dimensiona los puertos con este valor (debe ser = EbN0_max)
                 EbN0_step=1.0,
                 bits_por_punto=100000,
                 bits_guardia=1000,
                 delay_bits=0,
                 update_every=1000,
                 segmentos_arranque=3,  # Ajuste Fase 4: descartar el arranque
                 descartar_antes=8000,  # Ajuste Fase 4 v2: bits previos a un realineo
                 descartar_despues=1000):  # Ajuste Fase 4 v2: bits posteriores
        self.EbN0_min = float(EbN0_min)
        self.EbN0_max = float(EbN0_max)
        self.EbN0_step = float(EbN0_step)
        self.bits_por_punto = max(1, int(bits_por_punto))
        self.bits_guardia = max(0, int(bits_guardia))
        self.delay_bits = max(0, int(delay_bits))
        self.update_every = max(1, int(update_every))
        # Ajuste Fase 4 (hardware): no contar los primeros segmentos de la PRIMERA
        # pasada (overflows al abrir la GUI y alineacion de la referencia). La
        # asignacion de puntos no cambia; esos puntos se miden en pasadas siguientes.
        self.segmentos_arranque = max(0, int(segmentos_arranque))
        # Ajuste Fase 4 v2 (hardware): si se pierden muestras (overflow del HackRF,
        # underrun del USRP) la referencia se desalinea hasta que e_Ref_Alineada lo
        # detecta y emite el tag 'realineo'. Los bits comparados en ese lapso no son
        # errores del receptor: se retienen descartar_antes bits sin contar y, ante
        # un tag, se descartan junto con los descartar_despues siguientes.
        self.descartar_antes = max(0, int(descartar_antes))
        self.descartar_despues = max(0, int(descartar_despues))
        self.pendientes = deque()   # (point_index, error) aun sin contar
        self.saltar_hasta = -1      # indice absoluto hasta el que se ignoran bits
        self.descartados = 0
        self.realineos = 0
        self.contados = 0

        if self.EbN0_step <= 0:
            raise ValueError("EbN0_step debe ser > 0")
        if self.EbN0_max < self.EbN0_min:
            raise ValueError("EbN0_max debe ser >= EbN0_min")

        npts = int(round((self.EbN0_max-self.EbN0_min)/self.EbN0_step)) + 1
        self.eb_axis = self.EbN0_min + self.EbN0_step*np.arange(npts, dtype=np.float64)
        self.N = len(self.eb_axis)
        self.segment_bits = self.bits_guardia + self.bits_por_punto

        # Ajuste Fase 4: compatibilidad GNU Radio 3.10
        gr.decim_block.__init__(
            self,
            name='e_BER_Curve',
            in_sig=[np.int8, np.int8],
            out_sig=[(np.float32, self.N), (np.float32, self.N)],
            decim=self.update_every
        )

        self.tx_fifo = deque([0]*self.delay_bits)
        self.raw_items = 0
        self.valid_bit_index = 0

        self.count = np.zeros(self.N, dtype=np.int64)
        self.errors = np.zeros(self.N, dtype=np.int64)
        self.set_tag_propagation_policy(gr.TPP_DONT)

    def _realineo(self, abs_idx):
        n = len(self.pendientes)
        self.pendientes.clear()
        self.saltar_hasta = abs_idx + self.descartar_despues
        self.descartados += n + self.descartar_despues
        self.realineos += 1
        total = self.descartados + self.contados
        print('[e_BER_Curve] realineo #%d: %d bits descartados (acumulado %.2f %% de los bits)'
              % (self.realineos, n + self.descartar_despues,
                 100.0 * self.descartados / max(1, total)))

    def _contar(self, point_index, error):
        self.pendientes.append((point_index, error))
        while len(self.pendientes) > self.descartar_antes:
            p, e = self.pendientes.popleft()
            self.count[p] += 1
            self.errors[p] += e
            self.contados += 1

    def _process(self, tx, rx, abs0=0, marcas=()):
        for k, (t, r) in enumerate(zip(tx, rx)):
            abs_idx = abs0 + k
            if abs_idx in marcas:
                self._realineo(abs_idx)
            tb = int(t) & 1
            rb = int(r) & 1

            if self.delay_bits > 0:
                self.tx_fifo.append(tb)
                t_aligned = self.tx_fifo.popleft()
                if self.raw_items < self.delay_bits:
                    self.raw_items += 1
                    continue
            else:
                t_aligned = tb

            bit_index = self.valid_bit_index
            segment_index = bit_index // self.segment_bits
            point_index = segment_index % self.N
            pos = bit_index % self.segment_bits

            # Dejar que filtros/sincronizadores se estabilicen después
            # del cambio de nivel de ruido.
            if (pos >= self.bits_guardia and segment_index >= self.segmentos_arranque
                    and abs_idx > self.saltar_hasta):
                self._contar(point_index, 1 if t_aligned != rb else 0)

            self.valid_bit_index += 1
            self.raw_items += 1

    def _vectors(self):
        ber = np.zeros(self.N, dtype=np.float32)
        logber = np.zeros(self.N, dtype=np.float32)

        for i in range(self.N):
            n = int(self.count[i])
            e = int(self.errors[i])

            if n <= 0:
                ber[i] = 0.0
                logber[i] = 0.0
            elif e > 0:
                b = e/float(n)
                ber[i] = b
                logber[i] = np.log10(max(b, 1e-12))
            else:
                # BER observado = 0; para la gráfica usamos una cota superior.
                ber[i] = 0.0
                upper = min(1.0, 3.0/float(n))
                logber[i] = np.log10(max(upper, 1e-12))

        return ber, logber

    def work(self, input_items, output_items):
        tx = input_items[0]
        rx = input_items[1]
        out_ber = output_items[0]
        out_log = output_items[1]

        nout = len(out_ber)
        D = self.update_every
        base = self.nitems_read(0)
        marcas = set(t.offset for t in self.get_tags_in_window(
            0, 0, min(len(tx), nout * D), pmt.intern('realineo')))

        for k in range(nout):
            a = k*D
            b = min((k+1)*D, len(tx))
            if a < b:
                self._process(tx[a:b], rx[a:b], base + a, marcas)

            ber, logber = self._vectors()
            out_ber[k, :] = ber
            out_log[k, :] = logber

        return nout
