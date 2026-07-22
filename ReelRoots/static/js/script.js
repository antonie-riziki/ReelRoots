// Initialize Lucide Icons when the optional CDN library is available.
function refreshIcons() {
    if (window.lucide && typeof window.lucide.createIcons === 'function') {
        window.lucide.createIcons();
    }
}

window.refreshIcons = refreshIcons;

document.addEventListener('DOMContentLoaded', function() {
    refreshIcons();
    
    // Initialize Dark Mode
    initDarkMode();
    
    // Initialize Mobile Menu
    initMobileMenu();
});

// Dark Mode Management
function initDarkMode() {
    const themeToggle = document.getElementById('theme-toggle');
    const themeToggleMobile = document.getElementById('theme-toggle-mobile');
    const html = document.documentElement;
    
    // Check for saved theme preference or default to light
    const savedTheme = localStorage.getItem('theme') || 'light';
    
    // Apply saved theme
    if (savedTheme === 'dark') {
        html.classList.add('dark');
    } else {
        html.classList.remove('dark');
    }
    
    // Toggle function
    function toggleTheme() {
        if (html.classList.contains('dark')) {
            html.classList.remove('dark');
            localStorage.setItem('theme', 'light');
        } else {
            html.classList.add('dark');
            localStorage.setItem('theme', 'dark');
        }
        
        // Re-initialize icons to show correct sun/moon
        refreshIcons();
    }
    
    // Event listeners
    if (themeToggle) {
        themeToggle.addEventListener('click', toggleTheme);
    }
    
    if (themeToggleMobile) {
        themeToggleMobile.addEventListener('click', toggleTheme);
    }
    
    // Check system preference on load if no saved preference
    if (!localStorage.getItem('theme')) {
        if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
            html.classList.add('dark');
            localStorage.setItem('theme', 'dark');
            refreshIcons();
        }
    }
    
    // Listen for system theme changes
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', event => {
        if (!localStorage.getItem('theme') || localStorage.getItem('theme') === 'system') {
            if (event.matches) {
                html.classList.add('dark');
            } else {
                html.classList.remove('dark');
            }
            refreshIcons();
        }
    });
}

// Mobile Menu Management
function initMobileMenu() {
    const mobileMenuBtn = document.getElementById('mobile-menu-btn');
    const mobileMenu = document.getElementById('mobile-menu');
    let isOpen = false;
    
    if (mobileMenuBtn && mobileMenu) {
        mobileMenuBtn.addEventListener('click', function() {
            isOpen = !isOpen;
            
            if (isOpen) {
                mobileMenu.classList.remove('hidden');
                // Small delay to allow display:block to apply before adding opacity
                setTimeout(() => {
                    mobileMenu.classList.add('active');
                }, 10);
                
                // Change menu icon to X
                const icon = mobileMenuBtn.querySelector('i');
                if (icon) {
                    icon.setAttribute('data-lucide', 'x');
                    refreshIcons();
                }
            } else {
                mobileMenu.classList.remove('active');
                setTimeout(() => {
                    mobileMenu.classList.add('hidden');
                }, 300);
                
                // Change back to menu icon
                const icon = mobileMenuBtn.querySelector('i');
                if (icon) {
                    icon.setAttribute('data-lucide', 'menu');
                    refreshIcons();
                }
            }
        });
        
        // Close menu when clicking on a link
        const mobileLinks = mobileMenu.querySelectorAll('a');
        mobileLinks.forEach(link => {
            link.addEventListener('click', () => {
                isOpen = false;
                mobileMenu.classList.remove('active');
                setTimeout(() => {
                    mobileMenu.classList.add('hidden');
                }, 300);
                
                const icon = mobileMenuBtn.querySelector('i');
                if (icon) {
                    icon.setAttribute('data-lucide', 'menu');
                    refreshIcons();
                }
            });
        });
    }
}

// Smooth scroll for anchor links
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        }
    });
});

// Add scroll-based navbar background enhancement
let lastScroll = 0;
const nav = document.querySelector('nav');

if (nav) {
    window.addEventListener('scroll', () => {
        const currentScroll = window.pageYOffset;

        if (currentScroll > 50) {
            nav.classList.add('shadow-sm');
        } else {
            nav.classList.remove('shadow-sm');
        }

        lastScroll = currentScroll;
    });
}
