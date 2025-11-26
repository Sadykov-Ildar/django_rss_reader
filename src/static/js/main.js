function deselect_active_elements(css_class) {
    let elements = document.querySelectorAll("." + css_class);
    elements.forEach(element => {
        if (element != null) {
            element.classList.remove(css_class);
        }
    });
}

document.addEventListener('htmx:sendError', function(event) {
    // Handle network errors (e.g., server down)
    console.error('HTMX Send Error:', event.detail);
    document.getElementById('global_error_message_text').innerText = 'Server is currently unavailable. Please try again later.';
    document.getElementById('global_error_message').show();
});

function close_dialog_on_esc(dialog) {
    // Event listener for the Escape key
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && dialog.open) {
            dialog.close();
        }
    });
}