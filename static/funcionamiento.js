const API_URL = window.location.origin;

// Variables globales
let animesCache = [];
let currentPage = 1;
let totalPages = 1;
let currentFilter = 'all';
const itemsPerPage = 24;
let selectedTags = [];
let animeById = {};
let allAvailableTags = new Set();

// Cache global para todos los animes (se carga una sola vez)
let allAnimesCache = null;
let allAnimesCacheLoaded = false;
let isTagSearchActive = false;

// ========================================
// SISTEMA DE AUTENTICACIÓN Y PAGOS
// ========================================

class AnimeSearchAPI {
    constructor() {
        this.baseURL = `${API_URL}/api`;
        this.apiKey = localStorage.getItem('anime_api_key');
    }

    async register(email = null) {
        try {
            const response = await fetch(`${this.baseURL}/auth/register`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email })
            });
            return await response.json();
        } catch (error) {
            console.error('Error:', error);
            return null;
        }
    }

    async checkStatus() {
        if (!this.apiKey) {
            // No hay API key - usuario anónimo
            return null;
        }

        try {
            const response = await fetch(`${this.baseURL}/auth/status`, {
                headers: { 'X-API-Key': this.apiKey }
            });

            if (!response.ok) {
                // Si la API key es inválida (401, 403), limpiarla
                if (response.status === 401 || response.status === 403) {
                    console.warn('API key inválida, limpiando localStorage...');
                    localStorage.removeItem('anime_api_key');
                    this.apiKey = null;
                }
                return null;
            }

            return await response.json();
        } catch (error) {
            console.error('Error al verificar estado:', error);
            return null;
        }
    }

    async loginPassword(email, password) {
        const response = await fetch(`${this.baseURL}/auth/login-password`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });
        const data = await response.json();
        if (data.api_key) {
            this.apiKey = data.api_key;
            localStorage.setItem('anime_api_key', data.api_key);
        }
        return data;
    }

    async registerPassword(email, password) {
        const response = await fetch(`${this.baseURL}/auth/register-password`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });
        const data = await response.json();
        if (data.api_key) {
            this.apiKey = data.api_key;
            localStorage.setItem('anime_api_key', data.api_key);
        }
        return data;
    }

    async search(query, topK = 18) {
        const headers = {
            'Content-Type': 'application/json'
        };

        // Solo agregar API key si existe
        if (this.apiKey) {
            headers['X-API-Key'] = this.apiKey;
        }

        const response = await fetch(`${this.baseURL}/search`, {
            method: 'POST',
            headers: headers,
            body: JSON.stringify({ query, top_k: topK })
        });

        if (response.status === 429) {
            const data = await response.json();

            // Si la API key es inválida y se detecta en el mensaje de error 429
            if (data.invalid_api_key) {
                console.warn('API key inválida detectada, limpiando localStorage...');
                localStorage.removeItem('anime_api_key');
                this.apiKey = null;
            }

            this.showUpgradeModal(data);
            throw new Error(data.error);
        }

        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.error || 'Error en la búsqueda');
        }

        return await response.json();
    }

    showPayPalLoadingOverlay() {
        // Crear overlay inmediatamente
        const overlay = document.createElement('div');
        overlay.id = 'paypal-loading-overlay';
        overlay.className = 'payment-loading-overlay';
        overlay.innerHTML = `
            <div class="payment-loading-content">
                <div class="spinner"></div>
                <p>Redirigiendo a PayPal...</p>
                <small>Por favor espera un momento</small>
            </div>
        `;
        document.body.appendChild(overlay);
    }

    removePayPalLoadingOverlay() {
        const overlay = document.getElementById('paypal-loading-overlay');
        if (overlay) {
            overlay.remove();
        }
    }

    async createPayPalOrder() {
        // Mostrar overlay INMEDIATAMENTE antes de cualquier otra cosa
        this.showPayPalLoadingOverlay();

        if (!this.apiKey) await this.checkStatus();

        try {
            const response = await fetch(`${this.baseURL}/payment/create-order`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ api_key: this.apiKey })
            });

            const data = await response.json();

            if (data.approval_url) {
                localStorage.setItem('paypal_order_id', data.order_id);
                // No removemos el overlay aquí porque la redirección es inmediata
                window.location.href = data.approval_url;
            } else {
                this.removePayPalLoadingOverlay();
                alert('Error: No se pudo obtener la URL de PayPal');
            }
            return data;
        } catch (error) {
            console.error('Error al crear orden PayPal:', error);
            this.removePayPalLoadingOverlay();
            alert('Error al conectar con PayPal. Por favor intenta de nuevo.');
            throw error;
        }
    }

    async capturePayPalOrder(orderId) {
        try {
            const response = await fetch(`${this.baseURL}/payment/capture-order`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ order_id: orderId })
            });
            return await response.json();
        } catch (error) {
            console.error('Error al capturar pago:', error);
            throw error;
        }
    }

    showUpgradeModal(limitData) {
        const modal = document.createElement('div');
        modal.id = 'upgrade-modal';

        // Verificar si es usuario anónimo
        const isAnonymous = limitData.is_anonymous || limitData.require_register;

        modal.innerHTML = `
            <div class="modal-overlay">
                <div class="modal-content">
                    <h2>🚀 ${isAnonymous ? 'Búsquedas gratuitas agotadas' : 'Límite de búsquedas alcanzado'}</h2>
                    <p>Has usado <strong>${limitData.used}</strong> de <strong>${limitData.limit}</strong> búsquedas${isAnonymous ? '' : ' diarias'}.</p>
                    
                    ${isAnonymous ? `
                        <div class="upgrade-offer">
                            <h3>💎 ¡Obtén Premium!</h3>
                            <p class="info-text">Para comprar Premium, primero necesitas crear una cuenta.</p>
                            <ul>
                                <li>✅ 1,000 búsquedas diarias</li>
                                <li>✅ Acceso prioritario</li>
                                <li>✅ Sin anuncios</li>
                                <li>✅ Soporte premium</li>
                            </ul>
                            <p class="price">Solo $9.99/mes</p>
                            <button id="register-btn-modal" class="btn-premium">
                                📝 Registrarme para Comprar
                            </button>
                        </div>
                    ` : !limitData.is_premium ? `
                        <div class="upgrade-offer">
                            <h3>💎 Actualiza a Premium</h3>
                            <ul>
                                <li>✅ 1,000 búsquedas diarias</li>
                                <li>✅ Acceso prioritario</li>
                                <li>✅ Sin anuncios</li>
                                <li>✅ Soporte premium</li>
                            </ul>
                            <p class="price">Solo $9.99/mes</p>
                            <button id="upgrade-btn-modal" class="btn-premium">
                                💳 Pagar con PayPal
                            </button>
                        </div>
                    ` : `
                        <p>Has alcanzado tu límite premium. Vuelve mañana para continuar.</p>
                    `}
                    
                    <button id="close-modal-btn" class="btn-secondary">Cerrar</button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

        document.getElementById('close-modal-btn')?.addEventListener('click', () => {
            modal.remove();
        });

        document.getElementById('register-btn-modal')?.addEventListener('click', () => {
            modal.remove();
            openLoginModal();
        });

        document.getElementById('upgrade-btn-modal')?.addEventListener('click', () => {
            modal.remove();
            this.createPayPalOrder();
        });
    }
}

// Instancia global de la API
const searchAPI = new AnimeSearchAPI();

// ========================================
// ADMINISTRADOR DE UI PARA ESTADO DE BÚSQUEDAS
// ========================================

class SearchUIManager {
    constructor(api) {
        this.api = api;
        this.statusBar = null;
    }

    async init() {
        this.createStatusBar();
        await this.updateStatus();
        this.checkPaymentReturn();
        setInterval(() => this.updateStatus(), 60000);
    }

    async checkPaymentReturn() {
        const urlParams = new URLSearchParams(window.location.search);
        const token = urlParams.get('token');

        if (token) {
            const orderId = localStorage.getItem('paypal_order_id');

            if (orderId) {
                try {
                    this.showProcessingMessage();
                    const result = await this.api.capturePayPalOrder(orderId);

                    if (result.status === 'success') {
                        localStorage.removeItem('paypal_order_id');
                        this.showSuccessMessage();
                        await this.updateStatus();
                        window.history.replaceState({}, document.title, window.location.pathname);
                    } else {
                        this.showErrorMessage('Error procesando el pago');
                    }
                } catch (error) {
                    console.error('Error capturando pago:', error);
                    this.showErrorMessage('Error al procesar el pago');
                }
            }
        }
    }

    showProcessingMessage() {
        const msg = document.createElement('div');
        msg.className = 'payment-message processing';
        msg.innerHTML = `
            <div class="message-content">
                <div class="spinner"></div>
                <p>Procesando tu pago...</p>
            </div>
        `;
        document.body.appendChild(msg);
    }

    showSuccessMessage() {
        const processing = document.querySelector('.payment-message.processing');
        if (processing) processing.remove();

        const msg = document.createElement('div');
        msg.className = 'payment-message success';
        msg.innerHTML = `
            <div class="message-content">
                <div class="success-icon">✓</div>
                <h3>¡Pago exitoso!</h3>
                <p>Ahora tienes acceso Premium con 1,000 búsquedas diarias</p>
                <button onclick="this.parentElement.parentElement.remove()">Continuar</button>
            </div>
        `;
        document.body.appendChild(msg);
        setTimeout(() => msg.remove(), 5000);
    }

    showErrorMessage(message) {
        const processing = document.querySelector('.payment-message.processing');
        if (processing) processing.remove();

        const msg = document.createElement('div');
        msg.className = 'payment-message error';
        msg.innerHTML = `
            <div class="message-content">
                <div class="error-icon">✕</div>
                <h3>Error en el pago</h3>
                <p>${message}</p>
                <button onclick="this.parentElement.parentElement.remove()">Cerrar</button>
            </div>
        `;
        document.body.appendChild(msg);
    }

    createStatusBar() {
        const statusBar = document.createElement('div');
        statusBar.id = 'search-status-bar';
        statusBar.innerHTML = `
            <div class="status-container">
                <span id="search-count">Cargando...</span>
                <button id="upgrade-button" class="btn-upgrade" style="display:none;">
                    ⭐ Actualizar a Premium
                </button>
            </div>
        `;

        const searchContainer = document.querySelector('.search-container');
        if (searchContainer) {
            searchContainer.parentNode.insertBefore(statusBar, searchContainer.nextSibling);
        } else {
            document.body.insertBefore(statusBar, document.body.firstChild);
        }

        this.statusBar = statusBar;

        document.getElementById('upgrade-button')?.addEventListener('click', () => {
            this.api.createPayPalOrder();
        });
    }

    async updateStatus() {
        try {
            const status = await this.api.checkStatus();

            const countSpan = document.getElementById('search-count');
            const upgradeBtn = document.getElementById('upgrade-button');
            const statusContainer = document.querySelector('.status-container');
            const loginBtn = document.getElementById('loginBtn');
            const logoutBtn = document.getElementById('logoutBtn');

            if (!countSpan || !upgradeBtn || !statusContainer) return;

            // Usuario anónimo (sin API key o sin status)
            if (!status) {
                // Mostrar botón de login, ocultar logout
                if (loginBtn) loginBtn.style.display = 'block';
                if (logoutBtn) logoutBtn.style.display = 'none';

                // Obtener datos de la última búsqueda si existen
                const lastSearchData = window.lastSearchData;
                if (lastSearchData && lastSearchData.is_anonymous) {
                    const remaining = lastSearchData.searches_remaining;
                    countSpan.innerHTML = `
                        🎁 <strong>Modo Gratuito</strong> - 
                        Búsquedas restantes: <strong>${remaining}</strong>/10
                    `;

                    if (remaining <= 3) {
                        upgradeBtn.textContent = '✨ Registrarme';
                        upgradeBtn.style.display = 'inline-block';
                        upgradeBtn.onclick = () => openLoginModal();
                        statusContainer.classList.add('low-searches');
                    } else {
                        upgradeBtn.style.display = 'none';
                        statusContainer.classList.remove('low-searches');
                    }
                } else {
                    countSpan.innerHTML = `
                        🎁 <strong>Modo Gratuito</strong> - 
                        10 búsquedas sin registro
                    `;
                    upgradeBtn.style.display = 'none';
                    statusContainer.classList.remove('low-searches');
                }
                return;
            }

            // Usuario registrado - mostrar botón de logout, ocultar login
            if (loginBtn) loginBtn.style.display = 'none';
            if (logoutBtn) logoutBtn.style.display = 'block';

            if (status.is_premium) {
                countSpan.innerHTML = `
                    💎 <strong>Premium</strong> - 
                    Searches: <strong>${status.remaining}</strong>/${status.daily_limit}
                `;
                upgradeBtn.style.display = 'none';
                statusContainer.classList.remove('low-searches');
            } else {
                countSpan.innerHTML = `
                    Resulting searches: <strong>${status.remaining}</strong>/${status.daily_limit}
                `;

                if (status.remaining <= 3) {
                    upgradeBtn.textContent = '⭐ Actualizar a Premium';
                    upgradeBtn.style.display = 'inline-block';
                    upgradeBtn.onclick = () => this.api.createPayPalOrder();
                    statusContainer.classList.add('low-searches');
                } else {
                    upgradeBtn.style.display = 'none';
                    statusContainer.classList.remove('low-searches');
                }
            }
        } catch (error) {
            console.error('Error al actualizar estado:', error);
        }
    }
}

const uiManager = new SearchUIManager(searchAPI);

// ========================================
// SISTEMA DE TAGS (MANTENIDO)
// ========================================

function inicializarTags(animes) {
    allAvailableTags.clear();
    animes.forEach(anime => {
        if (anime.tags && Array.isArray(anime.tags)) {
            anime.tags.forEach(tag => allAvailableTags.add(tag.toLowerCase()));
        }
        if (anime.genres && Array.isArray(anime.genres)) {
            anime.genres.forEach(genre => allAvailableTags.add(genre.toLowerCase()));
        }
    });
    mostrarTagsDisponibles();
}

function mostrarTagsDisponibles() {
    const container = document.getElementById('tagsContainer');
    if (!container) return;

    const tagsArray = Array.from(allAvailableTags).sort();

    container.innerHTML = tagsArray.map(tag => `
        <button class="tag-chip ${selectedTags.includes(tag) ? 'tag-selected' : ''}" 
                onclick="toggleTag('${tag}')"
                data-tag="${tag}">
            ${tag}
        </button>
    `).join('');
}

function toggleTag(tag) {
    const index = selectedTags.indexOf(tag);

    if (index > -1) {
        selectedTags.splice(index, 1);
    } else {
        selectedTags.push(tag);
    }

    actualizarTagsSeleccionados();

    if (selectedTags.length > 0) {
        buscarPorTags(); // Ahora es async pero no necesitamos await aquí
    } else {
        resetearVista();
        cargarTendencias(null, 'all');
    }
}

function actualizarTagsSeleccionados() {
    const container = document.getElementById('selectedTagsContainer');
    if (!container) return;

    if (selectedTags.length === 0) {
        container.style.display = 'none';
        return;
    }

    container.style.display = 'flex';
    container.innerHTML = `
        <span class="selected-tags-label">Filtrando por:</span>
        ${selectedTags.map(tag => `
            <span class="selected-tag">
                ${tag}
                <button onclick="toggleTag('${tag}')" class="remove-tag">×</button>
            </span>
        `).join('')}
        <button onclick="limpiarTags()" class="clear-tags-btn">Limpiar todo</button>
    `;

    mostrarTagsDisponibles();
}

function limpiarTags() {
    selectedTags = [];
    actualizarTagsSeleccionados();
    resetearVista();
    cargarTendencias(null, 'all');
}

async function buscarPorTags() {
    if (selectedTags.length === 0) {
        return [];
    }

    isTagSearchActive = true;

    // OPTIMIZACIÓN: Usar cache en lugar de cargar de nuevo
    try {
        // Cargar cache si no existe
        if (!allAnimesCacheLoaded) {
            const response = await fetch(`${API_URL}/api/animes?per_page=99999`);
            const data = await response.json();
            allAnimesCache = data.animes || [];
            allAnimesCacheLoaded = true;
        }
        const todosAnimes = allAnimesCache;

        // Filtrar los animes basándose en los tags seleccionados
        const resultados = todosAnimes.filter(anime => {
            const animeTags = [];
            if (anime.tags && Array.isArray(anime.tags)) {
                animeTags.push(...anime.tags.map(t => t.toLowerCase()));
            }
            if (anime.genres && Array.isArray(anime.genres)) {
                animeTags.push(...anime.genres.map(g => g.toLowerCase()));
            }

            return selectedTags.every(selectedTag =>
                animeTags.some(animeTag => animeTag.includes(selectedTag))
            );
        });

        // Actualizar el cache con TODOS los animes, no solo los filtrados
        animesCache = todosAnimes;
        animeById = {};
        todosAnimes.forEach(a => { animeById[a.id] = a; });
        inicializarTags(todosAnimes);

        mostrarResultadosTags(resultados);
        return resultados;
    } catch (error) {
        console.error('Error al cargar animes para filtrar:', error);
        return [];
    }
}

function mostrarResultadosTags(animes) {
    document.getElementById('loading').style.display = 'none';
    document.getElementById('trendingSection').style.display = 'none';
    document.getElementById('emptyState').style.display = 'none';
    document.getElementById('resultsSection').style.display = 'block';

    document.getElementById('resultsTitle').textContent = 'Resultados por Tags';
    document.getElementById('resultsCount').textContent = `${animes.length} anime${animes.length !== 1 ? 's' : ''} encontrado${animes.length !== 1 ? 's' : ''}`;

    animesCache = animes;
    mostrarResultados(animes, 'results');
}

function agregarTagDesdeInput() {
    const input = document.getElementById('tagInput');
    if (!input) return;

    const tag = input.value.trim().toLowerCase();

    if (tag && !selectedTags.includes(tag)) {
        selectedTags.push(tag);
        input.value = '';
        actualizarTagsSeleccionados();
        buscarPorTags();
    }
}

function toggleTagsPanel() {
    const panel = document.getElementById('tagsPanel');
    if (!panel) return;

    const isVisible = panel.style.display === 'block';
    panel.style.display = isVisible ? 'none' : 'block';
}

// ========================================
// BÚSQUEDA SEMÁNTICA (ACTUALIZADA CON API)
// ========================================

async function buscar() {
    selectedTags = [];
    actualizarTagsSeleccionados();
    isTagSearchActive = false;

    const query = document.getElementById('searchInput').value.trim();
    const MAX_CHARS = 155;

    if (query.length > MAX_CHARS) {
        alert(`La descripción es demasiado larga. Por favor, limítala a un máximo de ${MAX_CHARS} caracteres para realizar la búsqueda.`);
        return;
    }

    if (!query) {
        resetearVista();
        cargarTendencias(null, 'all');
        return;
    }

    document.getElementById('loading').style.display = 'block';
    document.getElementById('resultsSection').style.display = 'none';
    document.getElementById('trendingSection').style.display = 'none';
    document.getElementById('emptyState').style.display = 'none';

    try {
        const data = await searchAPI.search(query, 18);

        // Guardar datos de la búsqueda para actualizar el estado
        window.lastSearchData = data;

        await uiManager.updateStatus();

        animesCache = data.results || [];
        animeById = {};
        animesCache.forEach(a => { animeById[a.id] = a; });
        console.log("✅ animeById cargado:", Object.keys(animeById).length);

        document.getElementById('loading').style.display = 'none';

        if (animesCache.length === 0) {
            document.getElementById('emptyState').style.display = 'block';
        } else {
            document.getElementById('resultsSection').style.display = 'block';
            document.getElementById('resultsTitle').textContent = 'Resultados de Búsqueda';
            document.getElementById('resultsCount').textContent = `${animesCache.length} anime encontrado${animesCache.length !== 1 ? 's' : ''}`;
            mostrarResultados(animesCache, 'results');
            inicializarTags(animesCache);
        }
    } catch (error) {
        console.error('Error:', error);
        document.getElementById('loading').style.display = 'none';
        let userMessage = error.message;
        if (userMessage.includes('Failed to fetch') || userMessage.includes('NetworkError')) {
            userMessage = 'Lo sentimos, el servidor no está disponible.';
        }
        alert(userMessage);
    }
}

// ========================================
// FUNCIONES DE VISUALIZACIÓN
// ========================================

function resetearVista() {
    isTagSearchActive = false;
    document.getElementById('loading').style.display = 'none';
    document.getElementById('resultsSection').style.display = 'none';
    document.getElementById('emptyState').style.display = 'none';
    document.getElementById('trendingSection').style.display = 'block';
}

function mostrarResultados(animes, containerId) {
    const container = document.getElementById(containerId);
    container.innerHTML = animes.map((anime, index) => {
        let tagsHtml = '';
        if (anime.tags || anime.genres) {
            const animeTags = [...(anime.tags || []), ...(anime.genres || [])].slice(0, 3);
            tagsHtml = `<div class="anime-tags">${animeTags.map(tag => `<span class="anime-tag">${tag}</span>`).join('')}</div>`;
        }

        return `
            <div class="anime-card" data-id="${anime.id}" onclick="verDetalle(${anime.id})">
                <img src="${anime.cover_image || 'https://via.placeholder.com/185x270?text=No+Image'}"
                    alt="${anime.main_title || 'No title'}"
                    onerror="this.src='https://via.placeholder.com/185x270?text=No+Image'">
                <div class="anime-card-info">
                    <h3>${anime.main_title || 'No title'}</h3>
                    ${tagsHtml}
                    <div class="anime-meta">
                        <span class="score">★ ${anime.score || 'N/A'}</span>
                        <span>• ${anime.year || 'N/A'}</span>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

window.verDetalle = function (id) {
    const anime = animeById[id];
    if (!anime) {
        alert("Error: No se encontró el anime seleccionado.");
        return;
    }
    localStorage.setItem("animeSeleccionado", JSON.stringify(anime));
    window.location.href = "./detalle.html";
};

async function cargarTendencias(btn, filter, page = 1) {
    selectedTags = [];
    actualizarTagsSeleccionados();
    isTagSearchActive = false;
    currentFilter = filter;
    currentPage = page;

    // Verificar que los elementos existan antes de acceder a sus propiedades
    const resultsSection = document.getElementById('resultsSection');
    const emptyState = document.getElementById('emptyState');
    const trendingSection = document.getElementById('trendingSection');

    if (resultsSection) resultsSection.style.display = 'none';
    if (emptyState) emptyState.style.display = 'none';
    if (trendingSection) trendingSection.style.display = 'block';

    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    if (btn) btn.classList.add('active');

    try {
        // OPTIMIZACIÓN: Usar cache si ya está cargado
        let animes;
        if (!allAnimesCacheLoaded) {
            // Primera vez: cargar y cachear
            const response = await fetch(`${API_URL}/api/animes?per_page=99999`);
            const data = await response.json();
            allAnimesCache = data.animes || [];
            allAnimesCacheLoaded = true;
            animes = allAnimesCache;
            console.log('✅ Cache de animes cargado:', animes.length, 'animes');
        } else {
            // Usar cache existente (INSTANTÁNEO)
            animes = allAnimesCache;
        }
        let filtrados = [...animes];

        switch (filter) {
            case 'trending': filtrados = filtrados.filter(a => (a.year || 0) >= 2023); break;
            case 'popular': filtrados = filtrados.sort((a, b) => (b.popularity || 0) - (a.popularity || 0)); break;
            case 'top_rated': filtrados = filtrados.sort((a, b) => (b.score || 0) - (a.score || 0)); break;
            case 'all': filtrados = filtrados.sort((a, b) => (a.main_title || '').localeCompare(b.main_title || '', 'en', { sensitivity: 'base' })); break;
        }

        const total = filtrados.length;
        totalPages = Math.ceil(total / itemsPerPage);
        const inicio = (page - 1) * itemsPerPage;
        const paginaActual = filtrados.slice(inicio, inicio + itemsPerPage);

        animesCache = filtrados;
        mostrarResultados(paginaActual, 'trending');
        mostrarPaginacion();

        animeById = {};
        animesCache.forEach(a => { animeById[a.id] = a; });
        inicializarTags(filtrados);

    } catch (error) {
        console.error('Error loading anime:', error);
    }
}

function mostrarPaginacion() {
    const container = document.getElementById('pagination');
    if (totalPages <= 1) {
        container.style.display = 'none';
        return;
    }
    container.style.display = 'flex';

    let html = '';

    // Botón Anterior
    html += `<button class="page-btn" onclick="cambiarPagina(${currentPage - 1})" ${currentPage === 1 ? 'disabled' : ''}>
        <i class="fas fa-chevron-left"></i>
    </button>`;

    // Lógica para mostrar números de página
    const maxVisibleButtons = 5;
    let startPage = Math.max(1, currentPage - Math.floor(maxVisibleButtons / 2));
    let endPage = Math.min(totalPages, startPage + maxVisibleButtons - 1);

    if (endPage - startPage + 1 < maxVisibleButtons) {
        startPage = Math.max(1, endPage - maxVisibleButtons + 1);
    }

    if (startPage > 1) {
        html += `<button class="page-btn" onclick="cambiarPagina(1)">1</button>`;
        if (startPage > 2) {
            html += `<span class="page-dots">...</span>`;
        }
    }

    for (let i = startPage; i <= endPage; i++) {
        html += `<button class="page-btn ${i === currentPage ? 'active' : ''}" 
                        onclick="cambiarPagina(${i})">${i}</button>`;
    }

    if (endPage < totalPages) {
        if (endPage < totalPages - 1) {
            html += `<span class="page-dots">...</span>`;
        }
        html += `<button class="page-btn" onclick="cambiarPagina(${totalPages})">${totalPages}</button>`;
    }

    // Botón Siguiente
    html += `<button class="page-btn" onclick="cambiarPagina(${currentPage + 1})" ${currentPage === totalPages ? 'disabled' : ''}>
        <i class="fas fa-chevron-right"></i>
    </button>`;

    container.innerHTML = html;
}

function cambiarPagina(page) {
    if (page < 1 || page > totalPages || page === currentPage) return;
    cargarTendencias(null, currentFilter, page);
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ========================================
// LÓGICA DE UI DE AUTENTICACIÓN
// ========================================

function openLoginModal() {
    document.getElementById('loginModal').style.display = 'flex';
}

function closeLoginModal() {
    document.getElementById('loginModal').style.display = 'none';
}

function switchAuthTab(tab) {
    const loginForm = document.getElementById('loginForm');
    const regForm = document.getElementById('registerForm');
    const tabs = document.querySelectorAll('.auth-tab');

    tabs.forEach(t => t.classList.remove('active'));

    if (tab === 'login') {
        loginForm.style.display = 'block';
        regForm.style.display = 'none';
        tabs[0].classList.add('active');
    } else {
        loginForm.style.display = 'none';
        regForm.style.display = 'block';
        tabs[1].classList.add('active');
    }
}

async function handlePasswordLogin() {
    const email = document.getElementById('loginEmail').value;
    const pass = document.getElementById('loginPassword').value;
    const status = document.getElementById('loginStatus');

    try {
        status.textContent = "Logging in...";
        status.className = "status-message";
        const res = await searchAPI.loginPassword(email, pass);

        if (res.api_key) {
            status.textContent = "Success!";
            status.className = "status-message success-text";
            setTimeout(() => {
                closeLoginModal();
                location.reload();
            }, 1000);
        } else {
            status.textContent = res.error || "Login failed";
            status.className = "status-message error-text";
        }
    } catch (e) {
        status.textContent = "Error connecting to server";
        status.className = "status-message error-text";
    }
}

async function handlePasswordRegister() {
    const email = document.getElementById('regEmail').value;
    const pass = document.getElementById('regPassword').value;
    const status = document.getElementById('loginStatus');

    try {
        status.textContent = "Creating account...";
        status.className = "status-message";
        const res = await searchAPI.registerPassword(email, pass);

        if (res.api_key) {
            status.textContent = "Account created!";
            status.className = "status-message success-text";
            setTimeout(() => {
                closeLoginModal();
                location.reload();
            }, 1000);
        } else if (res.require_email_verification) {
            // Registro exitoso - mostrar mensaje de verificación de email
            status.innerHTML = `
                ✅ <strong>¡Cuenta creada!</strong><br>
                📧 Te hemos enviado un email de verificación a <strong>${email}</strong>.<br>
                <small>Por favor revisa tu bandeja de entrada y haz clic en el enlace para activar tu cuenta.</small>
            `;
            status.className = "status-message success-text";
            // Limpiar campos
            document.getElementById('regEmail').value = '';
            document.getElementById('regPassword').value = '';
        } else {
            status.textContent = res.error || "Registration failed";
            status.className = "status-message error-text";
        }
    } catch (e) {
        status.textContent = "Error connecting to server";
        status.className = "status-message error-text";
    }
}

// Cerrar modal si se hace clic fuera
window.onclick = function (event) {
    const modal = document.getElementById('loginModal');
    if (event.target == modal) {
        closeLoginModal();
    }
}

// ========================================
// FUNCIÓN DE LOGOUT
// ========================================

function handleLogout() {
    if (confirm('¿Estás seguro de que quieres cerrar sesión? Regresarás al modo anónimo con búsquedas limitadas.')) {
        // Limpiar localStorage
        localStorage.removeItem('anime_api_key');
        localStorage.removeItem('paypal_order_id');

        // Actualizar la API
        searchAPI.apiKey = null;

        // Limpiar datos de la última búsqueda
        window.lastSearchData = null;

        // Actualizar UI inmediatamente
        const loginBtn = document.getElementById('loginBtn');
        const logoutBtn = document.getElementById('logoutBtn');

        if (loginBtn) loginBtn.style.display = 'block';
        if (logoutBtn) logoutBtn.style.display = 'none';

        // Actualizar el estado
        uiManager.updateStatus();

        // Mostrar mensaje de confirmación
        alert('Has cerrado sesión correctamente. Ahora estás en modo anónimo.');

        // Recargar la página para resetear todo
        window.location.reload();
    }
}

// Event Listeners para Inputs
document.getElementById('searchInput')?.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') buscar();
});

const tagInput = document.getElementById('tagInput');
if (tagInput) {
    tagInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            agregarTagDesdeInput();
        }
    });
}
// Inicialización
window.addEventListener('DOMContentLoaded', async () => {
    // Verificación de Magic Link
    const urlParams = new URLSearchParams(window.location.search);
    const magicKey = urlParams.get('api_key');
    if (magicKey) {
        localStorage.setItem('anime_api_key', magicKey);
        searchAPI.apiKey = magicKey;
        window.history.replaceState({}, document.title, window.location.pathname);
        alert("¡Inicio de sesión exitoso!");
    }

    // Asegurar que el usuario esté registrado antes de continuar
    await uiManager.init();

    // Pequeña pausa para asegurar que todo esté listo
    await new Promise(resolve => setTimeout(resolve, 100));

    cargarTendencias(null, 'all');
    console.log('🚀 Sistema iniciado con MongoDB Auth');
});
