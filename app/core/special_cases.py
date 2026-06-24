"""
Casi speciali: note e avvertenze per frontalieri, residenti settimanali, home office elevato.
Non cambia i calcoli numerici — aggiunge solo warnings alla risposta.
"""
from __future__ import annotations
from ..schemas.request import DeductionRequest, MealSituation, ResidencyType


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
        if req.annual_accommodation_cost_chf is not None:
            warnings.append(
                f"RESIDENTE SETTIMANALE: Alloggio infrasettimanale CHF {req.annual_accommodation_cost_chf:.2f} "
                "incluso come costo effettivo (costo 1 camera — Art. 25 cpv. 1 lett. c LT)."
            )
        else:
            warnings.append(
                "RESIDENTE SETTIMANALE: Indicare il costo annuo di alloggio infrasettimanale "
                "(campo 'annual_accommodation_cost_chf') per includerlo nella deduzione. "
                "Deducibile il costo effettivo di una camera (Art. 25 cpv. 1 lett. c LT)."
            )

    if req.meal_situation == MealSituation.SHIFT_WORK:
        warnings.append(
            "LAVORI A TURNI: Deduzione pasti calcolata a CHF 15.00/giorno, max CHF 3'200/anno. "
            "Se il datore di lavoro dispone di mensa o versa un contributo, applicare invece "
            "la tariffa ridotta CHF 7.50/giorno (situazione 'with_cafeteria', max CHF 1'600/anno)."
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

    if req.employer_pays_transport and req.company_car_monthly_chf is None:
        warnings.append(
            "CAMPO D: Il datore di lavoro mette a disposizione il trasporto gratuitamente. "
            "Nessuna deduzione ammessa (campo D Lohnausweis)."
        )

    if (
        req.company_car_monthly_chf is not None
        and req.transport_mode.value == "private_car"
    ):
        warnings.append(
            "AUTO AZIENDALE (cifra 13.2.2): Applicato calcolo forfettario Art. 5a RS 642.118.1. "
            "Verificare che l'importo mensile corrisponda esattamente alla cifra 13.2.2 del Lohnausweis."
        )

    if (
        req.company_car_monthly_chf is not None
        and req.transport_mode.value != "private_car"
    ):
        warnings.append(
            "company_car_monthly_chf fornito ma transport_mode non è private_car — il campo sarà ignorato"
        )

    if req.override_distance_km is not None:
        warnings.append(
            f"DISTANZA MANUALE: La distanza di {req.override_distance_km:.1f}km è stata fornita "
            "manualmente e non calcolata via geocoding. Verificare che corrisponda alla distanza "
            "effettiva casa-lavoro."
        )

    return warnings
