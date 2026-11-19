## Práctica 3

## 1. Objetivos

- Caracterizar experimentalmente un canal inalámbrico utilizando SDR.

- Evaluar los efectos de distancia, obstrucciones y multitrayectoria sobre una señal recibida.

- Estimar parámetros básicos de propagación a partir de mediciones reales.

## 2. Desarrollo de la práctica

En esta práctica se utilizarán dos SDR para transmitir una señal conocida y analizar cómo el canal inalámbrico modifica la señal recibida. Durante cada conjunto de mediciones se deberán mantener constantes la potencia de transmisión, las ganancias de los SDR, la frecuencia de operación y los demás parámetros del sistema.

## 2.1. Señal de prueba

- a) Diseñe una señal conocida que permita identificar y analizar correctamente la transmisión en el receptor.

- b) Transmita periódicamente la señal utilizando un SDR.

- c) Capture las muestras I/Q utilizando un segundo SDR.

- d) Implemente un procedimiento que permita detectar automáticamente cada transmisión y estimar su po- tencia recibida.

## 2.2. Pérdida de propagación

- a) Realice mediciones para diferentes distancias entre el transmisor y el receptor.

- b) Para cada distancia, realice múltiples adquisiciones y calcule la potencia recibida promedio.

- c) Grafique la potencia recibida en función de la distancia.

- d) Utilizando las mediciones obtenidas, estime los parámetros de un modelo de pérdida de propagación logarítmico.

- e) Compare el modelo obtenido con las mediciones experimentales.

## 2.3. Efecto de las obstrucciones

Manteniendo aproximadamente la misma distancia entre transmisor y receptor:

- a) Realice mediciones en una condición con línea de vista (LOS).

- b) Introduzca diferentes obstáculos entre transmisor y receptor y repita las mediciones.

- c) Compare las potencias recibidas.

- d) Analice el efecto de las diferentes condiciones de propagación.


## 2.4. Desvanecimiento a pequeña escala

- a) Mantenga fijo el transmisor.

- b) Desplace el receptor en pequeños intervalos sobre una distancia equivalente a varias longitudes de onda.

- c) Capture la señal recibida en cada posición.

- d) Grafique la potencia recibida en función de la posición.

- e) Analice las variaciones observadas y determine las diferencias entre este fenómeno y la pérdida de propa- gación estudiada anteriormente.

## 2.5. Multitrayectoria y estimación del canal

- a) Utilizando una señal conocida, implemente un procedimiento para estimar la respuesta del canal inalám- brico.

- b) Obtenga y grafique la respuesta estimada del canal.

- c) Repita el experimento para al menos dos escenarios diferentes:

- línea de vista;

- escenario con presencia significativa de multitrayectoria.

- d) Compare los resultados e identifique las principales componentes recibidas.

## 2.6. Análisis experimental

Utilizando todas las mediciones realizadas:

- a) Compare los efectos producidos por:

- distancia;

- obstrucciones;

- desplazamientos pequeños del receptor;

- multitrayectoria.

- b) Explique cuáles de estos efectos pueden ser compensados modificando únicamente la potencia o ganancia del sistema y cuáles requieren técnicas adicionales de procesamiento de señal.

La implementación deberá realizarse mediante programación en MATLAB o Python. No se permite utilizar bloques de GNU Radio.

## 3. Uso de inteligencia artificial

Se permite el uso de herramientas de inteligencia artificial durante el desarrollo de la práctica. Sin embargo, durante la presentación se evaluará la comprensión del código desarrollado, de los algoritmos utilizados y de los resultados obtenidos.


## 4. Presentación del informe

- Cuando el docente lo autorice, es decir luego de presentar la práctica, puede mandar un correo electrónico a: ahilariot@unsa.edu.pe con las siguientes especificaciones:

- Asunto: Redes Inalámbricas: X - Informe de práctica 3, Equipo Y.

- El correo electrónico debe contener: Informe en pdf (Escrito en LATEX), y un enlace para un Drive personal donde estén los programas desarrollados en MATLAB o Python.
