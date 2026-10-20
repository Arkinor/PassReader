// Password Manager v2.0 - Simplified Frontend

let passwords = [];
let encryptKey = '';

// ========== Ключ шифрования ==========

function getEncryptKey() {
    return encryptKey;
}

function setEncryptKey(key) {
    encryptKey = key || '';
    updateKeyStatus(!!key);
}

function updateKeyStatus(active) {
    const el = document.getElementById('keyStatus');
    if (active) {
        el.className = 'key-status active';
        el.innerHTML = '🔐 Ключ установлен';
    } else {
        el.className = 'key-status inactive';
        el.innerHTML = '🔓 Ключ не установлен';
    }
}

function openKeyModal() {
    document.getElementById('keyModal').classList.add('active');
    document.getElementById('modalKeyInput').focus();
}

function closeKeyModal() {
    document.getElementById('keyModal').classList.remove('active');
}

function toggleKeyVisibility(btn) {
    const input = document.getElementById('modalKeyInput');
    if (!btn) return;
    if (input.type === 'password') {
        input.type = 'text';
        btn.textContent = '🙈';
    } else {
        input.type = 'password';
        btn.textContent = '👁️';
    }
}

async function saveKey() {
    const key = document.getElementById('modalKeyInput').value.trim();
    if (!key) {
        showSaveNotification('⚠️ Введите мастер-ключ');
        document.getElementById('modalKeyInput').focus();
        return;
    }
    setEncryptKey(key);
    closeKeyModal();
    showSaveNotification('🔐 Ключ сохранён');
    loadPasswords();
}

// ========== Утилиты ==========

function showSaveNotification(text) {
    const n = document.getElementById('saveNotification');
    if (text) {
        n.textContent = text;
    } else {
        n.textContent = '✅ Сохранено';
    }
    n.style.display = 'block';
    setTimeout(() => { n.style.display = 'none'; }, 3000);
}

function copyToClipboard(text) {
    if (!text) return;
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(() => {
            showSaveNotification('📋 Скопировано');
        }).catch(() => {
            fallbackCopy(text);
        });
    } else {
        fallbackCopy(text);
    }
}

function fallbackCopy(text) {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.left = '-9999px';
    document.body.appendChild(ta);
    ta.select();
    try {
        document.execCommand('copy');
        showSaveNotification('📋 Скопировано');
    } catch (e) {
        // ignore
    }
    document.body.removeChild(ta);
}

function escapeHtml(text) {
    if (!text) return '';
    return String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#x27;');
}

function passwordField(value, id) {
    if (!value) {
        return '<span class="no-auth">—</span>';
    }
    const escaped = escapeHtml(value);
    return `
        <div class="password-field">
            <input type="password" id="${id}" class="password-input" value="${escaped}" readonly>
            <button type="button" class="field-btn" onclick="togglePassword(this)" title="Показать/скрыть" aria-label="Показать или скрыть пароль">👁️</button>
            <button type="button" class="field-btn field-copy" data-copy-source="${id}" onclick="copyFromSource(this)" title="Скопировать" aria-label="Скопировать пароль">📋</button>
        </div>
    `;
}

function copyFromSource(btn) {
    const sourceId = btn.dataset.copySource;
    if (sourceId) {
        const input = document.getElementById(sourceId);
        if (input) {
            const wasPassword = input.type === 'password';
            if (wasPassword) input.type = 'text';
            copyToClipboard(input.value);
            if (wasPassword) input.type = 'password';
            return;
        }
    }
    const text = btn.dataset.copyText || '';
    if (text) copyToClipboard(text);
}

function togglePassword(btn) {
    const inp = btn.previousElementSibling;
    if (inp.type === 'password') {
        inp.type = 'text';
        btn.textContent = '🙈';
    } else {
        inp.type = 'password';
        btn.textContent = '👁️';
    }
}

// ========== Менеджер паролей ==========

async function loadPasswords() {
    const key = getEncryptKey();
    if (!key) {
        // Без ключа сервер вернёт только шифротекст — просим ключ сразу.
        openKeyModal();
        return;
    }

    const refreshBtn = document.getElementById('refreshPasswordsBtn');
    const originalText = refreshBtn ? refreshBtn.innerHTML : '';
    if (refreshBtn) {
        refreshBtn.innerHTML = '⏳ Загрузка...';
        refreshBtn.disabled = true;
    }

    try {
        const headers = { 'X-Encrypt-Key': key };

        const resp = await fetch('/api/passwords', {
            headers,
            cache: 'no-cache'
        });

        if (!resp.ok) {
            let detail = '';
            try {
                const errorBody = await resp.json();
                detail = errorBody && errorBody.detail ? String(errorBody.detail) : '';
            } catch (e) {
                // тело ответа не JSON — используем статус
            }
            if (resp.status === 400) {
                throw new Error('Неверный ключ шифрования или повреждённые данные');
            }
            throw new Error(detail || ('Ошибка сервера: ' + resp.status));
        }

        const data = await resp.json();
        passwords = Array.isArray(data) ? data : [];

        updateGroupsDatalist();
        renderPasswords();
    } catch (e) {
        console.error('Error loading passwords:', e);
        passwords = [];
        const tbody = document.getElementById('passwordsBody');
        if (tbody) {
            tbody.innerHTML = `<tr><td colspan="7" class="empty-state error">❌ ${escapeHtml(e.message || 'Ошибка загрузки паролей')}</td></tr>`;
        }
        const noResults = document.getElementById('noResults');
        if (noResults) noResults.hidden = true;
        updateGroupsDatalist();
    } finally {
        if (refreshBtn) {
            refreshBtn.innerHTML = originalText;
            refreshBtn.disabled = false;
        }
    }
}

function renderPasswords() {
    const tbody = document.getElementById('passwordsBody');
    if (!tbody) return;

    if (passwords.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="empty-state">Нет записей. Добавьте пароль.</td></tr>';
        const noResults = document.getElementById('noResults');
        if (noResults) noResults.hidden = true;
        return;
    }

    let html = '';
    passwords.forEach((p, index) => {
        const name = escapeHtml(p.name || '');
        const login = escapeHtml(p.login || '');
        const email = escapeHtml(p.email || '');
        const password = p.password || '';
        const comment = escapeHtml(p.comment || '');
        const groupRaw = p.group || '';
        const group = escapeHtml(groupRaw);

        const copyBtn = (text) => text ? `<button type="button" class="field-btn field-copy" data-copy-text="${escapeHtml(text)}" onclick="copyFromSource(this)" title="Скопировать" aria-label="Скопировать значение">📋</button>` : '';

        html += `
            <tr data-index="${index}">
                <td data-col="name"><div class="clickable-cell" title="${name}">${name}${copyBtn(p.name || '')}</div></td>
                <td data-col="login"><div class="clickable-cell" title="${login}">${login}${copyBtn(p.login || '')}</div></td>
                <td data-col="email"><div class="clickable-cell" title="${email}">${email || '<span class="no-auth">—</span>'}${copyBtn(p.email || '')}</div></td>
                <td data-col="password">${passwordField(password, 'pwd-pw-' + index)}</td>
                <td data-col="comment"><div class="clickable-cell" title="${comment}">${comment}${copyBtn(p.comment || '')}</div></td>
                <td data-col="group"><div class="clickable-cell" title="${group}">${group ? `<span class="group-name">${group}</span>` : '<span class="no-auth">—</span>'}${copyBtn(groupRaw)}</div></td>
                <td class="actions-cell" data-col="actions">
                    <button class="btn btn-sm btn-primary" onclick="editPassword(${index})" title="Редактировать" aria-label="Редактировать запись">✏️</button>
                    <button class="btn btn-sm btn-danger" onclick="deletePassword(${index})" title="Удалить" aria-label="Удалить запись">🗑️</button>
                </td>
            </tr>
        `;
    });

    tbody.innerHTML = html;
    applyPasswordFilter();
}

function applyPasswordFilter() {
    const searchInput = document.getElementById('passwordSearchInput');
    const query = searchInput ? searchInput.value.trim().toLowerCase() : '';
    const tbody = document.getElementById('passwordsBody');
    if (!tbody) return;

    const rows = tbody.querySelectorAll('tr[data-index]');
    let visibleCount = 0;

    rows.forEach(row => {
        if (!query) {
            row.style.display = '';
            visibleCount++;
            return;
        }
        let text = '';
        row.querySelectorAll('td:not(.actions-cell)').forEach(td => {
            text += ' ' + (td.textContent || '');
        });
        const matches = text.toLowerCase().includes(query);
        row.style.display = matches ? '' : 'none';
        if (matches) visibleCount++;
    });

    const noResults = document.getElementById('noResults');
    if (noResults) {
        noResults.hidden = !(query && rows.length > 0 && visibleCount === 0);
    }
}

// ========== Модальное окно паролей ==========

function openPasswordModal() {
    document.getElementById('passwordModal').classList.add('active');
    document.getElementById('passwordModalNameInput').focus();
}

function closePasswordModal() {
    document.getElementById('passwordModal').classList.remove('active');
}

function togglePasswordModalVisibility(btn) {
    const input = document.getElementById('passwordModalValueInput');
    if (!btn) return;
    if (input.type === 'password') {
        input.type = 'text';
        btn.textContent = '🙈';
    } else {
        input.type = 'password';
        btn.textContent = '👁️';
    }
}

function showPasswordForm() {
    document.getElementById('passwordModalEditIndex').value = '-1';
    document.getElementById('passwordModalTitle').textContent = '🔑 Новая запись';
    document.getElementById('passwordModalNameInput').value = '';
    document.getElementById('passwordModalLoginInput').value = '';
    document.getElementById('passwordModalValueInput').value = '';
    document.getElementById('passwordModalEmailInput').value = '';
    document.getElementById('passwordModalCommentInput').value = '';
    document.getElementById('passwordModalGroupInput').value = '';
    openPasswordModal();
}

function editPassword(i) {
    const p = passwords[i];
    if (!p) return;

    document.getElementById('passwordModalEditIndex').value = i;
    document.getElementById('passwordModalTitle').textContent = '✏️ Редактирование записи';
    document.getElementById('passwordModalNameInput').value = p.name || '';
    document.getElementById('passwordModalLoginInput').value = p.login || '';
    document.getElementById('passwordModalValueInput').value = p.password || '';
    document.getElementById('passwordModalEmailInput').value = p.email || '';
    document.getElementById('passwordModalCommentInput').value = p.comment || '';
    document.getElementById('passwordModalGroupInput').value = p.group || '';
    openPasswordModal();
}

async function savePasswordModal() {
    const key = getEncryptKey();
    if (!key) {
        alert('Установите ключ шифрования');
        openKeyModal();
        return;
    }

    const name = document.getElementById('passwordModalNameInput').value.trim();
    if (!name) {
        alert('Введите название записи');
        document.getElementById('passwordModalNameInput').focus();
        return;
    }

    const idx = parseInt(document.getElementById('passwordModalEditIndex').value);
    const group = document.getElementById('passwordModalGroupInput').value.trim();

    const newItem = {
        name: name,
        login: document.getElementById('passwordModalLoginInput').value.trim(),
        password: document.getElementById('passwordModalValueInput').value,
        email: document.getElementById('passwordModalEmailInput').value.trim(),
        comment: document.getElementById('passwordModalCommentInput').value.trim(),
        group: group,
        _index: idx >= 0 ? idx : null
    };

    try {
        const resp = await fetch('/api/passwords/item', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Encrypt-Key': key
            },
            body: JSON.stringify(newItem)
        });

        if (resp.ok) {
            showSaveNotification('✅ Запись сохранена');
            closePasswordModal();
            await loadPasswords();
        } else {
            let detail = '';
            try {
                const errorBody = await resp.json();
                detail = errorBody && errorBody.detail ? String(errorBody.detail) : '';
            } catch (e) {
                // ignore
            }
            alert('Ошибка сохранения: ' + (detail || resp.status));
        }
    } catch (error) {
        alert('Ошибка сети при сохранении: ' + error.message);
    }
}

// ========== Удаление пароля ==========

async function deletePassword(i) {
    const item = passwords[i];
    const label = item && item.name ? `«${item.name}»` : 'эту запись';
    if (!confirm(`Удалить ${label}?`)) return;

    const key = getEncryptKey();
    if (!key) {
        alert('Ключ шифрования не установлен');
        return;
    }

    try {
        const resp = await fetch('/api/passwords', {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
                'X-Encrypt-Key': key
            },
            body: JSON.stringify({ index: i })
        });

        if (resp.ok) {
            showSaveNotification('🗑️ Запись удалена');
            await loadPasswords();
        } else {
            alert('Ошибка удаления: ' + resp.status);
        }
    } catch (error) {
        alert('Ошибка сети при удалении: ' + error.message);
    }
}

// ========== Группы (datalist автодополнение) ==========

function updateGroupsDatalist() {
    const existing = new Set();
    passwords.forEach(p => {
        if (p.group && p.group.trim()) {
            existing.add(p.group.trim());
        }
    });
    const dl = document.getElementById('groupsList');
    if (!dl) return;
    dl.innerHTML = '';
    existing.forEach(name => {
        const opt = document.createElement('option');
        opt.value = name;
        dl.appendChild(opt);
    });
}

// ========== Экспорт/Импорт ==========

function setLoading(buttonId, isLoading, statusText = '') {
    try {
        const btn = document.getElementById(buttonId);
        const statusEl = document.getElementById('jsonLoadingStatus');
        if (btn) {
            if (isLoading) {
                btn.classList.add('loading');
                btn.disabled = true;
            } else {
                btn.classList.remove('loading');
                btn.disabled = false;
            }
        }
        if (statusEl) {
            if (isLoading) {
                statusEl.style.display = 'flex';
                const span = statusEl.querySelector('span');
                if (span && statusText) {
                    span.textContent = statusText;
                }
            } else {
                statusEl.style.display = 'none';
            }
        }
    } catch (e) {
        console.warn('Error in setLoading:', e);
    }
}

async function exportPasswordsJson() {
    const key = getEncryptKey();
    if (!key) {
        alert('Для выгрузки паролей в JSON необходим установленный ключ шифрования');
        openKeyModal();
        return;
    }

    setLoading('exportJsonBtn', true, 'Выгрузка паролей...');

    try {
        const headers = { 'X-Encrypt-Key': key };
        const resp = await fetch('/api/passwords', { headers });
        if (!resp.ok) {
            throw new Error(resp.status === 400 ? 'Неверный ключ шифрования' : 'Ошибка сервера: ' + resp.status);
        }
        const decryptedPasswords = await resp.json();

        const jsonData = JSON.stringify(decryptedPasswords, null, 2);
        const blob = new Blob([jsonData], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'passwords.json';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

        showSaveNotification('💾 Экспорт завершён');
    } catch (e) {
        console.error('Error exporting passwords:', e);
        alert('❌ Ошибка при выгрузке паролей');
    } finally {
        setLoading('exportJsonBtn', false);
    }
}

function importPasswordsJson() {
    const key = getEncryptKey();
    if (!key) {
        alert('Для загрузки паролей из JSON необходим установленный ключ шифрования');
        openKeyModal();
        return;
    }
    document.getElementById('importHelpModal').classList.add('active');
}

function closeImportHelpModal() {
    document.getElementById('importHelpModal').classList.remove('active');
}

function confirmImportJson() {
    closeImportHelpModal();
    const input = document.getElementById('importPasswordsFile');
    if (input) {
        input.click();
    }
}

async function handlePasswordsFileImport(input) {
    const key = getEncryptKey();
    if (!key) {
        alert('Для загрузки паролей из JSON необходим установленный ключ шифрования');
        openKeyModal();
        input.value = '';
        return;
    }

    const file = input.files[0];
    if (!file) {
        input.value = '';
        return;
    }

    setLoading('importJsonBtn', true, 'Импорт паролей...');

    try {
        const text = await file.text();
        if (!text.trim()) {
            throw new Error('Файл пуст');
        }

        let importedPasswords;
        try {
            importedPasswords = JSON.parse(text);
        } catch (parseError) {
            throw new Error('Некорректный JSON формат: ' + parseError.message);
        }

        if (!Array.isArray(importedPasswords)) {
            throw new Error('Файл должен содержать массив паролей');
        }

        if (!confirm(`Вы уверены, что хотите импортировать ${importedPasswords.length} записей паролей? Текущие данные будут заменены.`)) {
            input.value = '';
            setLoading('importJsonBtn', false);
            return;
        }

        const resp = await fetch('/api/passwords/import', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Encrypt-Key': key
            },
            body: JSON.stringify(importedPasswords)
        });

        if (resp.ok) {
            const result = await resp.json();
            await loadPasswords();
            showSaveNotification('✅ Импорт завершён');
            alert(`✅ Успешно импортировано ${result.count || importedPasswords.length} записей паролей`);
        } else {
            let detail = '';
            try {
                const errorBody = await resp.json();
                detail = errorBody && errorBody.detail ? String(errorBody.detail) : '';
            } catch (e) {
                // ignore
            }
            throw new Error(detail || 'Ошибка сервера при импорте');
        }
    } catch (e) {
        console.error('Error importing passwords:', e);
        alert('❌ Ошибка при импорте паролей: ' + e.message);
    } finally {
        input.value = '';
        setLoading('importJsonBtn', false);
    }
}

// ========== Инициализация ==========

document.addEventListener('DOMContentLoaded', () => {
    updateKeyStatus(!!getEncryptKey());
    loadPasswords();

    const searchInput = document.getElementById('passwordSearchInput');
    if (searchInput) {
        searchInput.addEventListener('input', applyPasswordFilter);
    }

    // Разворачиваем длинные значения по клику на ячейку.
    const passwordsBody = document.getElementById('passwordsBody');
    if (passwordsBody) {
        passwordsBody.addEventListener('click', e => {
            if (e.target.closest('button')) return;
            const cell = e.target.closest('.clickable-cell');
            if (cell) cell.classList.toggle('expanded');
        });
    }
});

// Обработчики для модального окна ключа
document.getElementById('modalKeyInput').addEventListener('keypress', e => {
    if (e.key === 'Enter') saveKey();
});

document.getElementById('keyModal').addEventListener('click', e => {
    if (e.target === e.currentTarget) closeKeyModal();
});

// Обработчики для модального окна пароля
document.getElementById('passwordModalNameInput').addEventListener('keypress', e => {
    if (e.key === 'Enter') savePasswordModal();
});

document.getElementById('passwordModal').addEventListener('click', e => {
    if (e.target === e.currentTarget) closePasswordModal();
});

document.getElementById('importHelpModal').addEventListener('click', e => {
    if (e.target === e.currentTarget) closeImportHelpModal();
});

// Глобальные функции для onclick обработчиков
window.saveKey = saveKey;
window.openKeyModal = openKeyModal;
window.closeKeyModal = closeKeyModal;
window.showSaveNotification = showSaveNotification;
window.toggleKeyVisibility = toggleKeyVisibility;
window.togglePassword = togglePassword;
window.showPasswordForm = showPasswordForm;
window.deletePassword = deletePassword;
window.editPassword = editPassword;
window.loadPasswords = loadPasswords;
window.openPasswordModal = openPasswordModal;
window.closePasswordModal = closePasswordModal;
window.togglePasswordModalVisibility = togglePasswordModalVisibility;
window.savePasswordModal = savePasswordModal;
window.exportPasswordsJson = exportPasswordsJson;
window.importPasswordsJson = importPasswordsJson;
window.confirmImportJson = confirmImportJson;
window.closeImportHelpModal = closeImportHelpModal;
window.handlePasswordsFileImport = handlePasswordsFileImport;
window.copyToClipboard = copyToClipboard;
window.copyFromSource = copyFromSource;
