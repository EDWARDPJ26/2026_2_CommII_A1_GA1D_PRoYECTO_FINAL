"""
e_Texto_Rx
Rama de verificacion visual: reconstruye el texto de telemetria a partir de
los bits recuperados. NO interviene en la medicion BER.

Entrada 0 : bits recuperados por el receptor (byte 0/1, salida del Binary Slicer).

Busca la palabra de sincronizacion (ultimos 16 bits del preambulo + SFD 0x904E),
toma los bits de la carga, quita el blanqueo PN9 si pn9 = 1, y compara el texto
con el mensaje esperado.

Metodos para Function Probe:
    texto()  -> ultimo texto recibido
    estado() -> contador de tramas correctas / con error
"""

import time

import numpy as np
from gnuradio import gr

SINCRONIA = 0x5555904E      # 0x5555 (fin del preambulo) + SFD 0x904E
SINCRONIA_BITS = 32
MASCARA = (1 << SINCRONIA_BITS) - 1


class blk(gr.sync_block):
    def __init__(self, mensaje="ID:S01", pn9=0, max_errores_sincronia=2,
                 imprimir_cada=1.0):
        gr.sync_block.__init__(
            self,
            name='e_Texto_Rx',
            in_sig=[np.int8],
            out_sig=None
        )
        self.mensaje = str(mensaje)
        self.pn9 = int(pn9)
        self.max_errores_sincronia = int(max_errores_sincronia)
        self.imprimir_cada = float(imprimir_cada)

        self.carga_esperada = self._bytes_a_bits(self.mensaje.encode('ascii', errors='replace'))
        if self.pn9:
            self.carga_esperada = self._blanquear(self.carga_esperada)
        self.n_carga = len(self.carga_esperada)

        self.registro = 0
        self.capturando = False
        self.carga = []

        self.tramas_ok = 0
        self.tramas_error = 0
        self.ultimo_texto = '(esperando trama...)'
        self.ultimo_errores = 0
        self.ultima_impresion = 0.0

    @staticmethod
    def _bytes_a_bits(datos):
        return [(b >> (7 - i)) & 1 for b in datos for i in range(8)]

    @staticmethod
    def _blanquear(bits):
        # PN9: x^9 + x^5 + 1, semilla 0x1FF (igual que trama_telemetria)
        estado = 0x1FF
        salida = []
        for b in bits:
            salida.append(b ^ (estado & 1))
            nuevo = (estado ^ (estado >> 5)) & 1
            estado = (estado >> 1) | (nuevo << 8)
        return salida

    @staticmethod
    def _visible(datos):
        return ''.join(chr(c) if 32 <= c < 127 else '?' for c in datos)

    def _cerrar_trama(self):
        errores = sum(a != b for a, b in zip(self.carga, self.carga_esperada))
        bits = self._blanquear(self.carga) if self.pn9 else self.carga
        datos = bytes(
            sum(bits[k + i] << (7 - i) for i in range(8))
            for k in range(0, len(bits) - 7, 8)
        )
        self.ultimo_texto = self._visible(datos)
        self.ultimo_errores = errores
        if errores == 0:
            self.tramas_ok += 1
        else:
            self.tramas_error += 1

        ahora = time.time()
        if ahora - self.ultima_impresion >= self.imprimir_cada:
            self.ultima_impresion = ahora
            print('[Rx] %s | %s' % (self.ultimo_texto, self.estado()))

    def texto(self):
        return self.ultimo_texto

    def estado(self):
        total = self.tramas_ok + self.tramas_error
        return 'Tramas OK: %d / %d | errores en la ultima: %d bits' % (
            self.tramas_ok, total, self.ultimo_errores)

    def work(self, input_items, output_items):
        for b in input_items[0]:
            bit = int(b) & 1
            if self.capturando:
                self.carga.append(bit)
                if len(self.carga) == self.n_carga:
                    self._cerrar_trama()
                    self.capturando = False
                    self.registro = 0
                continue

            self.registro = ((self.registro << 1) | bit) & MASCARA
            if bin(self.registro ^ SINCRONIA).count('1') <= self.max_errores_sincronia:
                self.capturando = True
                self.carga = []
        return len(input_items[0])
