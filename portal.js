'use strict';

(() => {
  const byId = (id) => document.getElementById(id);
  const form = byId('document-form');
  const input = byId('document');
  const phone = byId('phone');
  const codeForm = byId('verification-form');
  const codeInput = byId('code');
  const steps = [...document.querySelectorAll('.steps li')];
  const panels = [form, byId('verification'), byId('result'), byId('install')];
  const currency = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });
  // Cole aqui o link completo do aplicativo na Google Play.
  const PLAY_STORE_URL = '';
  let state = 0;

  function showUnavailable() {
    form.querySelector('.card-description').textContent =
      'As consultas estão temporariamente indisponíveis. Tente novamente mais tarde.';
    form.querySelectorAll('.field').forEach((field) => { field.hidden = true; });
    form.querySelectorAll('input, button').forEach((control) => { control.disabled = true; });
    byId('submit').textContent = 'Consulta indisponível';
  }

  async function configureMode() {
    try {
      const response = await fetch('/api/mode', { cache: 'no-store' });
      const config = await response.json();
      if (config.consultationAvailable === false) {
        showUnavailable();
        return;
      }
      if (!config.testMode) return;
      byId('submit').firstChild.textContent = 'Gerar código de teste ';
      const instructions = byId('test-instructions');
      instructions.textContent = `Modo de teste local: CPF ${config.testCpf} e telefone ${config.testPhone}. Nenhum SMS será enviado.`;
      instructions.hidden = false;
      if (!input.value.trim()) {
        input.value = config.testCpf;
        input.dispatchEvent(new Event('input'));
        input.defaultValue = input.value;
      }
      if (!phone.value.trim()) {
        phone.value = config.testPhone;
        phone.defaultValue = phone.value;
      }
    } catch {
      // O servidor informará o erro ao solicitar o código.
    }
  }

  function showStep(next) {
    state = next;
    panels.forEach((panel, index) => { panel.hidden = index !== next; });
    steps.forEach((step, index) => {
      if (index === next) step.setAttribute('aria-current', 'step');
      else step.removeAttribute('aria-current');
    });
  }

  function showError(id, message) {
    const error = byId(id);
    error.textContent = message;
    error.hidden = false;
  }

  function clearError(id) {
    const error = byId(id);
    error.textContent = '';
    error.hidden = true;
  }

  async function postJson(path, body) {
    const response = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      credentials: 'same-origin'
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Não foi possível concluir a solicitação.');
    return data;
  }

  function showResult(data) {
    byId('client-name').textContent = data.name;
    const companies = byId('client-companies');
    companies.replaceChildren();
    for (const company of data.companies) {
      const item = document.createElement('li');
      item.textContent = company;
      companies.appendChild(item);
    }
    byId('amount').textContent = currency.format(data.simulatedAmountCents / 100);
    showStep(2);
    byId('result-title').focus();
    byId('announcement').textContent = 'Cadastro encontrado. O saldo exibido é simulado.';
  }

  function configureStoreLink() {
    try {
      const url = new URL(PLAY_STORE_URL);
      if (url.protocol !== 'https:' || url.hostname !== 'play.google.com') return;
      byId('play-store-link').href = url.href;
      byId('play-store-link').hidden = false;
      byId('store-unavailable').hidden = true;
    } catch {
      // O link só aparece após configurar uma URL válida da Google Play.
    }
  }

  input.addEventListener('input', () => {
    const digits = input.value.replace(/\D/g, '').slice(0, 11);
    input.value = digits.replace(/(\d{3})(\d)/, '$1.$2')
      .replace(/(\d{3})(\d)/, '$1.$2')
      .replace(/(\d{3})(\d{1,2})$/, '$1-$2');
    clearError('document-error');
  });

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (state !== 0) return;
    clearError('document-error');
    const submit = byId('submit');
    submit.disabled = true;
    try {
      const data = await postJson('/api/request-code', { cpf: input.value, phone: phone.value });
      if (data.testCode) {
        byId('verification-title').textContent = 'Confirme o código de teste';
        byId('verification-help').textContent = data.message;
        byId('test-code').textContent = `Código de teste: ${data.testCode}`;
        byId('test-code').hidden = false;
      } else {
        byId('verification-title').textContent = 'Confirme o código';
        byId('verification-help').textContent = data.message;
        byId('test-code').hidden = true;
      }
      codeInput.value = '';
      showStep(1);
      byId('verification-title').focus();
    } catch (error) {
      showError('document-error', error.message);
    } finally {
      submit.disabled = false;
    }
  });

  codeForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (state !== 1) return;
    clearError('code-error');
    const verify = byId('verify');
    verify.disabled = true;
    try {
      const data = await postJson('/api/check-code', { code: codeInput.value });
      showResult(data);
    } catch (error) {
      showError('code-error', error.message);
    } finally {
      verify.disabled = false;
    }
  });

  byId('back-to-document').addEventListener('click', () => {
    showStep(0);
    input.focus();
  });
  byId('redeem').addEventListener('click', () => {
    showStep(3);
    byId('install-title').focus();
  });
  byId('back-to-result').addEventListener('click', () => {
    showStep(2);
    byId('result-title').focus();
  });
  byId('restart').addEventListener('click', () => {
    form.reset();
    codeForm.reset();
    clearError('document-error');
    clearError('code-error');
    byId('announcement').textContent = '';
    byId('client-name').textContent = '';
    byId('client-companies').replaceChildren();
    byId('amount').textContent = '';
    showStep(0);
    input.focus();
  });

  configureStoreLink();
  configureMode();
})();
