# SUNARP Python Scraper

Scraper de Python usando `undetected_chromedriver` para acceder a SUNARP sin ser detectado.

## Instalación

1. Crear y activar un entorno virtual:
```bash
# Crear el entorno virtual
python -m venv venv

# Activar el entorno virtual (Windows PowerShell)
.\venv\Scripts\Activate.ps1

# O en Windows CMD
venv\Scripts\activate.bat
```

2. Instalar las dependencias:
```bash
pip install -r requirements.txt
```

## Uso

Ejecutar el scraper:
```bash
python sunarp_scraper.py
```

## Características

- ✅ Usa `undetected_chromedriver` para evitar detección de bots
- ✅ Configuración anti-detección con scripts CDP
- ✅ Simula comportamiento humano
- ✅ Toma capturas de pantalla automáticas
- ✅ Logging detallado del proceso
- ✅ Manejo de errores robusto

## Estructura

- `sunarp_scraper.py` - Script principal del scraper
- `requirements.txt` - Dependencias del proyecto
- `README.md` - Este archivo

## Notas

- El scraper automáticamente descarga el ChromeDriver compatible
- Las capturas de pantalla se guardan en el directorio actual
- El navegador se mantiene abierto durante 10 segundos por defecto
