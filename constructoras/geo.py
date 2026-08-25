# -*- coding: utf-8 -*-
"""Deteccion de relevancia geografica: provincias de Huelva y Sevilla."""
import re
import unicodedata

MUNICIPIOS_HUELVA = [
    "Alajar", "Aljaraque", "El Almendro", "Almonaster la Real", "Almonte", "Alosno",
    "Arroyomolinos de Leon", "Ayamonte", "Beas", "Berrocal", "Bollullos Par del Condado",
    "Bonares", "Cabezas Rubias", "Cala", "Calanas", "El Campillo", "Campofrio",
    "Canaveral de Leon", "Cartaya", "Castano del Robledo", "El Cerro de Andevalo",
    "Chucena", "Corteconcepcion", "Cortegana", "Cortelazor", "Cumbres de Enmedio",
    "Cumbres de San Bartolome", "Cumbres Mayores", "Encinasola", "Escacena del Campo",
    "Fuenteheridos", "Galaroza", "Gibraleon", "La Granada de Rio-Tinto", "El Granado",
    "Higuera de la Sierra", "Hinojales", "Hinojos", "Huelva", "Isla Cristina", "Jabugo",
    "Lepe", "Linares de la Sierra", "Lucena del Puerto", "Manzanilla", "Los Marines",
    "Minas de Riotinto", "Moguer", "La Nava", "Nerva", "Niebla", "La Palma del Condado",
    "Palos de la Frontera", "Paterna del Campo", "Paymogo", "Puebla de Guzman",
    "Puerto Moral", "Punta Umbria", "Rociana del Condado", "Rosal de la Frontera",
    "San Bartolome de la Torre", "San Juan del Puerto", "San Silvestre de Guzman",
    "Sanlucar de Guadiana", "Santa Ana la Real", "Santa Barbara de Casa",
    "Santa Olalla del Cala", "Trigueros", "Valdelarco", "Valverde del Camino",
    "Villablanca", "Villalba del Alcor", "Villanueva de las Cruces",
    "Villanueva de los Castillejos", "Villarrasa", "Zalamea la Real", "Zufre",
]

# Nucleos y urbanizaciones de Huelva que aparecen en los anuncios sin el municipio
ZONAS_HUELVA = [
    "Nuevo Portil", "El Portil", "El Rompido", "Islantilla", "La Antilla",
    "Matalascanas", "Mazagon", "Costa Esuri", "Punta del Moral", "Corrales",
    "Bellavista", "Ensanche Sur", "Molino de la Vega", "Marismas del Odiel",
    "Isla Chica", "La Orden", "Fuentepina", "Nuevo Colombino", "Costa de Huelva",
    "Costa Occidental", "Sierra de Aracena", "Condado de Huelva", "Cinta",
]

MUNICIPIOS_SEVILLA = [
    "Aguadulce", "Alanis", "Albaida del Aljarafe", "Alcala de Guadaira",
    "Alcala del Rio", "Alcolea del Rio", "La Algaba", "Algamitas",
    "Almaden de la Plata", "Almensilla", "Arahal", "Aznalcazar", "Aznalcollar",
    "Badolatosa", "Benacazon", "Bollullos de la Mitacion", "Bormujos", "Brenes",
    "Burguillos", "Las Cabezas de San Juan", "Camas", "La Campana", "Cantillana",
    "Canada Rosal", "Carmona", "Carrion de los Cespedes", "Casariche",
    "Castilblanco de los Arroyos", "Castilleja de Guzman", "Castilleja de la Cuesta",
    "Castilleja del Campo", "El Castillo de las Guardas", "Cazalla de la Sierra",
    "Constantina", "Coria del Rio", "Coripe", "El Coronil", "Los Corrales",
    "El Cuervo de Sevilla", "Dos Hermanas", "Ecija", "Espartinas", "Estepa",
    "Fuentes de Andalucia", "El Garrobo", "Gelves", "Gerena", "Gilena", "Gines",
    "Guadalcanal", "Guillena", "Herrera", "Huevar del Aljarafe", "Isla Mayor",
    "Isla Redonda-La Acenuela", "Lantejuela", "Lebrija", "Lora de Estepa",
    "Lora del Rio", "La Luisiana", "El Madrono", "Mairena del Alcor",
    "Mairena del Aljarafe", "Marchena", "Marinaleda", "Martin de la Jara",
    "Los Molares", "Montellano", "Moron de la Frontera", "Las Navas de la Concepcion",
    "Olivares", "Osuna", "Los Palacios y Villafranca", "El Palmar de Troya",
    "Palomares del Rio", "Paradas", "Pedrera", "El Pedroso", "Penaflor", "Pilas",
    "Pruna", "La Puebla de Cazalla", "La Puebla de los Infantes", "La Puebla del Rio",
    "El Real de la Jara", "La Rinconada", "La Roda de Andalucia", "El Ronquillo",
    "El Rubio", "Salteras", "San Juan de Aznalfarache", "San Nicolas del Puerto",
    "Sanlucar la Mayor", "Santiponce", "El Saucejo", "Sevilla", "Tocina", "Tomares",
    "Umbrete", "Utrera", "Valencina de la Concepcion", "Villamanrique de la Condesa",
    "Villanueva del Ariscal", "Villanueva del Rio y Minas", "Villanueva de San Juan",
    "Villaverde del Rio", "El Viso del Alcor",
]

ZONAS_SEVILLA = [
    "Entrenucleos", "Montequinto", "Nervion", "Triana", "Los Remedios",
    "Sevilla Este", "Palmas Altas", "Hacienda Rosario", "Aljarafe", "Condequinto",
    "Bami", "Bellavista", "Pino Montano", "Santa Justa", "Cartuja", "San Bernardo",
    "Torreblanca", "Alcosa", "Heliopolis", "Puerto Triana", "Vega de Triana",
    "Valdezorras", "Su Eminencia", "Higueron", "Quintillo", "Arco Norte",
]

# Terminos que por si solos ya indican provincia
TERMINOS_PROVINCIA = {
    "Huelva": ["huelva", "provincia de huelva", "onubense", "costa de la luz"],
    "Sevilla": ["sevilla", "provincia de sevilla", "sevillano", "hispalense"],
}

# Municipios ambiguos que existen en varias provincias o coinciden con
# palabras comunes: exigen que aparezca ademas el nombre de la provincia.
AMBIGUOS = {
    "cala", "herrera", "beas", "olivares", "gines", "camas", "estepa",
    "carmona", "utrera", "corrales", "bellavista", "cinta", "la nava",
    "los corrales", "santa olalla del cala", "el granado", "el campillo",
}


def normalizar(texto: str) -> str:
    """Minusculas, sin tildes, sin puntuacion, espacios colapsados."""
    if not texto:
        return ""
    t = unicodedata.normalize("NFKD", texto)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.lower()
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _construir_indice():
    idx = []
    for prov, nombres in (
        ("Huelva", MUNICIPIOS_HUELVA + ZONAS_HUELVA),
        ("Sevilla", MUNICIPIOS_SEVILLA + ZONAS_SEVILLA),
    ):
        for n in nombres:
            clave = normalizar(n)
            if len(clave) < 4:
                continue
            idx.append((prov, n, clave, clave in AMBIGUOS))
    # los mas largos primero para que "san juan del puerto" gane a "huelva"
    idx.sort(key=lambda x: -len(x[2]))
    return idx


INDICE = _construir_indice()


def _cuenta(norm: str, clave: str) -> int:
    return norm.count(f" {clave} ")


def analizar(texto: str, umbral_relativo: float = 0.34):
    """Devuelve (provincias:set, lugares:list) detectados en el texto.

    No basta con que un nombre aparezca: se puntua cada provincia por cuantas
    veces se la nombra. Asi una ficha de Merida que menciona Sevilla una vez
    en la direccion de la empresa no acaba clasificada como sevillana.
    """
    norm = " " + normalizar(texto) + " "
    puntos = {"Huelva": 0, "Sevilla": 0}
    citadas = set()
    lugares_por_prov = {"Huelva": [], "Sevilla": []}

    for prov, terms in TERMINOS_PROVINCIA.items():
        for t in terms:
            n = _cuenta(norm, normalizar(t))
            if n:
                citadas.add(prov)
                puntos[prov] += 2 * n      # nombrar la provincia pesa el doble

    for prov, nombre, clave, ambiguo in INDICE:
        n = _cuenta(norm, clave)
        if not n:
            continue
        if ambiguo and prov not in citadas:
            continue          # demasiado generico sin la provincia como respaldo
        puntos[prov] += n
        if nombre not in lugares_por_prov[prov]:
            lugares_por_prov[prov].append(nombre)

    maximo = max(puntos.values())
    if maximo == 0:
        return set(), []

    # Nos quedamos con la provincia dominante y, si la otra tambien tiene peso
    # real (promociones en ambas), con las dos.
    provincias = {p for p, v in puntos.items() if v >= max(1, maximo * umbral_relativo)}
    lugares = []
    for p in sorted(provincias, key=lambda x: -puntos[x]):
        lugares.extend(lugares_por_prov[p])
    return provincias, lugares


def es_relevante(texto: str) -> bool:
    provincias, _ = analizar(texto)
    return bool(provincias)
