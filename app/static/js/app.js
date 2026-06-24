// DdC Trasferta — frontend entry point

(function () {
  'use strict';

  const form = document.getElementById('deduction-form');
  const transportSelect = document.getElementById('transport_mode');
  const distanceOverrideGroup = document.getElementById('distance-override-group');
  const mixedFields = document.getElementById('mixed-fields');
  const formError = document.getElementById('form-error');
  const btnReset = document.getElementById('btn-reset');

  function updateTransportVisibility() {
    const mode = transportSelect.value;
    const needsDistance = mode === 'private_car' || mode === 'motorcycle';
    const isMixed = mode === 'mixed';

    distanceOverrideGroup.classList.toggle('hidden', !needsDistance);
    mixedFields.classList.toggle('hidden', !isMixed);

    // Required only when visible
    const carMixed = document.getElementById('car_distance_km_mixed');
    const ptMixed = document.getElementById('public_transport_cost_mixed_chf');
    carMixed.required = false;
    ptMixed.required = false;
  }

  transportSelect.addEventListener('change', updateTransportVisibility);
  updateTransportVisibility();

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

    const homeCity = document.getElementById('home_city').value.trim();
    const homeNpa = document.getElementById('home_npa').value.trim();
    const homeCountry = document.getElementById('home_country').value.trim() || 'CH';
    const workCity = document.getElementById('work_city').value.trim();
    const workNpa = document.getElementById('work_npa').value.trim();
    const workCountry = document.getElementById('work_country').value.trim() || 'CH';

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

    if (mode === 'mixed') {
      const carKm = document.getElementById('car_distance_km_mixed').value;
      const ptCost = document.getElementById('public_transport_cost_mixed_chf').value;
      if (carKm) payload.car_distance_km_mixed = parseFloat(carKm);
      if (ptCost) payload.public_transport_cost_mixed_chf = parseFloat(ptCost);
    }

    return payload;
  }

  function validateForm() {
    const homeCity = document.getElementById('home_city').value.trim();
    const homeNpa = document.getElementById('home_npa').value.trim();
    const workCity = document.getElementById('work_city').value.trim();
    const workNpa = document.getElementById('work_npa').value.trim();

    if (!homeCity) return 'Inserire la città del domicilio.';
    if (!/^[0-9]{4}$/.test(homeNpa)) return 'Il NPA del domicilio deve essere di 4 cifre.';
    if (!workCity) return 'Inserire la città del luogo di lavoro.';
    if (!/^[0-9]{4}$/.test(workNpa)) return 'Il NPA del luogo di lavoro deve essere di 4 cifre.';

    const mode = transportSelect.value;
    if (mode === 'mixed') {
      const carKm = document.getElementById('car_distance_km_mixed').value;
      const ptCost = document.getElementById('public_transport_cost_mixed_chf').value;
      if (!carKm && !ptCost) {
        return 'Per il trasporto misto fornire almeno la distanza in auto o il costo mezzi pubblici.';
      }
    }

    return null;
  }

  form.addEventListener('submit', async function (e) {
    e.preventDefault();
    hideError();

    const validationError = validateForm();
    if (validationError) {
      showError(validationError);
      return;
    }

    const payload = getFormPayload();

    try {
      const resp = await fetch('/v1/deduction/calculate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (resp.status === 422) {
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
        showError('Errore del server (' + resp.status + '). Riprovare più tardi.');
        return;
      }

      // Risultati gestiti in storie successive
      const data = await resp.json();
      document.getElementById('results').textContent = JSON.stringify(data, null, 2);
      document.getElementById('results').classList.remove('hidden');

    } catch (err) {
      showError('Impossibile contattare il server. Verificare la connessione.');
    }
  });

  btnReset.addEventListener('click', function () {
    form.reset();
    hideError();
    document.getElementById('results').classList.add('hidden');
    updateTransportVisibility();
  });
})();
