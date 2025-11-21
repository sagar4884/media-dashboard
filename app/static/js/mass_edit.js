document.addEventListener('DOMContentLoaded', function() {
    const massEditToggle = document.getElementById('mass-edit-toggle');
    if (!massEditToggle) return;

    const fab = document.getElementById('mass-edit-fab');
    const selectedCountSpan = document.getElementById('selected-count');
    let lastChecked = null;
    let isMassEditActive = false;

    // --- Initialization & State Management ---

    function initMassEdit() {
        // Re-query elements that might have been swapped by HTMX
        const checkboxes = document.querySelectorAll('.mass-edit-checkbox:not(#select-all)');
        const selectAllCheckbox = document.getElementById('select-all');

        // Sync visibility with active state
        checkboxes.forEach(cb => {
            cb.classList.toggle('hidden', !isMassEditActive);
        });

        if (selectAllCheckbox) {
            selectAllCheckbox.classList.toggle('hidden', !isMassEditActive);
            
            // Use .onchange to prevent stacking event listeners if initMassEdit is called multiple times
            selectAllCheckbox.onchange = function() {
                const isChecked = this.checked;
                document.querySelectorAll('.mass-edit-checkbox:not(#select-all)').forEach(cb => {
                    cb.checked = isChecked;
                });
                updateFab();
            };
        }

        updateFab();
    }

    // --- Event Listeners ---

    // Toggle Mass Edit Mode
    massEditToggle.addEventListener('click', function() {
        isMassEditActive = !isMassEditActive;
        this.textContent = isMassEditActive ? 'Exit Mass Edit' : 'Mass Edit';
        
        // Toggle button styles
        if (isMassEditActive) {
            this.classList.remove('text-gray-300', 'hover:bg-gray-700/50');
            this.classList.add('bg-blue-600', 'text-white', 'hover:bg-blue-700');
        } else {
            this.classList.add('text-gray-300', 'hover:bg-gray-700/50');
            this.classList.remove('bg-blue-600', 'text-white', 'hover:bg-blue-700');
        }
        
        // Update visibility
        const checkboxes = document.querySelectorAll('.mass-edit-checkbox');
        checkboxes.forEach(cb => {
            cb.classList.toggle('hidden', !isMassEditActive);
            if (!isMassEditActive) cb.checked = false;
        });

        updateFab();
    });

    // Event Delegation for Checkboxes (handles clicks on both static and dynamic elements)
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('mass-edit-checkbox') && e.target.id !== 'select-all') {
            const checkbox = e.target;
            const checkboxes = Array.from(document.querySelectorAll('.mass-edit-checkbox:not(#select-all)'));
            
            // Shift+Click Logic
            let inBetween = false;
            if (e.shiftKey && lastChecked) {
                checkboxes.forEach(cb => {
                    if (cb === checkbox || cb === lastChecked) {
                        inBetween = !inBetween;
                    }
                    if (inBetween) {
                        cb.checked = lastChecked.checked;
                    }
                });
            }
            lastChecked = checkbox;
            
            // Update Select All state
            const selectAllCheckbox = document.getElementById('select-all');
            if (selectAllCheckbox) {
                const allChecked = checkboxes.every(cb => cb.checked);
                const someChecked = checkboxes.some(cb => cb.checked);
                selectAllCheckbox.checked = allChecked;
                selectAllCheckbox.indeterminate = someChecked && !allChecked;
            }

            updateFab();
        }
    });

    // HTMX Integration
    document.body.addEventListener('htmx:afterSettle', function(evt) {
        // When content is swapped (search/filter), re-initialize mass edit state
        initMassEdit();
    });

    // Initialize on load
    initMassEdit();

    // Close Button Logic
    const closeBtn = document.getElementById('mass-edit-close');
    if (closeBtn) {
        closeBtn.addEventListener('click', function() {
            document.querySelectorAll('.mass-edit-checkbox').forEach(cb => cb.checked = false);
            const selectAll = document.getElementById('select-all');
            if (selectAll) {
                selectAll.checked = false;
                selectAll.indeterminate = false;
            }
            updateFab();
        });
    }

    function updateFab() {
        // Re-query elements to ensure we have the correct reference
        const fab = document.getElementById('mass-edit-fab');
        const selectedCountSpan = document.getElementById('selected-count');

        // Use Array.from and filter for more robust selection
        const selected = Array.from(document.querySelectorAll('.mass-edit-checkbox:checked')).filter(cb => cb.id !== 'select-all');
        const count = selected.length;
        
        if (selectedCountSpan) selectedCountSpan.textContent = count + ' Selected';
        
        if (fab) {
            if (count > 0) {
                fab.classList.remove('translate-y-full', 'opacity-0');
            } else {
                fab.classList.add('translate-y-full', 'opacity-0');
            }
        }
    }

    // Action Buttons
    document.querySelectorAll('.mass-edit-action').forEach(btn => {
        btn.addEventListener('click', async function() {
            const action = this.dataset.action;
            
            const selectedCheckboxes = document.querySelectorAll('.mass-edit-checkbox:checked:not(#select-all)');
            if (selectedCheckboxes.length === 0) return;

            // Use custom confirm modal if available, fallback to native
            const message = `Are you sure you want to ${action.replace(/_/g, ' ')} for ${selectedCheckboxes.length} items?`;
            const confirmed = window.confirmAction 
                ? await window.confirmAction('Confirm Mass Edit', message)
                : confirm(message);
            
            if (!confirmed) return;

            // Show loading state on button
            const originalText = this.textContent;
            this.textContent = 'Processing...';
            this.disabled = true;

            // Group by media type
            const groups = {};
            selectedCheckboxes.forEach(cb => {
                const type = cb.dataset.mediaType;
                if (!groups[type]) groups[type] = [];
                groups[type].push(parseInt(cb.value));
            });

            try {
                for (const [type, ids] of Object.entries(groups)) {
                    const response = await fetch('/media/bulk_action', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            media_type: type,
                            ids: ids,
                            action: action
                        })
                    });
                    const data = await response.json();
                    if (data.status !== 'success') {
                        throw new Error(data.message || data.error || 'Unknown error');
                    }
                }
                window.location.reload();
            } catch (error) {
                console.error('Error:', error);
                if (typeof Toastify !== 'undefined') {
                    Toastify({
                        text: "Error: " + error.message,
                        duration: 5000,
                        backgroundColor: "linear-gradient(to right, #ff5f6d, #ffc371)",
                        close: true
                    }).showToast();
                } else {
                    alert('An error occurred: ' + error.message);
                }
                this.textContent = originalText;
                this.disabled = false;
            }
        });
    });
});
