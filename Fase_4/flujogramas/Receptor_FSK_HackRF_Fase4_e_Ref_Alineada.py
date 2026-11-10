"""
e_Ref_Alineada
Genera la referencia Tx (la trama de telemetria repetida) ALINEADA con los bits
recuperados, para que e_BER_Curve trabaje con delay_bits = 0.

Se usa porque el Tx y el Rx corren en computadores distintos: el desfase entre
la trama recibida y una referencia local cambia en cada ejecucion, y la deriva
de reloj puede desplazarlo durante la medicion.

Entrada 0 : bits recuperados por el receptor (byte 0/1).
Salida 0  : bit de referencia correspondiente a cada bit recibido (byte 0/1).

Metodo: correlacion circular de los bits recibidos (+-1) con la trama conocida,
acumulada hasta que el pico es estadisticamente claro (z >= z_min). Entonces se
fija el desfase. Ya alineada, corrige cualquier salto (busqueda global; Ajuste
Fase 4) con la misma exigencia estadistica. max_salto ya no se usa. Funciona aun con BER alta: a menor
Eb/N0 solo tarda mas en decidir. La referencia NO copia bits del receptor:
siempre es la trama conocida, desplazada el desfase elegido.
"""

import numpy as np
from gnuradio import gr


class blk(gr.sync_block):
    def __init__(self, trama=(0, 1), z_min=10.0, max_salto=3, min_bits=2000, max_bits=20000):
        gr.sync_block.__init__(
            self,
            name='e_Ref_Alineada',
            in_sig=[np.int8],
            out_sig=[np.int8]
        )
        self.trama = np.array(trama, dtype=np.int8) & 1
        self.L = len(self.trama)
        self.t_pm = 2.0 * self.trama - 1.0
        self.T_fft = np.conj(np.fft.fft(self.t_pm))
        self.z_min = float(z_min)
        self.max_salto = int(max_salto)
        self.min_bits = int(min_bits)
        self.max_bits = int(max_bits)

        self.n = 0                  # indice absoluto del proximo bit recibido
        self.desfase = None         # d: ref[n] = trama[(n - d) % L]
        self.acc = np.zeros(self.L)
        self.acc_bits = 0
        self.cambios = 0

    def _decidir(self):
        # c[d] = sum_n rx_pm[n] * t_pm[(n - d) % L]
        c = np.real(np.fft.ifft(np.fft.fft(self.acc) * self.T_fft))
        sigma = np.sqrt(self.acc_bits)  # desviacion de c[d] para un desfase incorrecto
        if self.desfase is None:
            d = int(np.argmax(c))
            if c[d] / sigma < self.z_min:
                return
        else:
            # Ajuste Fase 4 (hardware): realineacion GLOBAL. Un overflow del HackRF o un
            # underrun del USRP puede saltar mas de +-max_salto bits; antes el bloque
            # quedaba desalineado para siempre (BER ~0.4 con el texto llegando bien).
            # Ahora se busca en todos los desfases, con la misma exigencia (z >= z_min).
            d = int(np.argmax(c))
            if d == self.desfase:
                # Desfase actual confirmado: reiniciar la ventana para detectar
                # rapido un salto futuro. Si aun no hay evidencia, seguir acumulando.
                if c[d] / sigma >= self.z_min or self.acc_bits >= self.max_bits:
                    self.acc[:] = 0.0
                    self.acc_bits = 0
                return
            if (c[d] - c[self.desfase]) / sigma < self.z_min:
                # Sin evidencia suficiente: seguir acumulando (hasta max_bits)
                if self.acc_bits >= self.max_bits:
                    self.acc[:] = 0.0
                    self.acc_bits = 0
                return
        z = c[d] / sigma
        if d != self.desfase:
            if self.desfase is not None:
                self.cambios += 1
                print('[e_Ref_Alineada] desfase corregido: %d -> %d bits (z = %.1f)'
                      % (self.desfase, d, z))
            else:
                print('[e_Ref_Alineada] alineada: desfase = %d bits (z = %.1f, %d bits)'
                      % (d, z, self.acc_bits))
            self.desfase = d
        self.acc[:] = 0.0
        self.acc_bits = 0

    def work(self, input_items, output_items):
        rx = input_items[0]
        out = output_items[0]
        m = len(rx)
        idx = self.n + np.arange(m)

        d = 0 if self.desfase is None else self.desfase
        out[:] = self.trama[(idx - d) % self.L]

        np.add.at(self.acc, idx % self.L, 2.0 * (rx & 1) - 1.0)
        self.acc_bits += m
        self.n += m
        # Antes de alinearse se evalua seguido (cada 250 bits) para fijar el desfase
        # dentro de los bits de guarda del primer punto; despues, cada min_bits.
        if self.acc_bits >= (250 if self.desfase is None else self.min_bits):
            self._decidir()
        return m
