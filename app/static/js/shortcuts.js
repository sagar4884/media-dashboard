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

    // Escape (Esc)
    if (e.key === 'Escape') {
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
                        <span class="text-gray-300">Search</span>
                        <kbd class="bg-gray-700 text-white px-2 py-1 rounded text-sm font-mono border border-gray-600">/</kbd>
                    </div>
                    <div class="flex justify-between items-center border-b border-gray-700 pb-2">
                        <span class="text-gray-300">Toggle Mass Edit</span>
                        <kbd class="bg-gray-700 text-white px-2 py-1 rounded text-sm font-mono border border-gray-600">m</kbd>
                    </div>
                    <div class="flex justify-between items-center border-b border-gray-700 pb-2">
                        <span class="text-gray-300">Close / Cancel</span>
                        <kbd class="bg-gray-700 text-white px-2 py-1 rounded text-sm font-mono border border-gray-600">Esc</kbd>
                    </div>
                    <div class="flex justify-between items-center">
                        <span class="text-gray-300">Show Shortcuts</span>
                        <kbd class="bg-gray-700 text-white px-2 py-1 rounded text-sm font-mono border border-gray-600">?</kbd>
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
