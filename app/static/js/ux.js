document.addEventListener('DOMContentLoaded', function() {
    // --- Undo Logic ---
    window.showUndoToast = function(message, undoCallback) {
        let toast = Toastify({
            text: message,
            duration: 5000,
            gravity: "bottom", 
            position: "right", 
            backgroundColor: "#1f2937", // gray-800
            className: "flex items-center gap-4 p-4 rounded-lg shadow-2xl border border-gray-700",
            stopOnFocus: true,
            onClick: function(){}, // Prevent default click behavior
        }).showToast();

        // Add Undo Button to the toast element manually since Toastify doesn't support complex HTML in 'text' easily without escaping
        // But we can use the returned toast object to find the element.
        // Actually, Toastify allows HTML if escapeMarkup is false (default is true in some versions, let's check).
        // Safer way: Create a custom node.
    };

    // We'll use a simpler approach for the toast content:
    // Expose a global function to trigger the toast with an undo action
    window.triggerUndoToast = function(actionText, undoUrl) {
        const toastNode = document.createElement('div');
        toastNode.className = "flex items-center justify-between w-full gap-4";
        toastNode.innerHTML = `
            <span class="text-sm font-medium text-gray-200">${actionText}</span>
            <button id="undo-btn" class="px-3 py-1 text-xs font-bold text-gray-900 bg-blue-400 rounded hover:bg-blue-300 transition-colors">
                UNDO
            </button>
        `;

        const toast = Toastify({
            node: toastNode,
            duration: 5000,
            gravity: "bottom",
            position: "right",
            backgroundColor: "#1f2937",
            className: "border border-gray-700 shadow-2xl rounded-lg",
            stopOnFocus: true,
        }).showToast();

        // Attach event listener to the button
        // Note: Toastify clones the node? No, usually appends.
        // We need to find the button *after* it's added or bind before.
        // Binding before works if the node is preserved.
        const btn = toastNode.querySelector('#undo-btn');
        btn.addEventListener('click', function() {
            // Execute Undo
            fetch(undoUrl)
                .then(response => {
                    if (response.ok) {
                        Toastify({
                            text: "Action undone",
                            duration: 2000,
                            backgroundColor: "#10B981", // green-500
                            gravity: "bottom",
                            position: "right"
                        }).showToast();
                        // Reload the row or page? 
                        // Ideally, we'd just swap the row back. 
                        // For now, let's reload the page or trigger an HTMX refresh.
                        window.location.reload(); 
                    } else {
                        throw new Error('Undo failed');
                    }
                })
                .catch(err => {
                    Toastify({
                        text: "Failed to undo",
                        backgroundColor: "#EF4444",
                        duration: 3000
                    }).showToast();
                });
            toast.hideToast();
        });
    };

    // --- Fade Out Logic ---
    // Intercept clicks on action buttons to perform async fetch instead of navigation
    document.body.addEventListener('click', function(e) {
        // Find the closest anchor tag with data-action attribute
        const btn = e.target.closest('a[data-action]');
        if (!btn) return;

        e.preventDefault(); // Stop the browser from following the link

        const row = btn.closest('tr') || btn.closest('.group'); // Table row or Poster card
        const action = btn.dataset.action;
        const url = btn.href;

        // Visual Feedback
        // Instead of fading out the row, we'll just flash it or dim it slightly while processing
        if (row) {
            row.style.opacity = '0.7';
            row.style.pointerEvents = 'none'; // Prevent double clicks
        }

        // Perform the action asynchronously
        fetch(url, {
            headers: {
                'Accept': 'application/json'
            }
        })
        .then(response => {
            if (response.ok) {
                return response.json();
            }
            throw new Error('Network response was not ok');
        })
        .then(data => {
            // Update the Badge
            if (row) {
                const badge = row.querySelector('.score-badge');
                if (badge) {
                    // Define styles for each score
                    const styles = {
                        'keep': { class: 'bg-green-400/10 text-green-400 ring-green-400/20', text: 'Keep' },
                        'delete': { class: 'bg-red-400/10 text-red-400 ring-red-400/20', text: 'Delete' },
                        'seasonal': { class: 'bg-purple-400/10 text-purple-400 ring-purple-400/20', text: 'Seasonal' },
                        'not_scored': { class: 'bg-gray-400/10 text-gray-400 ring-gray-400/20', text: 'Not Scored' }
                    };

                    const newStyle = styles[action] || styles['not_scored'];
                    
                    // Animate badge change
                    badge.style.transition = 'opacity 0.2s ease';
                    badge.style.opacity = '0';
                    
                    setTimeout(() => {
                        // Reset classes
                        badge.className = 'score-badge inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ' + newStyle.class;
                        badge.textContent = newStyle.text;
                        badge.style.opacity = '1';
                    }, 200);
                }

                // Restore row opacity
                row.style.opacity = '1';
                row.style.pointerEvents = 'auto';
                
                // Optional: Flash success
                row.animate([
                    { backgroundColor: 'rgba(255, 255, 255, 0.1)' },
                    { backgroundColor: 'transparent' }
                ], {
                    duration: 500,
                    easing: 'ease-out'
                });
            }

            // Show Undo Toast
            const undoUrl = data.undo_url; 
            const actionText = `Marked as ${action}`;
            
            if (window.triggerUndoToast && undoUrl) {
                window.triggerUndoToast(actionText, undoUrl);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            // Revert visual changes
            if (row) {
                row.style.opacity = '1';
                row.style.pointerEvents = 'auto';
            }
            Toastify({
                text: "Action failed: " + error.message,
                backgroundColor: "#EF4444",
                duration: 3000
            }).showToast();
        });
    });
});
