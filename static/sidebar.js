document.addEventListener('DOMContentLoaded', () => {
    const sidebar = document.querySelector('.sidebar');
    if (!sidebar) return;

    const toggleButton = sidebar.querySelector('.sidebar-toggle');
    const navLinks = sidebar.querySelectorAll('.sidebar-link');
    const currentPath = window.location.pathname;

    navLinks.forEach((link) => {
        const href = link.getAttribute('href');
        if (href === currentPath) {
            link.classList.add('active');
        }
    });

    if (toggleButton) {
        toggleButton.addEventListener('click', () => {
            sidebar.classList.toggle('collapsed');
            document.body.classList.toggle('sidebar-collapsed');
        });
    }
});
