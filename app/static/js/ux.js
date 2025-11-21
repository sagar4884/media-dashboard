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
    // We can attach this to any button that performs an action
    document.body.addEventListener('click', function(e) {
        // Check if it's an action button (Keep/Delete/etc)
        // These usually have hx-get or are links.
        // If it's an HTMX request, we can use htmx events.
    });

    // HTMX Event for Fade Out
    // When an element is about to be swapped out (or removed), we can animate it.
    // But our buttons usually replace the *row* or the *list*.
    // If the user clicks "Keep", the row is usually removed from the "Unscored" list.
    
    // Let's assume the buttons have a class `action-btn` or similar.
    // Looking at templates, they are usually links or buttons.
    
    // Better approach: Intercept the click on specific action buttons.
    const actionButtons = document.querySelectorAll('[data-action-type]');
    // We need to add data-action-type to buttons in the templates first.
});
