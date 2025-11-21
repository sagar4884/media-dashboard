document.addEventListener('keydown', function(e) {
    // Ignore if user is typing in an input or textarea
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
        if (e.key === 'Escape') {
            e.target.blur();
        }
        return;
    }

    // Search (/)
    if (e.key === '/') {
        e.preventDefault();
        const searchInput = document.getElementById('search');
        if (searchInput) {
            searchInput.focus();
        }
    }

    // Mass Edit (m)
    if (e.key === 'm') {
        const toggle = document.getElementById('mass-edit-toggle');
        if (toggle) {
            toggle.click();
        }
    }

    // Navigation (j/k)
    if (e.key === 'j' || e.key === 'k') {
        const rows = document.querySelectorAll('tbody tr');
        if (rows.length === 0) return;

        let currentIndex = -1;
        rows.forEach((row, index) => {
            if (row.classList.contains('keyboard-selected')) {
                currentIndex = index;
            }
        });

        if (e.key === 'j') {
            // Down
            const nextIndex = Math.min(currentIndex + 1, rows.length - 1);
            selectRow(rows[nextIndex]);
        } else {
            // Up
            const prevIndex = Math.max(currentIndex - 1, 0);
            selectRow(rows[prevIndex]);
        }
    }

    // Actions on Selected Row
    const selectedRow = document.querySelector('tr.keyboard-selected');
    if (selectedRow) {
        // Keep (k - wait, k is up? Gmail uses k for newer/up. Let's use 'e' for Keep or 'Enter')
        // Actually, user asked for 'k' to be Keep in the prompt? 
        // "k (or Enter): Keep"
        // But 'k' is standard for 'up' in vim/gmail. 
        // I will use 'Enter' for Keep to avoid conflict, or 'i' (archive/keep).
        // Let's stick to 'Enter' for Keep as primary, and maybe 'a' for Keep/Archive.
        
        if (e.key === 'Enter') {
            // Trigger Keep
            triggerRowAction(selectedRow, 'keep');
        }

        // Delete (x or #)
        if (e.key === 'x' || e.key === '#') {
            triggerRowAction(selectedRow, 'delete');
        }

        // Seasonal (s)
        if (e.key === 's') {
            triggerRowAction(selectedRow, 'seasonal');
        }
    }

    // Escape (Esc)
    if (e.key === 'Escape') {
        // Deselect row
        const selected = document.querySelector('.keyboard-selected');
        if (selected) selected.classList.remove('keyboard-selected');

        // Close Mass Edit if active
        const toggle = document.getElementById('mass-edit-toggle');
        if (toggle && toggle.classList.contains('active')) {
            toggle.click();
        }
        
        // Close Help Modal
        const helpModal = document.getElementById('shortcuts-help-modal');
        if (helpModal && !helpModal.classList.contains('hidden')) {
            helpModal.classList.add('hidden');
        }
    }

    // Help (?)
    if (e.key === '?' && e.shiftKey) {
        e.preventDefault();
        toggleHelpModal();
    }
});

function selectRow(row) {
    document.querySelectorAll('.keyboard-selected').forEach(r => r.classList.remove('keyboard-selected'));
    if (row) {
        row.classList.add('keyboard-selected');
        row.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
}

function triggerRowAction(row, action) {
    // Find the button corresponding to the action
    // We need to add data attributes to the buttons in the HTML to make this robust
    // Or find by text content/href
    
    // Assuming we add data-action="{action}" to the buttons
    const btn = row.querySelector(`[data-action="${action}"]`);
    if (btn) {
        btn.click();
        
        // Move to next row automatically after action
        const nextRow = row.nextElementSibling;
        if (nextRow) {
            setTimeout(() => selectRow(nextRow), 200); // Small delay to allow animation
        }
    }
}

function toggleHelpModal() {
    let modal = document.getElementById('shortcuts-help-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'shortcuts-help-modal';
        modal.className = 'fixed inset-0 bg-black/80 backdrop-blur-sm z-[100] flex items-center justify-center hidden';
        modal.innerHTML = `
            <div class="bg-gray-800 border border-gray-700 rounded-xl shadow-2xl p-6 max-w-md w-full mx-4 animate-fade-in-up">
                <div class="flex justify-between items-center mb-6">
                    <h3 class="text-xl font-bold text-white">Keyboard Shortcuts</h3>
                    <button onclick="document.getElementById('shortcuts-help-modal').classList.add('hidden')" class="text-gray-400 hover:text-white">
                        <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>
                <div class="space-y-4">
                    <div class="flex justify-between items-center border-b border-gray-700 pb-2">
                        <span class="text-gray-300">Navigation</span>
                        <div class="flex gap-2">
                            <kbd class="bg-gray-700 text-white px-2 py-1 rounded text-sm font-mono border border-gray-600">j</kbd>
                            <kbd class="bg-gray-700 text-white px-2 py-1 rounded text-sm font-mono border border-gray-600">k</kbd>
                        </div>
                    </div>
                    <div class="flex justify-between items-center border-b border-gray-700 pb-2">
                        <span class="text-gray-300">Keep</span>
                        <kbd class="bg-gray-700 text-white px-2 py-1 rounded text-sm font-mono border border-gray-600">Enter</kbd>
                    </div>
                    <div class="flex justify-between items-center border-b border-gray-700 pb-2">
                        <span class="text-gray-300">Delete</span>
                        <kbd class="bg-gray-700 text-white px-2 py-1 rounded text-sm font-mono border border-gray-600">x</kbd>
                    </div>
                    <div class="flex justify-between items-center border-b border-gray-700 pb-2">
                        <span class="text-gray-300">Seasonal (Shows)</span>
                        <kbd class="bg-gray-700 text-white px-2 py-1 rounded text-sm font-mono border border-gray-600">s</kbd>
                    </div>
                    <div class="flex justify-between items-center border-b border-gray-700 pb-2">
                        <span class="text-gray-300">Search</span>
                        <kbd class="bg-gray-700 text-white px-2 py-1 rounded text-sm font-mono border border-gray-600">/</kbd>
                    </div>
                    <div class="flex justify-between items-center border-b border-gray-700 pb-2">
                        <span class="text-gray-300">Toggle Mass Edit</span>
                        <kbd class="bg-gray-700 text-white px-2 py-1 rounded text-sm font-mono border border-gray-600">m</kbd>
                    </div>
                </div>
                <div class="mt-6 text-center text-xs text-gray-500">
                    Press <kbd class="bg-gray-700 px-1 rounded">Esc</kbd> to close
                </div>
            </div>
        `;
        document.body.appendChild(modal);
        
        // Close on click outside
        modal.addEventListener('click', function(e) {
            if (e.target === modal) {
                modal.classList.add('hidden');
            }
        });
    }
    modal.classList.toggle('hidden');
}

