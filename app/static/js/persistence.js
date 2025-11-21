document.addEventListener('DOMContentLoaded', function() {
    const path = window.location.pathname;
    // Only run on Radarr and Sonarr pages
    if (!path.includes('/radarr') && !path.includes('/sonarr')) return;
    
    // Clean key: /radarr -> radarr
    const pageKey = path.split('/').pop(); 
    const storageKey = `media_dashboard_prefs_${pageKey}`;
    
    // On Load: Check if we need to restore settings
    // We only restore if NO relevant params are present (clean load)
    const urlParams = new URLSearchParams(window.location.search);
    const relevantParams = ['view', 'sort_by', 'sort_order', 'per_page', 'score_filter'];
    const hasParams = relevantParams.some(p => urlParams.has(p));

    const defaults = {
        'view': 'table',
        'sort_by': 'title',
        'sort_order': 'asc',
        'score_filter': 'all',
        'per_page': '100'
    };

    if (!hasParams) {
        const saved = localStorage.getItem(storageKey);
        if (saved) {
            try {
                const prefs = JSON.parse(saved);
                const newUrl = new URL(window.location);
                let changed = false;
                
                Object.keys(prefs).forEach(key => {
                    // Only apply preference if it differs from the default
                    // This prevents unnecessary page reloads (flashing) when the saved pref matches the server default
                    if (prefs[key] && prefs[key] !== defaults[key]) {
                        newUrl.searchParams.set(key, prefs[key]);
                        changed = true;
                    }
                });
                
                if (changed) {
                    // Use replace to avoid back-button loops
                    window.location.replace(newUrl);
                }
            } catch (e) {
                console.error('Error parsing saved preferences:', e);
            }
        }
    } else {
        // If we loaded with params, save them immediately
        savePrefs(storageKey);
    }

    // Listen for HTMX history updates (when URL changes via filters/pagination)
    document.body.addEventListener('htmx:pushedIntoHistory', function() {
        savePrefs(storageKey);
    });
    
    function savePrefs(key) {
        const params = new URLSearchParams(window.location.search);
        const prefs = {};
        relevantParams.forEach(p => {
            if (params.has(p)) prefs[p] = params.get(p);
        });
        
        // Only save if we have at least one preference
        if (Object.keys(prefs).length > 0) {
            localStorage.setItem(key, JSON.stringify(prefs));
        }
    }
});
