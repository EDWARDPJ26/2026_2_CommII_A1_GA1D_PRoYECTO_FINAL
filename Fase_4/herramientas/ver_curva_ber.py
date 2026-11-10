"""
ver_curva_ber.py  (Fase 4)
Visor en vivo de la curva BER vs Eb/N0 medida por el receptor.

Relee Fase4/curva_BER.csv cada 2 s (lo escribe e_BER_CSV mientras corre el Rx)
y lo dibuja en escala logaritmica junto con las curvas simuladas de referencia
(Fase4/simulacion/curva_BER_sim_ascii.csv y curva_BER_sim_pn9.csv) y la linea
de BER = 1e-3 del criterio de la guia (penalizacion <= 2 dB).

Puntos sin errores: e_BER_CSV guarda BER = 0 y log10_BER = log10(3/N). Se dibujan
como cota superior (triangulo hacia abajo en 3/N), no como BER = 0.
Puntos aun no medidos (BER = 0 y log10_BER = 0) no se dibujan.

Uso (consola de radioconda o doble clic):
    python ver_curva_ber.py                 -> lee ..\\curva_BER.csv
    python ver_curva_ber.py archivo.csv     -> lee otro CSV (p. ej. curva_BER_ascii.csv)
    python ver_curva_ber.py archivo.csv --png salida.png   -> solo guarda la imagen

Solo lee: no modifica ningun archivo.
"""

import csv
import math
import sys
from pathlib import Path

CARPETA_FASE4 = Path(__file__).resolve().parent.parent
CSV_DEFECTO = CARPETA_FASE4 / 'curva_BER.csv'
SIMULADAS = [
    (CARPETA_FASE4 / 'simulacion' / 'curva_BER_sim_ascii.csv', 'Simulacion ASCII', '#7f7f7f', '--'),
    (CARPETA_FASE4 / 'simulacion' / 'curva_BER_sim_pn9.csv', 'Simulacion PN9', '#bcbd22', ':'),
]
PERIODO_MS = 2000


def leer_csv(ruta):
    """Devuelve (medidos, cotas): listas de (EbN0, BER). Tolera archivos a medio escribir."""
    medidos, cotas = [], []
    try:
        with open(ruta, newline='', encoding='utf-8') as f:
            filas = list(csv.DictReader(f))
    except (OSError, csv.Error):
        return None
    for fila in filas:
        try:
            eb = float(fila['EbN0_dB'])
            ber = float(fila['BER'])
            lb = float(fila['log10_BER'])
        except (KeyError, TypeError, ValueError):
            continue
        if ber > 0:
            medidos.append((eb, ber))
        elif lb < 0:                      # sin errores: cota 3/N
            cotas.append((eb, 10.0 ** lb))
        # ber == 0 y lb == 0: punto aun no medido
    return medidos, cotas


def ebn0_en_ber(puntos, objetivo=1e-3):
    """Eb/N0 (interpolado en log10) donde la curva cruza BER = objetivo, o None."""
    for (e1, b1), (e2, b2) in zip(puntos, puntos[1:]):
        if b1 >= objetivo >= b2 and b1 > 0 and b2 > 0 and b1 != b2:
            t = (math.log10(b1) - math.log10(objetivo)) / (math.log10(b1) - math.log10(b2))
            return e1 + t * (e2 - e1)
    return None


def main():
    args = sys.argv[1:]
    png = None
    if '--png' in args:
        i = args.index('--png')
        png = args[i + 1]
        del args[i:i + 2]
    ruta = Path(args[0]) if args else CSV_DEFECTO

    import matplotlib
    if png:
        matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation

    fig, ax = plt.subplots(figsize=(9, 6))
    try:
        fig.canvas.manager.set_window_title('Curva BER vs Eb/N0 (Fase 4)')
    except AttributeError:
        pass

    simuladas = []
    for r, etiqueta, color, estilo in SIMULADAS:
        datos = leer_csv(r)
        if datos and datos[0]:
            simuladas.append((etiqueta, datos[0], color, estilo))

    def dibujar(_=None):
        datos = leer_csv(ruta)
        if datos is None:
            return
        medidos, cotas = datos
        ax.clear()
        for etiqueta, pts, color, estilo in simuladas:
            x, y = zip(*pts)
            e3 = ebn0_en_ber(pts)
            extra = ' (1e-3 en %.1f dB)' % e3 if e3 is not None else ''
            ax.semilogy(x, y, estilo, color=color, lw=1.5, label=etiqueta + extra)
        if medidos:
            x, y = zip(*medidos)
            e3 = ebn0_en_ber(sorted(medidos))
            extra = ' (1e-3 en %.1f dB)' % e3 if e3 is not None else ''
            ax.semilogy(x, y, 'o-', color='#1f77b4', lw=2, ms=6, label='Experimental' + extra)
        if cotas:
            x, y = zip(*cotas)
            ax.semilogy(x, y, 'v', color='#2ca02c', ms=8,
                        label='Sin errores (cota 3/N)')
        ax.axhline(1e-3, color='#d62728', lw=1, ls='-.', label='BER = 1e-3 (criterio)')
        ax.set_ylim(1e-6, 1)
        ax.set_xlabel('Eb/N0 [dB]')
        ax.set_ylabel('BER')
        ax.set_title('Curva BER vs Eb/N0 - %s' % ruta.name)
        ax.grid(True, which='both', alpha=0.3)
        ax.legend(loc='lower left', fontsize=9)
        fig.tight_layout()

    dibujar()
    if png:
        fig.savefig(png, dpi=120)
        print('Imagen guardada en', png)
        return
    _anim = FuncAnimation(fig, dibujar, interval=PERIODO_MS, cache_frame_data=False)  # noqa: F841
    plt.show()


if __name__ == '__main__':
    main()
