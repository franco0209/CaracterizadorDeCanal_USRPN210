# Caracterizador de Canal — USRP N210

Aplicación de escritorio (Python + pywebview) para caracterizar un canal inalámbrico con dos SDR USRP N210: uno transmite una señal conocida y el otro captura muestras I/Q. Mide:

- Pérdida de propagación (modelo log-distancia)
- Efecto de obstrucciones (LOS vs. obstáculos)
- Desvanecimiento a pequeña escala
- Multitrayectoria y respuesta estimada del canal

Incluye un **canal simulado**, así que se puede probar toda la interfaz sin hardware.

## Estructura

- `app.py`: ventana y orquestación (interfaz ↔ hardware ↔ lógica)
- `radio.py`, `sdr_iq.py`: manejo del USRP (UHD)
- `logica/`: física y algoritmos (potencia, detección, propagación, canal, simulador…)
- `web/`: interfaz (HTML/JS/CSS)
- `mediciones/`, `exportados/`: datos generados al usar la app

## Instalación (Ubuntu/Debian)

```bash
# 1. Clonar
git clone https://github.com/franco0209/CaracterizadorDeCanal_USRPN210.git
cd CaracterizadorDeCanal_USRPN210

# 2. Dependencias del sistema (UHD + GUI)
apt install -y python3-uhd uhd-host python3-gi gir1.2-webkit2-4.1 \
    libcairo2-dev libgirepository1.0-dev

# 3. Entorno virtual (con acceso a python3-uhd del sistema)
python3 -m venv --system-site-packages venv
source venv/bin/activate

# 4. Dependencias de Python
pip install numpy pywebview
```

> Si no tienes las imágenes de firmware del USRP, descárgalas con `uhd_images_downloader`.

> Si falla `gir1.2-webkit2-4.1`, prueba con `gir1.2-webkit2-4.0`.

## Conexión del hardware (opcional)

Los N210 se conectan por Ethernet (IP por defecto `192.168.10.2`). Configura tu interfaz de red y comprueba:

```bash
sudo ip addr add 192.168.10.1/24 dev <tu_interfaz>   # ej. enp0s31f6
ping 192.168.10.2
uhd_find_devices
```

## Ejecución

```bash
source venv/bin/activate
python3 app.py

# con el inspector web (depuración)
DEBUG=1 python3 app.py
```

Sin USRP conectados, usa la fuente **simulada** desde la interfaz.
