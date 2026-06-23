"""
Casi speciali: note e avvertenze per frontalieri, residenti settimanali, home office elevato.
Non cambia i calcoli numerici — aggiunge solo warnings alla risposta.
"""
from __future__ import annotations
from ..schemas.request import DeductionRequest, ResidencyType


def collect_warnings(req: DeductionRequest) -> list[str]:
    warnings: list[str] = []

    if req.residency_type == ResidencyType.FRONTALIERE:
        warnings.append(
            "FRONTALIERE: Le regole fiscali per i frontalieri italiani sono cambiate con il nuovo "
            "accordo CH-IT firmato il 23.12.2020 (in vigore dal 17.07.2023, RS 0.642.045.43). "
            "Verificare con il superiore quale normativa si applica al caso specifico. Il calcolo "
            "mostrato è basato sulle regole standard LT/LIFD e potrebbe non essere corretto per "
            "questo contribuente."
        )

    if req.residency_type == ResidencyType.WEEKLY_RESIDENT:
        warnings.append(
            "RESIDENTE SETTIMANALE: I costi di alloggio infrasettimanale possono essere "
            "deducibili oltre alle spese di trasporto. Verificare Art. 25 cpv. 1 lett. c LT "
            "e la prassi cantonale TI per i residenti settimanali."
        )

    ws = req.work_schedule
    if ws.days_per_week > 0:
        home_office_pct = ws.home_office_days_per_week / ws.days_per_week * 100
        if home_office_pct >= 50:
            warnings.append(
                f"HOME OFFICE ELEVATO: Il contribuente lavora da casa il {home_office_pct:.0f}% "
                "del tempo. Le spese di trasporto sono calcolate solo sui giorni di presenza "
                "effettiva in ufficio. Verificare che la percentuale sia corretta."
            )

    if req.transport_mode.value == "private_car":
        warnings.append(
            "AUTO PRIVATA: La deduzione per veicolo privato è ammessa solo se nessun mezzo "
            "pubblico adeguato è disponibile (principio di necessità, Art. 25 LT). "
            "Assicurarsi di documentare l'indisponibilità dei mezzi pubblici."
        )

    if req.override_distance_km is not None:
        warnings.append(
            f"DISTANZA MANUALE: La distanza di {req.override_distance_km:.1f}km è stata fornita "
            "manualmente e non calcolata via geocoding. Verificare che corrisponda alla distanza "
            "effettiva casa-lavoro."
        )

    return warnings
