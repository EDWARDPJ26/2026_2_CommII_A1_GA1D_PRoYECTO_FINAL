"""Crea Fase4/Transmisor_FSK_USRP_Fase4.grc a partir de Transmisor_FSK_USRP.grc."""
import sys
from pathlib import Path

import yaml


class Dumper(yaml.SafeDumper):
    pass


def _str(dumper, data):
    estilo = '|' if '\n' in data else None
    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style=estilo)


Dumper.add_representer(str, _str)

origen = Path(sys.argv[1])
destino = Path(sys.argv[2])
modulo = Path(sys.argv[3]).read_text(encoding='utf-8')

with open(origen, encoding='utf-8') as f:
    fg = yaml.safe_load(f)

op = fg['options']['parameters']
op['id'] = 'Transmisor_FSK_USRP_Fase4'
op['title'] = 'Transmisor FSK - USRP 2920 (Fase 4: trama de telemetria)'
op['description'] = 'Transmisor FSK binario por USRP 2920 con trama de telemetria conocida para medir BER'
op['comment'] = 'Fase 4: transmite en bucle una trama de telemetria fija (preambulo + SFD + mensaje)'


def bloque(name, bid, params, coord):
    return {'name': name, 'id': bid, 'parameters': params,
            'states': {'coordinate': coord, 'rotation': 0, 'state': 'enabled'}}


nuevos = [
    bloque('trama_telemetria', 'epy_module',
           {'alias': '', 'comment': 'Arma la trama. El mismo modulo va en el receptor.',
            'source_code': modulo},
           [24, 100]),
    bloque('mensaje', 'variable',
           {'comment': 'Lecturas simuladas FIJAS: el receptor debe conocer el mismo texto',
            'value': '"ID:S01;T:24.5C;HR:15%;ALT:2500msnm;P:184kPa;NIV:72%;Q:3.4m3/h"'},
           [200, 100]),
    bloque('pn9', 'variable',
           {'comment': '0 = carga ASCII sin blanqueo\n1 = carga blanqueada con PN9\nDebe valer lo mismo en el Tx y en el Rx',
            'value': '0'},
           [640, 100]),
    bloque('trama_bits', 'variable',
           {'comment': 'Preambulo 0x55555555 + SFD 0x904E + carga',
            'value': 'trama_telemetria.construir_trama(mensaje, pn9)'},
           [760, 100]),
]

for b in fg['blocks']:
    if b['name'] == 'bit_source':
        b['parameters']['vector'] = 'trama_bits'
        b['parameters']['comment'] = 'Trama de telemetria repetida en bucle'

# Variables y modulo antes de los bloques de procesamiento
idx = next(i for i, b in enumerate(fg['blocks']) if b['name'] == 'bit_source')
fg['blocks'][idx:idx] = nuevos

with open(destino, 'w', encoding='utf-8', newline='\n') as f:
    yaml.dump(fg, f, Dumper=Dumper, sort_keys=False, allow_unicode=True, width=4096)
print('creado', destino)
