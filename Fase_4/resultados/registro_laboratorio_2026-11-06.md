# Registro de laboratorio – Fase 4 (06/11/2026)

Enlace por aire: USRP 2920 (Tx, otro PC) → HackRF One (Rx, portátil). fc = 870 MHz.

## Ajuste final del receptor
| Parámetro | Valor |
|---|---|
| `lo_offset` | 200 kHz (con 0 el pico de DC y el desbalance I/Q caían dentro del canal: I-Q elíptico) |
| `freq_corr` | −6500 Hz |
| LNA / VGA / AMP | 16 / 20 / 0 dB |
| `hackrf_rate` / `decim` | 8 MS/s / 8 (Rx original) → **4 MS/s / 4 (v2)** |
| Tx | `tx_gain` y `tx_amp` por defecto del `.grc` de la Fase 4 |

## Problemas encontrados en hardware y solución
1. **BER ≈ 0,3–0,4 en condición limpia con el texto llegando perfecto.**
   - Causa: overflows del HackRF (`O` en consola) al abrir la GUI o al usar el portátil. Se pierden muestras y el flujo salta varios bits.
   - `e_Ref_Alineada` solo corregía saltos de ±3 bits y quedaba desalineada para siempre.
   - Solución: realineación global (todos los desfases, z ≥ 10) y `segmentos_arranque = 3` en `e_BER_Curve`.
2. **El CSV dejó de actualizarse** (quedó `curva_BER.tmp`).
   - Causa: otro programa tenía `curva_BER.csv` abierto justo cuando `e_BER_CSV` lo reemplazaba; en Windows eso da error y el bloque se detenía.
   - Solución: `e_BER_CSV` reintenta en el siguiente guardado.
3. **La gráfica QT GUI Vector Sink (`curva_ber`) no dibuja los datos**: se queda en 0 aunque el CSV tenga valores.
   - Solución: visor externo `herramientas/ver_curva_ber.py`, que lee el CSV y superpone la simulación.
4. **Piso falso de BER (~1e-2 a 6e-2) en la primera medición 0–18 dB** (`curva_BER_ascii_intento1.csv`).
   - Causa: episodios de pérdida de muestras durante 16 min. Cada realineo dejaba ~1000–2000 bits comparados con la referencia desalineada.
   - Solución en `Receptor_FSK_HackRF_Fase4_v2.grc`:
     - Rx liviano: sin las gráficas pesadas y HackRF a 4 MS/s;
     - `e_Ref_Alineada` emite el tag `realineo`;
     - `e_BER_Curve` descarta los 8000 bits previos y los 1000 posteriores a cada realineo.
   - Validado sin hardware: sin errores reales da BER = 0; con 1/10/25/35 % de errores reales da la BER correcta, sin sesgo.

Todos los cambios del código van marcados con `# Ajuste Fase 4` o `# Ajuste Fase 4 v2`.
`Receptor_FSK_HackRF_Fase4.grc` (sin el descarte) se conserva sin modificar.

## Resultados
| Archivo | Condición | Resultado |
|---|---|---|
| `curva_BER_limpia.csv` / `.png` | Eb/N0 30–48 dB, 10 000 bits/punto | BER = 0 en los 19 puntos (cota ≈ 1e-4) |
| `curva_BER_ascii_intento1.csv` | 0–18 dB, Rx original, 16 min | **No válida**: piso falso por realineos |
| `curva_BER_ascii.csv` / `.png` | 0–18 dB, `pn9 = 0`, v2, 12,5 min (~4 pasadas, ~400 000 bits/punto) | **BER = 1e-3 en ≈ 14,3 dB** (simulación: 13,8 dB) → penalización ≈ 0,5 dB ≤ 2 dB → **CONFORME**. 4 realineos, 1,2 % de los bits descartados. Anomalía: 16 dB (3,9e-4) peor que 15 dB (2,1e-4), probablemente un residuo de perturbación. |
| `curva_BER_pn9_intento1.csv` | 0–18 dB, `pn9 = 1`, v2, ~15 min | **No válida**: más de 15 realineos (1,9–3 % de los bits descartados), piso falso de ~2e-3 a 7e-3 y curva corrida 2–3 dB. Coincide con el uso del portátil durante la corrida (captura a mitad de la medición) y posibles perturbaciones del entorno. |
| `curva_BER_pn9.csv` / `.png` | 0–18 dB, `pn9 = 1`, v2, ~10 min (~3 pasadas, ~300 000 bits/punto), sin tocar el portátil | **BER = 1e-3 en ≈ 14,2 dB** (simulación PN9: 13,7 dB) → penalización ≈ 0,5 dB ≤ 2 dB → **CONFORME**. Curva monótona. 4 realineos; el acumulado de bits descartados fue de 0,5 % a 1,9 % (valor final: 1,9 %). |
| `curvas_BER_comparacion.png` | ASCII y PN9 medidas frente a simuladas | Figura resumen para el informe |

### Medición PN9 (`curva_BER_pn9.csv`)
| Eb/N0 (dB) | 0 | 2 | 4 | 6 | 8 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| BER | 0,41 | 0,37 | 0,29 | 0,21 | 0,12 | 5,0e-2 | 2,6e-2 | 1,1e-2 | 3,8e-3 | 1,3e-3 | 2,3e-4 | 7,0e-5 | 6,7e-6 | 0 |

### Comparación (criterio de la guía: BER = 1e-3, penalización ≤ 2 dB)
| Modo | Simulación | Medida | Penalización | Veredicto |
|---|---|---|---|---|
| ASCII (`pn9 = 0`) | 13,8 dB | 14,3 dB | ≈ 0,5 dB | Conforme |
| PN9 (`pn9 = 1`) | 13,7 dB | 14,2 dB | ≈ 0,5 dB | Conforme |

La penalización de ~0,5 dB coincide con la estimada en simulación para un error de frecuencia residual de 2–5 kHz; también puede deberse al ruido propio del enlace. El blanqueo PN9 da una curva más regular (proporción de unos 0,498 frente a 0,451 en ASCII); el DC Blocker trabaja mejor con datos balanceados.

### Medición ASCII (`curva_BER_ascii.csv`)
| Eb/N0 (dB) | 0 | 2 | 4 | 6 | 8 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| BER | 0,39 | 0,35 | 0,33 | 0,20 | 0,11 | 6,4e-2 | 4,2e-2 | 1,6e-2 | 8,0e-3 | 1,8e-3 | 2,1e-4 | 3,9e-4 | 1,8e-5 | 0 |

## Observaciones para el informe
- Mientras corre la medición no se debe usar el portátil del Rx: capturas, mover ventanas o abrir programas generan overflows. Se comprobó con PN9: el intento con una captura a mitad de la corrida quedó invalidado y la repetición sin tocar nada salió conforme.
- Verificación del texto: el texto llega íntegro en condición limpia (≈ 100 % de tramas OK).

## Transmisor (valores por defecto de `Transmisor_FSK_USRP_Fase4.grc`)
| Parámetro | Valor |
|---|---|
| fc | 870 MHz |
| samp_rate / sps / Rb | 1 MS/s / 100 / 10 kbps |
| Δf | 20 kHz |
| `tx_gain` | 10 dB |
| `tx_amp` | 0,7 |

Hay que confirmar si en el PC del USRP se cambió alguno de estos valores en la GUI durante las mediciones.

## Capturas (`capturas_laboratorio\`)
| Archivo | Contenido |
|---|---|
| `01_ajuste_lo0_texto_ok_IQ_eliptico.png` | Ajuste con `lo_offset` = 0: texto bien, I-Q elíptico (desbalance I/Q) |
| `02_ajuste_lo200k_espectro_IQ_redondo.png` | Ajuste final: `lo_offset` 200 kHz, espectro, I-Q redondo, texto OK |
| `03_ajuste_frecuencia_instantanea_y_ojo.png` | Frecuencia instantánea y diagrama de ojo abierto |
| `04_ajuste_verificacion_canal_centrado.png` | Verificación de tramas y canal FSK centrado |
| `05_consola_overflows_al_arrancar.png` | Consola: overflows al arrancar y alineación de la referencia |
| `06_medicion_ascii_intento1_piso_falso.png` | Rx original: piso falso por realineos |
| `07_medicion_ascii_v2_valida.png` | Medición ASCII válida (v2) |
| `08_medicion_pn9_intento1.png` | PN9 con perturbaciones (no válida) |
| `09_medicion_pn9_v2_valida.png` | Medición PN9 válida (v2) |

**Falta para el informe:** una captura limpia y completa del flujograma v2 en GRC y otra del Tx. Se pueden tomar sin hardware, abriendo los `.grc` en GRC.
