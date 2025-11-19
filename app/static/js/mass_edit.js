document.addEventListener('DOMContentLoaded', function() {
    const massEditToggle = document.getElementById('mass-edit-toggle');
    if (!massEditToggle) return;

    const checkboxes = document.querySelectorAll('.mass-edit-checkbox');
    const fab = document.getElementById('mass-edit-fab');
    const selectedCountSpan = document.getElementById('selected-count');
    let lastChecked = null;

    // Toggle Mass Edit Mode
    massEditToggle.addEventListener('click', function() {
        const isActive = this.classList.toggle('active');
        this.textContent = isActive ? 'Exit Mass Edit' : 'Mass Edit';
        
        // Toggle button styles
        if (isActive) {
            this.classList.remove('text-gray-300', 'hover:bg-gray-700/50');
            this.classList.add('bg-blue-600', 'text-white', 'hover:bg-blue-700');
        } else {
            this.classList.add('text-gray-300', 'hover:bg-gray-700/50');
            this.classList.remove('bg-blue-600', 'text-white', 'hover:bg-blue-700');
        }
        
        checkboxes.forEach(cb => {
            cb.classList.toggle('hidden', !isActive);
            if (!isActive) cb.checked = false;
        });
        
        if (!isActive) updateFab();
    });

    // Checkbox Logic
    checkboxes.forEach(checkbox => {
        checkbox.addEventListener('click', function(e) {
            let inBetween = false;
            if (e.shiftKey && lastChecked) {
                checkboxes.forEach(cb => {
                    if (cb === this || cb === lastChecked) {
                        inBetween = !inBetween;
                    }
                    if (inBetween) {
                        cb.checked = lastChecked.checked;
                    }
                });
            }
            lastChecked = this;
            updateFab();
        });
    });

    function updateFab() {
        const selected = document.querySelectorAll('.mass-edit-checkbox:checked');
        const count = selected.length;
        if (selectedCountSpan) selectedCountSpan.textContent = count;
        
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
            
            const selectedCheckboxes = document.querySelectorAll('.mass-edit-checkbox:checked');
            if (selectedCheckboxes.length === 0) return;

            if (!confirm(`Are you sure you want to ${action.replace(/_/g, ' ')} for ${selectedCheckboxes.length} items?`)) return;

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
                alert('An error occurred: ' + error.message);
                this.textContent = originalText;
                this.disabled = false;
            }
        });
    });
});
