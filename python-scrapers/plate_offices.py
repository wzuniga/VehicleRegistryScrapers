"""
Diccionario de mapeo de primera letra de placa a oficina registral
Este mapeo se basa en la distribución de placas vehiculares en Perú
"""

PLATE_TO_OFFICE = {
    "A": "LIMA",
    "B": "LIMA",
    "C": "LIMA",
    "D": "LIMA",
    "E": "LIMA", # No definido
    "F": "LIMA",
    # "G": "LIMA", # No definido
    # "H": "Ancash",
    "I": "AYACUCHO",
    # "J": "LIMA",
    # "K": ["Lambayeque", "Cajamarca", "Amazonas"],
    # "L": "Loreto",
    # "M": ["Lambayeque", "Cajamarca", "Amazonas"],
    # "N": "LIMA",
    # "O": "LIMA",
    # "P": ["Tumbes", "Piura"],
    # "Q": "LIMA",
    # "R": "LIMA",
    # "S": "LIMA",
    "T": "TRUJILLO",
    # "U": "Ucayali",
    "V": "AREQUIPA",
    # "W": "AREQUIPA",
    "X": "CUSCO",
    # "Y": "TRUJILLO",
    "Z": "TACNA"
}


def get_office_by_plate(plate_number):
    """
    Obtiene la oficina registral basándose en la primera letra de la placa
    
    Args:
        plate_number (str): Número de placa vehicular
        
    Returns:
        str: Nombre de la oficina registral o False si no se encuentra
    """
    if not plate_number:
        return False
    
    first_letter = plate_number[0].upper()
    return PLATE_TO_OFFICE.get(first_letter, False)  # Retorna False si no existe

def list_all_mappings():
    """
    Retorna todos los mapeos disponibles
    
    Returns:
        dict: Diccionario completo de mapeos
    """
    return PLATE_TO_OFFICE.copy()
