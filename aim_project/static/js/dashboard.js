document.addEventListener("DOMContentLoaded", () => {
    // User dropdown toggle
    const userProfile = document.querySelector(".user-profile")
    if (userProfile) {
        userProfile.addEventListener("click", function() {
            const dropdown = this.querySelector(".user-dropdown")
            dropdown.style.display = dropdown.style.display === "block" ? "none" : "block"
        })

        // Close dropdown when clicking outside
        document.addEventListener("click", (event) => {
            if (!userProfile.contains(event.target)) {
                const dropdown = userProfile.querySelector(".user-dropdown")
                if (dropdown) {
                    dropdown.style.display = "none"
                }
            }
        })
    }

    // Mobile sidebar toggle
    const sidebarToggle = document.querySelector(".sidebar-toggle")
    if (sidebarToggle) {
        sidebarToggle.addEventListener("click", () => {
            const sidebar = document.querySelector(".dashboard-sidebar")
            const content = document.querySelector(".dashboard-content")

            sidebar.classList.toggle("collapsed")
            content.classList.toggle("expanded")
        })
    }

    // Form validation
    const forms = document.querySelectorAll(".needs-validation")
    Array.from(forms).forEach((form) => {
        form.addEventListener(
            "submit",
            (event) => {
                if (!form.checkValidity()) {
                    event.preventDefault()
                    event.stopPropagation()
                }
                form.classList.add("was-validated")
            },
            false,
        )
    })

    // File input display filename
    const fileInputs = document.querySelectorAll('input[type="file"]')
    fileInputs.forEach((input) => {
        input.addEventListener("change", function() {
            const fileName = this.files[0] ?.name || "No file chosen"
            const fileLabel = this.nextElementSibling
            if (fileLabel && fileLabel.classList.contains("custom-file-label")) {
                fileLabel.textContent = fileName
            }
        })
    })

    // Auto-hide alerts after 5 seconds
    const alerts = document.querySelectorAll(".alert:not(.alert-permanent)")
    alerts.forEach((alert) => {
        setTimeout(() => {
            if (typeof bootstrap !== "undefined") {
                // Check if Bootstrap is available
                if (typeof bootstrap.Alert === "function") {
                    const bsAlert = new bootstrap.Alert(alert)
                    bsAlert.close()
                } else {
                    alert.style.display = "none" // Fallback if Bootstrap's Alert is not available
                }
            } else {
                alert.style.display = "none" // Fallback if Bootstrap is not available
            }
        }, 5000)
    })
})