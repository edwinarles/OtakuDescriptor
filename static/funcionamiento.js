const API_URL = window.location.origin;

// Global variables
let animesCache = [];
let currentPage = 1;
let totalPages = 1;
let currentFilter = 'all';
const itemsPerPage = 24;
let selectedTags = [];
let animeById = {};
let allAvailableTags = new Set();

// Global cache for all animes (loaded only once)
let allAnimesCache = null;
let allAnimesCacheLoaded = false;
let isTagSearchActive = false;
let isSearching = false;  // Prevent duplicate search calls


// ========================================
// AUTHENTICATION AND PAYMENT SYSTEM
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
            // No API key - anonymous user
            return null;
        }

        try {
            const response = await fetch(`${this.baseURL}/auth/status`, {
                headers: { 'X-API-Key': this.apiKey }
            });

            if (!response.ok) {
                // If API key is invalid (401, 403), clear it
                if (response.status === 401 || response.status === 403) {
                    console.warn('Invalid API key, clearing localStorage...');
                    localStorage.removeItem('anime_api_key');
                    this.apiKey = null;
                }
                return null;
            }

            return await response.json();
        } catch (error) {
            console.error('Error checking status:', error);
            return null;
        }
    }

    async loginPassword(email, password) {
        try {
            const response = await fetch(`${this.baseURL}/auth/login-password`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ email, password })
            });

            const data = await response.json();

            if (!response.ok) {
                console.error('Login failed:', response.status, data);
                return {
                    error: data.error || `Server error (${response.status})`,
                    status: response.status
                };
            }

            if (data.api_key) {
                this.apiKey = data.api_key;
                localStorage.setItem('anime_api_key', data.api_key);
            }
            return data;
        } catch (error) {
            console.error('Network error during login:', error);
            return {
                error: 'Connection error',
                details: 'Cannot connect to server. Please check your internet connection.',
                networkError: true
            };
        }
    }

    async registerPassword(email, password) {
        try {
            const response = await fetch(`${this.baseURL}/auth/register-password`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ email, password })
            });

            const data = await response.json();

            // Check if response was not OK (status 4xx or 5xx)
            if (!response.ok) {
                console.error('Registration failed:', response.status, data);
                // Return data with error information for caller to handle
                return {
                    error: data.error || `Server error (${response.status})`,
                    details: data.details || 'Unknown error',
                    status: response.status
                };
            }

            if (data.api_key) {
                this.apiKey = data.api_key;
                localStorage.setItem('anime_api_key', data.api_key);
            }
            return data;
        } catch (error) {
            console.error('Network error during registration:', error);
            return {
                error: 'Connection error',
                details: 'Cannot connect to server. Please check your internet connection and try again.',
                networkError: true
            };
        }
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

            // If API key is invalid and detected in 429 error message
            if (data.invalid_api_key) {
                console.warn('Invalid API key detected, clearing localStorage...');
                localStorage.removeItem('anime_api_key');
                this.apiKey = null;
            }

            this.showUpgradeModal(data);
            throw new Error(data.error);
        }

        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.error || 'Search error');
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
        // Show overlay IMMEDIATELY before anything else
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
                // Don't remove overlay here because redirect is immediate
                window.location.href = data.approval_url;
            } else {
                this.removePayPalLoadingOverlay();
                alert('Error: Could not get PayPal URL');
            }
            return data;
        } catch (error) {
            console.error('Error creating PayPal order:', error);
            this.removePayPalLoadingOverlay();
            alert('Error connecting to PayPal. Please try again.');
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

        // Check if anonymous user
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
                                <li>✅ 200 búsquedas por hora</li>
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
                                <li>✅ 200 búsquedas por hora</li>
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
                        <p>Has alcanzado tu límite premium por hora. Tu límite se renovará pronto.</p>
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

// Global API instance
const searchAPI = new AnimeSearchAPI();

// ========================================
// UI MANAGER FOR SEARCH STATUS
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
                        this.showErrorMessage('Error processing payment');
                    }
                } catch (error) {
                    console.error('Error capturando pago:', error);
                    this.showErrorMessage('Error processing payment');
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
                <p>Processing your payment...</p>
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
                <h3>Payment successful!</h3>
                <p>You now have Premium access with 200 searches per hour</p>
                <button onclick="this.parentElement.parentElement.remove()">Continue</button>
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
                <h3>Payment error</h3>
                <p>${message}</p>
                <button onclick="this.parentElement.parentElement.remove()">Close</button>
            </div>
        `;
        document.body.appendChild(msg);
    }

    createStatusBar() {
        const statusBar = document.createElement('div');
        statusBar.id = 'search-status-bar';
        statusBar.innerHTML = `
            <div class="status-container">
                <span id="search-count">Loading...</span>
                <button id="upgrade-button" class="btn-upgrade" style="display:none;">
                    ⭐ Upgrade to Premium
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

            // Anonymous user (no API key or no status)
            if (!status) {
                // Show login button, hide logout
                if (loginBtn) loginBtn.style.display = 'block';
                if (logoutBtn) logoutBtn.style.display = 'none';

                // Try to fetch anonymous status from server
                try {
                    const anonResponse = await fetch(`${this.api.baseURL}/auth/anonymous-status`);
                    if (anonResponse.ok) {
                        const anonStatus = await anonResponse.json();
                        const remaining = anonStatus.remaining;

                        countSpan.innerHTML = `
                            🎁 <strong>Free Mode</strong> - 
                            Searches remaining: <strong>${remaining}</strong>/10
                        `;

                        if (remaining <= 3) {
                            upgradeBtn.textContent = '✨ Register';
                            upgradeBtn.style.display = 'inline-block';
                            upgradeBtn.onclick = () => openLoginModal();
                            statusContainer.classList.add('low-searches');
                        } else {
                            upgradeBtn.style.display = 'none';
                            statusContainer.classList.remove('low-searches');
                        }
                        return;
                    }
                } catch (error) {
                    console.error('Error fetching anonymous status:', error);
                }

                // Fallback: Get last search data if it exists
                const lastSearchData = window.lastSearchData;
                if (lastSearchData && lastSearchData.is_anonymous) {
                    const remaining = lastSearchData.searches_remaining;
                    countSpan.innerHTML = `
                        🎁 <strong>Free Mode</strong> - 
                        Searches remaining: <strong>${remaining}</strong>/10
                    `;

                    if (remaining <= 3) {
                        upgradeBtn.textContent = '✨ Register';
                        upgradeBtn.style.display = 'inline-block';
                        upgradeBtn.onclick = () => openLoginModal();
                        statusContainer.classList.add('low-searches');
                    } else {
                        upgradeBtn.style.display = 'none';
                        statusContainer.classList.remove('low-searches');
                    }
                } else {
                    countSpan.innerHTML = `
                        🎁 <strong>Free Mode</strong> - 
                        10 searches per day
                    `;
                    upgradeBtn.style.display = 'none';
                    statusContainer.classList.remove('low-searches');
                }
                return;
            }

            // Registered user - show logout button, hide login
            if (loginBtn) loginBtn.style.display = 'none';
            if (logoutBtn) logoutBtn.style.display = 'block';

            if (status.is_premium) {
                countSpan.innerHTML = `
                    💎 <strong>Premium</strong> - 
                    Searches: <strong>${status.remaining}</strong>/${status.hourly_limit} per hour
                `;
                upgradeBtn.style.display = 'none';
                statusContainer.classList.remove('low-searches');
            } else {
                countSpan.innerHTML = `
                    Remaining searches: <strong>${status.remaining}</strong>/${status.hourly_limit} per day
                `;

                if (status.remaining <= 3) {
                    upgradeBtn.textContent = '⭐ Upgrade to Premium';
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
        <span class="selected-tags-label">Filtering by:</span>
        ${selectedTags.map(tag => `
            <span class="selected-tag">
                ${tag}
                <button onclick="toggleTag('${tag}')" class="remove-tag">×</button>
            </span>
        `).join('')}
        <button onclick="limpiarTags()" class="clear-tags-btn">Clear all</button>
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

    // OPTIMIZATION: Use cache instead of loading again
    try {
        // Load cache if it doesn't exist
        if (!allAnimesCacheLoaded) {
            const response = await fetch(`${API_URL}/api/animes?per_page=99999`);
            const data = await response.json();
            allAnimesCache = data.animes || [];
            allAnimesCacheLoaded = true;
        }
        const todosAnimes = allAnimesCache;

        // Filter animes based on selected tags
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

        // Update cache with ALL animes, not just filtered ones
        animesCache = todosAnimes;
        animeById = {};
        todosAnimes.forEach(a => { animeById[a.id] = a; });
        inicializarTags(todosAnimes);

        mostrarResultadosTags(resultados);
        return resultados;
    } catch (error) {
        console.error('Error loading animes to filter:', error);
        return [];
    }
}

function mostrarResultadosTags(animes) {
    document.getElementById('loading').style.display = 'none';
    document.getElementById('trendingSection').style.display = 'none';
    document.getElementById('emptyState').style.display = 'none';
    document.getElementById('resultsSection').style.display = 'block';

    document.getElementById('resultsTitle').textContent = 'Results by Tags';
    document.getElementById('resultsCount').textContent = `${animes.length} anime found`;

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
// SEMANTIC SEARCH (UPDATED WITH API)
// ========================================

async function buscar() {
    // Prevent duplicate searches (e.g., when switching tabs)
    if (isSearching) {
        console.log('⚠️ Search already in progress, ignoring duplicate call');
        return;
    }

    console.log('🔍 buscar() function called at', new Date().toISOString());

    selectedTags = [];
    actualizarTagsSeleccionados();
    isTagSearchActive = false;

    const query = document.getElementById('searchInput').value.trim();
    const MAX_CHARS = 250;

    if (query.length > MAX_CHARS) {
        alert(`The description is too long. Please limit it to a maximum of ${MAX_CHARS} characters to perform the search.`);
        return;
    }

    if (!query) {
        resetearVista();
        cargarTendencias(null, 'all');
        return;
    }

    // Set searching flag
    isSearching = true;
    console.log('✅ isSearching flag set to true, making API call...');

    document.getElementById('loading').style.display = 'block';
    document.getElementById('resultsSection').style.display = 'none';
    document.getElementById('trendingSection').style.display = 'none';
    document.getElementById('emptyState').style.display = 'none';

    try {
        console.log('📡 Calling searchAPI.search() with query:', query);
        const data = await searchAPI.search(query, 18);
        console.log('📥 Search API response received:', {
            results_count: data.results?.length,
            searches_remaining: data.searches_remaining,
            is_anonymous: data.is_anonymous
        });

        // Save search data to update status
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
            document.getElementById('resultsTitle').textContent = 'Search Results';
            document.getElementById('resultsCount').textContent = `${animesCache.length} anime found`;
            mostrarResultados(animesCache, 'results');
            inicializarTags(animesCache);
        }
    } catch (error) {
        console.error('Error:', error);
        document.getElementById('loading').style.display = 'none';
        let userMessage = error.message;
        if (userMessage.includes('Failed to fetch') || userMessage.includes('NetworkError')) {
            userMessage = 'Sorry, the server is not available.';
        }
        alert(userMessage);
    } finally {
        // Always clear the searching flag
        console.log('🔓 isSearching flag cleared');
        isSearching = false;
    }
}



// ========================================
// DISPLAY FUNCTIONS
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
        alert("Error: Selected anime not found.");
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
        // OPTIMIZATION: Use cache if already loaded
        let animes;
        if (!allAnimesCacheLoaded) {
            // First time: load and cache
            const response = await fetch(`${API_URL}/api/animes?per_page=99999`);
            const data = await response.json();
            allAnimesCache = data.animes || [];
            allAnimesCacheLoaded = true;
            animes = allAnimesCache;
            console.log('✅ Anime cache loaded:', animes.length, 'animes');
        } else {
            // Use existing cache (INSTANT)
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
// AUTHENTICATION UI LOGIC
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
        } else if (res.error) {
            console.error('Login error:', res);
            status.innerHTML = `
                ❌ <strong>Error:</strong> ${res.error}<br>
                ${res.details ? `<small>${res.details}</small>` : ''}
            `;
            status.className = "status-message error-text";
        } else {
            status.textContent = "Login failed";
            status.className = "status-message error-text";
        }
    } catch (e) {
        console.error('Exception during login:', e);
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
        } else if (res.error) {
            // Enhanced error display - show backend error details
            let errorMsg = res.error;
            if (res.details) {
                errorMsg += `\n${res.details}`;
            }
            console.error('Registration error:', res);
            status.innerHTML = `
                ❌ <strong>Error:</strong> ${res.error}<br>
                ${res.details ? `<small>${res.details}</small>` : ''}
            `;
            status.className = "status-message error-text";
        } else {
            status.textContent = "Registration failed - Unknown error";
            status.className = "status-message error-text";
        }
    } catch (e) {
        console.error('Exception during registration:', e);
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
// LOGOUT FUNCTION
// ========================================

function handleLogout() {
    if (confirm('Are you sure you want to logout? You will be redirected to anonymous mode with limited searches.')) {
        // Limpiar localStorage
        localStorage.removeItem('anime_api_key');
        localStorage.removeItem('paypal_order_id');

        // Update API
        searchAPI.apiKey = null;

        // Clear last search data
        window.lastSearchData = null;

        // Update UI status
        uiManager.updateStatus();

        // Hide results sections
        document.getElementById('resultsSection').style.display = 'none';
        document.getElementById('emptyState').style.display = 'none';
        document.getElementById('trendingSection').style.display = 'block';

        // Show confirmation message
        alert('You have logged out successfully');

        // Reload page to reset everything
        window.location.reload();
    }
}

// Event Listeners for Inputs
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
// Initialization
window.addEventListener('DOMContentLoaded', async () => {
    // Magic Link verification
    const urlParams = new URLSearchParams(window.location.search);
    const apiKeyParam = urlParams.get('api_key');
    if (apiKeyParam) {
        localStorage.setItem('anime_api_key', apiKeyParam);
        searchAPI.apiKey = apiKeyParam;
        window.history.replaceState({}, document.title, window.location.pathname);
    }

    // Ensure user is registered before continuing
    if (!searchAPI.apiKey) { await searchAPI.register(); }

    // Initialize UI Manager to show search status bar
    await uiManager.init();

    // Short pause to ensure everything is ready
    await new Promise(resolve => setTimeout(resolve, 100));

    cargarTendencias(null, 'all');
    console.log('🚀 Sistema iniciado con MongoDB Auth');
});
