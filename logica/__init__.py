"""Lógica física/matemática de la Práctica 3 (caracterización del canal con SDR).

Orden sugerido de estudio (cada archivo depende solo de los anteriores):
    1. parametros.py        unidades, dB, longitud de onda, configuración del sistema
    2. senal_prueba.py      Zadoff-Chu y estructura de la ráfaga transmitida
    3. deteccion.py         detección de ráfagas (Schmidl-Cox), CFO y sincronismo fino
    4. potencia.py          potencia recibida, piso de ruido, SNR (procedimiento completo)
    5. propagacion.py       pérdida de propagación y modelo log-distancia
    6. obstrucciones.py     atenuación por obstáculos respecto a LOS
    7. desvanecimiento.py   desvanecimiento a pequeña escala (Rayleigh / Rice)
    8. canal.py             estimación de la respuesta al impulso, multitrayectoria
    9. analisis.py          comparación de efectos y qué se compensa con ganancia
   10. enlace.py            verificación de conexión (diagnóstico del módulo 00)
   11. simulador.py         canal simulado para ensayar sin hardware
"""
