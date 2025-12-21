function deselect_active_elements(css_class) {
    let elements = document.querySelectorAll("." + css_class);
    elements.forEach(element => {
        if (element != null) {
            element.classList.remove(css_class);
        }
    });
}

document.addEventListener('htmx:sendError', function (event) {
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


// Adding ability to sort inner elements of an entity with css-class "sortable"
htmx.onLoad(function (content) {
    var sortables = content.querySelectorAll(".sortable");
    for (var i = 0; i < sortables.length; i++) {
        var sortable = sortables[i];
        var sortableInstance = new Sortable(sortable, {
            animation: 150,
            ghostClass: 'blue-background-class',

            // Make the `.htmx-indicator` unsortable
            filter: ".htmx-indicator",
            onMove: function (evt) {
                return evt.related.className.indexOf('htmx-indicator') === -1;
            },

            // Disable sorting on the `end` event
            onEnd: function (evt) {
                this.option("disabled", true);
            }
        });

        // Re-enable sorting on the `htmx:afterSwap` event
        sortable.addEventListener("htmx:afterSwap", function () {
            sortableInstance.option("disabled", false);
        });
    }
})