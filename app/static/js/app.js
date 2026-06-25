// DdC Trasferta — frontend entry point

(function () {
  'use strict';

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
  const salaryGroup = document.getElementById('salary-group');

  const companyCarGroup = document.getElementById('company-car-group');
  const ptCostSection = document.getElementById('pt-cost-section');
  const arcobalenovFields = document.getElementById('arcobaleno-fields');
  const manualPtFields = document.getElementById('manual-pt-fields');
  const sbbLinkFields = document.getElementById('sbb-link-fields');

  const ARCOBALENO_2CL = { 1: 485, 2: 732, 3: 1074, 4: 1387, 5: 1691, 6: 1986, 7: 2157, 8: 2252 };
  const ARCOBALENO_1CL = { 1: 827, 2: 1245, 3: 1834, 4: 2366, 5: 2879, 6: 3382, 7: 3667, 8: 3829 };

  function makeTomSelectConfig() {
    return {
      valueField: 'name',
      labelField: 'name',
      searchField: 'name',
      create: true,
      placeholder: 'Cerca città…',
      load: function (query, callback) {
        if (query.length < 2) { callback([]); return; }
        fetch('/v1/locations/search?q=' + encodeURIComponent(query) + '&limit=10')
          .then(function (r) { return r.json(); })
          .then(callback)
          .catch(function () { callback([]); });
      },
    };
  }

  const tomSelectHome = new TomSelect('#home_city', makeTomSelectConfig());
  const tomSelectWork = new TomSelect('#work_city', makeTomSelectConfig());

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
    salaryGroup.classList.toggle('hidden', !includeOtherExpensesChk.checked);
    const salaryInput = document.getElementById('annual_net_salary_chf');
    salaryInput.required = includeOtherExpensesChk.checked;
  }

  transportSelect.addEventListener('change', updateTransportVisibility);
  includeMealsChk.addEventListener('change', updateMealVisibility);
  includeOtherExpensesChk.addEventListener('change', updateOtherExpensesVisibility);

  document.querySelectorAll('input[name=pt_cost_type]').forEach(function (radio) {
    radio.addEventListener('change', updatePtCostVisibility);
  });

  document.getElementById('arcobaleno_zones').addEventListener('change', updateArcobalenoCostPreview);
  document.getElementById('arcobaleno_class').addEventListener('change', updateArcobalenoCostPreview);

  updateTransportVisibility();
  updateMealVisibility();
  updateOtherExpensesVisibility();
  updatePtCostVisibility();
  updateArcobalenoCostPreview();

  // Tooltip: close on Escape
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      document.querySelectorAll('.tooltip-anchor').forEach(function (el) { el.blur(); });
    }
  });

  function showError(message) {
    formError.textContent = message;
    formError.classList.remove('hidden');
    formError.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  function hideError() {
    formError.classList.add('hidden');
    formError.textContent = '';
  }

  function getFormPayload() {
    const mode = transportSelect.value;
    const fiscalYear = parseInt(document.getElementById('fiscal_year').value, 10);
    const residencyType = document.getElementById('residency_type').value;
    const daysPerWeek = parseInt(document.getElementById('days_per_week').value, 10);
    const homeOfficeDays = parseInt(document.getElementById('home_office_days_per_week').value, 10);

    const homeCity = (tomSelectHome.getValue() || document.getElementById('home_city').value).trim();
    const homeNpa = document.getElementById('home_npa').value.trim();
    const homeCountry = document.getElementById('home_country').value || 'CH';
    const workCity = (tomSelectWork.getValue() || document.getElementById('work_city').value).trim();
    const workNpa = document.getElementById('work_npa').value.trim();
    const workCountry = document.getElementById('work_country').value || 'CH';

    const payload = {
      fiscal_year: fiscalYear,
      residency_type: residencyType,
      transport_mode: mode,
      home_address: {
        city: homeCity,
        postal_code: homeNpa,
        country: homeCountry,
      },
      work_address: {
        city: workCity,
        postal_code: workNpa,
        country: workCountry,
      },
      days_per_week: daysPerWeek,
      home_office_days_per_week: homeOfficeDays,
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
    }

    // Campi Lohnausweis
    payload.employer_pays_transport = document.getElementById('employer_pays_transport').checked;
    payload.employer_has_cafeteria = document.getElementById('employer_has_cafeteria').checked;

    if (mode === 'private_car') {
      const carMonthly = document.getElementById('company_car_monthly_chf').value;
      if (carMonthly) payload.company_car_monthly_chf = parseFloat(carMonthly);
    }

    return payload;
  }

  function validateNpa(npa, country, label) {
    if (country === 'CH' && !/^[0-9]{4}$/.test(npa)) return 'Il NPA CH ' + label + ' deve essere di 4 cifre.';
    if (country === 'IT' && !/^[0-9]{5}$/.test(npa)) return 'Il CAP italiano ' + label + ' deve essere di 5 cifre.';
    if (country !== 'CH' && country !== 'IT' && !/^[0-9A-Z -]{3,10}$/.test(npa)) return 'NPA ' + label + ' non valido.';
    return null;
  }

  function validateForm() {
    const homeCity = (tomSelectHome.getValue() || document.getElementById('home_city').value).trim();
    const homeNpa = document.getElementById('home_npa').value.trim();
    const homeCountry = document.getElementById('home_country').value || 'CH';
    const workCity = (tomSelectWork.getValue() || document.getElementById('work_city').value).trim();
    const workNpa = document.getElementById('work_npa').value.trim();
    const workCountry = document.getElementById('work_country').value || 'CH';

    if (!homeCity) return 'Inserire la città del domicilio.';
    const homeNpaErr = validateNpa(homeNpa, homeCountry, 'del domicilio');
    if (homeNpaErr) return homeNpaErr;
    if (!workCity) return 'Inserire la città del luogo di lavoro.';
    const workNpaErr = validateNpa(workNpa, workCountry, 'del luogo di lavoro');
    if (workNpaErr) return workNpaErr;

    const mode = transportSelect.value;
    if (mode === 'public_transport') {
      const ptRadio = document.querySelector('input[name=pt_cost_type]:checked');
      const ptVal = ptRadio ? ptRadio.value : 'arcobaleno';
      if (ptVal === 'manuale') {
        const c = document.getElementById('annual_public_transport_cost_chf').value;
        if (!c || parseFloat(c) <= 0) return 'Inserire il costo abbonamento annuale in CHF.';
      } else if (ptVal === 'sbb-link') {
        const c = document.getElementById('annual_public_transport_cost_chf_sbb').value;
        if (!c || parseFloat(c) <= 0) return 'Inserire il costo abbonamento trovato su SBB.ch.';
      }
    }
    if (mode === 'mixed') {
      const carKm = document.getElementById('car_distance_km_mixed').value;
      const ptCost = document.getElementById('public_transport_cost_mixed_chf').value;
      if (!carKm && !ptCost) {
        return 'Per il trasporto misto fornire almeno la distanza in auto o il costo mezzi pubblici.';
      }
    }

    if (includeOtherExpensesChk.checked) {
      const salary = document.getElementById('annual_net_salary_chf').value;
      if (!salary || parseFloat(salary) <= 0) {
        return 'Inserire il salario netto annuo per calcolare le altre spese professionali.';
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
    return "CHF " + amount.toLocaleString('de-CH', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  }

  function showSpinner() {
    resultsDiv.innerHTML =
      '<div class="spinner-wrapper">' +
        '<div class="spinner"></div>' +
        '<p class="spinner-label">Calcolo in corso…</p>' +
      '</div>';
    resultsDiv.classList.remove('hidden');
  }

  function clearResults() {
    resultsDiv.innerHTML = '';
    resultsDiv.classList.add('hidden');
  }

  // ── Results renderer ──────────────────────────────────────────────────────

  function buildDeductionTable(level) {
    const transport = level.transport_deduction;
    let rows = '';

    transport.lines.forEach(function (line) {
      const capMark = line.capped ? ' <span class="cap-icon" title="Tetto massimo applicato">⚠</span>' : '';
      const capRow = (line.capped && line.cap_amount_chf != null)
        ? '<tr><td colspan="3" class="cap-warning">Tetto massimo applicato: ' + formatChf(line.cap_amount_chf) + '</td></tr>'
        : '';

      rows +=
        '<tr>' +
          '<td>' + escapeHtml(line.label) + capMark +
            '<span class="legal-ref">' + escapeHtml(line.legal_reference) + '</span></td>' +
          '<td class="amount">' + formatChf(line.amount_chf) + '</td>' +
          '<td class="basis">' + escapeHtml(line.basis) + '</td>' +
        '</tr>' + capRow;
    });

    if (level.meals_deduction_chf != null) {
      rows +=
        '<tr>' +
          '<td>Pasti fuori domicilio</td>' +
          '<td class="amount">' + formatChf(level.meals_deduction_chf) + '</td>' +
          '<td class="basis">—</td>' +
        '</tr>';
    }

    if (level.other_expenses_deduction_chf != null) {
      rows +=
        '<tr>' +
          '<td>Altre spese professionali</td>' +
          '<td class="amount">' + formatChf(level.other_expenses_deduction_chf) + '</td>' +
          '<td class="basis">3% salario netto</td>' +
        '</tr>';
    }

    return (
      '<table class="deduction-table">' +
        '<thead><tr><th>Voce</th><th>Importo</th><th>Base di calcolo</th></tr></thead>' +
        '<tbody>' + rows + '</tbody>' +
      '</table>'
    );
  }

  function buildColumn(level, badgeClass, badgeLabel) {
    return (
      '<div class="results-column">' +
        '<div class="results-column-header">' +
          '<span class="' + badgeClass + '">' + badgeLabel + '</span>' +
        '</div>' +
        '<div class="total-amount">' + formatChf(level.total_deduction_chf) + '</div>' +
        buildDeductionTable(level) +
      '</div>'
    );
  }

  function renderResults(data) {
    // Header
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
      distHtml = ' &mdash; Distanza: <strong>' + data.distance_km.toFixed(1) + ' km</strong>';
    }

    // Errors[] in body (separate from HTTP errors)
    let errHtml = '';
    if (data.errors && data.errors.length > 0) {
      errHtml = '<div class="alert-danger">' +
        data.errors.map(function (e) { return escapeHtml(e); }).join('<br>') +
        '</div>';
    }

    // Warnings + notes from both levels
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

    const html =
      '<div class="results-header">' +
        '<strong>Anno fiscale ' + data.fiscal_year + '</strong>' +
        ' &mdash; Calcolato il ' + dateStr + ' alle ' + timeStr +
        distHtml + geoHtml +
      '</div>' +
      errHtml +
      '<div class="results-columns">' +
        buildColumn(data.cantonal_TI, 'badge-cantonal', 'Cantonale TI (IC)') +
        buildColumn(data.federal_IFD, 'badge-federal', 'Federale IFD') +
      '</div>' +
      warnHtml +
      '<div class="print-link">' +
        '<a href="#" onclick="window.print(); return false;">🖨 Stampa / Salva PDF</a>' +
      '</div>';

    resultsDiv.innerHTML = html;
    resultsDiv.classList.remove('hidden');
    resultsDiv.scrollIntoView({ behavior: 'smooth', block: 'start' });
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

    const payload = getFormPayload();
    showSpinner();

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
      showError('Impossibile contattare il server. Verificare la connessione.');
    }
  });

  btnReset.addEventListener('click', function () {
    form.reset();
    tomSelectHome.clear();
    tomSelectWork.clear();
    hideError();
    clearResults();
    updateTransportVisibility();
    updateMealVisibility();
    updateOtherExpensesVisibility();
  });
})();
