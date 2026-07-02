// DdC Trasferta — frontend entry point

(function () {
  'use strict';

  // ── Global state ──────────────────────────────────────────────────────────
  let leafletMap = null;
  let osrmPolyline = null;
  let spouseMarkers = [];
  let lastResponse = null;
  let assessmentActive = false;
  // Valori accertati: { tableId: { idx: value } }
  let assessedState = {};
  let assessmentDirty = false;

  const form = document.getElementById('deduction-form');
  const transportSelect = document.getElementById('transport_mode');
  const distanceOverrideGroup = document.getElementById('distance-override-group');
  const mixedFields = document.getElementById('mixed-fields');
  const formError = document.getElementById('form-error');
  const btnReset = document.getElementById('btn-reset');
  const resultsDiv = document.getElementById('results');

  const includeMealsChk = document.getElementById('include_meals');
  const mealSituationGroup = document.getElementById('meal-situation-group');

  const includeOtherExpensesChk = document.getElementById('include_other_expenses');
  const otherExpensesDetails = document.getElementById('other-expenses-details');

  const includeSecondaryChk = document.getElementById('include_secondary_activity');
  const secondaryDetails = document.getElementById('secondary-activity-details');

  const accommodationCard = document.getElementById('accommodation-card');

  const companyCarGroup = document.getElementById('company-car-group');
  const ptCostSection = document.getElementById('pt-cost-section');
  const arcobalenovFields = document.getElementById('arcobaleno-fields');
  const manualPtFields = document.getElementById('manual-pt-fields');
  const sbbLinkFields = document.getElementById('sbb-link-fields');

  const ARCOBALENO_2CL = { 1: 485, 2: 732, 3: 1074, 4: 1387, 5: 1691, 6: 1986, 7: 2157, 8: 2252 };
  const ARCOBALENO_1CL = { 1: 827, 2: 1245, 3: 1834, 4: 2366, 5: 2879, 6: 3382, 7: 3667, 8: 3829 };

  function fillNpa(cityValue, npaFieldId, countryFieldId) {
    if (!cityValue || !npaFieldId) return;
    var country = document.getElementById(countryFieldId).value || 'CH';
    fetch('/v1/locations/npa?city=' + encodeURIComponent(cityValue) + '&country=' + encodeURIComponent(country))
      .then(function (r) { return r.json(); })
      .then(function (data) { if (data && data.npa) { document.getElementById(npaFieldId).value = data.npa; } })
      .catch(function () {});
  }

  function makeTomSelectConfig(npaFieldId, countryFieldId) {
    return {
      valueField: 'name',
      labelField: 'name',
      searchField: 'name',
      create: true,
      maxItems: 1,
      placeholder: 'Cerca città…',
      render: {
        option: function (item, escape) {
          var npaStr = item.npa ? ' <span style="color:#888;font-size:0.85em">(' + escape(item.npa) + ')</span>' : '';
          return '<div>' + escape(item.name) + npaStr + '</div>';
        },
      },
      load: function (query, callback) {
        if (query.length < 2) { callback([]); return; }
        fetch('/v1/locations/search?q=' + encodeURIComponent(query) + '&limit=10')
          .then(function (r) { return r.json(); })
          .then(callback)
          .catch(function () { callback([]); });
      },
      onItemAdd: function (value) {
        var option = this.options[value];
        if (option && option.npa) {
          document.getElementById(npaFieldId).value = option.npa;
          document.getElementById(countryFieldId).value = 'CH';
        } else {
          fillNpa(value, npaFieldId, countryFieldId);
        }
      },
      onChange: function (value) {
        if (!value) return;
        var option = this.options[value];
        if (option && option.npa) {
          document.getElementById(npaFieldId).value = option.npa;
          document.getElementById(countryFieldId).value = 'CH';
        } else if (value) {
          fillNpa(value, npaFieldId, countryFieldId);
        }
      },
    };
  }

  const tomSelectHome = new TomSelect('#home_city', makeTomSelectConfig('home_npa', 'home_country'));
  const tomSelectWork = new TomSelect('#work_city', makeTomSelectConfig('work_npa', 'work_country'));

  function updateArcobalenoCostPreview() {
    const zones = parseInt(document.getElementById('arcobaleno_zones').value, 10);
    const cls = document.getElementById('arcobaleno_class').value;
    const table = cls === '1' ? ARCOBALENO_1CL : ARCOBALENO_2CL;
    const cost = table[zones] || table[8];
    const preview = document.getElementById('arcobaleno-cost-preview');
    if (preview) {
      preview.textContent = 'Costo annuo stimato: CHF ' + cost.toLocaleString('de-CH', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }
  }

  function updatePtCostVisibility() {
    const ptRadio = document.querySelector('input[name=pt_cost_type]:checked');
    const val = ptRadio ? ptRadio.value : 'arcobaleno';
    arcobalenovFields.classList.toggle('hidden', val !== 'arcobaleno');
    manualPtFields.classList.toggle('hidden', val !== 'manuale');
    sbbLinkFields.classList.toggle('hidden', val !== 'sbb-link');
  }

  function updateTransportVisibility() {
    const mode = transportSelect.value;
    const needsDistance = mode === 'private_car' || mode === 'motorcycle';
    const isMixed = mode === 'mixed';
    const isPublicTransport = mode === 'public_transport';
    const isPrivateCar = mode === 'private_car';

    distanceOverrideGroup.classList.toggle('hidden', !needsDistance);
    mixedFields.classList.toggle('hidden', !isMixed);
    companyCarGroup.classList.toggle('hidden', !isPrivateCar);
    ptCostSection.classList.toggle('hidden', !isPublicTransport);

    const carMixed = document.getElementById('car_distance_km_mixed');
    const ptMixed = document.getElementById('public_transport_cost_mixed_chf');
    carMixed.required = false;
    ptMixed.required = false;
  }

  function updateMealVisibility() {
    mealSituationGroup.classList.toggle('hidden', !includeMealsChk.checked);
  }

  function updateOtherExpensesVisibility() {
    otherExpensesDetails.classList.toggle('hidden', !includeOtherExpensesChk.checked);
  }

  function updateSecondaryVisibility() {
    secondaryDetails.classList.toggle('hidden', !includeSecondaryChk.checked);
  }

  function updateOtherExpensesMethod() {
    const radio = document.querySelector('input[name=other_expenses_method]:checked');
    const isEffettive = radio && radio.value === 'effettive';
    document.getElementById('actual-other-expenses-group').classList.toggle('hidden', !isEffettive);
  }

  function updateSecondaryMethod() {
    const radio = document.querySelector('input[name=secondary_method]:checked');
    const isEffettive = radio && radio.value === 'effettive';
    document.getElementById('actual-secondary-group').classList.toggle('hidden', !isEffettive);
  }

  function updateAccommodationVisibility() {
    const residency = document.getElementById('residency_type').value;
    accommodationCard.classList.toggle('hidden', residency !== 'weekly_resident');
  }

  transportSelect.addEventListener('change', updateTransportVisibility);
  includeMealsChk.addEventListener('change', updateMealVisibility);
  includeOtherExpensesChk.addEventListener('change', updateOtherExpensesVisibility);
  includeSecondaryChk.addEventListener('change', updateSecondaryVisibility);
  document.getElementById('residency_type').addEventListener('change', updateAccommodationVisibility);
  document.querySelectorAll('input[name=other_expenses_method]').forEach(function (r) {
    r.addEventListener('change', updateOtherExpensesMethod);
  });
  document.querySelectorAll('input[name=secondary_method]').forEach(function (r) {
    r.addEventListener('change', updateSecondaryMethod);
  });

  document.querySelectorAll('input[name=pt_cost_type]').forEach(function (radio) {
    radio.addEventListener('change', updatePtCostVisibility);
  });

  document.getElementById('arcobaleno_zones').addEventListener('change', updateArcobalenoCostPreview);
  document.getElementById('arcobaleno_class').addEventListener('change', updateArcobalenoCostPreview);

  updateTransportVisibility();
  updateMealVisibility();
  updateOtherExpensesVisibility();
  updateSecondaryVisibility();
  updateOtherExpensesMethod();
  updateSecondaryMethod();
  updateAccommodationVisibility();
  updatePtCostVisibility();
  updateArcobalenoCostPreview();

  // Tooltip: close on Escape
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      document.querySelectorAll('.tooltip-anchor').forEach(function (el) { el.blur(); });
    }
  });

  // ── Spouse form ───────────────────────────────────────────────────────────

  var includeSpouseChk = document.getElementById('include_spouse');
  var spouseFields = document.getElementById('spouse-fields');
  var spSameHomeChk = document.getElementById('sp_same_home');
  var spHomeFields = document.getElementById('sp-home-fields');
  var spTransportSel = document.getElementById('sp_transport_mode');
  var spPtSection = document.getElementById('sp-pt-section');
  var spArcobalenovFields = document.getElementById('sp-arcobaleno-fields');
  var spManualPtFields = document.getElementById('sp-manual-pt-fields');
  var spMealGroup = document.getElementById('sp-meal-group');
  var spIncludeMealsChk = document.getElementById('sp_include_meals');

  function updateSpousePtVisibility() {
    var ptRadio = document.querySelector('input[name=sp_pt_cost_type]:checked');
    var val = ptRadio ? ptRadio.value : 'arcobaleno';
    spArcobalenovFields.classList.toggle('hidden', val !== 'arcobaleno');
    spManualPtFields.classList.toggle('hidden', val !== 'manuale');
  }

  function updateSpouseTransportVisibility() {
    var mode = spTransportSel ? spTransportSel.value : '';
    var isTP = mode === 'public_transport';
    spPtSection.classList.toggle('hidden', !isTP);
    updateSpousePtVisibility();
  }

  if (includeSpouseChk) {
    includeSpouseChk.addEventListener('change', function () {
      spouseFields.classList.toggle('hidden', !includeSpouseChk.checked);
    });
  }
  if (spSameHomeChk) {
    spSameHomeChk.addEventListener('change', function () {
      spHomeFields.classList.toggle('hidden', spSameHomeChk.checked);
    });
  }
  if (spTransportSel) {
    spTransportSel.addEventListener('change', updateSpouseTransportVisibility);
  }
  document.querySelectorAll('input[name=sp_pt_cost_type]').forEach(function (r) {
    r.addEventListener('change', updateSpousePtVisibility);
  });
  if (spIncludeMealsChk) {
    spIncludeMealsChk.addEventListener('change', function () {
      spMealGroup.classList.toggle('hidden', !spIncludeMealsChk.checked);
    });
  }

  function showError(message) {
    formError.className = 'alert-error';
    formError.textContent = message;
    formError.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  function showWarning(message) {
    formError.className = 'alert-warning';
    formError.textContent = message;
    formError.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  function hideError() {
    formError.className = 'alert-error hidden';
    formError.textContent = '';
  }

  function getCapIfdWarning() {
    const mode = transportSelect.value;
    if (mode !== 'private_car') return null;
    const overrideKm = _numVal('override_distance_km');
    if (overrideKm === null) return null;
    const daysPerWeek = parseInt(document.getElementById('days_per_week').value, 10) || 5;
    const homeOfficeDays = parseInt(document.getElementById('home_office_days_per_week').value, 10) || 0;
    const effectiveDays = Math.round(((daysPerWeek - homeOfficeDays) / 5) * 220);
    const grossIfd = Math.round(overrideKm * 2 * 0.75 * effectiveDays);
    if (grossIfd > 3300) {
      return 'Attenzione: con ' + overrideKm + ' km la deduzione IFD auto privata ammonterebbe a CHF ' +
        grossIfd.toLocaleString('de-CH') + ', ma verrà limitata al tetto legale di CHF 3\'300 ' +
        '(Art. 26 LIFD). La deduzione cantonale TI non ha tetto massimo.';
    }
    return null;
  }

  function getFormPayload() {
    const mode = transportSelect.value;
    const fiscalYear = parseInt(document.getElementById('fiscal_year').value, 10);
    const residencyType = document.getElementById('residency_type').value;
    const daysPerWeek = parseInt(document.getElementById('days_per_week').value, 10);
    const homeOfficeDays = parseInt(document.getElementById('home_office_days_per_week').value, 10);

    const homeCity = (tomSelectHome.getValue() || document.getElementById('home_city').value).trim();
    const homeStreet = document.getElementById('home_street').value.trim();
    const homeNpa = document.getElementById('home_npa').value.trim();
    const homeCountry = document.getElementById('home_country').value || 'CH';
    const workCity = (tomSelectWork.getValue() || document.getElementById('work_city').value).trim();
    const workStreet = document.getElementById('work_street').value.trim();
    const workNpa = document.getElementById('work_npa').value.trim();
    const workCountry = document.getElementById('work_country').value || 'CH';

    const homeAddress = { street: homeStreet, city: homeCity, postal_code: homeNpa, country: homeCountry };
    const workAddress = { street: workStreet, city: workCity, postal_code: workNpa, country: workCountry };

    const payload = {
      fiscal_year: fiscalYear,
      residency_type: residencyType,
      transport_mode: mode,
      home_address: homeAddress,
      work_address: workAddress,
      work_schedule: { days_per_week: daysPerWeek, home_office_days_per_week: homeOfficeDays },
    };

    const overrideKm = document.getElementById('override_distance_km').value;
    if (overrideKm) {
      payload.override_distance_km = parseFloat(overrideKm);
    }

    if (mode === 'public_transport') {
      const ptRadio = document.querySelector('input[name=pt_cost_type]:checked');
      const ptVal = ptRadio ? ptRadio.value : 'arcobaleno';
      if (ptVal === 'arcobaleno') {
        payload.arcobaleno_zones = parseInt(document.getElementById('arcobaleno_zones').value, 10);
        payload.arcobaleno_class = document.getElementById('arcobaleno_class').value;
      } else if (ptVal === 'manuale') {
        const c = document.getElementById('annual_public_transport_cost_chf').value;
        if (c) payload.annual_public_transport_cost_chf = parseFloat(c);
      } else if (ptVal === 'sbb-link') {
        const c = document.getElementById('annual_public_transport_cost_chf_sbb').value;
        if (c) payload.annual_public_transport_cost_chf = parseFloat(c);
      }
    }

    if (mode === 'mixed') {
      const carKm = document.getElementById('car_distance_km_mixed').value;
      const ptCost = document.getElementById('public_transport_cost_mixed_chf').value;
      if (carKm) payload.car_distance_km_mixed = parseFloat(carKm);
      if (ptCost) payload.public_transport_cost_mixed_chf = parseFloat(ptCost);
    }

    // Pasti
    payload.include_meals = includeMealsChk.checked;
    if (includeMealsChk.checked) {
      payload.meal_situation = document.getElementById('meal_situation').value;
    }

    // Altre spese professionali
    payload.include_other_expenses = includeOtherExpensesChk.checked;
    if (includeOtherExpensesChk.checked) {
      const salary = document.getElementById('annual_net_salary_chf').value;
      if (salary) payload.annual_net_salary_chf = parseFloat(salary);
      const otherMethod = document.querySelector('input[name=other_expenses_method]:checked');
      if (otherMethod && otherMethod.value === 'effettive') {
        const actual = document.getElementById('actual_other_expenses_chf').value;
        if (actual) payload.actual_other_expenses_chf = parseFloat(actual);
      }
    }

    // Attività accessoria
    payload.include_secondary_activity = includeSecondaryChk.checked;
    if (includeSecondaryChk.checked) {
      const secMethod = document.querySelector('input[name=secondary_method]:checked');
      if (secMethod && secMethod.value === 'effettive') {
        const actual = document.getElementById('actual_secondary_activity_chf').value;
        if (actual) payload.actual_secondary_activity_chf = parseFloat(actual);
      }
    }

    // Alloggio residente settimanale
    if (document.getElementById('residency_type').value === 'weekly_resident') {
      const accType = document.querySelector('input[name=accommodation_type]:checked');
      if (accType) payload.accommodation_type = accType.value;
      const monthly = document.getElementById('accommodation_monthly_chf').value;
      if (monthly) payload.accommodation_monthly_chf = parseFloat(monthly);
    }

    // Campi Lohnausweis
    payload.employer_pays_transport = document.getElementById('employer_pays_transport').checked;
    payload.employer_has_cafeteria = document.getElementById('employer_has_cafeteria').checked;

    if (mode === 'private_car') {
      const carMonthly = document.getElementById('company_car_monthly_chf').value;
      if (carMonthly) payload.company_car_monthly_chf = parseFloat(carMonthly);
    }

    // Coniuge/partner
    if (includeSpouseChk && includeSpouseChk.checked) {
      var sp = getSpousePayload();
      if (sp) payload.spouse = sp;
    }

    return payload;
  }

  function getSpousePayload() {
    var spMode = document.getElementById('sp_transport_mode').value;
    var spWorkCity = document.getElementById('sp_work_city').value.trim();
    var spWorkStreet = document.getElementById('sp_work_street').value.trim();
    var spWorkNpa = document.getElementById('sp_work_npa').value.trim();
    var spWorkCountry = document.getElementById('sp_work_country').value || 'CH';
    var spDays = parseInt(document.getElementById('sp_days_per_week').value, 10);
    var spHoDays = parseInt(document.getElementById('sp_home_office_days').value, 10);

    var sp = {
      work_address: { street: spWorkStreet, city: spWorkCity, postal_code: spWorkNpa, country: spWorkCountry },
      transport_mode: spMode,
      work_schedule: { days_per_week: spDays, home_office_days_per_week: spHoDays },
    };

    // Domicilio coniuge (solo se diverso)
    if (spSameHomeChk && !spSameHomeChk.checked) {
      var spHomeCity = document.getElementById('sp_home_city').value.trim();
      var spHomeStreet = document.getElementById('sp_home_street').value.trim();
      var spHomeNpa = document.getElementById('sp_home_npa').value.trim();
      var spHomeCountry = document.getElementById('sp_home_country').value || 'CH';
      if (spHomeCity && spHomeStreet) {
        sp.home_address = { street: spHomeStreet, city: spHomeCity, postal_code: spHomeNpa, country: spHomeCountry };
      }
    }

    // Distanza manuale
    var spKm = document.getElementById('sp_override_distance_km').value;
    if (spKm) sp.override_distance_km = parseFloat(spKm);

    // Trasporto pubblico
    if (spMode === 'public_transport') {
      var spPtRadio = document.querySelector('input[name=sp_pt_cost_type]:checked');
      var spPtVal = spPtRadio ? spPtRadio.value : 'arcobaleno';
      if (spPtVal === 'arcobaleno') {
        sp.arcobaleno_zones = parseInt(document.getElementById('sp_arcobaleno_zones').value, 10);
        sp.arcobaleno_class = document.getElementById('sp_arcobaleno_class').value;
      } else if (spPtVal === 'manuale') {
        var spPtCost = document.getElementById('sp_annual_pt_cost').value;
        if (spPtCost) sp.annual_public_transport_cost_chf = parseFloat(spPtCost);
      }
    }

    // Pasti coniuge
    sp.include_meals = spIncludeMealsChk && spIncludeMealsChk.checked;
    if (sp.include_meals) {
      sp.meal_situation = document.getElementById('sp_meal_situation').value;
    }

    // Altre spese
    sp.include_other_expenses = document.getElementById('sp_include_other_expenses').checked;

    return sp;
  }

  function validateNpa(npa, country, label) {
    if (country === 'CH' && !/^[0-9]{4}$/.test(npa)) return 'Il NPA CH ' + label + ' deve essere di 4 cifre.';
    if (country === 'IT' && !/^[0-9]{5}$/.test(npa)) return 'Il CAP italiano ' + label + ' deve essere di 5 cifre.';
    if (country !== 'CH' && country !== 'IT' && !/^[0-9A-Z -]{3,10}$/.test(npa)) return 'NPA ' + label + ' non valido.';
    return null;
  }

  function _numVal(id) {
    var v = parseFloat(document.getElementById(id).value);
    return isNaN(v) ? null : v;
  }

  function validateForm() {
    const homeCity = (tomSelectHome.getValue() || document.getElementById('home_city').value).trim();
    const homeNpa = document.getElementById('home_npa').value.trim();
    const homeCountry = document.getElementById('home_country').value || 'CH';
    const workCity = (tomSelectWork.getValue() || document.getElementById('work_city').value).trim();
    const workNpa = document.getElementById('work_npa').value.trim();
    const workCountry = document.getElementById('work_country').value || 'CH';

    if (!homeCity) return 'Inserire la città del domicilio.';
    const homeStreet = document.getElementById('home_street').value.trim();
    if (!homeStreet) return 'Inserire la via e il numero civico del domicilio (obbligatorio per il calcolo della distanza).';
    const homeNpaErr = validateNpa(homeNpa, homeCountry, 'del domicilio');
    if (homeNpaErr) return homeNpaErr;
    if (!workCity) return 'Inserire la città del luogo di lavoro.';
    const workStreetVal = document.getElementById('work_street').value.trim();
    if (!workStreetVal) return 'Inserire la via e il numero civico del luogo di lavoro (obbligatorio per il calcolo della distanza).';
    const workNpaErr = validateNpa(workNpa, workCountry, 'del luogo di lavoro');
    if (workNpaErr) return workNpaErr;

    if (homeNpa && homeCountry === 'IT' && /^[0-9]{4}$/.test(homeNpa)) {
      return 'NPA domicilio a 4 cifre con paese "IT": il CAP italiano ha 5 cifre. ' +
             'Se il domicilio è in Svizzera, impostare il paese su CH.';
    }
    if (homeNpa && homeCountry === 'CH' && /^[0-9]{5}$/.test(homeNpa)) {
      return 'NPA domicilio a 5 cifre con paese "CH": il NPA svizzero ha 4 cifre. ' +
             'Se il domicilio è in Italia, impostare il paese su IT.';
    }
    if (workNpa && workCountry === 'IT' && /^[0-9]{4}$/.test(workNpa)) {
      return 'NPA luogo di lavoro a 4 cifre con paese "IT": il CAP italiano ha 5 cifre. ' +
             'Se il luogo di lavoro è in Svizzera, impostare il paese su CH.';
    }
    if (workNpa && workCountry === 'CH' && /^[0-9]{5}$/.test(workNpa)) {
      return 'NPA luogo di lavoro a 5 cifre con paese "CH": il NPA svizzero ha 4 cifre. ' +
             'Se il luogo di lavoro è in Italia, impostare il paese su IT.';
    }

    const overrideKm = _numVal('override_distance_km');
    if (overrideKm !== null) {
      if (overrideKm < 0.1) return 'La distanza deve essere almeno 0.1 km.';
      if (overrideKm > 500) return 'La distanza non può superare 500 km (valore inserito: ' + overrideKm + ' km).';
    }

    const mode = transportSelect.value;

    if (mode === 'public_transport') {
      const ptRadio = document.querySelector('input[name=pt_cost_type]:checked');
      const ptVal = ptRadio ? ptRadio.value : 'arcobaleno';
      if (ptVal === 'manuale') {
        const c = _numVal('annual_public_transport_cost_chf');
        if (c === null || c <= 0) return 'Inserire il costo abbonamento annuale in CHF.';
        if (c > 20000) return 'Il costo del trasporto pubblico non può superare CHF 20\'000 annui (inserito: CHF ' + c.toLocaleString('de-CH') + ').';
      } else if (ptVal === 'sbb-link') {
        const c = _numVal('annual_public_transport_cost_chf_sbb');
        if (c === null || c <= 0) return 'Inserire il costo abbonamento trovato su SBB.ch.';
        if (c > 20000) return 'Il costo del trasporto pubblico non può superare CHF 20\'000 annui (inserito: CHF ' + c.toLocaleString('de-CH') + ').';
      }
    }

    if (mode === 'mixed') {
      const carKm = _numVal('car_distance_km_mixed');
      const ptCost = _numVal('public_transport_cost_mixed_chf');
      if (carKm === null && ptCost === null) {
        return 'Per il trasporto misto fornire almeno la distanza in auto o il costo mezzi pubblici.';
      }
      if (carKm !== null && carKm > 500) return 'La distanza in auto non può superare 500 km (inseriti: ' + carKm + ' km).';
      if (ptCost !== null && ptCost > 20000) return 'Il costo del trasporto pubblico non può superare CHF 20\'000 annui.';
    }

    if (mode === 'private_car') {
      const companyCar = _numVal('company_car_monthly_chf');
      if (companyCar !== null && companyCar > 2000) {
        return 'Il forfait mensile auto aziendale (cifra 13.2.2) non può superare CHF 2\'000/mese (inserito: CHF ' + companyCar + ').';
      }
    }

    const accMonthly = _numVal('accommodation_monthly_chf');
    if (accMonthly !== null && accMonthly > 5000) {
      return 'Il costo mensile dell\'alloggio non può superare CHF 5\'000 (inserito: CHF ' + accMonthly.toLocaleString('de-CH') + ').';
    }

    if (includeOtherExpensesChk.checked) {
      const otherMethod = document.querySelector('input[name=other_expenses_method]:checked');
      if (otherMethod && otherMethod.value === 'effettive') {
        const actual = _numVal('actual_other_expenses_chf');
        if (actual !== null && actual > 50000) {
          return 'Le spese professionali effettive non possono superare CHF 50\'000 (inserito: CHF ' + actual.toLocaleString('de-CH') + ').';
        }
      }
      const salary = _numVal('annual_net_salary_chf');
      if (salary !== null && salary > 1000000) {
        return 'Il salario netto annuo non può superare CHF 1\'000\'000 (inserito: CHF ' + salary.toLocaleString('de-CH') + ').';
      }
    }

    if (includeSecondaryChk.checked) {
      const secMethod = document.querySelector('input[name=secondary_method]:checked');
      if (secMethod && secMethod.value === 'effettive') {
        const actual = _numVal('actual_secondary_activity_chf');
        if (actual !== null && actual > 500000) {
          return 'Le spese per l\'attività accessoria non possono superare CHF 500\'000 (inserito: CHF ' + actual.toLocaleString('de-CH') + ').';
        }
      }
    }

    // Validazione coniuge
    if (includeSpouseChk && includeSpouseChk.checked) {
      var spWorkCityVal = document.getElementById('sp_work_city').value.trim();
      var spWorkStreetVal = document.getElementById('sp_work_street').value.trim();
      if (!spWorkCityVal) return 'Inserire la città del luogo di lavoro del coniuge.';
      if (!spWorkStreetVal) return 'Inserire la via del luogo di lavoro del coniuge.';
      var spWorkNpaV = document.getElementById('sp_work_npa').value.trim();
      var spWorkCountryV = document.getElementById('sp_work_country').value || 'CH';
      if (spWorkNpaV) {
        var spNpaE = validateNpa(spWorkNpaV, spWorkCountryV, 'del luogo di lavoro del coniuge');
        if (spNpaE) return spNpaE;
      }
      var spKmVal = parseFloat(document.getElementById('sp_override_distance_km').value);
      if (!isNaN(spKmVal)) {
        if (spKmVal < 0.1) return 'La distanza casa-lavoro del coniuge deve essere almeno 0.1 km.';
        if (spKmVal > 500) return 'La distanza del coniuge non può superare 500 km (inserito: ' + spKmVal + ' km).';
      }
      var spModeV = document.getElementById('sp_transport_mode').value;
      if (spModeV === 'public_transport') {
        var spPtR = document.querySelector('input[name=sp_pt_cost_type]:checked');
        if (spPtR && spPtR.value === 'manuale') {
          var spPtC = parseFloat(document.getElementById('sp_annual_pt_cost').value);
          if (isNaN(spPtC) || spPtC <= 0) return 'Inserire il costo abbonamento annuale del coniuge.';
          if (spPtC > 20000) return 'Il costo abbonamento del coniuge non può superare CHF 20\'000.';
        }
      }
    }

    return null;
  }

  // ── Helpers ──────────────────────────────────────────────────────────────

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function formatChf(amount) {
    return "CHF " + amount.toLocaleString('de-CH', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  }

  function showSpinner() {
    // Nascondi TUTTE le azioni/sezioni legate ai risultati durante il calcolo
    var ra = document.getElementById('results-actions');
    if (ra) ra.classList.add('hidden');
    var banner = document.getElementById('assessment-banner');
    if (banner) banner.classList.add('hidden');
    var reasonSection = document.getElementById('assessment-reason-section');
    if (reasonSection) reasonSection.classList.add('hidden');
    resultsDiv.innerHTML =
      '<div class="spinner-wrapper">' +
        '<div class="spinner"></div>' +
        '<p class="spinner-label">Calcolo in corso…</p>' +
      '</div>';
    resultsDiv.classList.remove('hidden');
  }

  function setFormBusy(busy) {
    var submitBtn = form.querySelector('button[type=submit]');
    if (submitBtn) {
      submitBtn.disabled = busy;
      if (busy) {
        if (!submitBtn.dataset.label) submitBtn.dataset.label = submitBtn.textContent;
        submitBtn.textContent = 'Calcolo in corso…';
      } else if (submitBtn.dataset.label) {
        submitBtn.textContent = submitBtn.dataset.label;
      }
    }
    if (btnReset) btnReset.disabled = busy;
  }

  function clearResults() {
    resultsDiv.innerHTML = '';
    resultsDiv.classList.add('hidden');
    // Nascondi azioni, mappa, accertamento
    var ra = document.getElementById('results-actions');
    if (ra) ra.classList.add('hidden');
    hideAssessmentMode();
    hideMap();
    lastResponse = null;
  }

  // ── Mappa (US-1005/1006) ──────────────────────────────────────────────────

  function hideMap() {
    var mapSection = document.getElementById('map-section');
    if (mapSection) mapSection.classList.add('hidden');
    if (leafletMap) { leafletMap.remove(); leafletMap = null; }
    osrmPolyline = null;
    spouseMarkers.forEach(function (m) { /* already removed with map */ });
    spouseMarkers = [];
  }

  function initMap(data) {
    var homeC = data.home_coordinates;
    var workC = data.work_coordinates;
    if (!homeC || !workC) return;

    var mapSection = document.getElementById('map-section');
    mapSection.classList.remove('hidden');

    if (leafletMap) { leafletMap.remove(); leafletMap = null; }
    osrmPolyline = null;
    spouseMarkers = [];

    leafletMap = L.map('route-map');
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      maxZoom: 18,
      crossOrigin: true, // necessario per rasterizzare la mappa nel PDF (US-1112)
    }).addTo(leafletMap);

    // circleMarker (vettoriale, non HTML/divIcon) così leaflet-image può
    // rasterizzarli correttamente per l'export PDF (US-1112).
    function dotMarker(latlng, color, radius) {
      return L.circleMarker(latlng, {
        radius: radius, color: '#fff', weight: 2, fillColor: color, fillOpacity: 1,
        className: 'route-marker',
      });
    }

    var homeMarker = dotMarker([homeC.lat, homeC.lon], '#27ae60', 7).addTo(leafletMap).bindPopup('Casa');
    var workMarker = dotMarker([workC.lat, workC.lon], '#c0392b', 7).addTo(leafletMap).bindPopup('Lavoro');

    var bounds = L.latLngBounds([[homeC.lat, homeC.lon], [workC.lat, workC.lon]]);

    // Marker coniuge (US-1008)
    if (data.spouse) {
      var spHomeC = data.spouse.home_coordinates;
      var spWorkC = data.spouse.work_coordinates;
      if (spHomeC) {
        var m = dotMarker([spHomeC.lat, spHomeC.lon], '#7f8c8d', 5).addTo(leafletMap).bindPopup('Casa coniuge');
        spouseMarkers.push(m);
        bounds.extend([spHomeC.lat, spHomeC.lon]);
      }
      if (spWorkC) {
        var m2 = dotMarker([spWorkC.lat, spWorkC.lon], '#7f8c8d', 5).addTo(leafletMap).bindPopup('Lavoro coniuge');
        spouseMarkers.push(m2);
        bounds.extend([spWorkC.lat, spWorkC.lon]);
      }
    }

    leafletMap.fitBounds(bounds, { padding: [40, 40] });

    // Note mappa
    var mapNote = document.getElementById('map-note');
    var mode = data.cantonal_TI.transport_deduction.mode;
    if (mode === 'public_transport') {
      if (mapNote) { mapNote.textContent = 'Caricamento percorso mezzi pubblici…'; mapNote.classList.remove('hidden'); }
      drawTransitRoute(homeC, workC, mapNote);
    } else {
      if (mapNote) mapNote.classList.add('hidden');
      // Routing OSRM (US-1006)
      var osrmProfile = (mode === 'bicycle') ? 'cycling' : 'driving';
      drawOsrmRoute(homeC, workC, osrmProfile);
    }
  }

  function drawTransitRoute(homeC, workC, mapNote) {
    // Percorso mezzi pubblici via backend proxy (transport.opendata.ch).
    var url = '/v1/route/transit?from_lat=' + homeC.lat + '&from_lon=' + homeC.lon +
      '&to_lat=' + workC.lat + '&to_lon=' + workC.lon;
    var controller = new AbortController();
    var timeoutId = setTimeout(function () { controller.abort(); }, 7000);

    fetch(url, { signal: controller.signal })
      .then(function (r) { clearTimeout(timeoutId); return r.json(); })
      .then(function (data) {
        if (!leafletMap) return;
        var pts = (data && data.polyline) || [];
        if (pts.length >= 2) {
          if (osrmPolyline) { osrmPolyline.remove(); }
          osrmPolyline = L.polyline(pts, { color: '#8e44ad', weight: 4, opacity: 0.8, dashArray: '6,4' }).addTo(leafletMap);
          try { leafletMap.fitBounds(osrmPolyline.getBounds(), { padding: [40, 40] }); } catch (e) {}
          if (mapNote) { mapNote.textContent = 'Percorso mezzi pubblici (fonte: transport.opendata.ch).'; }
        } else {
          drawStraightLine(homeC, workC, mapNote);
        }
      })
      .catch(function () { drawStraightLine(homeC, workC, mapNote); });
  }

  function drawStraightLine(homeC, workC, mapNote) {
    if (!leafletMap) return;
    if (osrmPolyline) { osrmPolyline.remove(); }
    osrmPolyline = L.polyline([[homeC.lat, homeC.lon], [workC.lat, workC.lon]],
      { color: '#8e44ad', weight: 3, opacity: 0.6, dashArray: '4,6' }).addTo(leafletMap);
    if (mapNote) { mapNote.textContent = 'Percorso transit non disponibile — visualizzata linea diretta casa-lavoro.'; }
  }

  function drawOsrmRoute(homeC, workC, profile) {
    var url = 'https://router.project-osrm.org/route/v1/' + profile + '/' +
      homeC.lon + ',' + homeC.lat + ';' + workC.lon + ',' + workC.lat +
      '?overview=full&geometries=geojson';

    var controller = new AbortController();
    var timeoutId = setTimeout(function () { controller.abort(); }, 3000);

    fetch(url, { signal: controller.signal })
      .then(function (r) { clearTimeout(timeoutId); return r.json(); })
      .then(function (data) {
        if (!leafletMap) return;
        if (data.routes && data.routes[0] && data.routes[0].geometry) {
          if (osrmPolyline) { osrmPolyline.remove(); }
          osrmPolyline = L.geoJSON(data.routes[0].geometry, {
            style: { color: '#003366', weight: 4, opacity: 0.75 },
          }).addTo(leafletMap);
        }
      })
      .catch(function () { /* silently ignore OSRM failures */ });
  }

  // ── PDF generation (US-1009/1011/1112) ───────────────────────────────────

  // Estrae un array piatto di LatLng da un layer Leaflet (polyline o geoJSON/OSRM).
  function extractLatLngs(layer) {
    var out = [];
    if (!layer) return out;
    function flatten(x) {
      if (Array.isArray(x)) { x.forEach(flatten); } else if (x) { out.push(x); }
    }
    if (typeof layer.eachLayer === 'function') {
      layer.eachLayer(function (l) { if (typeof l.getLatLngs === 'function') flatten(l.getLatLngs()); });
    } else if (typeof layer.getLatLngs === 'function') {
      flatten(layer.getLatLngs());
    }
    return out;
  }

  // Rasterizza la mappa Leaflet corrente (tile + percorso + marker) in un PNG per il
  // PDF. Disegnato a mano (tile via canvas, marker/linea via leafletMap.latLngToContainerPoint)
  // perché il plugin leaflet-image (2016) non supporta il renderer SVG di Leaflet 1.9.
  // Richiama sempre callback(null|{dataUrl, width, height}), mai un'eccezione.
  function captureMapImage(callback) {
    var mapSection = document.getElementById('map-section');
    if (!mapSection || mapSection.classList.contains('hidden') || !leafletMap) { callback(null); return; }

    var scale = 2; // risoluzione doppia per una stampa nitida
    var size = leafletMap.getSize();
    var zoom = Math.round(leafletMap.getZoom());
    var origin = leafletMap.getPixelOrigin();
    var tileSize = 256;
    var maxTileIndex = Math.pow(2, zoom) - 1;

    var minTileX = Math.max(0, Math.floor(origin.x / tileSize));
    var minTileY = Math.max(0, Math.floor(origin.y / tileSize));
    var maxTileX = Math.min(maxTileIndex, Math.floor((origin.x + size.x) / tileSize));
    var maxTileY = Math.min(maxTileIndex, Math.floor((origin.y + size.y) / tileSize));

    var canvas = document.createElement('canvas');
    canvas.width = size.x * scale;
    canvas.height = size.y * scale;
    var ctx = canvas.getContext('2d');
    ctx.scale(scale, scale);

    var subdomains = ['a', 'b', 'c'];
    var tiles = [];
    for (var tx = minTileX; tx <= maxTileX; tx++) {
      for (var ty = minTileY; ty <= maxTileY; ty++) tiles.push({ x: tx, y: ty });
    }

    var done = false;
    var safetyTimer = setTimeout(finish, 8000); // non bloccare il PDF se i tile sono lenti/assenti

    var remaining = tiles.length;
    function tileDone() { remaining--; if (remaining <= 0) finish(); }
    if (remaining === 0) finish();

    tiles.forEach(function (t) {
      var img = new Image();
      img.crossOrigin = 'anonymous';
      var sub = subdomains[Math.abs(t.x + t.y) % subdomains.length];
      img.onload = function () {
        var dx = t.x * tileSize - origin.x;
        var dy = t.y * tileSize - origin.y;
        try { ctx.drawImage(img, dx, dy, tileSize, tileSize); } catch (e) { /* tile CORS: pagina rasterizzata senza quel tile */ }
        tileDone();
      };
      img.onerror = tileDone;
      img.src = 'https://' + sub + '.tile.openstreetmap.org/' + zoom + '/' + t.x + '/' + t.y + '.png';
    });

    function toXY(latlng) { return leafletMap.latLngToContainerPoint(latlng); }

    function dot(coord, color, radius) {
      if (!coord) return;
      var p = toXY([coord.lat, coord.lon]);
      ctx.beginPath();
      ctx.arc(p.x, p.y, radius, 0, 2 * Math.PI);
      ctx.fillStyle = color;
      ctx.fill();
      ctx.lineWidth = 2;
      ctx.strokeStyle = '#fff';
      ctx.stroke();
    }

    function finish() {
      if (done) return;
      done = true;
      clearTimeout(safetyTimer);

      var routeLatLngs = extractLatLngs(osrmPolyline);
      if (routeLatLngs.length >= 2) {
        ctx.beginPath();
        routeLatLngs.forEach(function (ll, i) {
          var p = toXY(ll);
          if (i === 0) ctx.moveTo(p.x, p.y); else ctx.lineTo(p.x, p.y);
        });
        ctx.strokeStyle = '#8e44ad';
        ctx.lineWidth = 4;
        ctx.lineJoin = 'round';
        ctx.lineCap = 'round';
        ctx.stroke();
      }

      if (lastResponse) {
        dot(lastResponse.home_coordinates, '#27ae60', 7);
        dot(lastResponse.work_coordinates, '#c0392b', 7);
        if (lastResponse.spouse) {
          dot(lastResponse.spouse.home_coordinates, '#7f8c8d', 5);
          dot(lastResponse.spouse.work_coordinates, '#7f8c8d', 5);
        }
      }

      try {
        callback({ dataUrl: canvas.toDataURL('image/png'), width: canvas.width, height: canvas.height });
      } catch (e) {
        callback(null); // canvas "tainted" o altro errore di export: il PDF prosegue senza mappa
      }
    }
  }

  function generatePdf(assessmentMode) {
    if (!lastResponse) return;
    captureMapImage(function (mapImg) { buildPdfDocument(assessmentMode, mapImg); });
  }

  function buildPdfDocument(assessmentMode, mapImg) {
    var jspdf = window.jspdf;
    if (!jspdf) return;
    var doc = new jspdf.jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });

    var today = new Date();
    var dateStr = today.toLocaleDateString('it-CH', { day: '2-digit', month: '2-digit', year: 'numeric' });
    var yyyymmdd = today.toISOString().slice(0, 10).replace(/-/g, '');
    var year = lastResponse.fiscal_year;

    // Intestazione
    doc.setFontSize(14);
    doc.setFont(undefined, 'bold');
    if (assessmentMode) {
      doc.text('DOCUMENTO DI ACCERTAMENTO', 14, 18);
      doc.setFontSize(11);
      doc.setFont(undefined, 'normal');
      doc.text('Calcolo Deduzioni Trasferta — Canton Ticino', 14, 25);
    } else {
      doc.text('Calcolo Deduzioni Trasferta — Canton Ticino', 14, 18);
    }
    doc.setFontSize(10);
    doc.setFont(undefined, 'normal');
    doc.text('Anno fiscale ' + year + ' | Generato il ' + dateStr, 14, 31);

    var yPos = 38;

    function addLevelTable(level, title, tableId) {
      doc.setFontSize(11);
      doc.setFont(undefined, 'bold');
      doc.text(title, 14, yPos);
      yPos += 4;

      // Valori accertati salvati per questa tabella, indicizzati per riga
      var assessed = (assessmentMode && assessedState[tableId]) ? assessedState[tableId] : {};
      var rowIdx = 0;       // indice riga-input (allineato a makeCell)
      var accertatoTotal = 0;
      var changedRowIdx = [];   // indici (in rows) delle righe con accertato ≠ calcolato

      function accertatoFor(calcolato) {
        var entry = assessed[rowIdx];
        var amount = (entry && entry.amount != null) ? entry.amount : calcolato;
        var reason = (entry && entry.reason) ? entry.reason : '';
        rowIdx++;
        accertatoTotal += amount;
        return { amount: amount, reason: reason, changed: Math.abs(amount - calcolato) > 0.005 };
      }

      // La freccia "→" dei testi basis non esiste nei font base di jsPDF
      // (usciva come "!'" con spaziatura rotta): la nota va a capo nella cella.
      function pdfBasis(text) {
        return (text || '').replace(/\s*→\s*/g, '\n');
      }

      function pushAssessed(label, calcolato, basis) {
        var a = accertatoFor(calcolato);
        if (a.changed) changedRowIdx.push(rows.length);
        rows.push([label, pdfBasis(basis), formatChf(calcolato), formatChf(a.amount), a.reason || (a.changed ? '—' : '')]);
      }

      var rows = [];
      var transport = level.transport_deduction;
      transport.lines.forEach(function (line) {
        var calcolato = line.amount_chf;
        if (assessmentMode) {
          pushAssessed(line.label, calcolato, line.basis);
        } else {
          rows.push([line.label, formatChf(calcolato), pdfBasis(line.basis)]);
        }
      });

      if (level.meals_deduction_chf != null) {
        if (assessmentMode) {
          pushAssessed('Pasti fuori domicilio', level.meals_deduction_chf, level.meals_basis_text);
        } else {
          rows.push(['Pasti fuori domicilio', formatChf(level.meals_deduction_chf), pdfBasis(level.meals_basis_text)]);
        }
      }
      if (level.other_expenses_deduction_chf != null) {
        // IC = forfait cantonale, IFD = 3% del salario netto (il backend non
        // fornisce un basis text per questa voce)
        var otherBasis = (tableId === 'fed' || tableId === 'spfed')
          ? "3% del salario netto (min CHF 2'000, max CHF 4'000)"
          : "Forfait cantonale CHF 3'000 o spese effettive documentate";
        if (assessmentMode) {
          pushAssessed('Altre spese professionali', level.other_expenses_deduction_chf, otherBasis);
        } else {
          rows.push(['Altre spese professionali', formatChf(level.other_expenses_deduction_chf), otherBasis]);
        }
      }
      if (assessmentMode) {
        rows.push(['TOTALE', '', formatChf(level.total_deduction_chf), formatChf(accertatoTotal), '']);
      } else {
        rows.push(['TOTALE', formatChf(level.total_deduction_chf), '']);
      }

      // In accertamento: Voce | Base di calcolo | Calcolato (prima) | Accertato (dopo) | Motivazione.
      var head = assessmentMode
        ? [['Voce', 'Base di calcolo', 'Calcolato (prima)', 'Accertato (dopo)', 'Motivazione']]
        : [['Voce', 'Importo CHF', 'Base di calcolo']];

      var totalRowIdx = rows.length - 1;

      doc.autoTable({
        head: head,
        body: rows,
        startY: yPos,
        margin: { left: 14, right: 14 },
        styles: { fontSize: assessmentMode ? 8 : 9, cellPadding: 2.5, valign: 'middle', overflow: 'linebreak' },
        headStyles: { fillColor: [0, 51, 102], textColor: [255, 255, 255], fontStyle: 'bold' },
        alternateRowStyles: { fillColor: [247, 249, 252] },
        columnStyles: assessmentMode
          ? { 0: { cellWidth: 34 }, 1: { cellWidth: 50, fontSize: 7 }, 2: { halign: 'right', cellWidth: 25 }, 3: { halign: 'right', cellWidth: 25 } }
          : { 0: { cellWidth: 52 }, 1: { halign: 'right', cellWidth: 30 } },
        didParseCell: function (data) {
          // Solo le celle del corpo tabella: l'header NON deve mai ereditare i colori
          // delle righe rettificate (altrimenti diventa testo bianco su sfondo chiaro).
          if (data.section !== 'body') return;
          if (data.row.index === totalRowIdx) {
            data.cell.styles.fontStyle = 'bold';
            data.cell.styles.fillColor = [233, 238, 245];
          } else if (assessmentMode && changedRowIdx.indexOf(data.row.index) >= 0) {
            // Evidenzia le righe effettivamente rettificate (giallo tenue)
            data.cell.styles.fillColor = [255, 243, 205];
            if (data.column.index === 3) {
              data.cell.styles.fontStyle = 'bold';
              data.cell.styles.textColor = [146, 64, 14];
            }
          }
        },
      });
      yPos = doc.lastAutoTable.finalY + 6;
    }

    addLevelTable(lastResponse.cantonal_TI, 'Imposta Cantonale TI (IC)', 'can');
    addLevelTable(lastResponse.federal_IFD, 'Imposta Federale Diretta (IFD)', 'fed');

    if (lastResponse.spouse) {
      if (yPos > 220) { doc.addPage(); yPos = 20; }
      doc.setFontSize(12);
      doc.setFont(undefined, 'bold');
      doc.text('Coniuge/Partner registrato', 14, yPos);
      yPos += 6;
      addLevelTable(lastResponse.spouse.cantonal_TI, 'IC — Coniuge', 'spcan');
      addLevelTable(lastResponse.spouse.federal_IFD, 'IFD — Coniuge', 'spfed');
    }

    if (mapImg) {
      var mapW = 180;
      var mapH = mapW * (mapImg.height / mapImg.width);
      if (yPos + 10 + mapH > 280) { doc.addPage(); yPos = 20; }
      doc.setFontSize(11);
      doc.setFont(undefined, 'bold');
      doc.text('Percorso casa-lavoro', 14, yPos);
      yPos += 4;
      doc.addImage(mapImg.dataUrl, 'PNG', 14, yPos, mapW, mapH);
      yPos += mapH + 3;
      doc.setFontSize(7);
      doc.setFont(undefined, 'italic');
      doc.text('Mappa: © OpenStreetMap contributors', 14, yPos);
      yPos += 6;
    }

    if (assessmentMode) {
      if (yPos > 220) { doc.addPage(); yPos = 20; }
      var reason = document.getElementById('assessment-reason').value.trim();
      doc.setFontSize(10);
      doc.setFont(undefined, 'bold');
      doc.text('Commento generale:', 14, yPos);
      yPos += 5;
      doc.setFont(undefined, 'normal');
      var lines = doc.splitTextToSize(reason, 180);
      doc.text(lines, 14, yPos);
      yPos += lines.length * 5 + 4;
    }

    // Footer
    doc.setFontSize(8);
    doc.setFont(undefined, 'italic');
    if (assessmentMode) {
      doc.text('Documento di accertamento generato il ' + dateStr + ' — verificare con l\'autorità fiscale competente.', 14, 287);
    } else {
      doc.text('Documento generato automaticamente — non ha valore legale.', 14, 287);
    }

    var fname = assessmentMode ? 'accertato_' + year + '_' + yyyymmdd + '.pdf' : 'deduzioni_' + year + '_' + yyyymmdd + '.pdf';
    doc.save(fname);
  }

  // ── Assessment mode (US-1010/1011) ────────────────────────────────────────

  function setSaveStatus(text, color) {
    var el = document.getElementById('assessment-save-status');
    if (!el) return;
    if (!text) { el.classList.add('hidden'); el.textContent = ''; return; }
    el.textContent = text;
    el.style.color = color || '#666';
    el.classList.remove('hidden');
  }

  function markAssessmentDirty() {
    assessmentDirty = true;
    setSaveStatus('● Modifiche non salvate', '#e67e22');
  }

  // Trova il campo «Motivo» associato a una riga (ora in una riga separata della tabella).
  function findReasonInput(tid, idx) {
    return resultsDiv.querySelector(
      '.assessment-reason-input[data-table="' + tid + '"][data-idx="' + idx + '"]'
    );
  }

  function saveAssessment() {
    if (!lastResponse) return;
    // Raccoglie importo + motivo correnti di ogni input nello stato accertato
    assessedState = {};
    resultsDiv.querySelectorAll('.assessment-input').forEach(function (inp) {
      var tid = inp.getAttribute('data-table');
      var idx = inp.getAttribute('data-idx');
      var reasonInp = findReasonInput(tid, idx);
      if (!assessedState[tid]) assessedState[tid] = {};
      assessedState[tid][idx] = {
        amount: parseFloat(inp.value) || 0,
        reason: reasonInp ? reasonInp.value.trim() : '',
      };
    });
    assessmentDirty = false;
    var now = new Date().toLocaleTimeString('it-CH', { hour: '2-digit', minute: '2-digit' });
    setSaveStatus('✓ Modifiche salvate alle ' + now, '#27ae60');
  }

  // Ritorna l'elenco delle righe modificate prive di motivo (per validazione PDF).
  function changedRowsMissingReason() {
    var missing = 0;
    resultsDiv.querySelectorAll('.assessment-input').forEach(function (inp) {
      var orig = parseFloat(inp.getAttribute('data-original'));
      var cur = parseFloat(inp.value) || 0;
      if (Math.abs(cur - orig) > 0.005) {
        var reasonInp = findReasonInput(inp.getAttribute('data-table'), inp.getAttribute('data-idx'));
        if (!reasonInp || !reasonInp.value.trim()) missing++;
      }
    });
    return missing;
  }

  function hideAssessmentMode() {
    assessmentActive = false;
    assessedState = {};
    assessmentDirty = false;
    var banner = document.getElementById('assessment-banner');
    var reasonSection = document.getElementById('assessment-reason-section');
    var btnA = document.getElementById('btn-assessment-mode');
    var btnD = document.getElementById('btn-download-assessment');
    var btnS = document.getElementById('btn-save-assessment');
    if (banner) banner.classList.add('hidden');
    if (reasonSection) reasonSection.classList.add('hidden');
    if (btnA) btnA.textContent = '✏ Modalità accertamento';
    if (btnD) btnD.classList.add('hidden');
    if (btnS) btnS.classList.add('hidden');
    setSaveStatus('');
  }

  function toggleAssessmentMode() {
    assessmentActive = !assessmentActive;
    var banner = document.getElementById('assessment-banner');
    var reasonSection = document.getElementById('assessment-reason-section');
    var btnA = document.getElementById('btn-assessment-mode');
    var btnD = document.getElementById('btn-download-assessment');
    var btnS = document.getElementById('btn-save-assessment');

    if (assessmentActive) {
      assessedState = {};
      assessmentDirty = false;
      if (banner) banner.classList.remove('hidden');
      if (reasonSection) reasonSection.classList.remove('hidden');
      if (btnA) btnA.textContent = '✕ Esci da modalità accertamento';
      if (btnD) btnD.classList.remove('hidden');
      if (btnS) btnS.classList.remove('hidden');
      setSaveStatus('Nessuna modifica', '#666');
    } else {
      if (banner) banner.classList.add('hidden');
      if (reasonSection) reasonSection.classList.add('hidden');
      if (btnA) btnA.textContent = '✏ Modalità accertamento';
      if (btnD) btnD.classList.add('hidden');
      if (btnS) btnS.classList.add('hidden');
      setSaveStatus('');
    }
    // Rirenderizza con/senza input editabili
    if (lastResponse) renderResults(lastResponse);
  }

  // ── Results renderer ──────────────────────────────────────────────────────

  function buildDeductionTable(level, tableId) {
    var assessment = assessmentActive;
    const transport = level.transport_deduction;
    let rows = '';
    var inputIdx = 0;
    var tid = tableId || 'tbl';

    // Ritorna { cell, reasonRow }: la cella editabile dell'importo + una riga
    // separata a tutta larghezza per il «Motivo della modifica» (così è sempre
    // cliccabile e non si sovrappone alla colonna "Base di calcolo").
    function makeCells(amount) {
      if (!assessment) {
        return { cell: '<td class="amount">' + formatChf(amount) + '</td>', reasonRow: '' };
      }
      var idx = inputIdx++;
      // Riusa valore + motivo già accertati per questa riga se presenti
      var entry = (assessedState[tid] && assessedState[tid][idx]) || {};
      var saved = (entry.amount != null) ? entry.amount : amount;
      var savedReason = entry.reason || '';
      var changed = Math.abs(saved - amount) > 0.005;
      var changedClass = changed ? ' is-changed' : '';
      var cell =
        '<td class="amount">' +
          '<input type="number" class="assessment-input' + changedClass + '" step="0.01" value="' + saved.toFixed(2) +
          '" data-original="' + amount.toFixed(2) + '" data-table="' + tid + '" data-idx="' + idx +
          '" aria-label="Importo accertato">' +
        '</td>';
      var reasonRow =
        '<tr class="assessment-reason-row' + (changed ? '' : ' hidden') + '">' +
          '<td class="reason-label">&#8627; Motivo della modifica</td>' +
          '<td colspan="2">' +
            '<input type="text" class="assessment-reason-input" maxlength="300" value="' + escapeHtml(savedReason) +
            '" data-table="' + tid + '" data-idx="' + idx + '" placeholder="Indicare il motivo della rettifica…" ' +
            'aria-label="Motivo della modifica">' +
          '</td>' +
        '</tr>';
      return { cell: cell, reasonRow: reasonRow };
    }

    transport.lines.forEach(function (line) {
      const capMark = line.capped ? ' <span class="cap-icon" title="Tetto massimo applicato">⚠</span>' : '';
      const capRow = (line.capped && line.cap_amount_chf != null)
        ? '<tr><td colspan="3" class="cap-warning">Tetto massimo applicato: ' + formatChf(line.cap_amount_chf) + '</td></tr>'
        : '';
      var c = makeCells(line.amount_chf);
      rows +=
        '<tr>' +
          '<td>' + escapeHtml(line.label) + capMark +
            '<span class="legal-ref">' + escapeHtml(line.legal_reference) + '</span></td>' +
          c.cell +
          '<td class="basis">' + escapeHtml(line.basis) + '</td>' +
        '</tr>' + c.reasonRow + capRow;
    });

    if (level.meals_deduction_chf != null) {
      var cm = makeCells(level.meals_deduction_chf);
      rows +=
        '<tr>' +
          '<td>Pasti fuori domicilio</td>' +
          cm.cell +
          '<td class="basis">' + escapeHtml(level.meals_basis_text || '—') + '</td>' +
        '</tr>' + cm.reasonRow;
    }

    if (level.other_expenses_deduction_chf != null) {
      var co = makeCells(level.other_expenses_deduction_chf);
      rows +=
        '<tr>' +
          '<td>Altre spese professionali</td>' +
          co.cell +
          '<td class="basis">3% salario netto</td>' +
        '</tr>' + co.reasonRow;
    }

    var totalId = tableId ? 'total-' + tableId : '';
    rows +=
      '<tr class="total-row">' +
        '<td><strong>Totale</strong></td>' +
        '<td class="amount" id="' + totalId + '"><strong>' + formatChf(level.total_deduction_chf) + '</strong></td>' +
        '<td></td>' +
      '</tr>';

    return (
      '<table class="deduction-table" data-total-id="' + totalId + '">' +
        '<thead><tr><th>Voce</th><th>Importo</th><th>Base di calcolo</th></tr></thead>' +
        '<tbody>' + rows + '</tbody>' +
      '</table>'
    );
  }

  function buildColumn(level, badgeClass, badgeLabel, tableId) {
    return (
      '<div class="results-column">' +
        '<div class="results-column-header">' +
          '<span class="' + badgeClass + '">' + badgeLabel + '</span>' +
        '</div>' +
        '<div class="total-amount">' + formatChf(level.total_deduction_chf) + '</div>' +
        buildDeductionTable(level, tableId) +
      '</div>'
    );
  }

  function buildAlternativeScenario(levelIC, levelIFD, title) {
    // Mostra lo scenario "auto fino alla stazione + abbonamento" quando presente.
    var altIC = levelIC && levelIC.alternative_transport;
    var altIFD = levelIFD && levelIFD.alternative_transport;
    if (!altIC && !altIFD) return '';

    function rows(alt) {
      if (!alt) return '';
      return alt.lines.map(function (l) {
        return '<tr><td>' + escapeHtml(l.label) + '</td><td class="amount">' + formatChf(l.amount_chf) + '</td></tr>';
      }).join('') +
        '<tr class="total-row"><td><strong>Totale scenario</strong></td><td class="amount"><strong>' +
        formatChf(alt.net_deduction_chf) + '</strong></td></tr>';
    }

    return (
      '<div class="alert-warning" style="margin-top:0.75rem;background:#eef6ff;border-color:#7fb1e6;">' +
        '<strong>🔀 ' + escapeHtml(title) + '</strong>' +
        '<p style="margin:0.25rem 0 0.5rem;font-size:0.85rem;">I mezzi pubblici erano ragionevolmente utilizzabili. ' +
        'Oltre allo scenario con deduzione auto azzerata (sopra), ecco lo scenario alternativo ' +
        '<em>auto fino alla stazione + abbonamento ARCOBALENO</em> (importi indicativi, zone stimate dalla distanza):</p>' +
        '<div class="results-columns">' +
          '<div class="results-column"><div class="results-column-header"><span class="badge-cantonal">Cantonale TI (IC)</span></div>' +
            '<table class="deduction-table"><tbody>' + rows(altIC) + '</tbody></table></div>' +
          '<div class="results-column"><div class="results-column-header"><span class="badge-federal">Federale IFD</span></div>' +
            '<table class="deduction-table"><tbody>' + rows(altIFD) + '</tbody></table></div>' +
        '</div>' +
      '</div>'
    );
  }

  var NPA_FIELD_MAP = {
    home: 'home_npa', work: 'work_npa',
    spouse_home: 'sp_home_npa', spouse_work: 'sp_work_npa',
  };
  var NPA_FIELD_LABEL = {
    home: 'domicilio', work: 'luogo di lavoro',
    spouse_home: 'domicilio coniuge', spouse_work: 'luogo di lavoro coniuge',
  };

  function buildNpaWarnings(data) {
    var checks = (data.address_validation || []).filter(function (c) { return !c.matched && c.resolved_npa; });
    if (checks.length === 0) return '';
    var items = checks.map(function (c) {
      var label = NPA_FIELD_LABEL[c.field] || c.field;
      return '<li style="margin-bottom:0.35rem;">NPA <strong>' + escapeHtml(c.input_npa) + '</strong> per il ' + escapeHtml(label) +
        ' non corrisponde alla località risolta (<strong>' + escapeHtml(c.resolved_npa) + ' ' + escapeHtml(c.resolved_city || '') + '</strong>). ' +
        '<button type="button" class="btn-secondary npa-fix-btn" data-npa-field="' + escapeHtml(c.field) +
        '" data-npa-value="' + escapeHtml(c.resolved_npa) + '" style="padding:2px 8px;font-size:0.8rem;">Usa ' + escapeHtml(c.resolved_npa) + '</button></li>';
    }).join('');
    return '<div class="alert-danger" id="npa-warning-box"><strong>⚠️ Verifica NPA</strong><ul style="margin:0.5rem 0 0;">' + items + '</ul></div>';
  }

  function renderResults(data) {
    lastResponse = data;

    const calcDate = new Date(data.calculated_at);
    const dateStr = calcDate.toLocaleDateString('it-CH', { day: '2-digit', month: '2-digit', year: 'numeric' });
    const timeStr = calcDate.toLocaleTimeString('it-CH', { hour: '2-digit', minute: '2-digit' });

    let geoHtml = '';
    if (data.geocoding_used) {
      const provider = (data.geocoding_provider || '').toLowerCase().indexOf('swisstopo') >= 0
        ? 'Swisstopo' : 'Nominatim';
      geoHtml = ' <span class="badge-geo">Geocoding: ' + provider + '</span>';
    }

    let distHtml = '';
    if (data.distance_km != null) {
      distHtml = ' &mdash; Distanza: <strong>' + data.distance_km.toFixed(1) + ' km</strong>';
    }

    let errHtml = '';
    if (data.errors && data.errors.length > 0) {
      errHtml = '<div class="alert-danger">' +
        data.errors.map(function (e) { return escapeHtml(e); }).join('<br>') +
        '</div>';
    }

    const allWarnings = (data.warnings || []).slice();
    (data.cantonal_TI.notes || []).forEach(function (n) { allWarnings.push(n); });
    (data.federal_IFD.notes || []).forEach(function (n) {
      if (allWarnings.indexOf(n) < 0) allWarnings.push(n);
    });

    let warnHtml = '';
    if (allWarnings.length > 0) {
      warnHtml =
        '<div class="alert-warning">' +
          '<strong>ℹ️ Note e avvertenze</strong>' +
          '<ul>' + allWarnings.map(function (w) { return '<li>' + escapeHtml(w) + '</li>'; }).join('') + '</ul>' +
        '</div>';
    }

    // Risultati contribuente
    var html =
      '<div class="results-header">' +
        '<strong>Anno fiscale ' + data.fiscal_year + '</strong>' +
        ' &mdash; Calcolato il ' + dateStr + ' alle ' + timeStr +
        distHtml + geoHtml +
      '</div>' +
      buildNpaWarnings(data) +
      errHtml +
      '<div class="results-columns">' +
        buildColumn(data.cantonal_TI, 'badge-cantonal', 'Cantonale TI (IC)', 'can') +
        buildColumn(data.federal_IFD, 'badge-federal', 'Federale IFD', 'fed') +
      '</div>' +
      buildAlternativeScenario(data.cantonal_TI, data.federal_IFD, 'Scenario alternativo trasporto') +
      warnHtml;

    // Risultati coniuge (US-1008)
    if (data.spouse) {
      var sp = data.spouse;
      var spDistHtml = sp.distance_km != null ? ' &mdash; Distanza: <strong>' + sp.distance_km.toFixed(1) + ' km</strong>' : '';
      html +=
        '<div class="results-header" style="margin-top:1rem;">' +
          '<strong>Coniuge/Partner registrato</strong>' + spDistHtml +
        '</div>' +
        '<div class="results-columns">' +
          buildColumn(sp.cantonal_TI, 'badge-cantonal', 'Cantonale TI (IC) — Coniuge', 'spcan') +
          buildColumn(sp.federal_IFD, 'badge-federal', 'Federale IFD — Coniuge', 'spfed') +
        '</div>' +
        buildAlternativeScenario(sp.cantonal_TI, sp.federal_IFD, 'Scenario alternativo trasporto — Coniuge');
      if (sp.warnings && sp.warnings.length > 0) {
        html +=
          '<div class="alert-warning">' +
            '<strong>ℹ️ Note coniuge</strong>' +
            '<ul>' + sp.warnings.map(function (w) { return '<li>' + escapeHtml(w) + '</li>'; }).join('') + '</ul>' +
          '</div>';
      }
    }

    resultsDiv.innerHTML = html;
    resultsDiv.classList.remove('hidden');

    // Wiring bottoni "Usa NPA corretto"
    resultsDiv.querySelectorAll('.npa-fix-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var field = btn.getAttribute('data-npa-field');
        var value = btn.getAttribute('data-npa-value');
        var inputId = NPA_FIELD_MAP[field];
        var input = inputId ? document.getElementById(inputId) : null;
        if (input) {
          input.value = value;
          input.style.background = '#eafaf1';
          btn.textContent = '✓ Applicato';
          btn.disabled = true;
        }
      });
    });

    // Azioni risultati (PDF, accertamento)
    var ra = document.getElementById('results-actions');
    if (ra) ra.classList.remove('hidden');

    // Aggiorna assessment mode se attivo
    if (assessmentActive) {
      var banner = document.getElementById('assessment-banner');
      if (banner) banner.classList.remove('hidden');
      var reasonSection = document.getElementById('assessment-reason-section');
      if (reasonSection) reasonSection.classList.remove('hidden');
    }

    // Listener su assessment-input per aggiornare i totali e lo stato accertato
    if (assessmentActive) {
      function storeEntry(tid, idx, amount, reason) {
        if (!assessedState[tid]) assessedState[tid] = {};
        assessedState[tid][idx] = { amount: amount, reason: reason || '' };
      }
      resultsDiv.querySelectorAll('.assessment-input').forEach(function (inp) {
        inp.addEventListener('input', function () {
          var orig = parseFloat(inp.getAttribute('data-original'));
          var cur = parseFloat(inp.value) || 0;
          var tid = inp.getAttribute('data-table');
          var idx = inp.getAttribute('data-idx');
          var reasonInp = findReasonInput(tid, idx);
          var changed = Math.abs(cur - orig) > 0.005;

          // Mostra/nasconde la RIGA «Motivo della modifica» a seconda che la riga sia rettificata
          if (reasonInp) {
            var reasonRow = reasonInp.closest('tr');
            if (reasonRow) reasonRow.classList.toggle('hidden', !changed);
          }
          storeEntry(tid, idx, cur, reasonInp ? reasonInp.value : '');

          inp.classList.toggle('is-changed', changed);
          // Ricalcola totale della tabella
          var tableEl = inp.closest('table');
          if (tableEl) {
            var totalCell = tableEl.querySelector('.total-row .amount');
            if (totalCell) {
              var sum = 0;
              tableEl.querySelectorAll('.assessment-input').forEach(function (i) { sum += parseFloat(i.value) || 0; });
              totalCell.innerHTML = '<strong>CHF ' + sum.toLocaleString('de-CH', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + '</strong>';
            }
          }
          markAssessmentDirty();
        });
      });
      // Listener sui campi motivo per salvarne il testo
      resultsDiv.querySelectorAll('.assessment-reason-input').forEach(function (rinp) {
        rinp.addEventListener('input', function () {
          var tid = rinp.getAttribute('data-table');
          var idx = rinp.getAttribute('data-idx');
          var entry = (assessedState[tid] && assessedState[tid][idx]) || {};
          storeEntry(tid, idx, entry.amount != null ? entry.amount : 0, rinp.value);
          markAssessmentDirty();
        });
      });
    }

    resultsDiv.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  // ── Wire up result action buttons ──────────────────────────────────────────

  var btnDownloadPdf = document.getElementById('btn-download-pdf');
  if (btnDownloadPdf) {
    btnDownloadPdf.addEventListener('click', function () { generatePdf(false); });
  }

  var btnAssessmentMode = document.getElementById('btn-assessment-mode');
  if (btnAssessmentMode) {
    btnAssessmentMode.addEventListener('click', toggleAssessmentMode);
  }

  var btnSaveAssessment = document.getElementById('btn-save-assessment');
  if (btnSaveAssessment) {
    btnSaveAssessment.addEventListener('click', saveAssessment);
  }

  var btnDownloadAssessment = document.getElementById('btn-download-assessment');
  if (btnDownloadAssessment) {
    btnDownloadAssessment.addEventListener('click', function () {
      var reason = document.getElementById('assessment-reason').value.trim();
      var errEl = document.getElementById('assessment-reason-error');
      var reasonSection = document.getElementById('assessment-reason-section');

      // 1) Ogni riga modificata deve avere il proprio motivo
      var missing = changedRowsMissingReason();
      if (missing > 0) {
        if (errEl) {
          errEl.textContent = 'Inserire il motivo per ciascuna voce modificata (' + missing + ' mancante/i): ' +
            'compilare il campo "Motivo della modifica" sotto ogni importo rettificato.';
          errEl.classList.remove('hidden');
        }
        resultsDiv.scrollIntoView({ behavior: 'smooth', block: 'start' });
        return;
      }
      // 2) Il commento generale resta obbligatorio
      if (!reason) {
        if (errEl) { errEl.textContent = 'Inserire il commento generale prima di scaricare il PDF accertato.'; errEl.classList.remove('hidden'); }
        if (reasonSection) reasonSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        return;
      }
      if (errEl) errEl.classList.add('hidden');
      // Salva SEMPRE prima del PDF, così la colonna Accertato non è mai vuota
      saveAssessment();
      generatePdf(true);
    });
  }

  // ── Form submit ───────────────────────────────────────────────────────────

  form.addEventListener('submit', async function (e) {
    e.preventDefault();
    hideError();

    const validationError = validateForm();
    if (validationError) {
      showError(validationError);
      return;
    }

    const capWarn = getCapIfdWarning();
    if (capWarn) showWarning(capWarn);

    const payload = getFormPayload();
    showSpinner();
    setFormBusy(true);
    hideMap();
    hideAssessmentMode();

    try {
      const resp = await fetch('/v1/deduction/calculate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (resp.status === 422) {
        clearResults();
        const data = await resp.json();
        const detail = data.detail;
        let msg = 'Errore di validazione.';
        if (Array.isArray(detail) && detail.length > 0) {
          msg = detail.map(function (d) { return d.msg; }).join(' ');
        } else if (typeof detail === 'string') {
          msg = detail;
        }
        showError(msg);
        return;
      }

      if (!resp.ok) {
        clearResults();
        showError('Errore del server (' + resp.status + '). Riprovare più tardi.');
        return;
      }

      const data = await resp.json();
      renderResults(data);

    } catch (err) {
      clearResults();
      showError(err && err.message ? ('Errore: ' + err.message) : 'Impossibile contattare il server. Verificare la connessione.');
      return;
    } finally {
      setFormBusy(false);
    }

    // initMap è fuori dal try: un crash della mappa non cancella i risultati
    try { initMap(lastResponse); } catch (e) { /* mappa non disponibile */ }
  });

  btnReset.addEventListener('click', function () {
    form.reset();
    tomSelectHome.clear();
    tomSelectWork.clear();
    hideError();
    clearResults();
    hideAssessmentMode();
    updateTransportVisibility();
    updateMealVisibility();
    updateOtherExpensesVisibility();
    updateSecondaryVisibility();
    updateOtherExpensesMethod();
    updateSecondaryMethod();
    updateAccommodationVisibility();
    // Reset coniuge
    if (includeSpouseChk) includeSpouseChk.checked = false;
    if (spouseFields) spouseFields.classList.add('hidden');
    if (spSameHomeChk) spSameHomeChk.checked = true;
    if (spHomeFields) spHomeFields.classList.add('hidden');
  });
})();
