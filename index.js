// initialization

const RESPONSIVE_WIDTH = 1024

let headerWhiteBg = false
let isHeaderCollapsed = window.innerWidth < RESPONSIVE_WIDTH
const collapseBtn = document.getElementById("collapse-btn")
const collapseHeaderItems = document.getElementById("collapsed-header-items")



function onHeaderClickOutside(e) {

    if (!collapseHeaderItems.contains(e.target)) {
        toggleHeader()
    }

}


function toggleHeader() {
    if (isHeaderCollapsed) {
        // collapseHeaderItems.classList.remove("max-md:tw-opacity-0")
        collapseHeaderItems.classList.add("opacity-100",)
        collapseHeaderItems.style.width = "60vw"
        collapseBtn.classList.remove("bi-list")
        collapseBtn.classList.add("bi-x", "max-lg:tw-fixed")
        isHeaderCollapsed = false

        setTimeout(() => window.addEventListener("click", onHeaderClickOutside), 1)

    } else {
        collapseHeaderItems.classList.remove("opacity-100")
        collapseHeaderItems.style.width = "0vw"
        collapseBtn.classList.remove("bi-x", "max-lg:tw-fixed")
        collapseBtn.classList.add("bi-list")
        isHeaderCollapsed = true
        window.removeEventListener("click", onHeaderClickOutside)

    }
}

function responsive() {
    if (window.innerWidth > RESPONSIVE_WIDTH) {
        collapseHeaderItems.style.width = ""

    } else {
        isHeaderCollapsed = true
    }
}

window.addEventListener("resize", responsive)

// DS Auto Insights specific functionality
document.addEventListener('DOMContentLoaded', function () {
    // Animate numbers on scroll
    const animateNumbers = () => {
        const numberElements = document.querySelectorAll('.animate-number');
        numberElements.forEach(element => {
            const rect = element.getBoundingClientRect();
            if (rect.top < window.innerHeight && rect.bottom > 0) {
                const target = parseInt(element.getAttribute('data-target'));
                const current = parseInt(element.textContent);
                if (current < target) {
                    const increment = Math.ceil(target / 50);
                    element.textContent = Math.min(current + increment, target);
                }
            }
        });
    };

    // Add smooth scroll for demo button
    const demoButton = document.querySelector('.demo-btn');
    if (demoButton) {
        demoButton.addEventListener('click', function (e) {
            e.preventDefault();
            // Redirect to your Streamlit app
            window.open('https://stats-compass-demo.streamlit.app', '_blank');
        });
    }

    // Intersection Observer for animations
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('animate-fade-in');
            }
        });
    }, observerOptions);

    // Observe all feature cards
    document.querySelectorAll('.feature-card, .data-card').forEach(card => {
        observer.observe(card);
    });

    // Scroll event for number animations
    window.addEventListener('scroll', animateNumbers);
    animateNumbers(); // Initial call
});
