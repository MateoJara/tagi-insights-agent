"""Phrase bank and composer for the synthetic free-text comments.

Every comment is built from one or two topic fragments plus an optional opener
and closer, so the generator knows which topics each comment is about. That
answer key is what the comment analysis gets checked against.
"""

# topic id -> (aspect, kind, fragments). Fragments start lowercase, no final period.
TOPICS = {
    "food_taste": ("food", "praise", [
        "la comida estuvo deliciosa",
        "todo muy rico",
        "el sabor de la comida es excelente",
        "muy rico el plato del día",
        "la sazón es como de casa",
        "el ajiaco estaba buenísimo",
        "la carne llegó en su punto",
        "se nota que cocinan con ingredientes frescos",
    ]),
    "food_portions": ("food", "praise", [
        "las porciones son generosas",
        "sirven bastante",
        "uno queda lleno con el almuerzo",
        "los platos vienen bien servidos",
    ]),
    "service_friendly": ("service", "praise", [
        "el mesero fue muy amable",
        "nos atendieron con muy buena actitud",
        "la atención fue excelente",
        "muy atentos todos",
        "el personal es muy querido",
        "la niña que nos atendió fue un amor",
    ]),
    "service_fast": ("service", "praise", [
        "nos atendieron rápido",
        "el pedido llegó rapidísimo",
        "no tuvimos que esperar nada",
        "sirven muy rápido para lo lleno que estaba",
    ]),
    "ambience_cozy": ("ambience", "praise", [
        "el lugar es acogedor",
        "buen ambiente para conversar",
        "la música está a un volumen agradable",
        "el sitio es limpio y bonito",
        "me gustó mucho la decoración",
        "es un lugar tranquilo para almorzar",
    ]),
    "value_price": ("value", "praise", [
        "buen precio para lo que sirven",
        "muy buena relación calidad-precio",
        "económico y llenador",
        "los precios son justos",
        "se come bien sin gastar mucho",
    ]),
    # Planted small detail: cheap for the owner, noticed by diners.
    "detail_cookie": (None, "praise", [
        "la galleta de cortesía con el café es un detallazo",
        "me encantó que el café venga con galletica",
        "el detalle de la galleta con el tinto me pareció muy lindo",
        "la galletica que dan con el café hace la diferencia",
        "qué buen detalle la galleta que traen con el tinto",
        "hasta galleta de cortesía dan con el café",
    ]),
    "service_wait": ("service", "complaint", [
        "esperamos más de media hora por el pedido",
        "la comida se demoró muchísimo",
        "estuvimos 40 minutos esperando el almuerzo",
        "se demoran demasiado en atender",
        "tocó esperar mucho para que nos tomaran el pedido",
        "la espera fue eterna",
        "el pedido tardó casi una hora",
        "pasaron 20 minutos antes de que alguien se acercara a la mesa",
    ]),
    "service_attitude": ("service", "complaint", [
        "el mesero fue cortante",
        "mala actitud del personal",
        "parecía que les molestaba atender",
        "nos atendieron de mala gana",
        "nadie saluda ni da las gracias",
    ]),
    "service_order_error": ("service", "complaint", [
        "se equivocaron con el pedido",
        "me trajeron otro plato",
        "olvidaron una de las bebidas",
        "la cuenta venía con cosas que no pedimos",
    ]),
    "food_cold": ("food", "complaint", [
        "el plato llegó frío",
        "la sopa estaba tibia",
        "la comida llegó fría a la mesa",
    ]),
    "food_bland": ("food", "complaint", [
        "a la comida le faltaba sabor",
        "el arroz estaba simple",
        "la carne estaba dura",
    ]),
    "food_portion_small": ("food", "complaint", [
        "la porción fue más pequeña que otras veces",
        "cada vez sirven menos",
    ]),
    "ambience_noise": ("ambience", "complaint", [
        "la música estaba demasiado alta",
        "había mucho ruido y no se podía hablar",
    ]),
    "ambience_space": ("ambience", "complaint", [
        "las mesas están muy juntas",
        "hacía mucho calor adentro",
        "el baño no estaba limpio",
    ]),
    "value_expensive": ("value", "complaint", [
        "subieron los precios y la porción es la misma",
        "me pareció caro para lo que sirven",
        "ya no es tan económico como antes",
    ]),
    "generic_praise": (None, "praise", [
        "excelente", "todo bien", "muy bueno", "rico", "10/10", "recomendado", "me gustó",
    ]),
    "generic_complaint": (None, "complaint", [
        "pésimo", "muy mal", "no vuelvo", "decepcionante", "regular",
    ]),
    "suggestion": (None, "suggestion", [
        "deberían tener más opciones vegetarianas",
        "sería bueno poder pagar con transferencia",
        "ojalá abrieran los domingos",
        "podrían poner más mesas afuera",
        "sería útil tener el menú en un código QR",
        "que haya más personal a la hora del almuerzo",
        "podrían ofrecer domicilios",
        "estaría bien tener jugos sin azúcar",
        "deberían recibir reservas",
        "sería bueno un menú infantil",
    ]),
}

OPENERS = {
    "praise": ["", "", "", "la verdad ", "como siempre, ", "primera vez que vengo y ", "vengo seguido y "],
    "complaint": ["", "", "", "la verdad ", "esta vez ", "lástima, ", "antes era mejor, ahora "],
    "suggestion": ["", "", "como sugerencia, ", "una idea: "],
}
CLOSERS = {
    "praise": ["", "", "", ". Volveré", ". Recomendado", ", gracias", "!!"],
    "complaint": ["", "", "", ". Ojalá mejoren", ". No creo que vuelva", ". Una lástima"],
    "suggestion": ["", "", ". Gracias"],
}
JOINERS = [" y ", ", además ", ". También "]

# Service complaints shift towards waiting times once service declines.
SERVICE_COMPLAINT_WEIGHTS = {
    False: {"service_wait": 0.30, "service_attitude": 0.30, "service_order_error": 0.40},
    True: {"service_wait": 0.65, "service_attitude": 0.25, "service_order_error": 0.10},
}
COOKIE_RATE = 0.15
GENERIC_RATE = 0.12
SECOND_TOPIC_RATE = 0.20
ACCENTS = str.maketrans("áéíóúÁÉÍÓÚ", "aeiouAEIOU")


def topics_for(aspect, kind):
    return [topic for topic, (topic_aspect, topic_kind, _) in TOPICS.items()
            if topic_aspect == aspect and topic_kind == kind]


def pick_praise_topics(aspect, rng):
    """One praise topic for the aspect, sometimes with the cookie or a second aspect."""
    if rng.random() < GENERIC_RATE:
        return ["generic_praise"]
    topics = [str(rng.choice(topics_for(aspect, "praise")))]
    roll = rng.random()
    if roll < COOKIE_RATE / 2:
        return ["detail_cookie"]
    if roll < COOKIE_RATE:
        return [*topics, "detail_cookie"]
    if roll < COOKIE_RATE + SECOND_TOPIC_RATE:
        other = str(rng.choice([a for a in ("food", "service", "ambience", "value") if a != aspect]))
        topics.append(str(rng.choice(topics_for(other, "praise"))))
    return topics


def pick_complaint_topics(aspect, in_decline, rng, allow_generic=True):
    if allow_generic and rng.random() < GENERIC_RATE:
        return ["generic_complaint"]
    if aspect == "service":
        weights = SERVICE_COMPLAINT_WEIGHTS[bool(in_decline)]
        return [str(rng.choice(list(weights), p=list(weights.values())))]
    return [str(rng.choice(topics_for(aspect, "complaint")))]


def _typo(text, rng):
    """Missing accents and swapped letters, as in text typed on a phone."""
    roll = rng.random()
    if roll < 0.12:
        return text.translate(ACCENTS)
    if roll < 0.17 and len(text) > 8:
        position = int(rng.integers(2, len(text) - 3))
        if text[position].isalpha() and text[position + 1].isalpha():
            return text[:position] + text[position + 1] + text[position] + text[position + 2:]
    return text


def _messy(text, rng):
    """Occasionally distort casing and spacing, as free-text answers do."""
    roll = rng.random()
    if roll < 0.05:
        return text.upper()
    if roll < 0.12:
        return text.lower()
    if roll < 0.17:
        return f"  {text} "
    if roll < 0.20:
        return text.replace(" ", "  ", 1)
    return text


def compose(topics, rng, joiner=None):
    """Build one comment from its topics. The first topic sets opener and closer."""
    fragments = [str(rng.choice(TOPICS[topic][2])) for topic in topics]
    kind = TOPICS[topics[0]][1]
    body = fragments[0]
    for fragment in fragments[1:]:
        body += (joiner or str(rng.choice(JOINERS))) + fragment
    if topics[0].startswith("generic"):
        text = body
    else:
        text = f"{rng.choice(OPENERS[kind])}{body}{rng.choice(CLOSERS[kind])}"
    text = ". ".join(part[0].upper() + part[1:] for part in text.split(". "))
    return _messy(_typo(text, rng), rng)
