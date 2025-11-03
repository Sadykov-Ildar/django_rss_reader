function deselect_active_elements(css_class) {
    let elements = document.querySelectorAll("." + css_class);
    elements.forEach(element => {
        if (element != null) {
            element.classList.remove(css_class);
        }
    });
}