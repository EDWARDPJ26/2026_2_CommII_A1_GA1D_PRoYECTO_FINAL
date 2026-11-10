"""
trama_telemetria
Arma la trama de telemetria de la Fase 4 (formato tipo IEEE 802.15.4g SUN-FSK):

    [preambulo 32 bits 0x55555555][SFD 16 bits 0x904E][carga: mensaje ASCII, MSB primero]

Si pn9 = 1, la carga se blanquea con la secuencia PN9 (x^9 + x^5 + 1, semilla 0x1FF).
El preambulo y el SFD nunca se blanquean, para poder detectarlos en el receptor.

El mismo modulo va en el transmisor y en el receptor, para que ambos tengan
exactamente la misma secuencia de referencia.
"""

PREAMBULO = 0x55555555
PREAMBULO_BITS = 32
SFD = 0x904E
SFD_BITS = 16


def entero_a_bits(valor, n):
    """Entero -> lista de n bits, MSB primero."""
    return [(valor >> (n - 1 - i)) & 1 for i in range(n)]


def bytes_a_bits(datos):
    """Bytes -> lista de bits, MSB primero en cada byte."""
    return [(b >> (7 - i)) & 1 for b in datos for i in range(8)]


def bits_a_bytes(bits):
    """Lista de bits (MSB primero) -> bytes. Ignora los bits sobrantes."""
    datos = bytearray()
    for k in range(0, len(bits) - 7, 8):
        b = 0
        for bit in bits[k:k + 8]:
            b = (b << 1) | (int(bit) & 1)
        datos.append(b)
    return bytes(datos)


def secuencia_pn9(n):
    """n bits de la PN9 (x^9 + x^5 + 1) con semilla 0x1FF."""
    estado = 0x1FF
    salida = []
    for _ in range(n):
        salida.append(estado & 1)
        nuevo = (estado ^ (estado >> 5)) & 1
        estado = (estado >> 1) | (nuevo << 8)
    return salida


def blanquear(bits):
    """XOR con la PN9. Aplicarlo dos veces devuelve los bits originales."""
    return [b ^ p for b, p in zip(bits, secuencia_pn9(len(bits)))]


def carga_bits(mensaje, pn9=0):
    """Bits de la carga (mensaje ASCII), blanqueados si pn9 = 1."""
    bits = bytes_a_bits(str(mensaje).encode('ascii', errors='replace'))
    return blanquear(bits) if int(pn9) else bits


def construir_trama(mensaje, pn9=0):
    """Trama completa como lista de bits 0/1."""
    return (entero_a_bits(PREAMBULO, PREAMBULO_BITS)
            + entero_a_bits(SFD, SFD_BITS)
            + carga_bits(mensaje, pn9))


def decodificar_carga(bits, pn9=0):
    """Bits de carga recibidos -> texto (para el receptor)."""
    bits = [int(b) & 1 for b in bits]
    if int(pn9):
        bits = blanquear(bits)
    return bits_a_bytes(bits).decode('ascii', errors='replace')
