document.addEventListener('DOMContentLoaded', (event) => {
    document.body.addEventListener('htmx:beforeSwap', function (evt) {
        if (evt.detail.xhr.status === 422) {
            evt.detail.shouldSwap = true;
            evt.detail.isError = false;
        }
    });
})

function deselect_active_elements(css_class) {
    let elements = document.querySelectorAll("." + css_class);
    elements.forEach(element => {
        if (element != null) {
            element.classList.remove(css_class);
        }
    });
}