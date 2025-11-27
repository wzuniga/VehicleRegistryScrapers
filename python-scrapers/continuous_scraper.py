"""
Script para ejecutar el scraper de SUNARP continuamente
Procesa placas pendientes de forma automática e indefinida
"""

import logging
import time
import requests
from sunarp_scraper import SunarpScraper, get_pending_plate
from plate_offices import get_office_by_plate

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Función principal - Loop continuo de scraping"""
    logger.info('=' * 80)
    logger.info('🔄 SUNARP Scraper Continuo - Procesamiento Automático')
    logger.info('=' * 80)
    logger.info('ℹ️ El scraper se ejecutará continuamente hasta que se detenga manualmente')
    logger.info('ℹ️ Presiona Ctrl+C para detener el proceso')
    logger.info('=' * 80)
    
    iteration = 0
    
    try:
        while True:
            iteration += 1
            logger.info('')
            logger.info('🔁' * 40)
            logger.info(f'📊 Iteración #{iteration}')
            logger.info('🔁' * 40)
            
            # Obtener placa pendiente de la API
            plate_data = get_pending_plate()
            
            if not plate_data:
                logger.warning('⚠️ No se pudo obtener placa de la API')
                logger.info('⏳ Esperando 5 segundos antes de reintentar...')
                time.sleep(5)
                continue
            
            plate_number = plate_data.get('plate')
            plate_id = plate_data.get('id')
            
            if not plate_number:
                logger.error('❌ La respuesta de la API no contiene una placa válida')
                logger.info('⏳ Esperando 5 segundos antes de reintentar...')
                time.sleep(5)
                continue
            
            # Obtener la oficina registral basándose en la primera letra de la placa
            office_name = get_office_by_plate(plate_number)
            
            logger.info(f'📋 Procesando nueva placa:')
            logger.info(f'   🆔 ID: {plate_id}')
            logger.info(f'   🚙 Placa: {plate_number}')
            logger.info(f'   🏢 Oficina detectada: {office_name}')
            
            # Crear nueva instancia del scraper para cada placa
            scraper = SunarpScraper()
            
            # Ejecutar scraper
            try:
                success = scraper.run(
                    office_name=office_name,
                    plate_number=plate_number,
                    plate_id=plate_id,
                    wait_time=3,  # Tiempo reducido entre placas
                    headless=False  # Ejecutar en modo headless para producción
                )
                
                if success:
                    logger.info(f'✅ Placa {plate_number} procesada exitosamente')
                else:
                    logger.error(f'❌ Error procesando placa {plate_number}')
                    
            except Exception as scraper_error:
                logger.error(f'❌ Excepción durante el scraping de {plate_number}: {scraper_error}')
            
            finally:
                # Asegurar limpieza del driver
                try:
                    scraper.cleanup()
                except:
                    pass
            
            logger.info(f'✅ Iteración #{iteration} completada')
            logger.info('⏳ Buscando siguiente placa pendiente...')
            time.sleep(2)  # Pequeña pausa entre iteraciones
            
    except KeyboardInterrupt:
        logger.info('')
        logger.info('🛑' * 40)
        logger.info('🛑 Proceso detenido por el usuario (Ctrl+C)')
        logger.info(f'📊 Total de iteraciones completadas: {iteration}')
        logger.info('🛑' * 40)
    except Exception as e:
        logger.error(f'❌ Error fatal en el loop principal: {e}')
        logger.error(f'📊 Iteraciones completadas antes del error: {iteration}')


if __name__ == '__main__':
    main()
