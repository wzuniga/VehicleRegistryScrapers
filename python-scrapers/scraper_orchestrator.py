"""Orquestador de scrapers.

Uso rapido:
  python scraper_orchestrator.py --mode test --plate BNP276
  python scraper_orchestrator.py --mode test --plate BNP276 --headless --plate-id 123
  python scraper_orchestrator.py --mode prod --once
  python scraper_orchestrator.py --mode prod
"""

import argparse
import logging
import time

from b_consulta_vehicular_scraper import ConsultaVehicularScraper, get_pending_plate


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_consulta_vehicular(plate_number, plate_id=None, headless=False):
    """Ejecuta una corrida del scraper de consulta vehicular."""
    scraper = ConsultaVehicularScraper()
    try:
        return scraper.run(
            plate_number=plate_number,
            plate_id=plate_id,
            headless=headless,
        )
    finally:
        if scraper.driver:
            scraper.cleanup()


def run_test_mode(args):
    """Modo test: permite enviar una placa manualmente."""
    plate_number = args.plate.strip().upper()

    logger.info('Iniciando modo TEST')
    logger.info('Placa manual: %s', plate_number)
    logger.info('Plate ID manual: %s', args.plate_id)
    logger.info('Headless: %s', args.headless)

    success = run_consulta_vehicular(
        plate_number=plate_number,
        plate_id=args.plate_id,
        headless=args.headless,
    )

    if success:
        logger.info('Ejecucion TEST finalizada correctamente')
        return 0

    logger.error('Ejecucion TEST fallida')
    return 1


def run_prod_mode(args):
    """Modo prod: consume placas pendientes desde API y ejecuta el scraper."""
    logger.info('Iniciando modo PROD')
    logger.info('Headless: %s', args.headless)
    logger.info('Solo una iteracion: %s', args.once)

    while True:
        plate_data = get_pending_plate()

        if not plate_data:
            if args.once:
                logger.info('No hay placas pendientes para procesar en esta iteracion')
                return 0

            logger.info('No hay placas pendientes; esperando %s segundos...', args.poll_seconds)
            time.sleep(args.poll_seconds)
            continue

        plate_number = plate_data.get('plate')
        plate_id = plate_data.get('id')

        if not plate_number:
            logger.error('La API devolvio una placa invalida: %s', plate_data)
            if args.once:
                return 1
            time.sleep(args.poll_seconds)
            continue

        logger.info('Procesando placa pendiente: %s (id=%s)', plate_number, plate_id)
        success = run_consulta_vehicular(
            plate_number=plate_number,
            plate_id=plate_id,
            headless=args.headless,
        )

        if not success:
            logger.error('Fallo al procesar la placa: %s', plate_number)
            if args.once:
                return 1

        if args.once:
            return 0 if success else 1

        time.sleep(args.poll_seconds)


def parse_args():
    parser = argparse.ArgumentParser(
        description='Orquestador para ejecutar scrapers en modo test o prod.'
    )

    parser.add_argument(
        '--mode',
        choices=['test', 'prod'],
        default='test',
        help='Modo de ejecucion. Default: test'
    )
    parser.add_argument(
        '--plate',
        help='Placa manual para modo test (ejemplo: BNP276)'
    )
    parser.add_argument(
        '--plate-id',
        help='ID opcional para modo test. Si no se envia, se omite mark-loaded.'
    )
    parser.add_argument(
        '--headless',
        action='store_true',
        help='Ejecuta Chrome en modo headless'
    )
    parser.add_argument(
        '--once',
        action='store_true',
        help='En modo prod, procesa solo una iteracion y termina'
    )
    parser.add_argument(
        '--poll-seconds',
        type=int,
        default=2,
        help='Segundos de espera entre iteraciones en modo prod (default: 2)'
    )

    args = parser.parse_args()

    if args.mode == 'test' and not args.plate:
        parser.error('--plate es obligatorio cuando --mode test')

    if args.poll_seconds < 1:
        parser.error('--poll-seconds debe ser mayor o igual a 1')

    return args


def main():
    args = parse_args()

    if args.mode == 'test':
        return run_test_mode(args)

    return run_prod_mode(args)


if __name__ == '__main__':
    raise SystemExit(main())
