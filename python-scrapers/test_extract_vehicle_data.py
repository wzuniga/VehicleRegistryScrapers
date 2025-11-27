"""
Script de prueba para extract_vehicle_data_from_markdown
"""
from consulta_vehicular_scraper import ConsultaVehicularScraper

# Texto de ejemplo con markdown
markdown_text = """\n# sunarp  \nSuperintendencia Nacional de los Registros Públicos  \n\n## Consulta Vehicular\n\n# DATOS DEL VEHÍCULO\n\n<table>\n  <tr>\n    <th>Nº PLACA:</th>\n    <td>BNP276</td>\n  </tr>\n<tr>\n    <th>Nº SERIE:</th>\n    <td>JTMR43FV1KD004392</td>\n  </tr>\n<tr>\n    <th>Nº VIN:</th>\n    <td>JTMR43FV1KD004392</td>\n  </tr>\n<tr>\n    <th>Nº MOTOR:</th>\n    <td>M20AV038255</td>\n  </tr>\n<tr>\n    <th>COLOR:</th>\n    <td>PLATA METALICO</td>\n  </tr>\n<tr>\n    <th>MARCA:</th>\n    <td>TOYOTA</td>\n  </tr>\n<tr>\n    <th>MODELO:</th>\n    <td>RAV4</td>\n  </tr>\n<tr>\n    <th>PLACA VIGENTE:</th>\n    <td>BNP276</td>\n  </tr>\n<tr>\n    <th>PLACA ANTERIOR:</th>\n    <td>NINGUNA</td>\n  </tr>\n<tr>\n    <th>ESTADO:</th>\n    <td>EN CIRCULACION</td>\n  </tr>\n<tr>\n    <th>ANOTACIONES:</th>\n    <td>NINGUNA</td>\n  </tr>\n<tr>\n    <th>SEDE:</th>\n    <td>LIMA</td>\n  </tr>\n<tr>\n    <th>AÑO DE MODELO:</th>\n    <td>2019</td>\n  </tr>\n</table>\n\n## PROPIETARIO(S):\n\nZÚÑIGA PUMA, VIDAL WALTER\n\n"""

# Crear instancia del scraper
scraper = ConsultaVehicularScraper()

# Probar extracción de datos
print("=" * 60)
print("TEST: Extracción de datos del vehículo")
print("=" * 60)

vehicle_data = scraper.extract_vehicle_data_from_markdown(markdown_text)

print("\n📊 Resultado:")
print("-" * 60)
import json
print(json.dumps(vehicle_data, indent=2, ensure_ascii=False))
print("-" * 60)

print(f"\n✅ Total de campos extraídos: {len(vehicle_data)}")

# Probar envío a API
print("\n" + "=" * 60)
print("TEST: Envío de datos a la API")
print("=" * 60)

if vehicle_data:
    success = scraper.send_vehicle_data_to_api(vehicle_data)
    if success:
        print("\n✅ Datos enviados exitosamente a la API")
    else:
        print("\n❌ Error al enviar datos a la API")
else:
    print("\n⚠️ No hay datos para enviar a la API")
