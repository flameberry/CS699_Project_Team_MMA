document.addEventListener('DOMContentLoaded', () => {
    //Part needed to channged for database usage - Madhur Bhai

    const mockDatabase = {
        "search-results": [
            { id: "doc001", case_title: "Union of India Vs. M/s G.S. Chatha Rice Mills", citation: "Civil Appeal No(s). 2176 of 2021", judgment_date: "2021-03-10", snippet: "The core issue revolves around the interpretation of customs tariffs and the applicability of certain notifications..." },
            { id: "doc002", case_title: "State of Punjab vs. Principal Secretary to the Governor", citation: "Writ Petition (Civil) No. 1224 of 2023", judgment_date: "2023-11-10", snippet: "This case addresses the constitutional powers of the Governor regarding the assent to Bills..." },
            { id: "doc003", case_title: "Competition Commission of India vs. Google LLC", citation: "Civil Appeal No. 54 of 2023", judgment_date: "2023-04-19", snippet: "Examining the allegations of abuse of dominant position by Google in the Android ecosystem..." }
        ],
        "documents": {
            "doc001": { id: "doc001", case_title: "Union of India Vs. M/s G.S. Chatha Rice Mills", citation: "Civil Appeal No(s). 2176 of 2021", judgment_date: "2021-03-10", judges: ["Hon'ble Mr. Justice D.Y. Chandrachud", "Hon'ble Mr. Justice M.R. Shah"], full_text: "<p>The present appeal arises from a judgment...</p>" },
            "doc002": { id: "doc002", case_title: "State of Punjab vs. Principal Secretary to the Governor", citation: "Writ Petition (Civil) No. 1224 of 2023", judgment_date: "2023-11-10", judges: ["Hon'ble Chief Justice D.Y. Chandrachud", "Hon'ble Mr. Justice J.B. Pardiwala"], full_text: "<p>This is a significant case concerning the constitutional relationship...</p>" },
            "doc003": { id: "doc003", case_title: "Competition Commission of India vs. Google LLC", citation: "Civil Appeal No. 54 of 2023", judgment_date: "2023-04-19", judges: ["Hon'ble Chief Justice D.Y. Chandrachud", "Hon'ble Mr. Justice P.S. Narasimha"], full_text: "<p>This landmark case tests the application of Indian competition law...</p>" }
        }
    };

    const getQueryParam = (param) => {
        const urlParams = new URLSearchParams(window.location.search);
        return urlParams.get(param);
    };

    const fetchSearchResults = async (query) => {
        return new Promise(resolve => setTimeout(() => resolve(mockDatabase['search-results']), 500));
    };

    const fetchDocumentById = async (id) => {
        return new Promise(resolve => setTimeout(() => resolve(mockDatabase.documents[id] || null), 500));
    };

    // Personal functions for each page

    const handleHomepage = () => {
        const searchForm = document.getElementById('search-form');
        if (!searchForm) return;
        searchForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const searchInput = document.getElementById('search-input');
            const query = searchInput.value.trim();
            if (query) window.location.href = `search-result.html?q=${encodeURIComponent(query)}`;
        });
    };

    const handleSearchResultsPage = async () => {
        const query = getQueryParam('q');
        const searchDisplay = document.getElementById('search-query-display');
        const resultsList = document.getElementById('results-list');
        const loadResults = document.getElementById('l-results');
        if (!query || !searchDisplay || !resultsList) return;
        searchDisplay.textContent = query;
        const results = await fetchSearchResults(query);
        if (loadResults) loadResults.style.display = 'none';
        resultsList.innerHTML = '';
        if (!results || results.length === 0) {
            resultsList.innerHTML = '<p>No results found</p>';
            return;
        }
        results.forEach(result => {
            const el = document.createElement('div');
            el.className = 'result-item';
            el.innerHTML = `
                <a href="Doc_view_page.html?id=${encodeURIComponent(result.id)}">
                    <h3>${result.case_title}</h3>
                    <p class="citation">${result.citation} • ${result.judgment_date}</p>
                    <p class="snippet">${result.snippet}</p>
                </a>`;
            resultsList.appendChild(el);
        });
    };

    const handleDocumentPage = async () => {
        const docId = getQueryParam('id');
        const loadDoc = document.getElementById('l-document');
        const docCon = document.getElementById('d-content');
        if (!docId) return;
        const doc = await fetchDocumentById(docId);
        if (loadDoc) loadDoc.style.display = 'none';
        if (docCon) docCon.classList.remove('hidden');
        if (!doc) {
            const t = document.getElementById('doc-title');
            if (t) t.textContent = 'Document not found';
            return;
        }
        document.getElementById('doc-title').textContent = doc.case_title;
        document.getElementById('doc-citation').textContent = doc.citation;
        document.getElementById('doc-judges').textContent = doc.judges.join(', ');
        document.getElementById('doc-date').textContent = doc.judgment_date;
        document.getElementById('doc-full-text').innerHTML = doc.full_text;
    };

    // Shared function to handle login and registration on each page
    const handleAuthMod = () => {
        const authMod = document.getElementById('auth-mod');
        if (!authMod) return;
        authMod.style.display = 'none';
        const modTitle = document.getElementById('mod-title');
        const modActionBut = document.getElementById('mod-action-btn');
        const modSwitchText = document.getElementById('mod-switch-text');
        const loginBut = document.getElementById('login-but');
        const registerBut = document.getElementById('register-but');
        const closeModBut = document.getElementById('close-modal-btn');
        const authForm = document.getElementById('auth-form');

        const openMod = (isLogin = true) => {
            if (isLogin) {
                modTitle.textContent = 'Login';
                modActionBut.textContent = 'Login';
                modSwitchText.innerHTML = `Create An Account Today: <a href="#" id="mod-switch-link" class="link">Register</a>`;
            } else {
                modTitle.textContent = 'Registration';
                modActionBut.textContent = 'Create Account';
                modSwitchText.innerHTML = `Already have an account? <a href="#" id="mod-switch-link" class="link">Login</a>`;
            }
            authMod.style.display = 'flex';
            const link = document.getElementById('mod-switch-link');
            if (link) {
                link.addEventListener('click', (e) => {
                    e.preventDefault();
                    openMod(modTitle.textContent === 'Registration');
                });
            }
        };

        const closeMod = () => {
            authMod.style.display = 'none';
        };

        if (loginBut) loginBut.onclick = () => openMod(true);
        if (registerBut) registerBut.onclick = () => openMod(false);
        if (closeModBut) closeModBut.onclick = closeMod;
        authMod.addEventListener('click', (e) => { if (e.target === authMod) closeMod(); });
        if (authForm) {
            authForm.addEventListener('submit', (e) => {
                e.preventDefault();
                alert(`${modTitle.textContent} successful`);
                closeMod();
            });
        }
    };

    //had to be made in single file bcoz gave error for import module.....
    const path = window.location.pathname.split('/').pop();
    switch (path) {
        case 'index.html':
        case '':
            handleHomepage();
            break;
        case 'search-result.html':
            handleSearchResultsPage();
            break;
        case 'Doc_view_page.html':
            handleDocumentPage();
            break;
    }
    handleAuthMod();
});
