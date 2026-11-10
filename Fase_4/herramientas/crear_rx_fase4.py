"""Crea Fase4/Receptor_FSK_HackRF_Fase4.grc a partir de Receptor_FSK_HackRF_Ojo.grc
y de la plantilla BER_SDR_INSTRUMENTACION_BASE.grc."""
import copy
import sys
from pathlib import Path

import yaml


class Dumper(yaml.SafeDumper):
    pass


def _str(dumper, data):
    estilo = '|' if '\n' in data else None
    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style=estilo)


Dumper.add_representer(str, _str)

if len(sys.argv) != 7:
    sys.exit('uso: crear_rx_fase4.py <rx_ojo.grc> <plantilla.grc> <tx_fase4.grc> <e_Texto_Rx.py> <e_Ref_Alineada.py> <destino.grc>')
origen, plantilla, tx_fase4, texto_rx, ref_alineada, destino = (Path(a) for a in sys.argv[1:7])
assert destino.suffix == '.grc'


def cargar(p):
    with open(p, encoding='utf-8') as f:
        return yaml.safe_load(f)


fg = cargar(origen)
base = cargar(plantilla)
tx = cargar(tx_fase4)


def buscar(g, name):
    return next(b for b in g['blocks'] if b['name'] == name)


def bloque(name, bid, params, coord):
    return {'name': name, 'id': bid, 'parameters': params,
            'states': {'coordinate': coord, 'rotation': 0, 'state': 'enabled'}}


op = fg['options']['parameters']
op['id'] = 'Receptor_FSK_HackRF_Fase4'
op['title'] = 'Receptor FSK - HackRF One (Fase 4: medicion BER vs Eb/N0)'
op['description'] = 'Receptor FSK con instrumentacion BER (e_EbN0_Sweep + e_BER_Curve) y verificacion del texto de telemetria'

# Hacer espacio: correr a la derecha la cadena de procesamiento desde channel_filter
for b in fg['blocks']:
    x, y = b['states']['coordinate']
    if y >= 300 and x >= 400:
        b['states']['coordinate'] = [x + 640, y]

# 1) Adaptacion de tasa + filtro de canal separado
cf = buscar(fg, 'channel_filter')
rate_adapt = copy.deepcopy(cf)
rate_adapt['name'] = 'rate_adapt'
rate_adapt['parameters']['taps'] = 'firdes.low_pass(1.0, hackrf_rate, 300e3, 100e3)'
rate_adapt['parameters']['comment'] = ('Adaptacion de tasa: centra la senal y baja de 8 MS/s a 1 MS/s\n'
                                       'con un filtro ANCHO (300 kHz), para que el filtro de canal\n'
                                       'quede despues del ruido de e_EbN0_Sweep')
rate_adapt['states']['coordinate'] = [408, 380]

cf['id'] = 'low_pass_filter'
cf['parameters'] = {
    'alias': '', 'affinity': '', 'beta': '6.76',
    'comment': 'Filtro de canal (parte del Rx digital), ajustado en la Fase 4:\n35 kHz / 10 kHz (antes 60/40): menos ruido al discriminador',
    'cutoff_freq': '35e3', 'decim': '1', 'gain': '1.0', 'interp': '1',
    'maxoutbuf': '0', 'minoutbuf': '0', 'samp_rate': 'samp_rate',
    'type': 'fir_filter_ccf', 'width': '10e3', 'win': 'window.WIN_HAMMING',
}

# 2) Instrumento de la plantilla (codigo sin modificar)
variables = [
    ('EbN0_min', '0.0', ''), ('EbN0_max', '18.0', 'Subido de 14 a 18 dB para cruzar BER = 1e-3 con margen'),
    ('EbN0_step', '1.0', ''),
    ('N_EbN0', 'int(round((EbN0_max-EbN0_min)/EbN0_step))+1', ''),
    ('Rb', 'symbol_rate', 'BFSK: Rb = Rs = 10 kbps'),
    ('bb_rate', 'samp_rate', 'Tasa I/Q a la entrada del Rx digital (1 MS/s)'),
    ('bits_por_punto', '100000', ''), ('bits_guardia', '1000', ''),
    ('delay_bits', '0', 'Queda en 0: e_Ref_Alineada entrega la referencia ya alineada'),
    ('update_every', '1000', ''),
]
nuevos = []
for i, (name, value, comment) in enumerate(variables):
    nuevos.append(bloque(name, 'variable', {'comment': comment, 'value': value},
                         [1400 + 112 * (i % 5), 12 + 72 * (i // 5)]))

sweep = buscar(base, 'e_EbN0_Sweep')
sweep['states']['coordinate'] = [720, 360]
sweep['parameters']['comment'] = 'Instrumento: AWGN controlado (barrido de Eb/N0)'

curve = buscar(base, 'e_BER_Curve')
curve['parameters'].update({
    'EbN0_min': 'EbN0_min', 'EbN0_max': 'EbN0_max', 'EbN0_step': 'EbN0_step',
    'bits_por_punto': 'bits_por_punto', 'bits_guardia': 'bits_guardia',
    'delay_bits': 'delay_bits', 'update_every': 'update_every',
    'comment': 'Entrada 0: bits Tx de referencia\nEntrada 1: bits Rx (slicer)',
})
curve['states'].pop('_io_cache', None)
AJUSTE = '  # Ajuste Fase 4: compatibilidad GNU Radio 3.10'
src = curve['parameters']['_source_code']
assert src.count('gr.sync_decimator') == 2
src = src.replace('class blk(gr.sync_decimator):', 'class blk(gr.decim_block):' + AJUSTE)
src = src.replace('        gr.sync_decimator.__init__(',
                  '        ' + AJUSTE.strip() + '\n        gr.decim_block.__init__(')
curve['parameters']['_source_code'] = src
curve['states']['coordinate'] = [2360, 800]

# GRC calcula el tamano de los puertos vectoriales con los valores POR DEFECTO del
# codigo: deben coincidir con el rango del barrido (EbN0_max = 18 -> 19 puntos).
AJUSTE_MAX = '  # Ajuste Fase 4: GRC dimensiona los puertos con este valor (debe ser = EbN0_max)'


def ajustar_default_max(blk):
    s = blk['parameters']['_source_code']
    lineas = [l for l in s.split('\n') if l.strip().startswith('EbN0_max=14.0')]
    assert len(lineas) == 1, lineas
    blk['parameters']['_source_code'] = s.replace(lineas[0], lineas[0].replace('14.0', '18.0') + AJUSTE_MAX)


ajustar_default_max(curve)

csv_blk = buscar(base, 'e_BER_CSV')
csv_blk['parameters']['comment'] = ('Guarda la curva en Fase4/curva_BER.csv\n'
                                    'Cada corrida lo sobrescribe: renombrarlo al terminar (ascii / pn9)')
csv_blk['states'].pop('_io_cache', None)
src = csv_blk['parameters']['_source_code']
viejo = '        self.carpeta = Path(__file__).resolve().parent\n'
assert src.count(viejo) == 1
src = src.replace(viejo, '        ' + AJUSTE.strip() + '\n'
                  "        self.carpeta = Path(__file__).resolve().parent if '__file__' in globals() else Path.cwd()\n")
csv_blk['parameters']['_source_code'] = src
ajustar_default_max(csv_blk)
csv_blk['states']['coordinate'] = [2760, 920]

curva = buscar(base, 'curva_ber')
curva['states']['coordinate'] = [2760, 780]

for b in (sweep, curve, csv_blk, curva):
    for k in ('bus_sink', 'bus_source', 'bus_structure'):
        b['states'].pop(k, None)
nuevos += [sweep, curve, csv_blk, curva]

# 3) Referencia Tx: mismo modulo, mensaje y pn9 que el transmisor
for name in ('trama_telemetria', 'mensaje', 'pn9', 'trama_bits'):
    b = copy.deepcopy(buscar(tx, name))
    nuevos.append(b)
buscar_n = {b['name']: b for b in nuevos}
buscar_n['trama_telemetria']['states']['coordinate'] = [1400, 160]
buscar_n['mensaje']['states']['coordinate'] = [1576, 160]
buscar_n['pn9']['states']['coordinate'] = [1960, 160]
buscar_n['trama_bits']['states']['coordinate'] = [2080, 160]

nuevos.append(bloque('e_Ref_Alineada', 'epy_block', {
    '_source_code': ref_alineada.read_text(encoding='utf-8'),
    'comment': 'Referencia Tx (trama conocida) alineada automaticamente\ncon los bits recibidos (Tx y Rx en PCs distintos)',
    'trama': 'trama_bits', 'z_min': '10.0', 'max_salto': '3', 'min_bits': '2000', 'max_bits': '20000',
}, [2080, 780]))

nuevos.append(bloque('ebn0_actual', 'qtgui_number_sink', {
    'autoscale': 'False', 'avg': '0', 'color1': '("black", "black")', 'factor1': '1',
    'graph_type': 'qtgui.NUM_GRAPH_HORIZ', 'gui_hint': '', 'label1': '"Eb/N0 aplicado"',
    'max': 'EbN0_max', 'min': 'EbN0_min', 'name': '"Punto actual del barrido"',
    'nconnections': '1', 'type': 'float', 'unit1': '"dB"', 'update_time': '0.25',
}, [1040, 220]))

# 4) Rama de texto
nuevos.append(bloque('e_Texto_Rx', 'epy_block', {
    '_source_code': texto_rx.read_text(encoding='utf-8'),
    'comment': 'Verificacion visual del texto (no afecta la BER)',
    'imprimir_cada': '1.0', 'max_errores_sincronia': '2',
    'mensaje': 'mensaje', 'pn9': 'pn9',
}, [2360, 980]))
nuevos.append(bloque('texto_probe', 'variable_function_probe', {
    'block_id': 'e_Texto_Rx', 'comment': '', 'function_args': '',
    'function_name': 'texto', 'poll_rate': '4', 'value': '""',
}, [1400, 260]))
nuevos.append(bloque('estado_probe', 'variable_function_probe', {
    'block_id': 'e_Texto_Rx', 'comment': '', 'function_args': '',
    'function_name': 'estado', 'poll_rate': '4', 'value': '""',
}, [1576, 260]))
nuevos.append(bloque('texto_rx', 'variable_qtgui_label', {
    'comment': '', 'formatter': 'None', 'gui_hint': '',
    'label': 'Texto recibido', 'type': 'string', 'value': 'texto_probe',
}, [1760, 260]))
nuevos.append(bloque('estado_rx', 'variable_qtgui_label', {
    'comment': '', 'formatter': 'None', 'gui_hint': '',
    'label': 'Verificacion', 'type': 'string', 'value': 'estado_probe',
}, [1960, 260]))

idx = next(i for i, b in enumerate(fg['blocks']) if b['id'] not in ('variable', 'variable_qtgui_range', 'import'))
fg['blocks'][idx:idx] = [b for b in nuevos if b['id'] in ('variable', 'epy_module', 'variable_function_probe', 'variable_qtgui_label')]
fg['blocks'] += [b for b in nuevos if b['id'] not in ('variable', 'epy_module', 'variable_function_probe', 'variable_qtgui_label')]
fg['blocks'].insert(fg['blocks'].index(cf), rate_adapt)

# Ajuste del Rx: integrador (Fase 2) + Symbol Sync en lugar de Delay + Keep 1 in N
df = buscar(fg, 'data_filter')
df['id'] = 'blocks_moving_average_xx'
df['parameters'] = {'alias': '', 'affinity': '', 'comment': 'Integrador (filtro acoplado NRZ), como en la Fase 2',
                    'length': 'sps', 'max_iter': '4000', 'maxoutbuf': '0', 'minoutbuf': '0',
                    'scale': '1.0/sps', 'type': 'float', 'vlen': '1'}

sync_blk = buscar(fg, 'symbol_sampler')
sync_blk['name'] = 'symbol_sync'
sync_blk['id'] = 'digital_symbol_sync_xx'
sync_blk['parameters'] = {
    'alias': '', 'affinity': '',
    'comment': 'Recupera el reloj del Tx (sigue la deriva) y elige\nel instante de muestreo. Reemplaza Delay + Keep 1 in N',
    'constellation': 'digital.constellation_bpsk().base()', 'damping': '1.0', 'loop_bw': '0.005',
    'max_dev': '0.05', 'maxoutbuf': '0', 'minoutbuf': '0', 'nfilters': '128', 'osps': '1',
    'pfb_mf_taps': '[]', 'resamp_type': 'digital.IR_MMSE_8TAP', 'sps': 'sps', 'ted_gain': '1.0',
    'ted_type': 'digital.TED_GARDNER', 'type': 'ff'}
fg['blocks'] = [b for b in fg['blocks'] if b['name'] not in ('sample_align', 'sample_delay')]
buscar(fg, 'eye_rx')['parameters']['comment'] = 'Ojo a la salida del integrador (maxima apertura al final de cada simbolo)'

bits_rx = buscar(fg, 'bits_rx')
bits_rx['parameters']['comment'] = 'Bits de la trama de telemetria'

# Conexiones
quitar = (['hackrf_source', '0', 'channel_filter', '0'], ['data_filter', '0', 'sample_align', '0'],
          ['sample_align', '0', 'eye_rx', '0'], ['sample_align', '0', 'symbol_sampler', '0'],
          ['symbol_sampler', '0', 'slicer', '0'])
con = [c for c in fg['connections'] if c not in quitar]
assert len(con) == len(fg['connections']) - len(quitar)
con += [
    ['hackrf_source', '0', 'rate_adapt', '0'],
    ['rate_adapt', '0', 'e_EbN0_Sweep', '0'],
    ['e_EbN0_Sweep', '0', 'channel_filter', '0'],
    ['e_EbN0_Sweep', '1', 'ebn0_actual', '0'],
    ['data_filter', '0', 'symbol_sync', '0'],
    ['data_filter', '0', 'eye_rx', '0'],
    ['symbol_sync', '0', 'slicer', '0'],
    ['slicer', '0', 'e_Ref_Alineada', '0'],
    ['e_Ref_Alineada', '0', 'e_BER_Curve', '0'],
    ['slicer', '0', 'e_BER_Curve', '1'],
    ['e_BER_Curve', '1', 'curva_ber', '0'],
    ['e_BER_Curve', '0', 'e_BER_CSV', '0'],
    ['e_BER_Curve', '1', 'e_BER_CSV', '1'],
    ['slicer', '0', 'e_Texto_Rx', '0'],
]
fg['connections'] = con

with open(destino, 'w', encoding='utf-8', newline='\n') as f:
    yaml.dump(fg, f, Dumper=Dumper, sort_keys=False, allow_unicode=True, width=4096)
print('creado', destino)
