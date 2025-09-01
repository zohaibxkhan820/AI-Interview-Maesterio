// Wait for the DOM to be fully loaded
document.addEventListener("DOMContentLoaded", () => {
    // Add smooth scrolling to all links
    document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
        anchor.addEventListener("click", function(e) {
            e.preventDefault()

            const targetId = this.getAttribute("href")
            if (targetId === "#") return

            const targetElement = document.querySelector(targetId)
            if (targetElement) {
                targetElement.scrollIntoView({
                    behavior: "smooth",
                    block: "start",
                })
            }
        })
    })

    // Add animation to the hero image
    const heroImage = document.querySelector(".hero-image")
    if (heroImage) {
        heroImage.style.opacity = "0"
        setTimeout(() => {
            heroImage.style.transition = "opacity 1s ease-in-out"
            heroImage.style.opacity = "1"
        }, 300)
    }

    // Add animation to the about image
    const aboutImage = document.querySelector(".about-image")
    if (aboutImage) {
        aboutImage.style.opacity = "0"
        setTimeout(() => {
            aboutImage.style.transition = "opacity 1s ease-in-out"
            aboutImage.style.opacity = "1"
        }, 300)
    }

    // Add hover effect to buttons
    const buttons = document.querySelectorAll(".btn")
    buttons.forEach((button) => {
        button.addEventListener("mouseenter", function() {
            this.style.transition = "all 0.3s ease"
            if (this.classList.contains("btn-get-started") || this.classList.contains("btn-signup")) {
                this.style.boxShadow = "0 8px 20px rgba(0, 180, 216, 0.8)"
                this.style.transform = "translateY(-3px)"
            }
        })

        button.addEventListener("mouseleave", function() {
            if (this.classList.contains("btn-get-started") || this.classList.contains("btn-signup")) {
                this.style.boxShadow = "0 0 15px rgba(0, 180, 216, 0.6)"
                this.style.transform = "translateY(0)"
            }
        })
    })

    // Add parallax effect to hero and about sections
    window.addEventListener("scroll", () => {
        const scrollPosition = window.scrollY

        const heroSection = document.querySelector(".hero")
        if (heroSection) {
            heroSection.style.backgroundPositionY = scrollPosition * 0.5 + "px"
        }

        const aboutSection = document.querySelector(".about-section")
        if (aboutSection) {
            aboutSection.style.backgroundPositionY = (scrollPosition - aboutSection.offsetTop) * 0.5 + "px"
        }
    })

    // Mobile menu toggle
    const navbarToggle = document.querySelector(".navbar-toggler")
    if (navbarToggle) {
        navbarToggle.addEventListener("click", () => {
            const navbarCollapse = document.querySelector(".navbar-collapse")
            navbarCollapse.classList.toggle("show")
        })
    }
})